import asyncio
import websockets
import json
import logging
from datetime import datetime
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PATHS_TO_TRY = [
    '/ws',
    '/websocket',
    '/socket',
    '/stream',
    '/v1/ws',
    '/v1/stream',
    '/api/v1/ws',
    '/api/v1/stream',
    '/api/ws',
    '/api/stream'
]

async def test_websocket_path(path):
    uri = f"wss://pumpportal.fun{path}"
    parsed_uri = urlparse(uri)

    try:
        logger.info(f"Attempting connection to {uri}")
        async with websockets.connect(
            uri,
            ping_interval=None,
            close_timeout=5,
            subprotocols=['websocket'],
            origin='https://pumpportal.fun',
            host=parsed_uri.netloc,
            user_agent_header='Mozilla/5.0'
        ) as websocket:
            logger.info(f"Connected successfully to {uri}")

            # Try subscribing to new tokens
            subscribe_msg = {
                "method": "subscribeNewToken"
            }
            await websocket.send(json.dumps(subscribe_msg))
            logger.info(f"Sent subscription request to {uri}")

            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                logger.info(f"Received response from {uri}: {message}")
                return True
            except asyncio.TimeoutError:
                logger.warning(f"No response received from {uri} after 5 seconds")
                return False

    except Exception as e:
        logger.error(f"Failed to connect to {uri}: {str(e)}")
        return False

async def main():
    logger.info(f"Starting WebSocket endpoint discovery at {datetime.now()}")

    for path in PATHS_TO_TRY:
        success = await test_websocket_path(path)
        if success:
            logger.info(f"Found working endpoint: {path}")
            return path

    logger.info("No working WebSocket endpoints found")
    return None

if __name__ == "__main__":
    asyncio.run(main())
