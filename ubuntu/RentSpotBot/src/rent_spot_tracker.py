"""
RentSpotTracker module for managing rent spots and batch burning operations.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Set
from config.constants import (
    BATCH_BURN_INTERVAL,
    MIN_RENT_SPOTS_FOR_BURN,
    MAX_RENT_SPOTS_PER_BURN,
    PUBLIC_KEY,
    RPC_ENDPOINT
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('rent_spots.log')]
)
logger = logging.getLogger(__name__)

class RentSpotTracker:
    def __init__(self):
        self.rent_spots: Dict[str, dict] = {}  # token_mint -> rent spot details
        self.pending_burns: Set[str] = set()  # token_mints pending burn
        self.burn_history: List[dict] = []  # history of batch burns
        self.last_burn_time = datetime.now()
        self.burn_lock = asyncio.Lock()

    async def add_rent_spot(self, token_mint: str, trade_details: dict) -> bool:
        """
        Add a new rent spot after a successful buy-sell sequence.
        """
        try:
            if token_mint not in self.rent_spots:
                self.rent_spots[token_mint] = {
                    'creation_time': datetime.now(),
                    'trade_details': trade_details,
                    'status': 'active'
                }
                logger.info(f"New rent spot created for token: {token_mint}")
                await self._check_batch_burn()
                return True
            return False
        except Exception as e:
            logger.error(f"Error adding rent spot for {token_mint}: {e}")
            return False

    async def _check_batch_burn(self) -> None:
        """
        Check if conditions are met for a batch burn operation.
        """
        async with self.burn_lock:
            current_time = datetime.now()
            time_since_last_burn = (current_time - self.last_burn_time).total_seconds()
            active_spots = [mint for mint, spot in self.rent_spots.items()
                          if spot['status'] == 'active' and mint not in self.pending_burns]

            if (len(active_spots) >= MIN_RENT_SPOTS_FOR_BURN and
                time_since_last_burn >= BATCH_BURN_INTERVAL):
                spots_to_burn = active_spots[:MAX_RENT_SPOTS_PER_BURN]
                await self._execute_batch_burn(spots_to_burn)

    async def _execute_batch_burn(self, spots_to_burn: List[str]) -> None:
        """
        Execute a batch burn operation for the specified rent spots.
        """
        try:
            logger.info(f"Initiating batch burn for {len(spots_to_burn)} spots")
            # Mark spots as pending
            for mint in spots_to_burn:
                self.pending_burns.add(mint)

            # TODO: Implement Solana transaction for batch burning
            # This will be implemented when we add Solana SDK integration

            # Record successful burn
            burn_record = {
                'timestamp': datetime.now(),
                'spots_burned': spots_to_burn,
                'status': 'completed'
            }
            self.burn_history.append(burn_record)
            self.last_burn_time = datetime.now()

            # Update spot statuses
            for mint in spots_to_burn:
                self.rent_spots[mint]['status'] = 'burned'
                self.pending_burns.remove(mint)

            logger.info(f"Successfully completed batch burn of {len(spots_to_burn)} spots")
        except Exception as e:
            logger.error(f"Error during batch burn: {e}")
            # Reset pending status on failure
            for mint in spots_to_burn:
                self.pending_burns.discard(mint)

    def get_active_spots_count(self) -> int:
        """Return the number of active rent spots."""
        return len([spot for spot in self.rent_spots.values() if spot['status'] == 'active'])

    def get_burn_history(self) -> List[dict]:
        """Return the history of batch burns."""
        return self.burn_history

    def get_spot_details(self, token_mint: str) -> dict:
        """Get details for a specific rent spot."""
        return self.rent_spots.get(token_mint, {})
