import asyncio
from typing import List, Dict, Optional
from decimal import Decimal
from dex.jupiter import JupiterDEX
import json
import time

class TradingStrategy:
    def __init__(self):
        self.jupiter = JupiterDEX()
        self.min_profit_threshold = 0.001  # Reduced to 0.1% minimum profit per trade
        self.max_slippage = 0.01  # 1% maximum slippage
        self.initial_capital = 1  # 1 SOL
        self.profit_target_usd = 1000  # $1000 target
        self.stop_loss_percentage = 0.02  # 2% stop loss per trade

        # Token lists for monitoring
        self.stable_tokens = [
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
            "DezXAZ8z7PnrnRJjA4ZwSuXGhs5eJBEjY8vVxR4pfRx",  # BONK
            "7i5KKsX2weiTkry7jA4ZwSuXGhs5eJBEjY8vVxR4pfRx",  # ORCA
        ]

        # High volume tokens for liquidity
        self.trading_tokens = [
            "So11111111111111111111111111111111111111112",  # SOL
            "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",  # mSOL
            "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj",  # stSOL
            "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs",  # ETH (Wormhole)
            "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",  # RAY
            "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",  # ORCA
            "AFbX8oGjGpmVFywbVouvhQSRmiW2aR1mohfahi4Y2AdB",  # GST
        ]

    async def calculate_triangular_arbitrage(self, amount: int) -> Optional[Dict]:
        best_profit = 0
        best_route = None

        print(f"\nChecking arbitrage opportunities with {amount/1e9:.3f} SOL...")

        for token_b in self.trading_tokens:
            for token_c in self.stable_tokens:
                try:
                    print(f"\nTrying route: SOL -> {token_b} -> {token_c} -> SOL")

                    quote1 = await self.jupiter.get_quote(self.jupiter.SOL_MINT, token_b, amount)
                    if not quote1:
                        print("  Failed to get quote for SOL -> token_b")
                        continue

                    amount_b = int(quote1["outAmount"])
                    print(f"  Quote1: {amount/1e9:.6f} SOL -> {amount_b/1e9:.6f} token_b")

                    quote2 = await self.jupiter.get_quote(token_b, token_c, amount_b)
                    if not quote2:
                        print("  Failed to get quote for token_b -> token_c")
                        continue

                    amount_c = int(quote2["outAmount"])
                    print(f"  Quote2: {amount_b/1e9:.6f} token_b -> {amount_c/1e9:.6f} token_c")

                    quote3 = await self.jupiter.get_quote(token_c, self.jupiter.SOL_MINT, amount_c)
                    if not quote3:
                        print("  Failed to get quote for token_c -> SOL")
                        continue

                    final_amount = int(quote3["outAmount"])
                    print(f"  Quote3: {amount_c/1e9:.6f} token_c -> {final_amount/1e9:.6f} SOL")

                    profit_percentage = (final_amount - amount) / amount
                    print(f"  Profit: {profit_percentage*100:.3f}% (min required: {self.min_profit_threshold*100:.3f}%)")

                    if profit_percentage > best_profit and profit_percentage > self.min_profit_threshold:
                        best_profit = profit_percentage
                        best_route = {
                            "profit_percentage": profit_percentage,
                            "route": [
                                {"from": self.jupiter.SOL_MINT, "to": token_b, "quote": quote1},
                                {"from": token_b, "to": token_c, "quote": quote2},
                                {"from": token_c, "to": self.jupiter.SOL_MINT, "quote": quote3}
                            ],
                            "final_amount": final_amount
                        }
                        print("  Found new best route!")

                except Exception as e:
                    print(f"  Error in arbitrage calculation: {e}")
                    continue

                await asyncio.sleep(0.1)

        return best_route

    async def monitor_market_opportunities(self):
        """
        Continuously monitor for profitable trading opportunities
        """
        initial_amount = int(self.initial_capital * 1e9)  # Convert SOL to lamports
        current_amount = initial_amount
        total_profit_usd = 0

        while total_profit_usd < self.profit_target_usd:
            try:
                # Get SOL price in USD
                sol_price = await self.jupiter.monitor_token_price(self.jupiter.SOL_MINT)
                if not sol_price:
                    continue

                # Find best arbitrage opportunity
                best_opportunity = await self.calculate_triangular_arbitrage(current_amount)
                if best_opportunity:
                    profit_percentage = best_opportunity["profit_percentage"]
                    profit_usd = (current_amount * profit_percentage * sol_price) / 1e9

                    print(f"Found opportunity: {profit_percentage*100:.2f}% profit (${profit_usd:.2f})")

                    # Execute trades would go here
                    # For now, just simulate the profit
                    current_amount = best_opportunity["final_amount"]
                    total_profit_usd += profit_usd

                    print(f"Total profit so far: ${total_profit_usd:.2f}")

            except Exception as e:
                print(f"Error in market monitoring: {e}")

            await asyncio.sleep(1)  # Rate limiting

        return total_profit_usd

    async def close(self):
        """Cleanup resources"""
        await self.jupiter.close()

    async def find_opportunity(self) -> Optional[Dict]:
        """Find the best trading opportunity."""
        try:
            print("\nFinding trading opportunities...")

            # Get current SOL price for profit calculation
            sol_price = await self.jupiter.monitor_token_price(self.jupiter.SOL_MINT)
            if sol_price is None:
                print("Error: Failed to get SOL price from Jupiter API")
                return None

            print(f"Current SOL price: ${sol_price:.2f}")

            # Verify Jupiter API connection
            try:
                test_quote = await self.jupiter.get_quote(
                    self.jupiter.SOL_MINT,
                    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                    int(0.1 * 1e9)  # 0.1 SOL
                )
                if not test_quote:
                    print("Error: Failed to get test quote from Jupiter API")
                    return None
                print("Jupiter API connection verified")
            except Exception as e:
                print(f"Error: Jupiter API test quote failed: {e}")
                return None

            # Calculate with 1 SOL as initial amount
            initial_amount = int(1e9)  # 1 SOL in lamports
            print(f"Searching with initial amount: {initial_amount/1e9:.3f} SOL")

            opportunity = await self.calculate_triangular_arbitrage(initial_amount)

            if opportunity and opportunity["profit_percentage"] > self.min_profit_threshold:
                profit_usd = (initial_amount * opportunity["profit_percentage"] * sol_price) / 1e9
                print(f"\nFound profitable opportunity!")
                print(f"Profit percentage: {opportunity['profit_percentage']*100:.3f}%")
                print(f"Expected profit: ${profit_usd:.2f}")

                return {
                    'input_token': self.jupiter.SOL_MINT,
                    'output_token': opportunity["route"][0]["to"],
                    'amount': initial_amount/1e9,
                    'expected_profit': profit_usd,
                    'route': opportunity["route"]
                }
            else:
                if opportunity:
                    print(f"\nOpportunity found but below threshold:")
                    print(f"Profit: {opportunity['profit_percentage']*100:.3f}% < {self.min_profit_threshold*100:.3f}%")
                else:
                    print("\nNo viable arbitrage opportunity found")
                return None

        except Exception as e:
            print(f"Error in find_opportunity: {str(e)}")
            return None
