from solders.keypair import Keypair
import base58

# Generate a new Solana keypair
keypair = Keypair()

# Get the public key and private key in base58 format
public_key = str(keypair.pubkey())
private_key = base58.b58encode(keypair.secret()).decode('utf-8')

print(f"Generated Solana Keys:")
print(f"Public Key: {public_key}")
print(f"Private Key: {private_key}")
