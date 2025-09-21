"""
WebSocket client for connecting to pump.fun
Maintains a single connection and handles subscriptions properly
"""
import asyncio
import json
import logging
import websockets
from typing import Callable, Optional, List
import random

from config.constants import WS_URI

logger = logging.getLogger(__name__)

class PumpWebSocketClient:
    def __init__(self, on_token_event: Callable):
        self.uri = WS_URI
        self.on_token_event = on_token_event
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._connect_lock = asyncio.Lock()
        self._listen_task = None
        self._subscribed_tokens: List[str] = []
        self._subscribed_accounts: List[str] = []
        self._is_subscribed_to_new_tokens = False
        self._reconnect_delay = 1  # Initial reconnect delay in seconds

    async def connect(self):
        """Connect to WebSocket and restore previous subscriptions"""
        async with self._connect_lock:
            if self.websocket and not self.websocket.closed:
                return  # Already connected

            try:
                self.websocket = await websockets.connect(self.uri)
                logger.info("Connected to WebSocket")

                # Restore previous subscriptions
                if self._is_subscribed_to_new_tokens:
                    await self._subscribe_new_tokens()
                if self._subscribed_tokens:
                    await self._subscribe_tokens(self._subscribed_tokens)
                if self._subscribed_accounts:
                    await self._subscribe_accounts(self._subscribed_accounts)

                # Start listening task if not already running
                if not self._listen_task or self._listen_task.done():
                    self._listen_task = asyncio.create_task(self._listen())

                self._reconnect_delay = 1  # Reset delay on successful connection
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
                self._reconnect_delay *= 2  # Double the delay for next attempt
                raise

    async def _subscribe_new_tokens(self):
        """Subscribe to new token events"""
        if not self.websocket or self.websocket.closed:
            return False

        try:
            payload = {"method": "subscribeNewToken"}
            await self.websocket.send(json.dumps(payload))
            self._is_subscribed_to_new_tokens = True
            logger.info("Subscribed to new token events")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to new token events: {e}")
            return False

    async def _subscribe_tokens(self, tokens: List[str]):
        """Subscribe to specific token trades"""
        if not self.websocket or self.websocket.closed:
            return False

        try:
            payload = {
                "method": "subscribeTokenTrade",
                "keys": tokens
            }
            await self.websocket.send(json.dumps(payload))
            self._subscribed_tokens.extend(token for token in tokens if token not in self._subscribed_tokens)
            logger.info(f"Subscribed to token trades: {tokens}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to token trades: {e}")
            return False

    async def _listen(self):
        """Listen for WebSocket messages"""
        while True:
            try:
                if not self.websocket or self.websocket.closed:
                    await self._reconnect()
                    continue

                message = await self.websocket.recv()
                data = json.loads(message)
                await self.on_token_event(data)
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed, will attempt to reconnect...")
                await self._reconnect()
            except Exception as e:
                logger.error(f"WebSocket message handling error: {e}")
                await asyncio.sleep(1)

    async def _reconnect(self):
        """Attempt to reconnect with backoff"""
        if self._connect_lock.locked():
            return  # Another reconnection attempt is already in progress

        logger.info(f"Waiting {self._reconnect_delay} seconds before reconnecting...")
        await asyncio.sleep(self._reconnect_delay)

        try:
            await self.connect()
        except Exception:
            pass  # Connection error already logged in connect()

    async def subscribe_to_new_tokens(self):
        """Public method to subscribe to new token events"""
        if not self._is_subscribed_to_new_tokens:
            return await self._subscribe_new_tokens()
        return True

    async def subscribe_to_tokens(self, tokens: List[str]):
        """Public method to subscribe to specific token trades"""
        new_tokens = [token for token in tokens if token not in self._subscribed_tokens]
        if new_tokens:
            return await self._subscribe_tokens(new_tokens)
        return True

    async def disconnect(self):
        """Disconnect from WebSocket"""
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            logger.info("Disconnected from WebSocket")

        # Clear subscription state
        self._is_subscribed_to_new_tokens = False
        self._subscribed_tokens.clear()
        self._subscribed_accounts.clear()
