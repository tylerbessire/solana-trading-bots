import asyncio
import json
import logging
import websockets
import os
import time
from typing import Optional, Callable, Dict, Any, Set
from decimal import Decimal

logging.basicConfig(level=logging.DEBUG)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger(__name__)

class OptimizedWebSocketClient:
    def __init__(self, uri: str = "wss://pumpportal.fun/api/data"):
        self.uri = uri
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.token_callback: Optional[Callable] = None
        self.price_callback: Optional[Callable] = None
        self.status_callback: Optional[Callable] = None
        self.running = False
        self.reconnect_delay = 1
        self.max_retries = 3
        self._lock = asyncio.Lock()

        # Token tracking sets
        self.processed_tokens: Set[str] = set()
        self.tracked_tokens: Set[str] = set()
        self.token_holders: Dict[str, int] = {}  # Track holder counts
        self.last_message_time = time.time()
        self.ping_interval = 30

        # Market cap tracking
        self.token_metrics = {}
        self.SOL_PRICE_USD = Decimal('256')

    async def _connect(self) -> bool:
        """Establish WebSocket connection with simple headers as shown in docs"""
        try:
            if self.websocket:
                await self.websocket.close()

            logger.info(f"Attempting to establish WebSocket connection to {self.uri}...")

            # Using minimal headers as shown in the documentation
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Origin': 'https://pumpportal.fun'
            }

            self.websocket = await websockets.connect(
                self.uri,
                extra_headers=headers,
                ping_interval=None,  # Disable automatic ping
                close_timeout=10
            )
            logger.info("WebSocket connection established successfully")

            if self.status_callback:
                await self.status_callback("connected")

            return True
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            if self.status_callback:
                await self.status_callback("error")
            return False

    async def subscribe_to_token(self, token_mint: str) -> bool:
        """Subscribe to token trades"""
        if self.websocket and not self.websocket.closed:
            try:
                payload = {
                    "method": "subscribeTokenTrade",
                    "keys": [token_mint]
                }
                await self.websocket.send(json.dumps(payload))
                self.tracked_tokens.add(token_mint)
                logger.info(f"Subscribed to trades for token: {token_mint}")
                return True
            except Exception as e:
                logger.error(f"Failed to subscribe to token {token_mint}: {e}")
                return False
        return False

    async def unsubscribe_from_token(self, token_mint: str) -> bool:
        """Unsubscribe from token trades"""
        if self.websocket and not self.websocket.closed:
            try:
                payload = {
                    "method": "unsubscribeTokenTrade",
                    "keys": [token_mint]
                }
                await self.websocket.send(json.dumps(payload))
                self.tracked_tokens.remove(token_mint)
                if token_mint in self.token_holders:
                    del self.token_holders[token_mint]
                logger.info(f"Unsubscribed from token: {token_mint}")
                return True
            except Exception as e:
                logger.error(f"Failed to unsubscribe from token {token_mint}: {e}")
                return False
        return False

    async def _subscribe_initial(self) -> bool:
        """Initial subscription to data streams"""
        try:
            logger.info("Attempting to subscribe to initial data streams...")
            # Removing the duplicate subscription since we handle it in start_monitoring
            logger.info("Subscription handled by start_monitoring")
            return True
        except Exception as e:
            logger.error(f"Subscription error: {str(e)}")
            return False

    async def _heartbeat(self):
        """Send periodic heartbeat to keep connection alive"""
        while self.running:
            try:
                await self.websocket.send(json.dumps({"type": "ping"}))
                await asyncio.sleep(15)
            except Exception as e:
                logger.error(f"Heartbeat error: {str(e)}")
                break

    def is_token_processed(self, token_mint: str) -> bool:
        """Check if token has been processed"""
        return token_mint in self.processed_tokens

    def mark_token_processed(self, token_mint: str):
        """Mark token as processed"""
        self.processed_tokens.add(token_mint)

    def get_holder_count(self, token_mint: str) -> int:
        """Get current holder count for token"""
        return self.token_holders.get(token_mint, 0)

    async def set_callbacks(self,
                         token_callback: Optional[Callable] = None,
                         price_callback: Optional[Callable] = None,
                         status_callback: Optional[Callable] = None):
        """Set callbacks for events"""
        self.token_callback = token_callback
        self.price_callback = price_callback
        self.status_callback = status_callback

    async def _handle_new_token(self, data: Dict[str, Any]):
        """Handle new token creation events"""
        try:
            token_data = {
                'mint': data.get('mint'),
                'marketCapSol': data.get('marketCapSol'),
                'initialBuy': data.get('initialBuy'),
                'name': data.get('name'),
                'symbol': data.get('symbol'),
                'traderPublicKey': data.get('traderPublicKey'),
                'timestamp': time.time()
            }

            if not all(k in token_data for k in ['mint', 'marketCapSol']):
                logger.warning(f"Incomplete token data: {json.dumps(data, indent=2)}")
                return

            logger.info(f"New token detected: {token_data['name']} ({token_data['symbol']})")
            logger.debug(f"Token details: {json.dumps(token_data, indent=2)}")

            if self.token_callback:
                await self.token_callback(token_data, "new_token", None, None)

        except Exception as e:
            logger.error(f"Error handling new token: {str(e)}")
            logger.debug(f"Problem data: {json.dumps(data, indent=2)}")

            # Subscribe to trades immediately
            self.token_metrics[data.get('mint')] = token_data
            await self.subscribe_to_token(data.get('mint'))

    async def _handle_token_trade(self, data: dict):
        """Process trade events and update holder counts"""
        try:
            mint = data.get('mint')
            if not mint:
                return

            # Debug logging
            logger.debug(f"Trade update raw data: {json.dumps(data, indent=2)}")

            price = Decimal(str(data.get('price', 0)))
            mcap = Decimal(str(data.get('marketCapSol', 0)))
            holders = data.get('uniqueHolders',
                      data.get('holders',
                      data.get('numHolders', 0)))

            if holders:
                self.token_holders[mint] = int(holders)

            usd_mcap = mcap * self.SOL_PRICE_USD

            trade_data = {
                'mint': mint,
                'price': float(price),
                'market_cap': float(mcap),
                'usd_market_cap': float(usd_mcap),
                'holders': self.token_holders.get(mint, 0),
                'timestamp': time.time()
            }

            if mint in self.token_metrics:
                self.token_metrics[mint].update(trade_data)

            # Only log if we have meaningful data
            if mcap > 0 or holders:
                logger.info(f"\n💹 Trade Update - {mint}")
                logger.info(f"Market Cap: ${usd_mcap:,.2f}")
                logger.info(f"Price: ${float(price * self.SOL_PRICE_USD):,.6f}")
                if holders:
                    logger.info(f"Holders: {holders}")

            # Notify callback
            if self.price_callback:
                await self.price_callback(trade_data)

        except Exception as e:
            logger.error(f"Error handling trade: {str(e)}")
            logger.debug(f"Problem data: {json.dumps(data, indent=2)}")

    async def _process_message(self, message: str):
        """Process incoming WebSocket messages"""
        try:
            logger.info(f"Raw message received: {message}")
            data = json.loads(message)
            self.last_message_time = time.time()

            logger.info(f"Parsed message data: {json.dumps(data, indent=2)}")

            # Handle subscription confirmations
            if isinstance(data, dict) and data.get('method') in ['subscribeNewToken', 'subscribeTokenTrade']:
                logger.info(f"Subscription confirmation received: {data.get('method')}")
                return

            # Handle direct token creation messages
            if isinstance(data, dict) and all(key in data for key in ['mint', 'marketCapSol']):
                await self._handle_new_token(data)
                return

            # Handle wrapped messages
            if isinstance(data, dict):
                payload = data.get('data', data)
                logger.debug(f"Processing payload: {json.dumps(payload, indent=2)}")

                if payload.get('type') == 'ping':
                    await self.websocket.send(json.dumps({"type": "pong"}))
                elif payload.get('txType') == 'create':
                    await self._handle_new_token(payload)
                elif payload.get('txType') in ['trade', 'buy', 'sell']:
                    await self._handle_token_trade(payload)
                # Fallback for trade updates without explicit type
                elif all(key in payload for key in ['price', 'mint']):
                    await self._handle_token_trade(payload)
                else:
                    logger.info(f"Unhandled message type: {json.dumps(data, indent=2)}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message as JSON: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            logger.error(f"Problem message: {message}")

    async def start_monitoring(self):
        """Start WebSocket monitoring following documentation example"""
        self.running = True
        retry_count = 0

        while self.running:
            try:
                logger.info("Starting WebSocket monitoring...")
                if not await self._connect():
                    raise Exception("Failed to establish connection")

                # Simple subscription as shown in docs
                subscribe_msg = {
                    "method": "subscribeNewToken"
                }
                await self.websocket.send(json.dumps(subscribe_msg))
                logger.info("Subscribed to new token events")

                # Main message processing loop
                async for message in self.websocket:
                    retry_count = 0  # Reset retry counter on successful message
                    await self._process_message(message)

            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed")
                if self.status_callback:
                    await self.status_callback("disconnected")

            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                if self.status_callback:
                    await self.status_callback("error")

            finally:
                retry_count += 1
                wait_time = min(5 * retry_count, 30)
                logger.info(f"Waiting {wait_time} seconds before reconnecting...")
                await asyncio.sleep(wait_time)

        self.running = False
        if self.status_callback:
            await self.status_callback("disconnected")

        self.running = False
        if self.status_callback:
            await self.status_callback(None, "connection_status", "disconnected", None)

    async def stop(self):
        """Stop WebSocket monitoring"""
        try:
            if self.websocket:
                await self.websocket.close()
                self.websocket = None
            logger.info("WebSocket connection closed successfully")
        except Exception as e:
            logger.error(f"Error closing WebSocket connection: {str(e)}")

if __name__ == "__main__":
    async def test_callback(data):
        print(f"Test callback received: {json.dumps(data, indent=2)}")

    async def main():
        client = OptimizedWebSocketClient()
        await client.set_callbacks(token_callback=test_callback)
        await client.start_monitoring()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down...")
