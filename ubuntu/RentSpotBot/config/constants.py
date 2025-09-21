"""
Configuration constants for the RentSpotBot.
"""

# WebSocket Configuration
WS_URI = "wss://pumpportal.fun/api/data"
TRADE_URL = "https://pumpportal.fun/api/trade-local"

# Solana Configuration
RPC_ENDPOINT = "https://api.mainnet-beta.solana.com/"
PUBLIC_KEY = "Ewid3FwjW4eFSBhQHr9SHyZnV5aePYVgjsphvtXcfvmv"

# Trade Parameters
MAX_TRADE_AMOUNT = 0.0001  # Amount in SOL for each trade
PRIORITY_FEE = 0.00001     # Priority fee for transactions
BRIBERY_FEE = 0.00001      # Bribery fee for transactions
MAX_TOKENS_HELD = 5        # Maximum number of tokens to hold at once
SNIPING_ACTIVITY_THRESHOLD = 10  # Number of trades that indicate sniping
TOP_HOLDERS_THRESHOLD = 80  # Percentage threshold for top holder concentration

# Rent Spot Parameters
BATCH_BURN_INTERVAL = 3600  # Time in seconds between batch burns (1 hour)
MIN_RENT_SPOTS_FOR_BURN = 5  # Minimum number of rent spots to trigger a batch burn
MAX_RENT_SPOTS_PER_BURN = 20  # Maximum number of rent spots to burn in one batch
