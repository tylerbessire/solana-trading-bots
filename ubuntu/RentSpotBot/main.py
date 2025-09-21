import asyncio
import logging
import json
from typing import Dict, List
from src.websocket_client import PumpWebSocketClient
from src.batch_burner import BatchBurner
from src.profit_tracker import ProfitTracker
from config.wallet_config import WALLET_PUBLIC_KEY, WALLET_PRIVATE_KEY
from config.constants import WS_URI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RentSpotBot:
    def __init__(self):
        self.batch_burner = BatchBurner(
            wallet_public_key=WALLET_PUBLIC_KEY,
            private_key=WALLET_PRIVATE_KEY,
            min_spots_to_burn=5  # Adjust based on optimal batch size
        )
        self.ws_client = PumpWebSocketClient(on_token_event=self.handle_new_token)
        self.active = True

    async def handle_new_token(self, token_data: Dict):
        """Handle new token event from WebSocket."""
        try:
            logger.debug(f"Received token data: {token_data}")

            # Check if this is a new token event
            if isinstance(token_data, dict) and 'data' in token_data:
                token_info = token_data['data']
                if isinstance(token_info, dict) and 'token_mint' in token_info:
                    logger.info(f"New token detected: {token_info['token_mint']}")

                    # Add to pending spots for burning
                    await self.batch_burner.add_rent_spot({
                        "token_mint": token_info['token_mint'],
                        "signature": token_info.get('signature', 'pending')
                    })

                    # Check if we have enough spots to trigger a burn
                    if self.batch_burner.get_pending_spots_count() >= self.batch_burner.min_spots_to_burn:
                        burn_result = await self.batch_burner.execute_batch_burn()
                        if burn_result:
                            profit_summary = self.batch_burner.get_profit_summary()
                            logger.info(f"Batch burn completed. Profit summary: {profit_summary}")

        except Exception as e:
            logger.error(f"Error handling new token: {str(e)}", exc_info=True)

    async def start(self):
        """Start the bot."""
        try:
            logger.info("Starting RentSpotBot...")

            # Connect to WebSocket and start monitoring
            await self.ws_client.connect()

            # Keep the bot running
            while self.active:
                await asyncio.sleep(60)  # Check profit summary every minute
                profit_summary = self.batch_burner.get_profit_summary()
                logger.info(f"Current profit summary: {profit_summary}")

        except Exception as e:
            logger.error(f"Fatal error in bot: {str(e)}")
            raise
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Cleanup resources."""
        try:
            await self.ws_client.disconnect()
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

async def main():
    bot = RentSpotBot()
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested...")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
    finally:
        await bot.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
