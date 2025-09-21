"""
Test script to validate WebSocket connection and token event handling.
"""
import asyncio
import logging
from src.websocket_client import PumpWebSocketClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_token_handler(event_data):
    """
    Test handler for token events.
    """
    logger.info(f"Test handler received token event: {event_data}")

async def main():
    """
    Run WebSocket connection test.
    """
    logger.info("Starting WebSocket connection test...")

    client = PumpWebSocketClient(on_token_event=test_token_handler)
    try:
        logger.info("Attempting to connect to WebSocket...")
        # Run for 60 seconds to test connection and event handling
        connection_task = asyncio.create_task(client.connect())
        await asyncio.sleep(60)

        logger.info("Test completed. Disconnecting...")
        await client.disconnect()

    except Exception as e:
        logger.error(f"Test failed with error: {e}")
    finally:
        if not client.websocket.closed:
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
