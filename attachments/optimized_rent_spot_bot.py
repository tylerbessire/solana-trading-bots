import asyncio
import json
import logging
from typing import Dict, Any, Set
from dotenv import load_dotenv
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
import base58
import aiohttp
import os
import time
from decimal import Decimal
from enum import Enum

from optimized_websocket_client import OptimizedWebSocketClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProfitStage(Enum):
    AWAITING_FIRST_SPIKE = 0    
    AWAITING_SECOND_SPIKE = 1   
    AWAITING_THIRD_SPIKE = 2    
    AWAITING_FOURTH_SPIKE = 3   
    LETTING_IT_RIDE = 4         

class TokenTracker:
    def __init__(self, initial_mcap: Decimal, token_mint: str):
        self.token_mint = token_mint
        self.price_history = []
        self.mcap_history = []
        self.volume_history = []
        self.initial_mcap = initial_mcap
        self.current_mcap = initial_mcap
        self.entry_mcap = None
        self.peak_mcap = initial_mcap
        self.entry_price = None
        self.profit_stage = ProfitStage.AWAITING_FIRST_SPIKE
        self.last_sell_mcap = None
        self.created_at = time.time()
        self.last_update = time.time()
        self.trailing_stop_activated = False
        self.trailing_stop_price = None
        self.trailing_stop_percentage = Decimal('10')  # 10% trailing stop default
        self.SOL_PRICE_USD = Decimal('211')
        
        # Dynamic trailing stop parameters
        self.volatility_window = 10  # Look back period for volatility
        self.min_trailing_stop = Decimal('5')  # Minimum 5% trailing stop
        self.max_trailing_stop = Decimal('20')  # Maximum 20% trailing stop

    def update(self, mcap: Decimal, price: Decimal, volume: Decimal = None) -> Dict[str, Any]:
        """Update metrics and check for trailing stop/profit taking"""
        self.price_history.append(price)
        self.mcap_history.append(mcap)
        if volume:
            self.volume_history.append(volume)
        
        if len(self.price_history) > 30:
            self.price_history.pop(0)
            self.mcap_history.pop(0)
            if self.volume_history:
                self.volume_history.pop(0)
            
        self.current_mcap = mcap
        old_peak = self.peak_mcap
        self.peak_mcap = max(self.peak_mcap, mcap)
        self.last_update = time.time()

        # Update trailing stop if price is making new highs
        if self.peak_mcap > old_peak and self.entry_price:
            self._adjust_trailing_stop(price)

        # Check trailing stop first
        if self._check_trailing_stop(price):
            return {
                "should_sell": True,
                "percentage": 99,
                "reason": "Trailing stop triggered"
            }

        # Then check profit targets
        return self._check_profit_taking()

    def _adjust_trailing_stop(self, current_price: Decimal):
        """Dynamically adjust trailing stop based on volatility"""
        if len(self.price_history) < self.volatility_window:
            return

        # Calculate recent volatility
        recent_prices = self.price_history[-self.volatility_window:]
        returns = [(recent_prices[i] / recent_prices[i-1] - 1) * 100 
                  for i in range(1, len(recent_prices))]
        volatility = sum(abs(r) for r in returns) / len(returns)

        # Adjust trailing stop percentage based on volatility
        self.trailing_stop_percentage = max(
            self.min_trailing_stop,
            min(self.max_trailing_stop, volatility * Decimal('2'))
        )

        # Update trailing stop price
        if not self.trailing_stop_price or current_price > self.trailing_stop_price:
            self.trailing_stop_price = current_price * (1 - self.trailing_stop_percentage / 100)

    def _check_trailing_stop(self, current_price: Decimal) -> bool:
        """Check if trailing stop has been hit"""
        if not self.trailing_stop_price:
            return False
        return current_price <= self.trailing_stop_price

    def _check_profit_taking(self) -> Dict[str, Any]:
        """Check profit taking conditions based on dashboard parameters"""
        if not self.entry_mcap:
            return {"should_sell": False}
            
        # Get current parameters from bot instance
        bot = self._get_bot_instance()
        if not bot:
            return {"should_sell": False}

        mcap_multiple = self.current_mcap / self.entry_mcap
        usd_mcap = self.current_mcap * self.SOL_PRICE_USD

        # Check auto buyback condition
        if bot.auto_buyback and mcap_multiple >= Decimal('2'):
            return {
                "should_sell": True,
                "percentage": 50,
                "reason": f"Auto buyback triggered at {mcap_multiple:.1f}x"
            }

        # Check sell market cap threshold
        if usd_mcap >= bot.sell_mcap_usd:
            return {
                "should_sell": True,
                "percentage": 99,
                "reason": f"Market cap target reached: ${float(usd_mcap):,.2f}"
            }

        return {"should_sell": False}

    @staticmethod
    def _get_bot_instance():
        """Get bot instance from Streamlit session state"""
        import streamlit as st
        return st.session_state.get('bot')



class OptimizedRentSpotBot:
    def __init__(self):
        # Trade tracking variables
        self.active_tokens: Set[str] = set()
        self.attempted_tokens: Set[str] = set()
        self.successful_trades: Set[str] = set()
        self.blacklisted_tokens: Set[str] = set()
        self.trade_callback = None
        self.running = True

        # Dashboard configurable parameters
        self.min_mcap_usd = 7000      # Default $20k min mcap
        self.min_token_age = 15       # Default 30s minimum age
        self.trade_amount = 0.01        # Default 0.1 SOL per trade
        self.slippage = 5             # Default 5% slippage
        self.auto_buyback = True      # Default auto buyback enabled
        self.sell_mcap_usd = 30000    # Default $75k sell target

        # Token tracking
        self.token_trackers = {}  
        self.SOL_PRICE_USD = Decimal('243')

        # Load configuration
        load_dotenv(override=True)
        self._load_configuration()



    async def start(self):
        """Start the bot and WebSocket monitoring"""
        try:
            logger.info("Starting bot and WebSocket monitoring...")

            # Set callbacks before starting monitoring
            await self.ws_client.set_callbacks(
                token_callback=self.handle_new_token,
                price_callback=self.handle_price_update,
                status_callback=self.trade_callback
            )

            # Start monitoring with single connection
            logger.info("Starting WebSocket monitoring...")
            await self.ws_client.start_monitoring()

        except Exception as e:
            logger.error(f"Bot error: {str(e)}")

    def _load_configuration(self):
        """Load and validate configuration"""
        self.public_key = os.getenv('PUBLIC_KEY')
        if not self.public_key:
            raise ValueError("PUBLIC_KEY environment variable is required")

        self.private_key = os.getenv('PRIVATE_KEY')
        if not self.private_key:
            raise ValueError("PRIVATE_KEY environment variable is required")

        self.trade_url = os.getenv('TRADE_URL', 'https://pumpportal.fun/api/trade-local')
        self.ws_uri = os.getenv('WS_URI', 'wss://pumpportal.fun/api/data')

        try:
            self.pubkey = Pubkey.from_string(self.public_key)
            private_key_bytes = base58.b58decode(self.private_key)
            self.keypair = Keypair.from_seed(private_key_bytes[:32])

            if str(self.keypair.pubkey()) != self.public_key:
                raise ValueError("Public key mismatch with keypair")

            # Initialize WebSocket client without connecting
            self.ws_client = OptimizedWebSocketClient(uri=self.ws_uri)

            logger.info("Successfully initialized bot configuration")
            self._log_parameters()

        except Exception as e:
            logger.error(f"Initialization error: {str(e)}")
            raise

    def _log_parameters(self):
        """Log current trading parameters"""
        logger.info("Trading Parameters:")
        logger.info(f"Min Market Cap: ${self.min_mcap_usd:,}")
        logger.info(f"Min Token Age: {self.min_token_age}s")
        logger.info(f"Trade Amount: {self.trade_amount} SOL")
        logger.info(f"Slippage: {self.slippage}%")
        logger.info(f"Auto Buyback: {'Enabled' if self.auto_buyback else 'Disabled'}")
        logger.info(f"Sell Target: ${self.sell_mcap_usd:,}")

    def update_parameters(self, 
                        min_mcap: int = None,
                        min_age: int = None,
                        trade_amount: float = None,
                        slippage: int = None,
                        auto_buyback: bool = None,
                        sell_mcap: int = None):
        """Update trading parameters from dashboard"""
        if min_mcap is not None:
            self.min_mcap_usd = min_mcap
        if min_age is not None:
            self.min_token_age = min_age
        if trade_amount is not None:
            self.trade_amount = trade_amount
        if slippage is not None:
            self.slippage = slippage
        if auto_buyback is not None:
            self.auto_buyback = auto_buyback
        if sell_mcap is not None:
            self.sell_mcap_usd = sell_mcap
            
        self._log_parameters()

    async def execute_manual_sell(self, token_mint: str) -> Dict[str, Any]:
        """Execute manual sell from dashboard"""
        try:
            if token_mint not in self.active_tokens:
                return {"success": False, "error": "Token not in active trades"}

            sell_trade = {
                "publicKey": str(self.pubkey),
                "action": "sell",
                "mint": token_mint,
                "amount": "99%",
                "denominatedInSol": "false",
                "slippage": self.slippage,
                "priorityFee": 0.000035,
                "briberyFee": 0.000002,
                "pool": "raydium"
            }

            logger.info(f"Executing manual sell for {token_mint}")
            sell_result = await self._send_transaction(sell_trade)
            
            if sell_result["success"]:
                self.active_tokens.remove(token_mint)
                logger.info("Manual sell successful")
            
            return sell_result

        except Exception as e:
            logger.error(f"Manual sell error: {str(e)}")
            return {"success": False, "error": str(e)}

    
  	 # In OptimizedRentSpotBot.py

    async def handle_new_token(self, token_data: Dict[str, Any]):
        """Handle new token post-bonding curve"""
        try:
            token_mint = token_data.get('mint')
            if not token_mint:
                logger.warning("No mint address in token data")
                return

            # Extract key metrics
            mcap = Decimal(str(token_data.get('marketCapSol', 0)))
            usd_mcap = mcap * self.SOL_PRICE_USD
            initial_buy = Decimal(str(token_data.get('initialBuy', 0)))
        
            logger.info(f"\nAnalyzing token: {token_data.get('name')} ({token_data.get('symbol')})")
            logger.info(f"Mint: {token_mint}")
            logger.info(f"Market Cap: ${usd_mcap:,.2f}")
            logger.info(f"Initial Buy: {initial_buy:,.2f} tokens")

            # Notify dashboard
            if self.trade_callback:
                await self.trade_callback(token_mint, "new_token", float(mcap), float(initial_buy))

            # Skip if already processed
            if token_mint in self.attempted_tokens:
                logger.info(f"Skipping {token_mint} - Already processed")
                return

            # Check market cap requirements
            if usd_mcap < self.min_mcap_usd:
                logger.info(f"Skipping {token_mint} - Market cap too low (${usd_mcap:,.2f} < ${self.min_mcap_usd:,.2f})")
                return

            # Check if we have too many active positions
            if len(self.active_tokens) >= 30:  # Max active positions
                logger.info("Skipping - Maximum active positions reached")
                return

            # Execute the trade
            logger.info(f"Attempting to trade {token_mint}")
            trade_result = await self.execute_trade(token_mint, token_data)
        
            if trade_result.get("success"):
                logger.info(f"Successfully traded {token_mint}")
                self.active_tokens.add(token_mint)
                self.successful_trades.add(token_mint)
            else:
                logger.error(f"Trade failed: {trade_result.get('error')}")

            self.attempted_tokens.add(token_mint)

        except Exception as e:
            logger.error(f"Token handling error: {str(e)}")
            if token_mint in self.active_tokens:
                self.active_tokens.remove(token_mint)

    async def execute_trade(self, token_mint: str, token_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute trade with proper parameters"""
        try:
            # Calculate optimal fees for initial buy
            total_fee = Decimal('0.0003')  # 70/30 split for fees
            priority_fee = float(total_fee * Decimal('0.7'))
            jito_tip = float(total_fee * Decimal('0.3'))

            # Prepare trade data
            trade_data = {
                "publicKey": str(self.pubkey),
                "action": "buy",
                "mint": token_mint,
                "amount": float(self.trade_amount),
                "denominatedInSol": "true",
                "slippage": self.slippage,
                "priorityFee": priority_fee,
                "briberyFee": jito_tip,
                "pool": "pump"
            }

            logger.info(f"Executing trade with parameters:")
            logger.info(f"Amount: {self.trade_amount} SOL")
            logger.info(f"Slippage: {self.slippage}%")
            logger.info(f"Priority Fee: {priority_fee} SOL")
            logger.info(f"Jito Tip: {jito_tip} SOL")

            # Send transaction
            result = await self._send_transaction(trade_data)
        
            if result.get("success"):
                logger.info(f"Trade successful: {result.get('signature')}")
            
                # Notify dashboard of successful buy
                if self.trade_callback:
                    await self.trade_callback(
                        token_mint,
                        "buy",
                        float(token_data.get('marketCapSol', 0)),
                        float(self.trade_amount)
                    )
                
            return result

        except Exception as e:
            logger.error(f"Trade execution error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_price_update(self, price_data: Dict[str, Any]):
        """Handle price updates and monitor profit taking opportunities"""
        try:
            token_mint = price_data.get('mint')
            if not token_mint or token_mint in self.blacklisted_tokens:
                return

            mcap = Decimal(str(price_data.get('market_cap', 0)))
            price = Decimal(str(price_data.get('price', 0)))

            if token_mint in self.token_trackers:
                tracker = self.token_trackers[token_mint]
                profit_check = tracker.update(mcap, price)

                if profit_check.get("should_sell", False):
                    logger.info(f"\n💰 Profit taking signal for {token_mint}")
                    logger.info(profit_check["reason"])

        except Exception as e:
            logger.error(f"Price update error: {str(e)}")

    async def register_trade_callback(self, callback):
        """Register callback for trade updates"""
        self.trade_callback = callback
        return True

    async def stop(self):
        """Gracefully stop the bot"""
        logger.info("Stopping bot...")
        self.running = False
        if self.ws_client:
            await self.ws_client.stop()
        logger.info("Bot stopped")
