"""
Wallet configuration for RentSpotBot
"""
import base58
from typing import List

def _validate_private_key(key: str) -> List[int]:
    """Validate and convert private key to bytes"""
    try:
        # Remove any whitespace and validate length
        key = key.strip()
        if len(key) != 88:  # Standard Solana private key length
            raise ValueError("Invalid private key length")

        # Decode and validate
        decoded = base58.b58decode(key)
        if len(decoded) != 64:  # Expected byte length
            raise ValueError("Invalid decoded key length")

        return list(decoded)
    except Exception as e:
        raise ValueError(f"Invalid private key format: {str(e)}")

# Wallet configuration
WALLET_PUBLIC_KEY = "4cKqq471gbC78cJm7Nb5tD2kb9DYXKeXTt6o1AqZywqt"
_PRIVATE_KEY = "3qjxPM7NAeCocJhyupfPKWxDEx9WfXyDwFX5pwLaAC55Nx74sbZtAnHcc1XvmrR8WCCiCeWdygbFno3DxXTyXAup"
WALLET_PRIVATE_KEY_BYTES = _validate_private_key(_PRIVATE_KEY)

# Trade parameters (as numeric values)
MAX_TRADE_AMOUNT = 0.0001  # Amount in SOL
PRIORITY_FEE = 0.00001     # Priority fee in SOL
BRIBERY_FEE = 0.00001      # Bribery fee in SOL
SLIPPAGE = 1000            # 10% slippage (as integer)

# RPC configuration
RPC_ENDPOINT = "https://api.mainnet-beta.solana.com/"
