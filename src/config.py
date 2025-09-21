from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    PRIVATE_KEY = os.getenv('PRIVATE_KEY')
    PUBLIC_KEY = os.getenv('PUBLIC_KEY')
    RPC_ENDPOINT = os.getenv('RPC_ENDPOINT')

    # Trading parameters
    MIN_TRADE_SIZE = 0.05  # SOL
    MAX_TRADE_SIZE = 1.0   # SOL
    PROFIT_TARGET = 1000   # USD
    MAX_SLIPPAGE = 0.01    # 1%

    # Risk management
    STOP_LOSS_PERCENTAGE = 0.02  # 2%
    TAKE_PROFIT_PERCENTAGE = 0.05  # 5%

    # Time constraints
    MAX_TRADE_DURATION = 3600  # 1 hour in seconds
    TRADE_TIMEOUT = 30  # 30 seconds for order execution
