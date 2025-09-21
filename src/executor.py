import asyncio
from typing import Dict, Optional
from solders.keypair import Keypair
from solders.transaction import Transaction
from solana.rpc.async_api import AsyncClient
import base58
from dex.jupiter import JupiterDEX
import json
import time
import os
from dotenv import load_dotenv

class TradeExecutor:
    def __init__(self):
        load_dotenv()
        self.client = AsyncClient(os.getenv('RPC_ENDPOINT'))
        self.jupiter = JupiterDEX()
        private_key_bytes = base58.b58decode(os.getenv('PRIVATE_KEY'))
        self.keypair = Keypair.from_bytes(private_key_bytes)
        self.max_retries = 3
        self.retry_delay = 1  # seconds

    async def execute_swap(self, route_info: Dict) -> Optional[Dict]:
        """Execute a swap through Jupiter with retry logic"""
        for attempt in range(self.max_retries):
            try:
                # Get transaction data from Jupiter
                swap_data = {
                    "route": route_info["route"],
                    "userPublicKey": self.keypair.public_key,
                    "slippageBps": 50  # 0.5% slippage
                }

                async with self.jupiter._session.post(f"{self.jupiter.swap_api}/swap", json=swap_data) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to get swap transaction: {await response.text()}")

                    swap_response = await response.json()

                    # Create and sign transaction
                    transaction = Transaction.deserialize(base58.b58decode(swap_response['transaction']))
                    signed_tx = transaction.sign(self.keypair)

                    # Send transaction
                    tx_hash = await self.client.send_transaction(signed_tx, self.keypair)

                    # Wait for confirmation
                    confirmation = await self.client.confirm_transaction(tx_hash['result'])

                    if confirmation:
                        return {
                            "success": True,
                            "tx_hash": tx_hash['result'],
                            "route": route_info
                        }

            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                continue

        return None

    async def execute_arbitrage_route(self, route: Dict) -> Optional[Dict]:
        """Execute a complete arbitrage route"""
        results = []

        for leg in route["route"]:
            result = await self.execute_swap(leg)
            if not result:
                # If any leg fails, try to reverse previous successful trades
                await self.reverse_trades(results)
                return None
            results.append(result)

            # Small delay between trades to ensure proper order
            await asyncio.sleep(0.1)

        return {
            "success": True,
            "trades": results,
            "profit_percentage": route["profit_percentage"]
        }

    async def reverse_trades(self, completed_trades: list):
        """Attempt to reverse completed trades if arbitrage fails"""
        for trade in reversed(completed_trades):
            try:
                # Create reverse route
                reverse_route = {
                    "route": {
                        "from": trade["route"]["to"],
                        "to": trade["route"]["from"],
                        "quote": await self.jupiter.get_quote(
                            trade["route"]["to"],
                            trade["route"]["from"],
                            int(trade["route"]["quote"]["outAmount"])
                        )
                    }
                }
                await self.execute_swap(reverse_route)
            except Exception as e:
                print(f"Failed to reverse trade: {e}")

    async def close(self):
        """Cleanup resources"""
        await self.client.close()
        await self.jupiter.close()

    async def execute_trade(self, opportunity: Dict) -> bool:
        """Execute a simulated or real trade opportunity"""
        try:
            # For test trades, simulate the execution
            if opportunity.get('test_mode', True):
                print(f"Simulating trade: {opportunity['amount']} SOL -> {opportunity['output_token']}")
                print(f"Expected profit: ${opportunity.get('expected_profit', 0):.2f}")
                return True

            # For real trades, execute through Jupiter
            quote = await self.jupiter.get_quote(
                opportunity['input_token'],
                opportunity['output_token'],
                int(opportunity['amount'] * 1e9)  # Convert SOL to lamports
            )

            if not quote:
                print("Failed to get quote for trade")
                return False

            result = await self.execute_swap({
                "route": quote["data"],
                "from": opportunity['input_token'],
                "to": opportunity['output_token'],
                "quote": quote
            })

            return result is not None and result.get('success', False)

        except Exception as e:
            print(f"Error executing trade: {e}")
            return False
