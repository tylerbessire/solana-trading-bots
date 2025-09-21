"""
Main RentSpotBot implementation integrating WebSocket client and rent spot tracking.
"""
import asyncio
import logging
from typing import Optional
import json
import aiohttp
import os
from datetime import datetime
import base58
import base64
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

from config.constants import (
    TRADE_URL,
)
from config.wallet_config import (
    WALLET_PUBLIC_KEY,
    MAX_TRADE_AMOUNT,
    PRIORITY_FEE,
    BRIBERY_FEE,
    RPC_ENDPOINT,
    SLIPPAGE
)
from src.websocket_client import PumpWebSocketClient
from src.rent_spot_tracker import RentSpotTracker
from src.token_logger import TokenEventLogger

# Trade parameters
TRADE_PARAMS = {
    "amount": "0.0001",
    "denominatedInSol": "true",
    "slippage": 1000,
    "priorityFee": "0.00001",
    "briberyFee": "0.00001",
    "pool": "pump"
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RentSpotBot:
    def __init__(self):
        self.ws_client = PumpWebSocketClient(on_token_event=self._handle_token_event)
        self.rent_tracker = RentSpotTracker()
        self.token_logger = TokenEventLogger()
        self.trade_lock = asyncio.Lock()
        self._running = False
        self._last_token = None
        self._last_trade_success = False
        self._total_trades = 0

    async def start(self):
        """Start the bot."""
        logger.info("Starting RentSpotBot...")
        self._running = True
        await self.ws_client.connect()
        # Explicitly subscribe to new token events
        subscription_success = await self.ws_client.subscribe_to_new_tokens()
        if not subscription_success:
            logger.error("Failed to subscribe to new token events")
            self._running = False
            raise RuntimeError("Failed to subscribe to new token events")
        logger.info("Successfully subscribed to new token events")

    async def stop(self):
        """Stop the bot and cleanup resources."""
        logger.info("Stopping RentSpotBot...")
        self._running = False
        if hasattr(self, 'ws_client'):
            await self.ws_client.disconnect()
        logger.info("Bot stopped successfully")

    async def _handle_token_event(self, event_data: dict):
        """
        Handle new token events from the WebSocket.

        Args:
            event_data (dict): The token event data
        """
        try:
            if not self._running:
                logger.info("Bot is not running, ignoring token event")
                return

            if not isinstance(event_data, dict):
                logger.error(f"Invalid event data format: {event_data}")
                return

            token_mint = event_data.get('mint')
            if not token_mint:
                logger.error(f"No mint address in event data: {event_data}")
                return

            logger.info(f"New token detected: {token_mint}")
            await self.token_logger.log_event(event_data)  # Changed to use correct method name

            # Execute trade sequence and track rent spot if successful
            trade_result = await self._execute_trade_sequence(token_mint)
            if trade_result:
                await self.rent_tracker.add_rent_spot(token_mint, trade_result)
                logger.info(f"Successfully added rent spot for token: {token_mint}")
        except Exception as e:
            logger.error(f"Error handling token event: {str(e)}")

    async def _execute_trade_sequence(self, token_mint: str) -> Optional[dict]:
        """
        Execute buy-sell sequence for rent spot creation.
        """
        async with self.trade_lock:
            try:
                # Execute buy transaction
                buy_result = await self._execute_trade(token_mint, "buy")
                if not buy_result:
                    return None

                # Execute sell transaction
                sell_result = await self._execute_trade(token_mint, "sell")
                if not sell_result:
                    logger.warning(f"Buy succeeded but sell failed for {token_mint}")
                    return None

                trade_details = {
                    'token_mint': token_mint,
                    'buy_timestamp': buy_result.get('timestamp'),
                    'sell_timestamp': sell_result.get('timestamp'),
                    'buy_price': buy_result.get('price'),
                    'sell_price': sell_result.get('price'),
                    'fees_paid': {
                        'priority': PRIORITY_FEE,
                        'bribery': BRIBERY_FEE
                    }
                }

                logger.info(f"Successfully completed trade sequence for {token_mint}")
                return trade_details

            except Exception as e:
                logger.error(f"Error in trade sequence for {token_mint}: {e}")
                return None

    async def _execute_trade(self, token_mint: str, action: str = "buy") -> bool:
        """Execute a trade for a given token."""
        self._last_trade_success = False  # Reset trade success status
        self._last_token = token_mint

        try:
            # Create keypair from private key
            private_key_b58 = os.getenv("WALLET_PRIVATE_KEY")
            if not private_key_b58:
                logger.error("WALLET_PRIVATE_KEY environment variable not set")
                return False

            # Decode base58 private key to bytes
            try:
                private_key_bytes = base58.b58decode(private_key_b58)
                keypair = Keypair.from_bytes(private_key_bytes)
                logger.info("Successfully created keypair")
            except Exception as e:
                logger.error(f"Failed to create keypair: {str(e)}")
                return False

            # Prepare trade request payload
            payload = {
                "publicKey": str(keypair.pubkey()),
                "action": action,
                "mint": token_mint,
                **TRADE_PARAMS
            }

            logger.info(f"Trade request payload: {json.dumps(payload, indent=2)}")

            # Execute trade request
            async with aiohttp.ClientSession() as session:
                try:
                    logger.info(f"Executing {action} trade for {token_mint}")
                    async with session.post(
                        TRADE_URL,
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"Trade API error: {error_text}")
                            return False

                        # Read raw bytes from response
                        tx_bytes = await response.read()
                        if not tx_bytes:
                            logger.error("No transaction bytes in response")
                            return False

                        try:
                            # Create versioned transaction directly from bytes
                            tx = VersionedTransaction.from_bytes(tx_bytes)
                            logger.info("Created versioned transaction")

                            # Sign the transaction
                            tx = tx.sign_with_keypairs([keypair])
                            logger.info("Successfully signed transaction")

                            # Serialize the signed transaction
                            serialized_tx = base64.b64encode(bytes(tx)).decode('utf-8')
                            logger.info("Successfully serialized transaction")

                            # Prepare RPC request
                            rpc_request = {
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": "sendTransaction",
                                "params": [
                                    serialized_tx,
                                    {"encoding": "base64", "preflightCommitment": "confirmed"}
                                ]
                            }

                            # Send signed transaction
                            async with session.post(
                                RPC_ENDPOINT,
                                json=rpc_request,
                                headers={"Content-Type": "application/json"}
                            ) as rpc_response:
                                rpc_data = await rpc_response.json()
                                if "error" in rpc_data:
                                    logger.error(f"RPC error: {rpc_data['error']}")
                                    return False

                                logger.info(f"Transaction submitted successfully: {rpc_data.get('result')}")
                                self._last_trade_success = True
                                self._total_trades += 1
                                return True

                        except Exception as e:
                            logger.error(f"Error in transaction signing/submission: {str(e)}")
                            return False

                except Exception as e:
                    logger.error(f"Error in trade API request: {str(e)}")
                    return False

        except Exception as e:
            logger.error(f"Error executing {action} trade for {token_mint}: {str(e)}")
            return False

    def get_status(self) -> dict:
        """Get the current status of the bot."""
        return {
            "is_running": self._running,
            "last_token": self._last_token,
            "last_trade_success": self._last_trade_success if hasattr(self, '_last_trade_success') else False,
            "total_trades": self._total_trades if hasattr(self, '_total_trades') else 0
        }

async def main():
    """Main entry point for the RentSpotBot."""
    try:
        bot = RentSpotBot()
        logger.info("Starting RentSpotBot...")

        # Start the bot
        await bot.start()

        # Keep the bot running
        trade_count = 0
        max_trades = 5

        while trade_count < max_trades:
            try:
                await asyncio.sleep(1)
                status = bot.get_status()
                if status.get('last_trade_success'):
                    trade_count += 1
                    logger.info(f"Successful trade completed. Trade count: {trade_count}/{max_trades}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                continue

        # Stop the bot after max trades or if interrupted
        await bot.stop()
        logger.info("Bot stopped successfully")

    except Exception as e:
        logger.error(f"Fatal error in main: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
        raise
