import pytest
from datetime import datetime
from decimal import Decimal
from src.profit_tracker import ProfitTracker

def test_profit_tracking():
    """Test profit tracking functionality."""
    tracker = ProfitTracker()

    # Test transaction recording
    test_transactions = [
        {
            'type': 'buy',
            'amount': 0.0001,
            'fee': 0.000005,
            'signature': 'test_sig_1',
            'timestamp': datetime.now()
        },
        {
            'type': 'buy',
            'amount': 0.0001,
            'fee': 0.000005,
            'signature': 'test_sig_2',
            'timestamp': datetime.now()
        },
        {
            'type': 'sell',
            'amount': 0.00025,
            'fee': 0.000005,
            'signature': 'test_sig_3',
            'timestamp': datetime.now()
        }
    ]

    # Record test transactions
    for tx in test_transactions:
        tracker.record_transaction(
            transaction_type=tx['type'],
            amount=tx['amount'],
            fee=tx['fee'],
            signature=tx['signature'],
            timestamp=tx['timestamp']
        )

    # Test profit summary
    summary = tracker.get_profit_summary()
    assert summary['total_transactions'] == 3, "Should have recorded 3 transactions"

    expected_costs = 0.0001 * 2 + 0.000005 * 3  # Two buys + three fees
    assert abs(summary['total_costs'] - expected_costs) < 1e-8, "Costs calculated incorrectly"

    expected_returns = 0.00025  # One sell
    assert abs(summary['total_returns'] - expected_returns) < 1e-8, "Returns calculated incorrectly"

    expected_profit = expected_returns - expected_costs
    assert abs(summary['net_profit'] - expected_profit) < 1e-8, "Net profit calculated incorrectly"

    # Test transaction history
    history = tracker.get_transaction_history()
    assert len(history) == 3, "Should have 3 transactions in history"
    assert all('transaction_url' in tx for tx in history), "All transactions should have URLs"
    assert all('timestamp' in tx for tx in history), "All transactions should have timestamps"

def test_edge_cases():
    """Test edge cases in profit tracking."""
    tracker = ProfitTracker()

    # Test empty tracker
    summary = tracker.get_profit_summary()
    assert summary['total_transactions'] == 0, "Should have no transactions"
    assert summary['total_costs'] == 0, "Should have no costs"
    assert summary['total_returns'] == 0, "Should have no returns"
    assert summary['roi_percentage'] == 0, "ROI should be 0 with no transactions"

    # Test with zero amount transaction
    tracker.record_transaction('buy', 0, 0, 'test_sig_zero')
    summary = tracker.get_profit_summary()
    assert summary['total_transactions'] == 1, "Should record zero amount transaction"
    assert summary['total_costs'] == 0, "Zero amount should not affect costs"

if __name__ == '__main__':
    pytest.main([__file__])
