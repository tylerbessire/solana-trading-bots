import pytest
import logging
from src.batch_burner import BatchBurner

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test wallet credentials
WALLET_PUBLIC_KEY = "4cKqq471gbC78cJm7Nb5tD2kb9DYXKeXTt6o1AqZywqt"
WALLET_PRIVATE_KEY = "3qjxPM7NAeCocJhyupfPKWxDEx9WfXyDwFX5pwLaAC55Nx74sbZtAnHcc1XvmrR8WCCiCeWdygbFno3DxXTyXAup"

@pytest.mark.asyncio
async def test_profit_tracking_integration():
    """Test profit tracking during actual burn operations."""
    burner = BatchBurner(
        wallet_public_key=WALLET_PUBLIC_KEY,
        private_key=WALLET_PRIVATE_KEY,
        min_spots_to_burn=2
    )

    # Add test spots
    test_spots = [
        {
            "token_mint": "GMEfQZEjF6AbZMB4aQG2QEfH8uSWGMTxTnMsNzfCG6sk",
            "signature": f"test_sig_{i}"
        } for i in range(3)
    ]

    # Add spots and execute burn
    for spot in test_spots:
        await burner.add_rent_spot(spot)

    burn_result = await burner.execute_batch_burn()
    assert burn_result is not None, "Burn operation should succeed"

    # Verify profit tracking
    profit_summary = burner.get_profit_summary()
    assert profit_summary['total_transactions'] > 0, "Should have recorded transactions"
    assert profit_summary['total_costs'] > 0, "Should have recorded costs"
    assert 'roi_percentage' in profit_summary, "Should calculate ROI"

    # Verify transaction history
    tx_history = burner.get_transaction_history()
    assert len(tx_history) > 0, "Should have transaction history"
    assert all('transaction_url' in tx for tx in tx_history), "All transactions should have URLs"
    assert all('fee' in tx for tx in tx_history), "All transactions should record fees"

    logger.info(f"Profit Summary: {profit_summary}")
    logger.info(f"Transaction History: {tx_history}")

if __name__ == "__main__":
    pytest.main([__file__])
