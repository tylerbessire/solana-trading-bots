"""
Comprehensive test suite for buy-sell sequences with multiple tokens.
"""
import asyncio
import logging
from datetime import datetime
from src.rent_spot_bot import RentSpotBot
from config.wallet_config import WALLET_PUBLIC_KEY, MAX_TRADE_AMOUNT

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test tokens (mix of valid and invalid tokens for comprehensive testing)
TEST_TOKENS = [
    "GMEfQZEjF6AbZMB4aQG2QEfH8uSWGMTxTnMsNzfCG6sk",  # Known working token
    "So11111111111111111111111111111111111111112",   # SOL token
    "InvalidTokenAddressForTesting123456789",         # Invalid token for error handling
]

async def test_trade_sequence(bot: RentSpotBot, token_mint: str) -> dict:
    """
    Test a complete buy-sell sequence for a single token.
    Returns test results including timing and success status.
    """
    start_time = datetime.now()
    result = {
        'token': token_mint,
        'start_time': start_time.isoformat(),
        'buy_success': False,
        'sell_success': False,
        'total_time': None,
        'error': None
    }

    try:
        logger.info(f"Testing trade sequence for token: {token_mint}")

        # Execute buy transaction
        buy_result = await bot._execute_trade(token_mint, "buy")
        if buy_result:
            result['buy_success'] = True
            result['buy_signature'] = buy_result.get('signature')

            # Wait longer for transaction confirmation and token balance update
            logger.info("Waiting for buy transaction to confirm and token balance to update...")
            await asyncio.sleep(10)  # Increased from 5 to 10 seconds

            # Add additional logging for debugging
            logger.info(f"Buy transaction confirmed. Proceeding with sell for {token_mint}")

            # Execute sell transaction
            sell_result = await bot._execute_trade(token_mint, "sell")
            if sell_result:
                result['sell_success'] = True
                result['sell_signature'] = sell_result.get('signature')
                logger.info(f"Complete sequence successful for {token_mint}")
            else:
                result['error'] = "Sell transaction failed"
        else:
            result['error'] = "Buy transaction failed"

    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Error in trade sequence: {e}")

    end_time = datetime.now()
    result['total_time'] = (end_time - start_time).total_seconds()
    return result

async def run_test_suite():
    """
    Run comprehensive tests on multiple tokens.
    """
    bot = RentSpotBot()
    results = []

    logger.info(f"Starting comprehensive test suite with wallet: {WALLET_PUBLIC_KEY}")
    logger.info(f"Trade amount per transaction: {MAX_TRADE_AMOUNT} SOL")

    for token in TEST_TOKENS:
        result = await test_trade_sequence(bot, token)
        results.append(result)
        # Add delay between test sequences
        await asyncio.sleep(2)

    return results

async def main():
    """
    Main test execution function.
    """
    logger.info("Starting comprehensive trade sequence testing...")
    results = await run_test_suite()

    # Print summary
    success_count = sum(1 for r in results if r['buy_success'] and r['sell_success'])
    logger.info(f"\nTest Summary:")
    logger.info(f"Total tests: {len(results)}")
    logger.info(f"Successful sequences: {success_count}")
    logger.info(f"Failed sequences: {len(results) - success_count}")

    # Detailed results
    for result in results:
        logger.info(f"\nToken: {result['token']}")
        logger.info(f"Buy Success: {result['buy_success']}")
        logger.info(f"Sell Success: {result['sell_success']}")
        logger.info(f"Total Time: {result['total_time']:.2f} seconds")
        if result['error']:
            logger.info(f"Error: {result['error']}")

if __name__ == "__main__":
    asyncio.run(main())
