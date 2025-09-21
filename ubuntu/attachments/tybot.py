import asyncio
import websockets
import json
import requests
import os
import logging
from datetime import datetime
from solders.transaction import VersionedTransaction
from solders.keypair import Keypair
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction import Transaction

logging.basicConfig(
    level=logging.DEBUG,
    format=
    '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[logging.StreamHandler(),
              logging.FileHandler('bot_debug.log')])
logger = logging.getLogger(__name__)

# Define URLs and environment variables
WS_URI = "wss://pumpportal.fun/api/data"
TRADE_URL = "https://pumpportal.fun/api/trade-local"
PUBLIC_KEY = os.getenv("PUBLIC_KEY")

# Trade parameters
MAX_TRADE_AMOUNT = 0.00001
PRIORITY_FEE = 0.00001
BRIBERY_FEE = 0.00001

# Trade tracking variables and locks
PROCESSED_TOKENS = set()
tokens_held_lock = asyncio.Lock()
processed_tokens_lock = asyncio.Lock()
BOT_RUNNING = False
trade_callback = None


def set_bot_running_state(running: bool):
    global BOT_RUNNING
    BOT_RUNNING = running
    logger.info(f"Bot running state changed to: {running}")


async def register_trade_callback(callback):
    global trade_callback
    trade_callback = callback
    logger.info("Trade callback registered successfully")
    return True


async def notify_trade_update(token_mint, action, price, amount, profit=None):
    if trade_callback:
        try:
            await trade_callback(token_mint, action, price, amount, profit)
            logger.debug(
                f"Trade update sent: {token_mint}, {action}, {price}, {amount}, {profit}"
            )
        except Exception as e:
            logger.error(f"Error in trade callback: {e}", exc_info=True)


async def execute_immediate_trade(token_mint):
    """Execute immediate buy and sell trade via Pump.fun."""
    try:
        logger.info(f"Executing immediate trade for {token_mint}")

        # Send buy request
        buy_response = await send_pump_fun_trade_request(token_mint, "buy")
        if not buy_response:
            logger.error("Buy transaction failed")
            return False

        logger.info("Buy successful, executing immediate sell")
        await notify_trade_update(token_mint, "buy", MAX_TRADE_AMOUNT,
                                  MAX_TRADE_AMOUNT)

        # Send sell request
        sell_response = await send_pump_fun_trade_request(token_mint, "sell")
        if sell_response:
            logger.info("Sell successful")
            await notify_trade_update(token_mint, "sell", MAX_TRADE_AMOUNT,
                                      MAX_TRADE_AMOUNT)
            return True

        logger.error("Sell transaction failed")
        return False

    except Exception as e:
        logger.error(f"Error in immediate trade execution: {e}", exc_info=True)
        return False


async def send_pump_fun_trade_request(token_mint, action):
    """Send trade request to Pump.fun for buy/sell action."""
    try:
        trade_data = {
            "publicKey": PUBLIC_KEY,
            "action": action,
            "mint": token_mint,
            "amount": MAX_TRADE_AMOUNT,
            "denominatedInSol": "false",  # False assumes amount in tokens
            "slippage": 10,
            "priorityFee": PRIORITY_FEE,
            "pool": "pump"  # Choose between "pump" or "raydium"
        }

        response = requests.post(TRADE_URL, data=trade_data)
        if response.status_code == 200:
            logger.info(
                f"{action.capitalize()} transaction to Pump.fun successful")
            return True

        logger.error(
            f"{action.capitalize()} transaction failed: {response.text}")
        return False

    except Exception as e:
        logger.error(f"Error in send_pump_fun_trade_request: {e}",
                     exc_info=True)
        return False


async def websocket_handler():
    """Handles WebSocket connection and processes messages."""
    global BOT_RUNNING
    retry_count = 0
    max_retries = 3
    connection_start_time = None

    while retry_count < max_retries and BOT_RUNNING:
        try:
            connection_start_time = datetime.now()
            logger.info(
                f"[{connection_start_time.isoformat()}] Attempting to establish WebSocket connection to {WS_URI}"
            )

            async with websockets.connect(WS_URI) as websocket:
                connection_established_time = datetime.now()
                connection_duration = (connection_established_time -
                                       connection_start_time).total_seconds()
                logger.info(
                    f"[{connection_established_time.isoformat()}] WebSocket connection established in {connection_duration:.2f}s"
                )

                await notify_trade_update(None, "connection_status",
                                          "connected", None)

                # Subscribe to new token events
                await websocket.send(
                    json.dumps({"method": "subscribeNewToken"}))
                logger.debug("Subscribed to new token events")

                # Subscribe to trades made by a specific account (replace with actual account keys if needed)
                account_keys = ["YOUR_ACCOUNT_ADDRESS_HERE"]
                await websocket.send(
                    json.dumps({
                        "method": "subscribeAccountTrade",
                        "keys": account_keys
                    }))
                logger.debug(
                    f"Subscribed to trades by accounts: {account_keys}")

                # Subscribe to trades on specific tokens (replace with actual token CAs if needed)
                token_keys = ["YOUR_TOKEN_ADDRESS_HERE"]
                await websocket.send(
                    json.dumps({
                        "method": "subscribeTokenTrade",
                        "keys": token_keys
                    }))
                logger.debug(f"Subscribed to trades on tokens: {token_keys}")

                monitored_tokens = set()
                message_count = 0
                last_message_time = datetime.now()

                while BOT_RUNNING:
                    try:
                        message = await websocket.recv()
                        current_time = datetime.now()
                        message_count += 1
                        time_since_last = (current_time -
                                           last_message_time).total_seconds()

                        logger.debug(
                            f"[{current_time.isoformat()}] WebSocket message #{message_count} received ({time_since_last:.2f}s since last)"
                        )

                        try:
                            data = json.loads(message)
                            logger.debug(
                                f"[{current_time.isoformat()}] Message type: {data.get('method')}, Content: {json.dumps(data)}"
                            )

                            # Handle different message types
                            if data.get('method') == 'newToken':
                                token_mint = data.get('params', {}).get('mint')
                                if token_mint:
                                    logger.info(
                                        f"New token detected: {token_mint}")
                                    async with processed_tokens_lock:
                                        if token_mint not in PROCESSED_TOKENS:
                                            await execute_immediate_trade(
                                                token_mint)
                                            PROCESSED_TOKENS.add(token_mint)

                            elif data.get('method') == 'tokenTrade':
                                token_mint = data.get('params', {}).get('mint')
                                if token_mint:
                                    price = float(data['params'].get(
                                        'price', 0))
                                    volume = float(data['params'].get(
                                        'volume', 0))
                                    logger.debug(
                                        f"Trade update - Token: {token_mint}, Price: {price}, Volume: {volume}"
                                    )
                                    async with prices_lock:
                                        latest_prices[token_mint] = price
                                    await notify_trade_update(
                                        token_mint, "price_update", price,
                                        volume)

                            elif data.get('method') == 'accountTrade':
                                logger.info(
                                    f"Account trade message received: {json.dumps(data)}"
                                )

                        except json.JSONDecodeError as e:
                            logger.error(
                                f"Failed to decode message: {e}\nRaw message: {message}"
                            )

                        last_message_time = current_time

                    except Exception as e:
                        logger.error(f"Error processing message: {e}",
                                     exc_info=True)

                logger.info("WebSocket connection closing (bot stopped)")
                retry_count = 0

        except websockets.exceptions.ConnectionClosed as e:
            retry_count += 1
            logger.warning(
                f"WebSocket connection closed (attempt {retry_count}/{max_retries}): {e}"
            )
            await asyncio.sleep(5 * retry_count)
        except Exception as e:
            retry_count += 1
            logger.error(f"Unexpected error in websocket_handler: {e}",
                         exc_info=True)
            await asyncio.sleep(5 * retry_count)

    if retry_count >= max_retries:
        logger.critical("Maximum connection retries reached")
        set_bot_running_state(False)
        await notify_trade_update(None, "connection_status", "disconnected",
                                  None)


async def analyze_new_token(token_mint, websocket, monitored_tokens):
    analysis_start = datetime.now()
    logger.info(
        f"[{analysis_start.isoformat()}] Starting analysis for token: {token_mint}"
    )

    try:
        async with tokens_held_lock:
            current_tokens = len(tokens_held)
            logger.debug(
                f"Current tokens held: {current_tokens}/{MAX_TOKENS_HELD}")
            if current_tokens >= MAX_TOKENS_HELD:
                logger.info(
                    f"Maximum tokens held reached, skipping {token_mint}")
                async with processed_tokens_lock:
                    PROCESSED_TOKENS.add(token_mint)
                return False

        sniping_start = datetime.now()
        logger.info(f"Starting sniping activity check for {token_mint}")
        has_sniping = await check_sniping_activity(token_mint, websocket,
                                                   monitored_tokens)
        sniping_duration = (datetime.now() - sniping_start).total_seconds()
        logger.debug(
            f"Sniping check completed in {sniping_duration:.2f}s. Result: {has_sniping}"
        )

        if has_sniping:
            logger.warning(f"Sniping activity detected for {token_mint}")
            async with processed_tokens_lock:
                PROCESSED_TOKENS.add(token_mint)
            return False

        concentration_start = datetime.now()
        logger.info(f"Starting holder concentration check for {token_mint}")
        high_concentration = await check_top_holders_concentration(token_mint)
        concentration_duration = (datetime.now() -
                                  concentration_start).total_seconds()
        logger.debug(
            f"Concentration check completed in {concentration_duration:.2f}s. Result: {high_concentration}"
        )

        if high_concentration:
            logger.warning(f"High holder concentration for {token_mint}")
            async with processed_tokens_lock:
                PROCESSED_TOKENS.add(token_mint)
            return False

        if not has_sniping and not high_concentration:
            logger.info(
                f"Token {token_mint} passed all checks, executing immediate trade"
            )
            trade_success = await execute_immediate_trade(token_mint)
            logger.info(
                f"Immediate trade execution {'succeeded' if trade_success else 'failed'} for {token_mint}"
            )

        total_duration = (datetime.now() - analysis_start).total_seconds()
        logger.info(
            f"Token analysis and trading completed in {total_duration:.2f}s")

        async with processed_tokens_lock:
            PROCESSED_TOKENS.add(token_mint)
            logger.debug(f"Added {token_mint} to processed tokens")

        return True

    except Exception as e:
        logger.error(f"Error analyzing token {token_mint}: {e}", exc_info=True)
        async with processed_tokens_lock:
            PROCESSED_TOKENS.add(token_mint)
        return False


async def check_sniping_activity(token_mint, websocket, monitored_tokens):
    start_time = datetime.now()
    logger.debug(f"Starting sniping detection for {token_mint}")
    trade_count = 0
    monitoring_duration = 60

    try:
        trade_queue = asyncio.Queue()
        trade_queues[token_mint] = trade_queue

        subscribe_msg = {"method": "subscribeTokenTrade", "keys": [token_mint]}
        await websocket.send(json.dumps(subscribe_msg))
        logger.debug(f"Subscribed to trades for {token_mint}")
        monitored_tokens.add(token_mint)

        monitoring_start = time.time()
        while time.time() - monitoring_start < monitoring_duration:
            try:
                data = await asyncio.wait_for(trade_queue.get(), timeout=1.0)
                trade_count += 1
                elapsed = time.time() - monitoring_start
                logger.debug(
                    f"Trade detected for {token_mint} ({trade_count}/{SNIPING_ACTIVITY_THRESHOLD}, {elapsed:.1f}s elapsed)"
                )

                if trade_count > SNIPING_ACTIVITY_THRESHOLD:
                    logger.warning(
                        f"Sniping threshold exceeded for {token_mint}")
                    return True

            except asyncio.TimeoutError:
                continue

    except Exception as e:
        logger.error(f"Error monitoring sniping activity: {e}", exc_info=True)
        return True
    finally:
        try:
            await websocket.send(
                json.dumps({
                    "method": "unsubscribeTokenTrade",
                    "keys": [token_mint]
                }))
            logger.debug(f"Unsubscribed from trades for {token_mint}")
        except Exception as e:
            logger.error(f"Error unsubscribing from trades: {e}")

        monitored_tokens.discard(token_mint)
        trade_queues.pop(token_mint, None)

    duration = (datetime.now() - start_time).total_seconds()
    logger.info(
        f"Sniping check complete for {token_mint}: {trade_count} trades in {duration:.2f}s"
    )
    return False


async def check_top_holders_concentration(token_mint):
    start_time = datetime.now()
    logger.debug(f"Checking holder concentration for {token_mint}")

    try:
        async with AsyncClient(SOLANA_RPC_URL) as client:
            supply_start = datetime.now()
            logger.debug(f"Fetching total supply for {token_mint}")
            supply_info = await client.get_token_supply(
                Pubkey.from_string(token_mint))

            if not supply_info.value or not supply_info.value.amount:
                logger.warning(f"Could not get supply info for {token_mint}")
                return True

            total_supply = int(supply_info.value.amount)
            logger.debug(f"Total supply for {token_mint}: {total_supply}")

            holders_start = datetime.now()
            logger.debug(f"Fetching largest token holders for {token_mint}")
            largest_accounts = await client.get_token_largest_accounts(
                Pubkey.from_string(token_mint))

            if not largest_accounts.value:
                logger.warning(f"Could not get holder info for {token_mint}")
                return True

            top_holdings = sum(
                int(account.amount) for account in largest_accounts.value[:10])
            concentration = (top_holdings / total_supply) * 100

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Holder concentration check completed in {duration:.2f}s. Token: {token_mint}, Concentration: {concentration:.2f}%"
            )

            return concentration > TOP_HOLDERS_THRESHOLD

    except Exception as e:
        logger.error(f"Error checking holder concentration: {e}",
                     exc_info=True)
        return True


if __name__ == "__main__":
    asyncio.run(websocket_handler())
