"""
Profit tracking module for monitoring costs and returns from rent spot operations.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)

class ProfitTracker:
    def __init__(self):
        self.transactions = []
        self.total_costs = Decimal('0')
        self.total_returns = Decimal('0')

    def record_transaction(self, transaction_type: str, amount: float, fee: float,
                         signature: str, timestamp: Optional[datetime] = None) -> None:
        """
        Record a transaction with its associated costs or returns.

        Args:
            transaction_type: Type of transaction ('buy', 'sell', or 'burn')
            amount: Transaction amount in SOL
            fee: Transaction fee in SOL
            signature: Transaction signature
            timestamp: Transaction timestamp (defaults to current time)
        """
        if timestamp is None:
            timestamp = datetime.now()

        transaction = {
            'type': transaction_type,
            'amount': Decimal(str(amount)),
            'fee': Decimal(str(fee)),
            'signature': signature,
            'timestamp': timestamp,
            'transaction_url': f"https://solscan.io/tx/{signature}"
        }

        self.transactions.append(transaction)

        # Update totals
        if transaction_type == 'buy':
            self.total_costs += (transaction['amount'] + transaction['fee'])
        elif transaction_type in ['sell', 'burn']:
            self.total_returns += transaction['amount']
            self.total_costs += transaction['fee']

    def get_profit_summary(self) -> Dict:
        """
        Get a summary of current profit/loss status.

        Returns:
            Dictionary containing profit metrics
        """
        net_profit = self.total_returns - self.total_costs
        total_transactions = len(self.transactions)

        return {
            'total_costs': float(self.total_costs),
            'total_returns': float(self.total_returns),
            'net_profit': float(net_profit),
            'total_transactions': total_transactions,
            'average_cost_per_transaction': float(self.total_costs / total_transactions) if total_transactions > 0 else 0,
            'roi_percentage': float((net_profit / self.total_costs) * 100) if self.total_costs > 0 else 0
        }

    def get_transaction_history(self) -> List[Dict]:
        """
        Get the complete transaction history.

        Returns:
            List of transaction records
        """
        return [{
            'type': tx['type'],
            'amount': float(tx['amount']),
            'fee': float(tx['fee']),
            'signature': tx['signature'],
            'timestamp': tx['timestamp'].isoformat(),
            'transaction_url': tx['transaction_url']
        } for tx in self.transactions]
