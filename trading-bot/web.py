import asyncio
import websockets
import json
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

async def subscribe():
    """Subscribe to pump.fun WebSocket feed"""
    uri = "wss://pumpportal.fun/api/data"
    try:
        async with websockets.connect(uri) as websocket:
            logger.info("Connected to WebSocket")

            # Subscribing to token creation events
            payload = {
                "method": "subscribeNewToken",
            }
            await websocket.send(json.dumps(payload))

            # Subscribing to trades made by accounts
            payload = {
                "method": "subscribeAccountTrade",
                "keys": ["YOUR_ACCOUNT_ADDRESS_HERE"]  # array of accounts to watch
            }
            await websocket.send(json.dumps(payload))

            # Subscribing to trades on tokens
            payload = {
                "method": "subscribeTokenTrade",
                "keys": ["91WNez8D22NwBssQbkzjy4s2ipFrzpmn5hfvWVe2aY5p"]  # array of token CAs to watch
            }
            await websocket.send(json.dumps(payload))

            # Process incoming messages
            async for message in websocket:
                try:
                    data = json.loads(message)
                    logger.debug(f"Received message: {data}")
                    yield data
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode message: {e}")
                    continue

    except websockets.exceptions.WebSocketException as e:
        logger.error(f"WebSocket error: {e}")
        raise

if __name__ == "__main__":
    async def main():
        async for message in subscribe():
            print(message)

    asyncio.get_event_loop().run_until_complete(main())
