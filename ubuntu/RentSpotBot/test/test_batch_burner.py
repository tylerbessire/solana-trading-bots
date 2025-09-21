"""
Test suite for the BatchBurner module.
"""
import asyncio
import pytest
from datetime import datetime
from src.batch_burner import BatchBurner

@pytest.mark.asyncio
async def test_spot_accumulation():
    """Test adding rent spots and tracking pending spots."""
    burner = BatchBurner("test_wallet", min_spots_to_burn=5)

    # Add test spots
    test_spots = [
        {"token_mint": f"test_token_{i}", "signature": f"sig_{i}"}
        for i in range(3)
    ]

    for spot in test_spots:
        await burner.add_rent_spot(spot)

    assert burner.get_pending_spots_count() == 3, "Should have 3 pending spots"
    assert len(burner.get_burn_history()) == 0, "Should have no burn history yet"

@pytest.mark.asyncio
async def test_batch_burn_trigger():
    """Test batch burn triggering when minimum spots reached."""
    burner = BatchBurner("test_wallet", min_spots_to_burn=3)

    # Add spots to trigger burn
    test_spots = [
        {"token_mint": f"test_token_{i}", "signature": f"sig_{i}"}
        for i in range(4)
    ]

    for spot in test_spots:
        await burner.add_rent_spot(spot)

    assert burner.get_pending_spots_count() == 1, "Should have 1 pending spot after burn"
    assert len(burner.get_burn_history()) == 1, "Should have one burn record"

    burn_history = burner.get_burn_history()
    assert burn_history[0]['spots_burned'] == 3, "Should have burned 3 spots"

@pytest.mark.asyncio
async def test_multiple_burns():
    """Test multiple batch burns with spot accumulation."""
    burner = BatchBurner("test_wallet", min_spots_to_burn=2)

    # First batch
    for i in range(3):
        await burner.add_rent_spot({
            "token_mint": f"token_batch1_{i}",
            "signature": f"sig_batch1_{i}"
        })

    assert len(burner.get_burn_history()) == 1, "Should have one burn after first batch"

    # Second batch
    for i in range(2):
        await burner.add_rent_spot({
            "token_mint": f"token_batch2_{i}",
            "signature": f"sig_batch2_{i}"
        })

    assert len(burner.get_burn_history()) == 2, "Should have two burns after second batch"
    assert burner.get_pending_spots_count() == 1, "Should have 1 pending spot"

if __name__ == "__main__":
    asyncio.run(pytest.main([__file__]))
