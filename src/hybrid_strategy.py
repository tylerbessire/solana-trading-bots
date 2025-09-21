import asyncio
from typing import Dict, Optional, List
from decimal import Decimal
from dex.jupiter import JupiterDEX

class HybridStrategy:
    def __init__(self):
        self.jupiter = JupiterDEX()
        self.min_profit_threshold = 0.0005
        self.max_slippage = 0.0005
        self.initial_capital = 1
        self.profit_target_usd = 1000
        self.stop_loss_percentage = 0.0005
        self.position_size_percentage = 0.5
        self.price_history = {}
        self.market_making_orders = {}
        self.active_positions = {}

        # Focus only on the most liquid pairs
        self.trading_pairs = [
            {
                "token": "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",
                "name": "mSOL",
                "min_price_change": 0.0001,
                "spread_multiplier": 1.1
            },
            {
                "token": "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj",
                "name": "stSOL",
                "min_price_change": 0.0001,
                "spread_multiplier": 1.1
            }
        ]

    async def monitor_price_action(self, token_data: Dict) -> Optional[Dict]:
        """Monitor price action for trading signals"""
        try:
            token = token_data['token']
            token_name = token_data['name']

            # Get current market price
            current_price = await self.jupiter.monitor_token_price(token)
            if not current_price:
                return None

            # Calculate market-based spread
            # Use tighter spreads for more liquid tokens
            base_spread = self.min_profit_threshold
            if token_name in ['mSOL', 'stSOL']:
                base_spread *= 0.8  # 20% tighter spreads for liquid tokens

            # Calculate bid/ask prices with dynamic spread
            bid_price = current_price * (1 - base_spread)
            ask_price = current_price * (1 + base_spread)

            # Calculate expected profit per trade
            expected_profit = (ask_price - bid_price) / bid_price
            spread = (ask_price - bid_price) / current_price

            # Store price history for trend analysis
            if token not in self.price_history:
                self.price_history[token] = []
            self.price_history[token].append(current_price)

            # Keep only recent price points
            if len(self.price_history[token]) > 10:
                self.price_history[token].pop(0)

            # Calculate price momentum
            price_momentum = 0
            if len(self.price_history[token]) >= 2:
                price_momentum = (self.price_history[token][-1] - self.price_history[token][0]) / self.price_history[token][0]

            # Adjust spread based on momentum
            if abs(price_momentum) > 0.001:  # 0.1% price movement
                if price_momentum > 0:
                    ask_price *= 1.001  # Increase ask price in uptrend
                else:
                    bid_price *= 0.999  # Decrease bid price in downtrend

            return {
                'token': token,
                'name': token_name,
                'current_price': current_price,
                'bid_price': bid_price,
                'ask_price': ask_price,
                'expected_profit': expected_profit,
                'spread': spread,
                'momentum': price_momentum
            }

        except Exception as e:
            print(f"Error monitoring price action: {e}")
            return None

    async def find_opportunity(self) -> Optional[Dict]:
        """Find the best trading opportunity using multiple strategies"""
        try:
            print("\nAnalyzing market conditions...")

            # Get SOL price for calculations
            sol_price = await self.jupiter.monitor_token_price(self.jupiter.SOL_MINT)
            if not sol_price:
                print("Error: Failed to get SOL price")
                return None

            print(f"Current SOL price: ${sol_price:.2f}")

            # Always try to create market making opportunities
            for pair in self.trading_pairs:
                price_data = await self.monitor_price_action(pair)
                if not price_data:
                    continue

                print(f"\nAnalyzing {pair['name']}:")
                print(f"Price: ${price_data['current_price']:.4f}")
                print(f"Expected profit per trade: {price_data['expected_profit']*100:.3f}%")
                print(f"Spread: {price_data['spread']*100:.3f}%")
                print(f"Momentum: {price_data['momentum']*100:.3f}%")

                # Calculate potential daily profit based on current spread
                trades_per_hour = 30  # Aggressive estimate
                daily_trades = trades_per_hour * 24
                potential_daily_profit = daily_trades * price_data['expected_profit'] * self.position_size_percentage

                print(f"Potential daily profit: {potential_daily_profit*100:.2f}% (with {daily_trades} trades)")

                # Consider any liquid pair with positive expected profit as an opportunity
                if price_data['expected_profit'] > 0:
                    opportunity = {
                        'input_token': self.jupiter.SOL_MINT,
                        'output_token': price_data['token'],
                        'token_name': price_data['name'],
                        'amount': self.initial_capital * self.position_size_percentage,
                        'current_price': price_data['current_price'],
                        'bid_price': price_data['bid_price'],
                        'ask_price': price_data['ask_price'],
                        'expected_profit': price_data['expected_profit'],
                        'momentum': price_data['momentum'],
                        'strategy': 'continuous_market_making'
                    }

                    print(f"\nFound opportunity with {opportunity['token_name']}:")
                    print(f"Current price: ${opportunity['current_price']:.4f}")
                    print(f"Bid: ${opportunity['bid_price']:.4f}")
                    print(f"Ask: ${opportunity['ask_price']:.4f}")
                    print(f"Expected profit per trade: {opportunity['expected_profit']*100:.3f}%")
                    print(f"Price momentum: {opportunity['momentum']*100:.3f}%")

                    return opportunity

            print("\nNo viable trading opportunities found")
            return None

        except Exception as e:
            print(f"Error finding opportunities: {e}")
            return None

    async def execute_trade(self, opportunity: Dict) -> bool:
        """Execute continuous market making strategy"""
        try:
            amount_in = int(opportunity['amount'] * 1e9)  # Convert to lamports

            # Get actual quotes for both sides
            bid_quote = await self.jupiter.get_quote(
                self.jupiter.SOL_MINT,
                opportunity['output_token'],
                amount_in // 2
            )

            ask_quote = await self.jupiter.get_quote(
                opportunity['output_token'],
                self.jupiter.SOL_MINT,
                int(amount_in * opportunity['current_price'] // 2)
            )

            if not bid_quote or not ask_quote:
                print("Failed to get quotes for market making")
                return False

            # Execute trades
            bid_result = await self.jupiter.execute_swap(bid_quote)
            ask_result = await self.jupiter.execute_swap(ask_quote)

            if bid_result and ask_result:
                print("\nMarket making orders executed:")
                print(f"Bid: {amount_in/2e9:.4f} SOL -> {opportunity['token_name']}")
                print(f"Ask: {opportunity['token_name']} -> {amount_in/2e9:.4f} SOL")
                return True

            return False

        except Exception as e:
            print(f"Error executing trade: {e}")
            return False

    async def monitor_positions(self):
        """Continuously monitor and update market making positions"""
        update_interval = 1  # Update every second
        min_price_update = 0.0005  # 0.05% minimum price update threshold

        while self.market_making_orders:
            try:
                # Get current SOL price for profit calculations
                sol_price = await self.jupiter.monitor_token_price(self.jupiter.SOL_MINT)
                if not sol_price:
                    print("Error: Failed to get SOL price")
                    continue

                for token, position in list(self.market_making_orders.items()):
                    # Get current market price
                    current_price = await self.jupiter.monitor_token_price(token)
                    if not current_price:
                        continue

                    time_since_update = asyncio.get_event_loop().time() - position['last_update']

                    # Update orders if price has moved significantly or time threshold reached
                    price_change = abs(current_price - position['bid_price']) / position['bid_price']
                    if price_change > min_price_update or time_since_update >= 30:
                        # Calculate new bid/ask prices
                        spread = self.min_profit_threshold * 2
                        new_bid = current_price * (1 - spread/4)
                        new_ask = current_price * (1 + spread/4)

                        # Check for filled orders
                        if current_price <= position['bid_price']:
                            # Bid was filled, place new ask
                            profit = (position['ask_price'] - position['bid_price']) / position['bid_price']
                            position['total_profit'] += profit
                            position['trades_executed'] += 1
                            print(f"\nBid filled for {position['token_name']}!")
                            print(f"Profit: {profit*100:.3f}%")
                            print(f"Total profit: {position['total_profit']*100:.3f}%")
                            print(f"Trades executed: {position['trades_executed']}")

                        elif current_price >= position['ask_price']:
                            # Ask was filled, place new bid
                            profit = (position['ask_price'] - position['bid_price']) / position['bid_price']
                            position['total_profit'] += profit
                            position['trades_executed'] += 1
                            print(f"\nAsk filled for {position['token_name']}!")
                            print(f"Profit: {profit*100:.3f}%")
                            print(f"Total profit: {position['total_profit']*100:.3f}%")
                            print(f"Trades executed: {position['trades_executed']}")

                        # Update order prices
                        position['bid_price'] = new_bid
                        position['ask_price'] = new_ask
                        position['last_update'] = asyncio.get_event_loop().time()

                        print(f"\nUpdated orders for {position['token_name']}:")
                        print(f"New bid: ${new_bid:.4f}")
                        print(f"New ask: ${new_ask:.4f}")
                        print(f"Current market: ${current_price:.4f}")

                        # Check if profit target reached
                        if position['total_profit'] * self.initial_capital * sol_price >= self.profit_target_usd:
                            print(f"\nProfit target reached for {position['token_name']}!")
                            print(f"Total profit: ${position['total_profit'] * self.initial_capital * sol_price:.2f}")
                            return True

            except Exception as e:
                print(f"Error monitoring positions: {e}")

            await asyncio.sleep(update_interval)

    async def close(self):
        """Cleanup resources"""
        await self.jupiter.close()
