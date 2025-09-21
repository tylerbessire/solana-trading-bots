import asyncio
import logging
from dotenv import load_dotenv
from optimized_rent_spot_bot import OptimizedRentSpotBot
import subprocess
import sys
import os
from decimal import Decimal
import signal
import time

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot_debug.log')
    ]
)
logger = logging.getLogger(__name__)

# Global state
running = True
bot_instance = None

async def trade_update_callback(token_mint, action, price, amount, profit=None):
    """Enhanced trade update callback with detailed logging"""
    try:
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

        if action == "connection_status":
            logger.info(f"Connection status changed to: {price}")
            return

        if action == "new_token":
            logger.info(
                f"New token detected:\n"
                f"Token: {token_mint.get('mint')}\n"
                f"Name: {token_mint.get('name')} ({token_mint.get('symbol')})\n"
                f"Market Cap: {token_mint.get('marketCapSol'):.6f} SOL\n"
                f"Initial Buy: {token_mint.get('initialBuy', 0):.6f}\n"
                f"Timestamp: {timestamp}"
            )
            return

        if action == "buy":
            logger.info(
                f"Buy executed - Token: {token_mint}\n"
                f"Price: {price:.6f} SOL\n"
                f"Amount: {amount:.6f} SOL\n"
                f"Timestamp: {timestamp}"
            )

        elif action == "sell":
            profit_str = f", Profit: {profit:.6f} SOL" if profit is not None else ""
            amount_str = f"{amount}%" if isinstance(amount, str) else f"{amount:.6f} SOL"
            logger.info(
                f"Sell executed - Token: {token_mint}\n"
                f"Price: {price:.6f} SOL\n"
                f"Amount: {amount_str}{profit_str}\n"
                f"Timestamp: {timestamp}"
            )

        elif action == "dust_update":
            logger.info(
                f"Dust position update - Token: {token_mint}\n"
                f"Current Price: {price:.6f} SOL\n"
                f"Unrealized Profit: {profit:.6f} SOL\n"
                f"Timestamp: {timestamp}"
            )

        elif action == "price_update":
            logger.debug(
                f"Price update - Token: {token_mint}\n"
                f"New Price: {price:.6f} SOL\n"
                f"Timestamp: {timestamp}"
            )

    except Exception as e:
        logger.error(f"Error in trade callback: {str(e)}", exc_info=True)

def start_dashboard():
    """Start the Streamlit dashboard with error handling"""
    try:
        dashboard_process = subprocess.Popen([
            "streamlit", "run", 
            "dashboard.py",
            "--server.port=8502",
            "--server.address=localhost",
            "--server.headless=true",
            "--browser.serverAddress=localhost",
            "--browser.serverPort=8502"
        ])
        logger.info("Dashboard started successfully at http://localhost:8502")
        return dashboard_process
    except Exception as e:
        logger.error(f"Failed to start dashboard: {str(e)}")
        raise

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global running, bot_instance
    logger.info(f"Received signal {signum}, initiating shutdown...")
    running = False
    if bot_instance:
        asyncio.create_task(bot_instance.stop())

async def monitor_system_resources():
    """Monitor system resources and log metrics"""
    while running:
        try:
            # Log memory usage
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            logger.info(f"Memory usage: {memory_info.rss / 1024 / 1024:.2f} MB")
            
            # Log CPU usage
            cpu_percent = process.cpu_percent(interval=1)
            logger.info(f"CPU usage: {cpu_percent}%")
            
            await asyncio.sleep(60)  # Check every minute
        except Exception as e:
            logger.error(f"Error monitoring resources: {str(e)}")
            await asyncio.sleep(60)

async def start_bot():
    """Initialize and start the trading bot with enhanced error handling"""
    global bot_instance
    
    try:
        # Initialize bot
        logger.info("Initializing RentSpot Bot...")
        bot_instance = OptimizedRentSpotBot()
        
        # Register callbacks
        await bot_instance.register_trade_callback(trade_update_callback)
        logger.info("Trade callback registered successfully")
        
        # Start resource monitoring
        asyncio.create_task(monitor_system_resources())
        
        # Start the bot
        logger.info("Starting bot operations...")
        await bot_instance.start()
        
    except KeyboardInterrupt:
        logger.info("Shutting down bot due to keyboard interrupt...")
    except Exception as e:
        logger.error(f"Critical bot error: {str(e)}", exc_info=True)
        raise
    finally:
        if bot_instance:
            await bot_instance.stop()
            logger.info("Bot shutdown complete")

async def main():
    """Main entry point with comprehensive error handling and cleanup"""
    dashboard_process = None
    
    try:
        # Load environment variables
        load_dotenv(override=True)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Validate required environment variables
        required_vars = ['PUBLIC_KEY', 'PRIVATE_KEY', 'RPC_ENDPOINT']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        # Start dashboard
        dashboard_process = start_dashboard()
        
        # Start bot
        await start_bot()
        
    except Exception as e:
        logger.critical(f"Fatal error in main: {str(e)}", exc_info=True)
        sys.exit(1)
        
    finally:
        # Cleanup
        if dashboard_process:
            dashboard_process.terminate()
            try:
                dashboard_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                dashboard_process.kill()
            logger.info("Dashboard shutdown complete")
        
        logger.info("Cleanup complete, exiting...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.critical(f"Unhandled exception: {str(e)}", exc_info=True)
        sys.exit(1)
