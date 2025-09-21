"""
Test script to verify token event logging functionality.
"""
import asyncio
import logging
from pathlib import Path
from src.rent_spot_bot import RentSpotBot
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def verify_logs():
    """
    Verify that token events are being properly logged.
    """
    bot = RentSpotBot()

    try:
        # Start the bot
        logger.info("Starting bot for log verification...")
        await bot.start()

        # Let it run for 60 seconds to collect some events
        logger.info("Collecting token events for 60 seconds...")
        await asyncio.sleep(60)

        # Stop the bot
        await bot.stop()

        # Verify log files
        log_dir = Path("logs")
        csv_file = log_dir / "token_events.csv"

        if not csv_file.exists():
            logger.error("Token events CSV file not found!")
            return False

        # Read and display statistics
        df = pd.read_csv(csv_file)
        logger.info(f"Total events logged: {len(df)}")
        logger.info(f"Unique tokens: {df['mint'].nunique()}")

        # Check for detailed JSON logs
        json_files = list(log_dir.glob("detailed_*.json"))
        logger.info(f"Detailed JSON logs created: {len(json_files)}")

        # Get bot status
        status = bot.get_status()
        logger.info("Bot Status:")
        logger.info(f"Token Statistics: {status['token_statistics']}")
        logger.info(f"Recent Tokens: {status['recent_tokens']}")

        return True

    except Exception as e:
        logger.error(f"Error during log verification: {e}")
        return False

async def main():
    """
    Run the logging verification test.
    """
    logger.info("Starting token logging verification test...")
    success = await verify_logs()

    if success:
        logger.info("Token logging verification completed successfully!")
    else:
        logger.error("Token logging verification failed!")

if __name__ == "__main__":
    asyncio.run(main())
