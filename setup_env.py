import os
from eth_account import Account
from base58 import b58encode
import json

def setup_solana_environment():
    # Get Ethereum private key
    eth_private_key = os.getenv('WALLET_PRIVATE_KEY')
    if not eth_private_key:
        raise ValueError("WALLET_PRIVATE_KEY not found in environment")

    if not eth_private_key.startswith('0x'):
        eth_private_key = '0x' + eth_private_key

    # Convert to Solana format
    account = Account.from_key(eth_private_key)
    private_key_bytes = account.key
    solana_private_key = b58encode(private_key_bytes).decode()

    # Create .env file with proper Solana credentials
    env_content = f"""
RPC_ENDPOINT=https://api.mainnet-beta.solana.com
PRIVATE_KEY={solana_private_key}
WS_URI=wss://api.mainnet-beta.solana.com
"""

    with open('.env', 'w') as f:
        f.write(env_content.strip())

    print("Environment setup complete")

if __name__ == "__main__":
    setup_solana_environment()
