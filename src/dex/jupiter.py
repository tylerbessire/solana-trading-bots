import aiohttp
import json
import os
import base58
from typing import Dict, Optional, List
import asyncio

class JupiterDEX:
    def __init__(self):
        self.SOL_MINT = "So11111111111111111111111111111111111111112"
        self.USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        self.WSOL_MINT = "So11111111111111111111111111111111111111112"
        self.quote_api = "https://quote-api.jup.ag/v6"
        self.swap_api = "https://quote-api.jup.ag/v6"
        self._session = None
        self.LAMPORTS_PER_SOL = 1000000000  # 1 SOL = 1 billion lamports
        self.last_quote = None
        self.last_route = None

    async def ensure_session(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def get_quote(self, input_mint: str, output_mint: str, amount: int) -> Optional[Dict]:
        """Get a quote for swapping tokens"""
        try:
            session = await self.ensure_session()
            from urllib.parse import urlencode

            # Convert amount to lamports (input is already in lamports)
            params = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),  # Amount is already in lamports
                "slippageBps": "50",
                "feeBps": "4",
                "onlyDirectRoutes": "false"
            }

            # Build URL with properly encoded parameters
            url = f"{self.quote_api}/quote?{urlencode(params)}"
            print(f"\nGetting quote from URL: {url}")

            async with session.get(url) as response:
                response_text = await response.text()
                print(f"Quote response: {response_text}")

                if response.status == 200:
                    try:
                        quote = json.loads(response_text)
                        self.last_quote = quote
                        return quote
                    except json.JSONDecodeError:
                        print("Failed to parse quote response as JSON")
                        return None

                print(f"Quote error (Status {response.status})")
                return None

        except Exception as e:
            print(f"Error getting quote: {e}")
            return None

    async def get_best_route(self, input_mint: str, output_mint: str, amount: int) -> Optional[Dict]:
        """Get the best route for a swap"""
        quote = await self.get_quote(input_mint, output_mint, amount)
        if quote and "data" in quote:
            return quote["data"]
        return None

    async def monitor_token_price(self, token_mint: str, base_mint: str = None) -> Optional[float]:
        """Monitor token price in terms of base token (default USDC)"""
        try:
            if base_mint is None:
                base_mint = self.USDC_MINT

            print(f"\nGetting price for token: {token_mint}")
            print(f"Base token: {base_mint}")

            # Use 0.1 SOL for price checking (more accurate quotes)
            amount = int(0.1 * 1_000_000_000)  # 0.1 SOL in lamports
            print(f"Checking price with amount: {amount} lamports")

            quote = await self.get_quote(token_mint, base_mint, amount)
            if quote and "outAmount" in quote:  # Changed from "data" to direct "outAmount"
                out_amount = float(quote["outAmount"]) / 1_000_000  # Convert from USDC decimals
                price = (out_amount * 10)  # Multiply by 10 since we used 0.1 SOL
                print(f"Quote received: {out_amount} USDC for 0.1 SOL")
                print(f"Calculated price: ${price:.2f} per SOL")
                return price
            else:
                print("Failed to get quote from Jupiter API")
                if quote:
                    print(f"Quote response: {json.dumps(quote, indent=2)}")
                return None
        except Exception as e:
            print(f"Error monitoring price: {str(e)}")
            if 'quote' in locals():
                print(f"Last quote response: {json.dumps(quote, indent=2)}")
            return None

    async def execute_swap(self, quote: Dict) -> Optional[Dict]:
        """Execute a swap transaction"""
        try:
            session = await self.ensure_session()

            # Get public key from environment (should be base58 encoded Solana address)
            public_key = os.getenv('PUBLIC_KEY')
            if not public_key:
                print("No public key found in environment")
                return None

            # Create swap data exactly matching Jupiter v6 API format
            swap_data = {
                "route": quote,  # Use full quote response as route
                "userPublicKey": public_key,
                "wrapAndUnwrapSol": True,
                "feeAccount": None,
                "computeUnitPriceMicroLamports": 1,
                "asLegacyTransaction": False,
                "useSharedAccounts": True,
                "dynamicComputeUnitLimit": True,
                "skipUserAccountsCheck": True
            }

            print(f"\nPreparing swap with data: {json.dumps(swap_data, indent=2)}")

            # Get swap transaction
            async with session.post(f"{self.swap_api}/swap", json=swap_data) as response:
                response_text = await response.text()
                print(f"Swap API response: {response_text}")

                if response.status != 200:
                    print(f"\nFailed to get swap transaction. Status: {response.status}")
                    return None

                try:
                    swap_result = json.loads(response_text)
                except json.JSONDecodeError:
                    print("Failed to parse swap response as JSON")
                    return None

                # Sign and submit transaction
                signed_tx = await self._sign_transaction(swap_result['swapTransaction'])
                if not signed_tx:
                    print("Failed to sign transaction")
                    return None

                # Submit signed transaction
                submit_data = {
                    "swapTransaction": signed_tx,
                    "lastValidBlockHeight": swap_result.get('lastValidBlockHeight'),
                    "minimumTargetAmount": None
                }

                async with session.post(f"{self.swap_api}/swap-submit", json=submit_data) as submit_response:
                    submit_text = await submit_response.text()
                    print(f"Submit response: {submit_text}")

                    if submit_response.status != 200:
                        print(f"Failed to submit transaction. Status: {submit_response.status}")
                        return None

                    try:
                        submit_result = json.loads(submit_text)
                        print(f"Transaction submitted: {submit_result}")
                        return submit_result
                    except json.JSONDecodeError:
                        print("Failed to parse submit response as JSON")
                        return None

        except Exception as e:
            print(f"Error executing swap: {e}")
            return None

    async def _sign_transaction(self, transaction_data: str) -> Optional[str]:
        """Sign a transaction with the private key"""
        try:
            import base58
            from solana.transaction import Transaction
            from solana.keypair import Keypair

            # Get private key from environment
            private_key = os.getenv('WALLET_PRIVATE_KEY')
            if not private_key:
                print("No private key found in environment")
                return None

            # Create keypair from private key
            keypair = Keypair.from_secret_key(base58.b58decode(private_key))

            # Decode and deserialize transaction
            transaction = Transaction.deserialize(base58.b58decode(transaction_data))

            # Sign transaction
            transaction.sign([keypair])

            # Return signed transaction
            return base58.b58encode(transaction.serialize()).decode('utf-8')
        except Exception as e:
            print(f"Error signing transaction: {e}")
            return None

    async def close(self):
        """Close the aiohttp session"""
        if self._session:
            await self._session.close()
            self._session = None
