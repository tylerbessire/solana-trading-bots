"""
Batch burner module for handling rent spot burning operations.
"""
import asyncio
import logging
import aiohttp
import json
from datetime import datetime
from typing import List, Dict, Optional
from solders.transaction import VersionedTransaction
from solders.keypair import Keypair
from solders.commitment_config import CommitmentLevel
import base58
from .profit_tracker import ProfitTracker

logger = logging.getLogger(__name__)

class BatchBurner:
    def __init__(self, wallet_public_key: str, private_key: str, min_spots_to_burn: int = 5):
        """
        Initialize the BatchBurner.

        Args:
            wallet_public_key: Public key of the wallet
            private_key: Private key for transaction signing
            min_spots_to_burn: Minimum number of rent spots required to trigger a burn
        """
        self.wallet_public_key = wallet_public_key
        self.private_key = private_key
        self.min_spots_to_burn = min_spots_to_burn
        self.pending_spots: List[Dict] = []
        self.burn_history: List[Dict] = []
        self.profit_tracker = ProfitTracker()

    def get_profit_summary(self) -> Dict:
        return self.profit_tracker.get_profit_summary()

    def get_transaction_history(self) -> List[Dict]:
        return self.profit_tracker.get_transaction_history()

    async def add_rent_spot(self, spot_data: Dict) -> None:
        """
        Add a new rent spot to the pending list.

        Args:
            spot_data: Dictionary containing rent spot information
        """
        self.pending_spots.append({
            'token_mint': spot_data['token_mint'],
            'created_at': datetime.now().isoformat(),
            'transaction_signature': spot_data.get('signature'),
        })

        logger.info(f"Added rent spot for token {spot_data['token_mint']}. Total pending spots: {len(self.pending_spots)}")

        if len(self.pending_spots) >= self.min_spots_to_burn:
            await self.execute_batch_burn()

    async def execute_batch_burn(self) -> Optional[Dict]:
        """
        Execute a batch burn operation for accumulated rent spots.

        Returns:
            Dictionary containing burn transaction details if successful
        """
        if not self.pending_spots:
            logger.info("No pending spots to burn")
            return None

        try:
            # Calculate optimal batch size and fees based on current pending spots
            batch_size = min(len(self.pending_spots), 5)  # Max 5 spots per batch for optimal gas usage
            base_priority_fee = 0.000005  # Reduced from 0.00001 to minimize costs

            # Adjust priority fee based on batch size
            priority_fee = "{:.9f}".format(base_priority_fee / batch_size)  # Further reduce fee per spot in batch

            logger.info(f"Initiating batch burn for {batch_size} spots with priority fee {priority_fee}")
            successful_burns = []

            # Process each spot individually
            for spot in self.pending_spots:
                # Prepare sell transaction data
                sell_data = {
                    'publicKey': self.wallet_public_key,
                    'action': 'sell',
                    'mint': spot['token_mint'],
                    'amount': '100%',  # Sell all tokens
                    'denominatedInSol': 'false',  # Amount is in tokens
                    'slippage': 1,  # 1% slippage tolerance
                    'priorityFee': priority_fee,
                    'pool': 'pump'
                }

                logger.info(f"Requesting sell transaction for token {spot['token_mint']}")

                # Get serialized transaction from pump.fun API
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        'https://pumpportal.fun/api/trade-local',
                        json=sell_data,
                        headers={'Content-Type': 'application/json'}
                    ) as response:
                        # Log request details
                        logger.info(f"Sending request to API with data: {sell_data}")

                        content_type = response.headers.get('content-type', '')
                        logger.info(f"Response content type: {content_type}")
                        logger.info(f"Response headers: {dict(response.headers)}")

                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"Failed to get sell transaction for {spot['token_mint']}: {response.status} {error_text}")
                            continue

                        # Try to read raw bytes first
                        raw_response = await response.read()
                        logger.info(f"Raw response length: {len(raw_response)}")
                        logger.info(f"First 100 bytes of response: {raw_response[:100]}")

                        try:
                            # Try to decode as JSON first
                            response_text = raw_response.decode('utf-8')
                            response_data = json.loads(response_text)
                            logger.info(f"Successfully parsed JSON response: {response_data}")

                            if not isinstance(response_data, dict) or 'transaction' not in response_data:
                                logger.error(f"Invalid response format from API: {response_data}")
                                continue

                            tx_bytes = base58.b58decode(response_data['transaction'])
                        except (UnicodeDecodeError, json.JSONDecodeError) as e:
                            # If not JSON, treat as raw transaction bytes
                            logger.info(f"Response is not JSON, treating as raw transaction bytes: {str(e)}")
                            tx_bytes = raw_response

                # Create keypair from private key
                keypair = Keypair.from_base58_string(self.private_key)

                # Create and sign transaction
                tx = VersionedTransaction(VersionedTransaction.from_bytes(tx_bytes).message, [keypair])

                # Send transaction to Solana
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        'https://api.mainnet-beta.solana.com',
                        headers={'Content-Type': 'application/json'},
                        json={
                            'jsonrpc': '2.0',
                            'id': 1,
                            'method': 'sendTransaction',
                            'params': [
                                base58.b58encode(bytes(tx)).decode('ascii'),
                                {'encoding': 'base58', 'preflightCommitment': 'confirmed'}
                            ]
                        }
                    ) as response:
                        if response.status != 200:
                            response_text = await response.text()
                            logger.error(f"Failed to send sell transaction for {spot['token_mint']}: {response.status} {response_text}")
                            continue

                        result = await response.json()
                        tx_signature = result.get('result')

                        if not tx_signature:
                            logger.error(f"No transaction signature in response for {spot['token_mint']}: {result}")
                            continue

                        # Calculate actual amount from percentage
                        amount = 0.0001  # Default amount for rent spot transactions

                        # Record the transaction in profit tracker
                        self.profit_tracker.record_transaction(
                            transaction_type='sell',
                            amount=amount,  # Use fixed amount instead of percentage
                            fee=float(priority_fee),
                            signature=tx_signature
                        )

                        successful_burns.append({
                            'token_mint': spot['token_mint'],
                            'signature': tx_signature
                        })
                        logger.info(f"Successfully sold token {spot['token_mint']}. Transaction: https://solscan.io/tx/{tx_signature}")

            if successful_burns:
                # Record successful batch burn
                burn_record = {
                    'timestamp': datetime.now().isoformat(),
                    'spots_burned': len(successful_burns),
                    'spots': successful_burns,
                    'signature': successful_burns[0]['signature'],  # Use first signature as main record
                    'transaction_url': f"https://solscan.io/tx/{successful_burns[0]['signature']}"  # Single URL for the batch
                }

                self.burn_history.append(burn_record)
                self.pending_spots.clear()

                logger.info(f"Batch burn completed successfully. {len(successful_burns)} spots processed.")
                return burn_record
            else:
                logger.error("No spots were successfully burned in this batch")
                return None

        except Exception as e:
            logger.error(f"Error during batch burn: {e}")
            return None

    def get_pending_spots_count(self) -> int:
        """
        Get the number of pending spots waiting to be burned.
        """
        return len(self.pending_spots)

    def get_burn_history(self) -> List[Dict]:
        """
        Get the history of successful burns.
        """
        return self.burn_history
