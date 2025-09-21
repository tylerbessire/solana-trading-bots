from datetime import datetime
from typing import Dict, List, Any
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class TradeTracker:
    def __init__(self):
        # Core tracking
        self.active_trades: Dict[str, Dict] = {}
        self.trade_history: List[Dict] = []
        self.performance_data: List[Dict] = []
        self.cumulative_profit = Decimal('0')
        
        # Enhanced tracking
        self.dust_positions: Dict[str, Dict] = {}  # Track remaining 1% positions
        self.token_metrics: Dict[str, Dict] = {}
        self.hourly_stats: List[Dict] = []
        
        # Performance metrics
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.avg_profit_per_trade = Decimal('0')
        self.best_trade_profit = Decimal('0')
        self.worst_trade_profit = Decimal('0')
        
        # Risk metrics
        self.max_drawdown = Decimal('0')
        self.current_drawdown = Decimal('0')
        self.peak_value = Decimal('0')

    def add_trade(self, token_mint: str, price: Decimal, amount: Decimal, 
                 action: str = 'buy', profit: Decimal = None):
        """Record trade with enhanced tracking"""
        try:
            timestamp = datetime.now()

            if action == 'buy':
                # Record buy trade
                self.active_trades[token_mint] = {
                    'token_mint': token_mint,
                    'buy_price': price,
                    'current_price': price,
                    'amount': amount,
                    'timestamp': timestamp,
                    'market_cap_entry': self._calculate_market_cap(price, amount)
                }

                # Initialize token metrics
                if token_mint not in self.token_metrics:
                    self.token_metrics[token_mint] = {
                        'entry_points': [],
                        'exit_points': [],
                        'price_history': [],
                        'volume_history': [],
                        'stats': {
                            'total_trades': 0,
                            'profitable_trades': 0,
                            'total_profit': Decimal('0'),
                            'best_profit': Decimal('0'),
                            'worst_profit': Decimal('0'),
                            'avg_hold_time': Decimal('0')
                        }
                    }

                self.token_metrics[token_mint]['entry_points'].append({
                    'price': price,
                    'amount': amount,
                    'timestamp': timestamp
                })

                logger.info(f"Recorded buy - Token: {token_mint}, Price: {price}, Amount: {amount}")

            elif action == 'sell':
                if token_mint in self.active_trades:
                    trade_data = self.active_trades[token_mint]
                    buy_price = trade_data['buy_price']
                    
                    # Calculate profit if not provided
                    if profit is None:
                        profit = (price - buy_price) * amount
                        
                    self.cumulative_profit += profit
                    self.total_trades += 1

                    # Update performance metrics
                    if profit > Decimal('0'):
                        self.successful_trades += 1
                    self.avg_profit_per_trade = self.cumulative_profit / self.total_trades
                    self.best_trade_profit = max(self.best_trade_profit, profit)
                    self.worst_trade_profit = min(self.worst_trade_profit, profit)

                    # Update peak value and drawdown
                    current_value = self.cumulative_profit
                    if current_value > self.peak_value:
                        self.peak_value = current_value
                    else:
                        drawdown = (self.peak_value - current_value) / self.peak_value
                        self.current_drawdown = drawdown
                        self.max_drawdown = max(self.max_drawdown, drawdown)

                    # Calculate hold time
                    hold_time = (timestamp - trade_data['timestamp']).total_seconds() / 3600
                    
                    # Handle dust position (1% remaining)
                    if isinstance(amount, str) and amount.endswith('%'):
                        sell_percentage = Decimal(amount.rstrip('%')) / 100
                        remaining_amount = trade_data['amount'] * (1 - sell_percentage)
                        
                        if remaining_amount > 0:
                            self.dust_positions[token_mint] = {
                                'amount': remaining_amount,
                                'buy_price': buy_price,
                                'last_price': price,
                                'timestamp': timestamp
                            }
                            logger.info(f"Tracking dust position for {token_mint}: {remaining_amount}")

                    # Update token metrics
                    metrics = self.token_metrics[token_mint]['stats']
                    metrics['total_trades'] += 1
                    metrics['total_profit'] += profit
                    if profit > 0:
                        metrics['profitable_trades'] += 1
                    metrics['best_profit'] = max(metrics['best_profit'], profit)
                    metrics['worst_profit'] = min(metrics['worst_profit'], profit)
                    
                    if metrics['total_trades'] > 0:
                        metrics['avg_hold_time'] = (
                            (metrics['avg_hold_time'] * (metrics['total_trades'] - 1) + hold_time) / 
                            metrics['total_trades']
                        )

                    # Record trade
                    trade_record = {
                        'token_mint': token_mint,
                        'action': action,
                        'price': price,
                        'amount': amount,
                        'profit': profit,
                        'timestamp': timestamp,
                        'entry_price': buy_price,
                        'hold_duration': hold_time,
                        'market_cap_exit': self._calculate_market_cap(price, amount)
                    }

                    self.trade_history.append(trade_record)
                    self.performance_data.append({
                        'timestamp': timestamp,
                        'cumulative_profit': self.cumulative_profit,
                        'drawdown': self.current_drawdown,
                        'trade_count': self.total_trades,
                        'success_rate': self.get_success_rate()
                    })

                    # Remove from active trades if fully sold
                    if not isinstance(amount, str) or amount == "100%":
                        del self.active_trades[token_mint]
                    else:
                        self.active_trades[token_mint]['amount'] *= (1 - Decimal(amount.rstrip('%')) / 100)

                    logger.info(
                        f"Recorded sell - Token: {token_mint}, "
                        f"Price: {price}, Amount: {amount}, Profit: {profit}"
                    )

        except Exception as e:
            logger.error(f"Error recording trade: {str(e)}")

    def update_dust_position(self, token_mint: str, current_price: Decimal):
        """Update and track dust position value"""
        if token_mint in self.dust_positions:
            position = self.dust_positions[token_mint]
            position['last_price'] = current_price
            unrealized_profit = (current_price - position['buy_price']) * position['amount']
            
            logger.info(
                f"Dust position update - Token: {token_mint}, "
                f"Current Price: {current_price}, "
                f"Unrealized Profit: {unrealized_profit}"
            )
            
            return unrealized_profit
        return Decimal('0')

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics"""
        return {
            'total_trades': self.total_trades,
            'successful_trades': self.successful_trades,
            'success_rate': self.get_success_rate(),
            'cumulative_profit': float(self.cumulative_profit),
            'avg_profit_per_trade': float(self.avg_profit_per_trade),
            'best_trade': float(self.best_trade_profit),
            'worst_trade': float(self.worst_trade_profit),
            'max_drawdown': float(self.max_drawdown),
            'current_drawdown': float(self.current_drawdown),
            'active_positions': len(self.active_trades),
            'dust_positions': len(self.dust_positions),
            'unrealized_dust_profit': float(self._calculate_total_dust_profit())
        }

    def get_success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_trades == 0:
            return 0.0
        return (self.successful_trades / self.total_trades) * 100

    def _calculate_market_cap(self, price: Decimal, supply: Decimal) -> Decimal:
        """Calculate market cap in SOL"""
        return price * supply

    def _calculate_total_dust_profit(self) -> Decimal:
        """Calculate total unrealized profit from dust positions"""
        return sum(
            (pos['last_price'] - pos['buy_price']) * pos['amount']
            for pos in self.dust_positions.values()
        )

    def get_trade_history(self) -> List[Dict[str, Any]]:
        """Get formatted trade history"""
        return self.trade_history

    def get_dust_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get current dust positions with metrics"""
        return {
            mint: {
                'amount': float(pos['amount']),
                'buy_price': float(pos['buy_price']),
                'current_price': float(pos['last_price']),
                'unrealized_profit': float((pos['last_price'] - pos['buy_price']) * pos['amount']),
                'hold_time': (datetime.now() - pos['timestamp']).total_seconds() / 3600
            }
            for mint, pos in self.dust_positions.items()
        }
