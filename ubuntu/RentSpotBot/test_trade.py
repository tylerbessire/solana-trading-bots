"""
Test script to verify trading functionality.
"""
import asyncio
import logging
from src.rent_spot_bot import RentSpotBot
from config.wallet_config import WALLET_PUBLIC_KEY

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_trade():
    """
    Test a single buy-sell sequence on a known token.
    """
    bot = RentSpotBot()

    # Test token mint (you can replace this with a real token mint from your logs)
    test_token = "GMEfQZEjF6AbZMB4aQG2QEfH8uSWGMTxTnMsNzfCG6sk"

    logger.info(f"Testing trade functionality with token: {test_token}")
    logger.info(f"Using wallet: {WALLET_PUBLIC_KEY}")

    try:
        # Execute buy transaction
        logger.info("Attempting buy transaction...")
        buy_result = await bot._execute_trade(test_token, "buy")

        if buy_result:
            logger.info(f"Buy transaction successful: {buy_result}")

            # Wait for transaction confirmation
            logger.info("Waiting for buy transaction to confirm...")
            await asyncio.sleep(5)  # Wait 5 seconds for confirmation

            # Execute sell transaction
            logger.info("Attempting sell transaction...")
            sell_result = await bot._execute_trade(test_token, "sell")

            if sell_result:
                logger.info(f"Sell transaction successful: {sell_result}")
                return True
            else:
                logger.error("Sell transaction failed")
                return False
        else:
            logger.error("Buy transaction failed")
            return False

    except Exception as e:
        logger.error(f"Error during trade test: {e}")
        return False

async def main():
    """
    Run the trade test.
    """
    logger.info("Starting trade functionality test...")
    success = await test_trade()

    if success:
        logger.info("Trade test completed successfully!")
    else:
        logger.error("Trade test failed!")

if __name__ == "__main__":
    asyncio.run(main())
