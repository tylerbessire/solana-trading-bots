import asyncio
from typing import Dict, Optional, List
from decimal import Decimal
from dex.jupiter import JupiterDEX

class MomentumStrategy:
    def __init__(self):
        self.jupiter = JupiterDEX()
        self.min_profit_threshold = 0.02  # 2% minimum profit per trade
        self.max_slippage = 0.01  # 1% maximum slippage
        self.initial_capital = 1  # 1 SOL
        self.profit_target_usd = 1000  # $1000 target
        self.stop_loss_percentage = 0.015  # 1.5% stop loss per trade
        self.position_size_percentage = 0.5  # Use 50% of capital per trade

        # Focus on most liquid tokens first
        self.target_tokens = [
            "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",  # mSOL (highest quote success)
            "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj",  # stSOL
            "7i5KKsX2weiTkry7jA4ZwSuXGhs5eJBEjY8vVxR4pfRx",  # ORCA
            "DezXAZ8z7PnrnRJjA4ZwSuXGhs5eJBEjY8vVxR4pfRx",  # BONK
        ]

        self.price_history = {}  # Store recent price history
        self.active_positions = {}  # Track current positions

    async def monitor_token_momentum(self, token_mint: str) -> Optional[Dict]:
        """Monitor token price momentum and volume"""
        try:
            # Get current price
            current_price = await self.jupiter.monitor_token_price(token_mint)
            if not current_price:
                return None

            # Store price history
            if token_mint not in self.price_history:
                self.price_history[token_mint] = []

            self.price_history[token_mint].append(current_price)

            # Keep last 3 price points
            if len(self.price_history[token_mint]) > 3:
                self.price_history[token_mint].pop(0)

            # Need at least 2 price points for momentum calculation
            if len(self.price_history[token_mint]) < 2:
                return None

            # Calculate momentum indicators
            prices = self.price_history[token_mint]
            price_change = (prices[-1] - prices[0]) / prices[0]
            momentum = sum([1 if prices[i] < prices[i+1] else -1
                          for i in range(len(prices)-1)])

            return {
                'token': token_mint,
                'current_price': current_price,
                'price_change': price_change,
                'momentum': momentum
            }

        except Exception as e:
            print(f"Error monitoring momentum for {token_mint}: {e}")
            return None

    async def find_opportunity(self) -> Optional[Dict]:
        """Find the best trading opportunity based on momentum"""
        try:
            print("\nAnalyzing market momentum...")

            # Get SOL price for calculations
            sol_price = await self.jupiter.monitor_token_price(self.jupiter.SOL_MINT)
            if not sol_price:
                print("Error: Failed to get SOL price")
                return None

            print(f"Current SOL price: ${sol_price:.2f}")

            best_opportunity = None
            highest_momentum = -float('inf')

            for token in self.target_tokens:
                momentum_data = await self.monitor_token_momentum(token)
                if not momentum_data:
                    continue

                # Strong upward momentum and price increase
                if (momentum_data['momentum'] > 1 and
                    momentum_data['price_change'] > self.min_profit_threshold):

                    if momentum_data['momentum'] > highest_momentum:
                        highest_momentum = momentum_data['momentum']
                        best_opportunity = {
                            'input_token': self.jupiter.SOL_MINT,
                            'output_token': token,
                            'amount': self.initial_capital * self.position_size_percentage,
                            'expected_profit': momentum_data['price_change'] * 100,
                            'momentum_score': momentum_data['momentum'],
                            'current_price': momentum_data['current_price']
                        }

            if best_opportunity:
                print(f"\nFound momentum opportunity!")
                print(f"Token: {best_opportunity['output_token']}")
                print(f"Momentum score: {best_opportunity['momentum_score']}")
                print(f"Expected profit potential: {best_opportunity['expected_profit']:.2f}%")

            return best_opportunity

        except Exception as e:
            print(f"Error finding opportunities: {e}")
            return None

    async def execute_trade(self, opportunity: Dict) -> bool:
        """Execute a trade based on the identified opportunity"""
        try:
            amount_in = int(opportunity['amount'] * 1e9)  # Convert to lamports

            # Get quote for the trade
            quote = await self.jupiter.get_quote(
                opportunity['input_token'],
                opportunity['output_token'],
                amount_in
            )

            if not quote:
                print("Failed to get quote for trade")
                return False

            # Set stop loss and take profit levels
            entry_price = opportunity['current_price']
            stop_loss = entry_price * (1 - self.stop_loss_percentage)
            take_profit = entry_price * (1 + self.min_profit_threshold)

            # Store position details
            self.active_positions[opportunity['output_token']] = {
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'amount': int(quote['outAmount']),
                'token': opportunity['output_token']
            }

            print(f"\nTrade executed:")
            print(f"Entry price: ${entry_price:.4f}")
            print(f"Stop loss: ${stop_loss:.4f}")
            print(f"Take profit: ${take_profit:.4f}")

            return True

        except Exception as e:
            print(f"Error executing trade: {e}")
            return False

    async def monitor_positions(self):
        """Monitor active positions for exit conditions"""
        while self.active_positions:
            for token, position in list(self.active_positions.items()):
                try:
                    current_price = await self.jupiter.monitor_token_price(token)
                    if not current_price:
                        continue

                    # Check stop loss and take profit conditions
                    if (current_price <= position['stop_loss'] or
                        current_price >= position['take_profit']):

                        # Execute exit trade
                        quote = await self.jupiter.get_quote(
                            token,
                            self.jupiter.SOL_MINT,
                            position['amount']
                        )

                        if quote:
                            profit_loss = (current_price - position['entry_price']) / position['entry_price']
                            print(f"\nPosition closed:")
                            print(f"Token: {token}")
                            print(f"Profit/Loss: {profit_loss*100:.2f}%")
                            del self.active_positions[token]

                except Exception as e:
                    print(f"Error monitoring position for {token}: {e}")

            await asyncio.sleep(1)  # Rate limiting

    async def close(self):
        """Cleanup resources"""
        await self.jupiter.close()
