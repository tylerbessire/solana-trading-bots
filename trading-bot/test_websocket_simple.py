import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_websocket():
    uri = "wss://pumpportal.fun/api/data"

    async with websockets.connect(uri) as websocket:
        logger.info("Connected to WebSocket")

        # Subscribe to new tokens
        subscribe_msg = {
            "method": "subscribeNewToken"
        }
        await websocket.send(json.dumps(subscribe_msg))
        logger.info("Sent subscription request")

        # Listen for messages
        while True:
            try:
                message = await websocket.recv()
                logger.info(f"Raw message received: {message}")
                data = json.loads(message)
                logger.info(f"Parsed message: {json.dumps(data, indent=2)}")
            except Exception as e:
                logger.error(f"Error: {str(e)}")
                break

if __name__ == "__main__":
    asyncio.run(test_websocket())
