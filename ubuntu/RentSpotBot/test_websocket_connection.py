"""
WebSocket connection test script for pump.fun with rate limiting and connection management
"""
import asyncio
import websockets
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from src.message_handler import MessageHandler, TradeEvent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RateLimitedWebSocket:
    def __init__(self, uri: str):
        self.uri = uri
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.last_connection_attempt = datetime.min
        self.connection_attempt_count = 0
        self.message_queue: List[Dict] = []
        self.last_message_time = datetime.min
        self.min_message_interval = 1.0  # Minimum seconds between messages
        self.max_reconnect_delay = 300  # Maximum reconnection delay in seconds
        self.extra_headers = {
            'Origin': 'https://pump.fun',
            'Host': 'pumpportal.fun',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Upgrade': 'websocket',
            'Connection': 'Upgrade',
            'Sec-WebSocket-Version': '13',
            'Sec-WebSocket-Extensions': 'permessage-deflate; client_max_window_bits'
        }
        self.message_handler = MessageHandler()
        logger.info("WebSocket client initialized")

    def get_reconnect_delay(self) -> float:
        """Calculate reconnection delay with exponential backoff"""
        delay = min(2 ** self.connection_attempt_count, self.max_reconnect_delay)
        return delay

    async def connect(self) -> None:
        """Establish WebSocket connection with rate limiting"""
        now = datetime.now()
        if (now - self.last_connection_attempt).total_seconds() < self.get_reconnect_delay():
            return

        self.last_connection_attempt = now
        self.connection_attempt_count += 1

        try:
            logger.info(f"Attempting to connect to {self.uri} with headers: {self.extra_headers}")
            self.websocket = await websockets.connect(
                self.uri,
                extra_headers=self.extra_headers,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10
            )
            self.connected = True
            self.connection_attempt_count = 0
            logger.info("Successfully connected to WebSocket")

            # Send initial subscription message
            subscription_msg = {
                "method": "subscribeNewToken"
            }
            await self.websocket.send(json.dumps(subscription_msg))
            logger.info("Sent subscription request")

            # Wait for subscription confirmation
            response = await self.websocket.recv()
            logger.info(f"Received subscription response: {response}")

        except websockets.exceptions.InvalidStatusCode as e:
            logger.error(f"Invalid status code during connection: {e.status_code}")
            self.connected = False
        except websockets.exceptions.InvalidMessage as e:
            logger.error(f"Invalid message during connection: {e}")
            self.connected = False
        except Exception as e:
            logger.error(f"Failed to connect: {str(e)}")
            self.connected = False

    async def send_message(self, message: Dict) -> None:
        """Send message with rate limiting"""
        if not self.connected or not self.websocket:
            self.message_queue.append(message)
            return

        now = datetime.now()
        time_since_last = (now - self.last_message_time).total_seconds()

        if time_since_last < self.min_message_interval:
            self.message_queue.append(message)
            return

        try:
            await self.websocket.send(json.dumps(message))
            self.last_message_time = now
            logger.info(f"Sent message: {message}")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            self.connected = False
            self.message_queue.append(message)

    async def process_message_queue(self) -> None:
        """Process queued messages"""
        while self.message_queue and self.connected:
            message = self.message_queue.pop(0)
            await self.send_message(message)

    async def receive_messages(self) -> None:
        """Receive and process incoming messages"""
        if not self.connected or not self.websocket:
            return

        try:
            async for message in self.websocket:
                data = json.loads(message)
                logger.info(f"Received message: {data}")
                # Process message using MessageHandler with parsed data
                trade_event = self.message_handler.process_message(data)
                if trade_event:
                    await self.message_handler.handle_trade_event(trade_event)
                    logger.info(f"Processed trade event: {trade_event.tx_type}")
                else:
                    logger.debug(f"Received non-trade message: {data}")
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")
            self.connected = False

    async def run(self) -> None:
        """Main loop with connection management and message handling"""
        try:
            while True:
                if not self.connected:
                    logger.info("Not connected. Attempting to establish connection...")
                    await self.connect()
                    if self.connected:
                        logger.info("Connection established successfully")
                    else:
                        logger.warning("Connection attempt failed, will retry with backoff")
                        await asyncio.sleep(self.get_reconnect_delay())
                        continue

                try:
                    if self.connected:
                        await self.process_message_queue()
                        await self.receive_messages()
                except websockets.exceptions.ConnectionClosed:
                    logger.error("WebSocket connection closed unexpectedly")
                    self.connected = False
                except Exception as e:
                    logger.error(f"Error in main loop: {str(e)}")
                    self.connected = False

                await asyncio.sleep(1)  # Prevent tight loop
        finally:
            # Cleanup resources
            if self.websocket:
                await self.websocket.close()
            await self.message_handler.transaction_handler.close()
            logger.info("WebSocket client shutdown complete")

async def main():
    uri = os.getenv("WS_URI", "wss://pumpportal.fun/api/data")
    client = RateLimitedWebSocket(uri)
    try:
        await client.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await client.message_handler.transaction_handler.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down due to keyboard interrupt...")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
