import asyncio
import logging
from optimized_rent_spot_bot import OptimizedRentSpotBot
from dashboard import main as run_dashboard
import streamlit as st
from dotenv import load_dotenv
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/trading_bot.log'),
        logging.StreamHandler()
    ]
)

async def main():
    try:
        # Load environment variables
        load_dotenv()

        # Verify environment variables
        if not os.getenv('PUBLIC_KEY') or not os.getenv('PRIVATE_KEY'):
            raise ValueError("Missing required environment variables: PUBLIC_KEY and PRIVATE_KEY")

        bot = OptimizedRentSpotBot()

        # Configure initial parameters
        bot.min_mcap_usd = 7000      # $7k minimum market cap
        bot.min_token_age = 15       # 15s minimum age
        bot.trade_amount = 0.01      # 0.01 SOL per trade
        bot.slippage = 5            # 5% slippage
        bot.auto_buyback = True     # Enable auto buyback
        bot.sell_mcap_usd = 30000   # $30k sell target

        await bot.start()

    except Exception as e:
        logging.error(f"Bot error: {str(e)}")
        if 'bot' in locals():
            await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
