import pytest
import asyncio
import logging
from src.batch_burner import BatchBurner

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test wallet credentials
WALLET_PUBLIC_KEY = "4cKqq471gbC78cJm7Nb5tD2kb9DYXKeXTt6o1AqZywqt"
WALLET_PRIVATE_KEY = "3qjxPM7NAeCocJhyupfPKWxDEx9WfXyDwFX5pwLaAC55Nx74sbZtAnHcc1XvmrR8WCCiCeWdygbFno3DxXTyXAup"

@pytest.mark.asyncio
async def test_optimized_fees():
    """Test batch burning with optimized fee settings."""
    burner = BatchBurner(
        wallet_public_key=WALLET_PUBLIC_KEY,
        private_key=WALLET_PRIVATE_KEY,
        min_spots_to_burn=2
    )

    # Add multiple test spots to test batch optimization
    test_spots = [
        {
            "token_mint": "GMEfQZEjF6AbZMB4aQG2QEfH8uSWGMTxTnMsNzfCG6sk",
            "signature": f"test_sig_{i}"
        } for i in range(5)  # Test with max batch size
    ]

    # Add spots and trigger burn
    for spot in test_spots:
        await burner.add_rent_spot(spot)

    # Execute batch burn with optimized fees
    burn_result = await burner.execute_batch_burn()

    # Verify burn was successful
    assert burn_result is not None, "Burn should succeed with optimized fees"
    assert burn_result['spots_burned'] > 0, "Should burn at least one spot"

    # Log transaction details for fee analysis
    logger.info(f"Burn completed with {burn_result['spots_burned']} spots")
    logger.info(f"Transaction URL: {burn_result['transaction_url']}")

if __name__ == "__main__":
    asyncio.run(test_optimized_fees())
