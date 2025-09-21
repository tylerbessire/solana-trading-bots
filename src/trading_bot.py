from solana.rpc.api import Client
from solana.transaction import Transaction
from solana.keypair import Keypair
from spl.token.instructions import get_associated_token_account
import websockets
import json
import time
from config import Config

class TradingBot:
    def __init__(self):
        self.config = Config()
        self.client = Client(self.config.RPC_ENDPOINT)
        self.keypair = Keypair.from_secret_key(bytes.fromhex(self.config.PRIVATE_KEY))
        self.ws = None

    async def connect_websocket(self):
        """Establish and maintain a single WebSocket connection"""
        if not self.ws:
            try:
                self.ws = await websockets.connect(self.config.RPC_ENDPOINT.replace('https', 'wss'))
            except Exception as e:
                print(f"WebSocket connection error: {e}")
                self.ws = None

    async def get_market_data(self, token_address):
        """Get current market data for a token"""
        try:
            # Ensure WebSocket connection is established
            await self.connect_websocket()
            if not self.ws:
                raise Exception("WebSocket connection failed")

            # Get token account info
            response = await self.client.get_token_account_balance(token_address)
            return response
        except Exception as e:
            print(f"Error getting market data: {e}")
            return None

    async def execute_trade(self, token_address, amount, is_buy):
        """Execute a trade on the chosen DEX"""
        try:
            # Create and sign transaction
            transaction = Transaction()
            # Implementation will depend on specific DEX integration
            # This is a placeholder for actual DEX integration
            return False
        except Exception as e:
            print(f"Error executing trade: {e}")
            return False

    async def monitor_position(self, token_address, entry_price):
        """Monitor an open position for take profit or stop loss"""
        try:
            while True:
                current_price = await self.get_market_data(token_address)
                if not current_price:
                    continue

                # Check stop loss and take profit conditions
                profit_loss = (current_price - entry_price) / entry_price

                if profit_loss <= -self.config.STOP_LOSS_PERCENTAGE:
                    return await self.execute_trade(token_address, 0, False)  # Close position
                elif profit_loss >= self.config.TAKE_PROFIT_PERCENTAGE:
                    return await self.execute_trade(token_address, 0, False)  # Close position

                await asyncio.sleep(1)
        except Exception as e:
            print(f"Error monitoring position: {e}")
            return False

    def calculate_position_size(self, token_price):
        """Calculate the optimal position size based on current balance and risk parameters"""
        try:
            # Simple position sizing based on config parameters
            balance = float(self.config.MIN_TRADE_SIZE)  # Starting with 1 SOL
            max_position = min(balance * self.config.MAX_TRADE_SIZE, balance)
            return max_position
        except Exception as e:
            print(f"Error calculating position size: {e}")
            return None

    async def close(self):
        """Clean up resources"""
        if self.ws:
            await self.ws.close()
