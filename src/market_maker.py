import asyncio
import websockets
import json
from typing import Dict, Set, Optional
from decimal import Decimal
import backoff
import time

class MarketMaker:
    def __init__(self):
        self.ws = None
        self.subscribed_tokens: Set[str] = set()
        self.price_feeds: Dict[str, float] = {}
        self.ws_uri = "wss://api.mainnet-beta.solana.com"
        self._lock = asyncio.Lock()
        self._reconnect_interval = 1
        self._max_reconnect_interval = 30
        self._last_message_time = 0
        self._heartbeat_interval = 30
        self._process_task = None
        self._heartbeat_task = None

    async def connect(self):
        if not self.ws or self.ws.closed:
            try:
                self.ws = await websockets.connect(
                    self.ws_uri,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10
                )
                self._last_message_time = time.time()
                await self._resubscribe_all()
            except Exception as e:
                print(f"Connection error: {e}")
                await asyncio.sleep(min(self._reconnect_interval, self._max_reconnect_interval))
                self._reconnect_interval *= 2
                raise

    async def _resubscribe_all(self):
        tokens_to_resubscribe = self.subscribed_tokens.copy()
        self.subscribed_tokens.clear()
        for token in tokens_to_resubscribe:
            await self.subscribe_to_token(token)

    async def _heartbeat(self):
        while True:
            try:
                if self.ws and not self.ws.closed:
                    current_time = time.time()
                    if current_time - self._last_message_time > self._heartbeat_interval:
                        ping_message = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "ping"
                        }
                        await self.ws.send(json.dumps(ping_message))
                await asyncio.sleep(self._heartbeat_interval)
            except Exception as e:
                print(f"Heartbeat error: {e}")
                await asyncio.sleep(1)

    async def start(self):
        if not self._process_task:
            self._process_task = asyncio.create_task(self.process_messages())
        if not self._heartbeat_task:
            self._heartbeat_task = asyncio.create_task(self._heartbeat())

    async def subscribe_to_token(self, token_address: str):
        if token_address in self.subscribed_tokens:
            return

        async with self._lock:
            try:
                if not self.ws or self.ws.closed:
                    await self.connect()

                subscribe_message = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "accountSubscribe",
                    "params": [
                        token_address,
                        {"encoding": "jsonParsed", "commitment": "processed"}
                    ]
                }

                await self.ws.send(json.dumps(subscribe_message))
                self.subscribed_tokens.add(token_address)
            except Exception as e:
                print(f"Error subscribing to token {token_address}: {e}")
                if token_address in self.subscribed_tokens:
                    self.subscribed_tokens.remove(token_address)

    async def process_messages(self):
        while True:
            try:
                if not self.ws or self.ws.closed:
                    await self.connect()

                message = await self.ws.recv()
                self._last_message_time = time.time()
                data = json.loads(message)

                if "method" in data and data["method"] == "accountNotification":
                    token_address = data["params"]["result"]["value"]["pubkey"]
                    self.price_feeds[token_address] = self._parse_price_data(data)

            except websockets.exceptions.ConnectionClosed:
                print("WebSocket connection closed. Reconnecting...")
                await asyncio.sleep(min(self._reconnect_interval, self._max_reconnect_interval))
                self._reconnect_interval *= 2
                continue
            except Exception as e:
                print(f"Error processing message: {e}")
                await asyncio.sleep(1)
            else:
                self._reconnect_interval = 1

    def _parse_price_data(self, data: Dict) -> Optional[float]:
        try:
            return float(data["params"]["result"]["value"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"])
        except (KeyError, ValueError) as e:
            print(f"Error parsing price data: {e}")
            return None

    async def get_latest_price(self, token_address: str) -> Optional[float]:
        return self.price_feeds.get(token_address)

    async def close(self):
        if self._process_task:
            self._process_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self.ws:
            await self.ws.close()
            self.ws = None
            self.subscribed_tokens.clear()
            self.price_feeds.clear()
