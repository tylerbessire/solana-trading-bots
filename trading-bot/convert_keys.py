import hashlib
from eth_keys import keys
import base58

def eth_to_solana_keypair(eth_private_key: str):
    # Remove '0x' prefix if present
    private_key = eth_private_key.replace('0x', '')

    # Convert private key to bytes
    private_key_bytes = bytes.fromhex(private_key)

    # Hash the private key to get a consistent 32-byte seed
    seed = hashlib.sha256(private_key_bytes).digest()[:32]

    # Convert to base58 for Solana format
    solana_private_key = base58.b58encode(seed).decode('utf-8')

    return solana_private_key

if __name__ == "__main__":
    eth_private = "[REDACTED SECRET]"

    solana_priv = eth_to_solana_keypair(eth_private)
    print(f"Solana Private Key (32 bytes, base58): {solana_priv}")
