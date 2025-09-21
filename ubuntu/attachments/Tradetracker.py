from datetime import datetime


class TradeTracker:

    def __init__(self):
        self.active_trades = {}
        self.trade_history = []
        self.performance_data = []
        self.cumulative_profit = 0.0
        self.trade_details = {}
        self.daily_returns = []

    def add_trade(self, token_mint, price, amount, action='buy'):
        timestamp = datetime.now()

        if action == 'buy':
            self.active_trades[token_mint] = {
                'token_mint': token_mint,
                'buy_price': price,
                'current_price': price,
                'amount': amount,
                'timestamp': timestamp
            }

            if token_mint not in self.trade_details:
                self.trade_details[token_mint] = {
                    'entry_points': [],
                    'exit_points': [],
                    'price_history': [],
                    'token_stats': {
                        'total_trades': 0,
                        'profitable_trades': 0,
                        'total_profit': 0.0,
                        'max_profit': 0.0,
                        'max_loss': 0.0,
                        'avg_hold_time': 0.0
                    }
                }

            self.trade_details[token_mint]['entry_points'].append({
                'price':
                price,
                'amount':
                amount,
                'timestamp':
                timestamp
            })

        elif action == 'sell':
            if token_mint in self.active_trades:
                buy_price = self.active_trades[token_mint]['buy_price']
                profit = (price - buy_price) * amount
                self.cumulative_profit += profit

                stats = self.trade_details[token_mint]['token_stats']
                stats['total_trades'] += 1
                stats['total_profit'] += profit
                if profit > 0:
                    stats['profitable_trades'] += 1
                stats['max_profit'] = max(stats['max_profit'], profit)
                stats['max_loss'] = min(stats['max_loss'], profit)

                hold_time = (timestamp -
                             self.active_trades[token_mint]['timestamp']
                             ).total_seconds() / 3600
                stats['avg_hold_time'] = (stats['avg_hold_time'] *
                                          (stats['total_trades'] - 1) +
                                          hold_time) / stats['total_trades']

                self.trade_details[token_mint]['exit_points'].append({
                    'price':
                    price,
                    'amount':
                    amount,
                    'profit':
                    profit,
                    'timestamp':
                    timestamp,
                    'hold_time':
                    hold_time
                })

                daily_return = (profit / (buy_price * amount)) * 100
                self.daily_returns.append(daily_return)

                trade_record = {
                    'token_mint': token_mint,
                    'action': action,
                    'price': price,
                    'amount': amount,
                    'profit': profit,
                    'timestamp': timestamp,
                    'entry_price': buy_price,
                    'hold_duration': hold_time,
                    'return_percentage': daily_return
                }

                self.trade_history.append(trade_record)
                self.performance_data.append({
                    'timestamp': timestamp,
                    'cumulative_profit': self.cumulative_profit,
                    'daily_return': daily_return
                })

                if amount >= self.active_trades[token_mint]['amount']:
                    del self.active_trades[token_mint]
                else:
                    self.active_trades[token_mint]['amount'] -= amount

    def get_completed_trades_count(self):
        """Return the number of completed trades in the trade history."""
        return len(self.trade_history)

    # Additional methods for getting trade stats
