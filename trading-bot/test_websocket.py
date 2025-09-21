import asyncio
import json
import logging
import websockets.client
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_websocket():
    uri = "wss://pumpportal.fun/api/data"

    async with websockets.client.connect(
        uri,
        user_agent_header='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        origin='https://pumpportal.fun',
        extra_headers={
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        }
    ) as websocket:
        logger.info("Connected to WebSocket")

        # Subscribe to new tokens with authentication
        subscribe_msg = {
            "method": "subscribeNewToken",
            "publicKey": os.getenv('PUBLIC_KEY')
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
