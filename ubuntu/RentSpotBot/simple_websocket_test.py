import asyncio
import websockets
import json
import logging
import ssl
import socket
from websockets.exceptions import WebSocketException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def subscribe():
    uri = "wss://pumpportal.fun/api/data"
    headers = {
        'Upgrade': 'websocket',
        'Host': 'pumpportal.fun',
        'Origin': 'https://pump.fun',
        'Sec-WebSocket-Key': '4hqE+H//GWhenGLKnaFcMw==',
        'Sec-WebSocket-Version': '13',
        'Connection': 'Upgrade'
    }

    try:
        # First try to resolve the domain
        try:
            ip = socket.gethostbyname('pumpportal.fun')
            logger.info(f"Successfully resolved pumpportal.fun to {ip}")
        except socket.gaierror as e:
            logger.error(f"Failed to resolve domain: {str(e)}")
            return

        # Create SSL context
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED

        logger.info("Attempting WebSocket connection...")
        async with websockets.connect(
            uri,
            extra_headers=headers,
            ssl=ssl_context,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=10
        ) as websocket:
            logger.info("WebSocket connection established")

            # Subscribing to token creation events
            payload = {
                "method": "subscribeNewToken",
            }
            await websocket.send(json.dumps(payload))
            logger.info("Sent subscription request")

            async for message in websocket:
                data = json.loads(message)
                logger.info(f"Received message: {data}")

    except WebSocketException as e:
        logger.error(f"WebSocket error: {str(e)}")
    except ssl.SSLError as e:
        logger.error(f"SSL error: {str(e)}")
    except ConnectionRefusedError as e:
        logger.error(f"Connection refused: {str(e)}")
    except Exception as e:
        logger.error(f"Connection error: {str(e)}")
        logger.exception("Full traceback:")

async def main():
    retry_count = 0
    max_retries = 3

    while retry_count < max_retries:
        try:
            await subscribe()
            break
        except Exception as e:
            retry_count += 1
            if retry_count < max_retries:
                wait_time = 2 ** retry_count
                logger.warning(f"Connection attempt {retry_count} failed. Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                logger.error("Max retries reached. Giving up.")
                break

# Run the main function
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down due to keyboard interrupt...")
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
        logger.exception("Full traceback:")
