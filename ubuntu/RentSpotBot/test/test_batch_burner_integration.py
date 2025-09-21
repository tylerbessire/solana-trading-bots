"""
Integration test for BatchBurner with pump.fun API.
"""
import asyncio
import pytest
import os
from datetime import datetime
from src.batch_burner import BatchBurner

# Wallet credentials
WALLET_PUBLIC_KEY = "4cKqq471gbC78cJm7Nb5tD2kb9DYXKeXTt6o1AqZywqt"
WALLET_PRIVATE_KEY = "3qjxPM7NAeCocJhyupfPKWxDEx9WfXyDwFX5pwLaAC55Nx74sbZtAnHcc1XvmrR8WCCiCeWdygbFno3DxXTyXAup"

@pytest.mark.asyncio
async def test_real_burn_integration():
    """Test actual burn functionality with pump.fun API."""
    burner = BatchBurner(
        wallet_public_key=WALLET_PUBLIC_KEY,
        private_key=WALLET_PRIVATE_KEY,
        min_spots_to_burn=2
    )

    # Add test spots (using real token from previous tests)
    test_spots = [
        {
            "token_mint": "GMEfQZEjF6AbZMB4aQG2QEfH8uSWGMTxTnMsNzfCG6sk",
            "signature": "test_sig_1"
        },
        {
            "token_mint": "GMEfQZEjF6AbZMB4aQG2QEfH8uSWGMTxTnMsNzfCG6sk",
            "signature": "test_sig_2"
        }
    ]

    # Add spots and trigger burn
    for spot in test_spots:
        await burner.add_rent_spot(spot)

    # Verify burn history
    burn_history = burner.get_burn_history()
    assert len(burn_history) == 1, "Should have one burn record"
    assert burn_history[0]['spots_burned'] == 2, "Should have burned 2 spots"
    assert 'signature' in burn_history[0], "Should have transaction signature"
    assert 'transaction_url' in burn_history[0], "Should have transaction URL"

if __name__ == "__main__":
    asyncio.run(pytest.main([__file__]))
