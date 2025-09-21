import asyncio
import json
import logging
import websockets
from typing import Optional, Callable, Dict, Any, Set
import time
from decimal import Decimal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('websocket.log', mode='w')  # New log file, 'w' mode to start fresh
    ]
)
logger = logging.getLogger(__name__)

class OptimizedWebSocketClient:
    def __init__(self, uri: str = "wss://pumpportal.fun/api/data"):
        self.uri = uri
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self.reconnect_delay = 5
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
        self.SOL_PRICE_USD = Decimal('256')  # Updated to current SOL price

        # Callbacks
        self.status_callback = None
        self.trade_callback = None
        self.new_token_callback = None

        logger.info(f"Initialized WebSocket client with URI: {self.uri}")

    async def set_callbacks(self,
                          status_callback: Optional[Callable] = None,
                          trade_callback: Optional[Callable] = None,
                          new_token_callback: Optional[Callable] = None):
        """Set callback functions for different event types"""
        self.status_callback = status_callback
        self.trade_callback = trade_callback
        self.new_token_callback = new_token_callback
        logger.info("Callbacks configured successfully")

    async def _connect(self) -> bool:
        """Establish WebSocket connection with proper headers"""
        try:
            if self.websocket:
                logger.info("Closing existing WebSocket connection...")
                await self.websocket.close()

            logger.info(f"Attempting to establish WebSocket connection to {self.uri}...")

            # Updated connection parameters to be compatible with websockets library
            self.websocket = await websockets.connect(
                self.uri,
                ping_interval=20,
                ping_timeout=15,
                close_timeout=10,
                max_size=10 * 1024 * 1024,  # 10MB max message size
                user_agent_header='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            logger.info("WebSocket connection established successfully")

            # Update connection status
            if self.status_callback:
                await self.status_callback(None, "connection_status", "connected", None)
            return True
        except Exception as e:
            logger.error(f"Connection error: {str(e)}", exc_info=True)  # Add full traceback
            if self.status_callback:
                await self.status_callback(None, "connection_status", "disconnected", None)
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

    async def _process_message(self, message: str):
        """Process incoming WebSocket messages"""
        try:
            data = json.loads(message)
            logger.debug(f"Received message: {data}")

            # Handle different message types
            if "type" in data:
                if data["type"] == "newToken":
                    logger.info(f"New token detected: {data}")
                    if self.new_token_callback:
                        await self.new_token_callback(data)

                    # Auto-subscribe to the new token's trades
                    payload = {
                        "method": "subscribeTokenTrade",
                        "keys": [data.get('mint')]
                    }
                    await self.websocket.send(json.dumps(payload))
                    logger.info(f"Subscribed to trades for new token: {data.get('mint')}")

                elif data["type"] == "trade":
                    logger.info(f"Trade event: {data}")
                    if self.trade_callback:
                        await self.trade_callback(data)

                else:
                    logger.warning(f"Unknown message type: {data['type']}")

            # Update last message time for connection health check
            self.last_message_time = time.time()

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            logger.error(f"Message content: {message}")

    def is_token_processed(self, token_mint: str) -> bool:
        """Check if token has been processed"""
        return token_mint in self.processed_tokens

    def mark_token_processed(self, token_mint: str):
        """Mark token as processed"""
        self.processed_tokens.add(token_mint)

    def get_holder_count(self, token_mint: str) -> int:
        """Get current holder count for token"""
        return self.token_holders.get(token_mint, 0)

    async def _subscribe_initial(self) -> bool:
        """Subscribe to initial data streams"""
        try:
            logger.info("Attempting to subscribe to initial data streams...")

            # Subscribe to new token events using exact format from docs
            new_token_payload = {
                "method": "subscribeNewToken"
            }
            await self.websocket.send(json.dumps(new_token_payload))
            logger.info("Subscribed to new token events")

            # Subscribe to existing tracked tokens if any
            if self.tracked_tokens:
                token_trade_payload = {
                    "method": "subscribeTokenTrade",
                    "keys": list(self.tracked_tokens)
                }
                await self.websocket.send(json.dumps(token_trade_payload))
                logger.info(f"Subscribed to {len(self.tracked_tokens)} tracked tokens")

            return True

        except Exception as e:
            logger.error(f"Subscription error: {str(e)}", exc_info=True)
            return False

    async def start_monitoring(self):
        """Start WebSocket monitoring with reconnection"""
        logger.info("Starting WebSocket monitoring...")
        self.running = True
        retries = 0

        if self.status_callback:
            await self.status_callback(None, "connection_status", "connecting", None)
            logger.info("Initial status: connecting")

        while self.running:
            try:
                logger.info("Attempting to establish connection...")
                if await self._connect():
                    logger.info("Connection established, subscribing to initial data streams...")
                    if await self._subscribe_initial():
                        retries = 0  # Reset retries on successful connection
                        logger.info("Successfully subscribed to data streams")

                        if self.status_callback:
                            await self.status_callback(None, "connection_status", "connected", None)
                            logger.info("Status callback: connected")

                        while self.running:
                            try:
                                async for message in self.websocket:
                                    await self._process_message(message)
                                    self.last_message_time = time.time()
                            except websockets.exceptions.ConnectionClosed as e:
                                logger.error(f"WebSocket connection closed: {str(e)}")
                                if self.status_callback:
                                    await self.status_callback(None, "connection_status", "reconnecting", None)
                                    logger.info("Status callback: reconnecting")
                                break
                    else:
                        logger.error("Failed to subscribe to initial data streams")
                        if self.status_callback:
                            await self.status_callback(None, "connection_status", "subscription_failed", None)
                            logger.info("Status callback: subscription_failed")
                else:
                    logger.error("Failed to establish connection")
                    if self.status_callback:
                        await self.status_callback(None, "connection_status", "connection_failed", None)
                        logger.info("Status callback: connection_failed")

                # Implement exponential backoff for reconnection
                if retries < self.max_retries:
                    wait_time = min(300, self.reconnect_delay * (2 ** retries))  # Cap at 5 minutes
                    logger.info(f"Waiting {wait_time} seconds before reconnecting...")
                    await asyncio.sleep(wait_time)
                    retries += 1
                else:
                    logger.error("Max retries reached, stopping monitoring")
                    break

            except Exception as e:
                logger.error(f"Monitoring error: {str(e)}", exc_info=True)
                if self.status_callback:
                    await self.status_callback(None, "connection_status", "error", None)
                    logger.info("Status callback: error")
                if retries >= self.max_retries:
                    break
                await asyncio.sleep(self.reconnect_delay * (2 ** retries))
                retries += 1

        logger.info("WebSocket monitoring stopped")
        if self.status_callback:
            await self.status_callback(None, "connection_status", "disconnected", None)
            logger.info("Status callback: disconnected")

    async def _handle_new_token(self, data: dict):
        """Process new token events"""
        if self.token_callback and 'mint' in data:
            try:
                # Print raw data for debugging
                logger.debug(f"New token raw data: {json.dumps(data, indent=2)}")

                mcap = Decimal(str(data.get('marketCapSol', 0)))
                price = Decimal(str(data.get('price', 0)))
                liquidity = Decimal(str(data.get('liquidity', 0)))
                mint = data.get('mint')
                usd_mcap = mcap * self.SOL_PRICE_USD

                # Store initial state
                token_data = {
                    'mint': mint,
                    'market_cap': float(mcap),
                    'usd_market_cap': float(usd_mcap),
                    'price': float(price),
                    'liquidity': float(liquidity),
                    'timestamp': time.time()
                }

                logger.info(f"\n🔍 New Token Analysis:")
                logger.info(f"Mint: {mint}")
                logger.info(f"Market Cap: ${usd_mcap:,.2f}")
                logger.info(f"Price: ${float(price * self.SOL_PRICE_USD):,.6f}")
                logger.info(f"Liquidity: {liquidity} SOL")

                # Subscribe to trades immediately
                self.token_metrics[mint] = token_data
                await self.subscribe_to_token(mint)

                # Notify callback
                if self.token_callback:
                    await self.token_callback(token_data)

            except Exception as e:
                logger.error(f"Error processing new token: {str(e)}")
                logger.debug(f"Problem data: {json.dumps(data, indent=2)}")

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

    async def stop(self):
        """Stop monitoring and cleanup"""
        self.running = False
        if self.websocket and not self.websocket.closed:
            try:
                # Unsubscribe from all tokens
                for token in list(self.tracked_tokens):
                    await self.unsubscribe_from_token(token)
                await self.websocket.close()
            except Exception as e:
                logger.error(f"Error closing connection: {str(e)}")

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
