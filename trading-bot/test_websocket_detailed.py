import asyncio
import websockets
import json
import logging
import ssl
import certifi

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_websocket():
    uri = "wss://pumpportal.fun/api/data"
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    try:
        async with websockets.connect(
            uri,
            ssl=ssl_context,
            open_timeout=10,
            close_timeout=10,
            max_size=None,
            subprotocols=[],
            compression=None,
            user_agent_header='Mozilla/5.0'
        ) as websocket:
            logger.info("Connected to WebSocket")

            # Subscribe to new tokens
            subscribe_msg = {
                "method": "subscribeNewToken"
            }
            await websocket.send(json.dumps(subscribe_msg))
            logger.info("Sent subscription request")

            while True:
                try:
                    message = await websocket.recv()
                    logger.info(f"Raw message received: {message}")
                    data = json.loads(message)
                    logger.info(f"Parsed message: {json.dumps(data, indent=2)}")
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    break

    except Exception as e:
        logger.error(f"Connection error: {str(e)}")
        if isinstance(e, websockets.exceptions.InvalidStatusCode):
            logger.error(f"Invalid status code: {e.status_code}")
        elif isinstance(e, ssl.SSLError):
            logger.error(f"SSL Error: {str(e)}")
        elif isinstance(e, websockets.exceptions.InvalidMessage):
            logger.error(f"Invalid message: {str(e)}")
        else:
            logger.error(f"Other error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
