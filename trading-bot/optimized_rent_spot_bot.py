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

        # Trading metrics
        self.trade_amount = Decimal('0.01')  # Default trade amount
        self.initial_mcap = initial_mcap
        self.current_mcap = initial_mcap
        self.entry_mcap = None
        self.peak_mcap = initial_mcap
        self.entry_price = None
        self.cumulative_loss = Decimal('0')  # Track cumulative losses
        self.stop_loss_threshold = Decimal('0.1')  # 0.1 SOL stop loss
        self.profit_stage = ProfitStage.AWAITING_FIRST_SPIKE
        self.last_sell_mcap = None
        self.created_at = time.time()
        self.last_update = time.time()
        self.trailing_stop_activated = False
        self.trailing_stop_price = None
        self.trailing_stop_percentage = Decimal('10')  # 10% trailing stop default
        self.SOL_PRICE_USD = Decimal('256')  # Updated to current SOL price

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

        # Set entry price if not set
        if not self.entry_price:
            self.entry_price = price

        # Calculate current loss if price dropped
        if price < self.entry_price:
            current_loss = (self.entry_price - price) * self.trade_amount
            if current_loss > Decimal('0'):
                self.cumulative_loss = current_loss
                if self.cumulative_loss >= self.stop_loss_threshold:
                    return {
                        "should_sell": True,
                        "percentage": 99,
                        "reason": f"Stop loss triggered - Cumulative loss: {self.cumulative_loss} SOL"
                    }

        # Update trailing stop if price is making new highs
        if self.peak_mcap > old_peak and self.entry_price:
            self._adjust_trailing_stop(price)

        # Check trailing stop
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
        """Check if trailing stop or cumulative loss limit has been hit"""
        if not self.trailing_stop_price:
            return False

        # Calculate current loss if price is below entry
        if self.entry_price and current_price < self.entry_price:
            current_loss = (self.entry_price - current_price) * self.trade_amount
            self.cumulative_loss += current_loss

            # Check cumulative loss threshold
            if self.cumulative_loss >= self.stop_loss_threshold:
                logger.warning(f"Cumulative loss threshold reached: {self.cumulative_loss} SOL")
                return True

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
        # Wallet pattern tracking
        self.successful_wallets = {}  # Track wallets with successful trades
        self.wallet_trade_history = {}  # Track all wallet trading activity
        self.min_success_threshold = 10  # Minimum seconds for success
        self.successful_tokens = set()  # Tokens that survived > 10 seconds
        self.token_creation_times = {}  # Track token creation timestamps
        self.token_creators = {}  # Track token creator wallets



class OptimizedRentSpotBot:
    def __init__(self):
        """Initialize the bot with configuration"""
        # Trading parameters
        self.trade_amount = Decimal('0.01')  # 0.01 SOL per trade
        self.bribery_fee = Decimal('0.001')  # 0.001 SOL bribery fee
        self.priority_fee = Decimal('0.001')  # 0.001 SOL priority fee
        self.min_mcap_usd = 100000  # $100k minimum market cap
        self.min_token_age = 300    # 5 minutes minimum token age
        self.slippage = 5
        self.auto_buyback = False
        self.sell_mcap_usd = 1000000  # $1M sell target
        self.max_active_tokens = 30

        # Load configuration and initialize keypair
        self._load_configuration()

        # Initialize WebSocket client explicitly
        self.ws_client = OptimizedWebSocketClient(uri=self.ws_uri)
        logger.info("WebSocket client initialized in __init__")

        # Trading state
        self.active_tokens: Set[str] = set()
        self.token_trackers: Dict[str, TokenTracker] = {}
        self.trade_callback = None

        logger.info("Bot initialized successfully")



    async def start(self):
        """Start the bot and WebSocket monitoring"""
        try:
            logger.info("Starting bot and WebSocket monitoring...")

            # Define status callback to handle connection updates
            async def status_callback(_, event_type, status, __):
                if event_type == "connection_status":
                    logger.info(f"WebSocket connection status changed to: {status}")
                    # Use trade_callback to update connection status through the queue system
                    if self.trade_callback:
                        await self.trade_callback(None, "connection_status", status, None)
                    if status == "connected":
                        logger.info("Successfully connected to WebSocket server")
                    elif status == "disconnected":
                        logger.warning("WebSocket connection lost")
                elif self.trade_callback:
                    await self.trade_callback(_, event_type, status, __)

            # Set callbacks using the correct parameter names
            await self.ws_client.set_callbacks(
                status_callback=status_callback,
                trade_callback=self.handle_price_update,
                new_token_callback=self.handle_new_token
            )
            # Start monitoring
            logger.info("Starting WebSocket monitoring...")
            await self.ws_client.start_monitoring()
            logger.info("WebSocket monitoring started successfully")
        except Exception as e:
            logger.error(f"Bot startup error: {str(e)}")
            if self.trade_callback:
                await self.trade_callback(None, "connection_status", "error", None)
            raise

    def _load_configuration(self):
        """Load and validate configuration"""
        # Load environment variables
        load_dotenv()

        self.public_key = os.getenv('PUBLIC_KEY')
        if not self.public_key:
            raise ValueError("PUBLIC_KEY environment variable is required")

        # Convert Ethereum public key to Solana format
        if self.public_key.startswith('0x'):
            self.public_key = self.public_key[2:]  # Remove 0x prefix
            # Convert to bytes then to base58
            public_key_bytes = bytes.fromhex(self.public_key)
            self.public_key = base58.b58encode(public_key_bytes).decode('utf-8')

        self.private_key = os.getenv('WALLET_PRIVATE_KEY')
        if not self.private_key:
            raise ValueError("WALLET_PRIVATE_KEY environment variable is required")

        # Load trading configuration from config.json
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)

            # Set trading parameters
            self.trade_amount = Decimal(str(config['trading']['trade_amount']))
            self.priority_fee = Decimal(str(config['trading']['fees']['priority']))
            self.bribery_fee = Decimal(str(config['trading']['fees']['bribery']))
            self.slippage = config['trading']['slippage']
            self.max_active_tokens = config['trading']['max_active_tokens']

            # Set monitoring parameters
            self.min_mcap_usd = config['monitoring']['min_mcap_usd']
            self.min_token_age = config['monitoring']['min_token_age']
            self.sell_mcap_usd = config['monitoring']['sell_mcap_usd']

            # Set WebSocket configuration
            self.trade_url = os.getenv('TRADE_URL', 'https://pumpportal.fun/api/trade-local')
            self.ws_uri = os.getenv('WS_URI', config['websocket']['uri'])

            # Create keypair from seed (32-byte private key)
            if self.private_key.startswith('0x'):
                self.private_key = self.private_key[2:]
            private_key_bytes = bytes.fromhex(self.private_key)
            self.keypair = Keypair.from_seed(private_key_bytes)

            logger.info("Configuration loaded successfully")
            self._log_parameters()

        except Exception as e:
            logger.error(f"Configuration error: {str(e)}")
            raise

    def _log_parameters(self):
        """Log current trading parameters"""
        logger.info("\n=== Trading Configuration ===")
        logger.info(f"Trade Amount: {self.trade_amount} SOL")
        logger.info(f"Priority Fee: {self.priority_fee} SOL")
        logger.info(f"Bribery Fee: {self.bribery_fee} SOL")
        logger.info(f"Slippage: {self.slippage}%")
        logger.info(f"Max Active Tokens: {self.max_active_tokens}")
        logger.info("\n=== Monitoring Parameters ===")
        logger.info(f"Min Market Cap: ${self.min_mcap_usd:,.2f}")
        logger.info(f"Min Token Age: {self.min_token_age} seconds")
        logger.info(f"Sell Market Cap: ${self.sell_mcap_usd:,.2f}")
        logger.info("\n=== Connection Details ===")
        logger.info(f"Trade URL: {self.trade_url}")
        logger.info(f"WebSocket URI: {self.ws_uri}")
        logger.info("===========================\n")

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
            self.trade_amount = Decimal(str(trade_amount))
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
                "priorityFee": float(self.priority_fee),
                "briberyFee": float(self.bribery_fee),
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

            # Track token creation time and creator
            creator_wallet = token_data.get('creator')
            self.token_creation_times[token_mint] = time.time()
            self.token_creators[token_mint] = creator_wallet

            if creator_wallet:
                if creator_wallet not in self.wallet_trade_history:
                    self.wallet_trade_history[creator_wallet] = {
                        'total_tokens': 0,
                        'successful_tokens': 0,
                        'tokens': set()
                    }
                self.wallet_trade_history[creator_wallet]['total_tokens'] += 1
                self.wallet_trade_history[creator_wallet]['tokens'].add(token_mint)

            # Check if creator has successful history
            is_trusted_creator = False
            if creator_wallet in self.successful_wallets:
                success_rate = (self.wallet_trade_history[creator_wallet]['successful_tokens'] /
                              self.wallet_trade_history[creator_wallet]['total_tokens'])
                is_trusted_creator = success_rate > 0.3  # 30% success rate threshold

            logger.info(f"\nAnalyzing token: {token_data.get('name')} ({token_data.get('symbol')})")
            logger.info(f"Creator wallet: {creator_wallet}")
            logger.info(f"Creator success rate: {success_rate if creator_wallet in self.successful_wallets else 'N/A'}")

            # Skip if already processed
            if token_mint in self.attempted_tokens:
                logger.info(f"Skipping {token_mint} - Already processed")
                return

            # Check market cap requirements
            if usd_mcap < self.min_mcap_usd:
                logger.info(f"Skipping {token_mint} - Market cap too low (${usd_mcap:,.2f} < ${self.min_mcap_usd:,.2f})")
                return

            # Check if we have too many active positions
            if len(self.active_tokens) >= 30:
                logger.info("Skipping - Maximum active positions reached")
                return

            # Execute trade with higher priority for trusted creators
            if is_trusted_creator:
                logger.info(f"Prioritizing trade for trusted creator: {creator_wallet}")
                self.priority_fee *= Decimal('1.5')  # Increase priority fee for trusted creators

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

            # Check for successful tokens (survived > 10 seconds)
            if (token_mint in self.token_creation_times and
                token_mint not in self.successful_tokens and
                time.time() - self.token_creation_times[token_mint] > self.min_success_threshold):

                self.successful_tokens.add(token_mint)
                creator = self.token_creators.get(token_mint)
                if creator:
                    if creator not in self.successful_wallets:
                        self.successful_wallets[creator] = 1
                    else:
                        self.successful_wallets[creator] += 1
                    self.wallet_trade_history[creator]['successful_tokens'] += 1
                    logger.info(f"Token {token_mint} survived 10s. Creator {creator} success rate: "
                              f"{self.wallet_trade_history[creator]['successful_tokens']}/{self.wallet_trade_history[creator]['total_tokens']}")

            # Log wallet pattern statistics
            successful_creators = sorted(
                self.successful_wallets.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]

            logger.info("\nTop Successful Creator Wallets:")
            for creator, successes in successful_creators:
                history = self.wallet_trade_history[creator]
                success_rate = (history['successful_tokens'] / history['total_tokens']) * 100
                logger.info(f"Creator: {creator}")
                logger.info(f"Success Rate: {success_rate:.2f}%")
                logger.info(f"Total Tokens: {history['total_tokens']}")
                logger.info(f"Successful Tokens: {history['successful_tokens']}\n")

            logger.info(f"Total Successful Tokens: {len(self.successful_tokens)}")
            logger.info("============================\n")

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
            # Use fixed fees as specified
            priority_fee = float(self.priority_fee)
            bribery_fee = float(self.bribery_fee)
            mcap = Decimal(str(token_data.get('marketCapSol', 0)))

            # Create token tracker with trade amount
            tracker = TokenTracker(mcap, token_mint)
            tracker.trade_amount = self.trade_amount  # Set trade amount for loss tracking
            self.token_trackers[token_mint] = tracker

            # Prepare trade data
            trade_data = {
                "publicKey": str(self.pubkey),
                "action": "buy",
                "mint": token_mint,
                "amount": float(self.trade_amount),
                "denominatedInSol": "true",
                "slippage": self.slippage,
                "priorityFee": priority_fee,
                "briberyFee": bribery_fee,
                "pool": "pump"
            }

            logger.info(f"Executing trade with parameters:")
            logger.info(f"Amount: {self.trade_amount} SOL")
            logger.info(f"Slippage: {self.slippage}%")
            logger.info(f"Priority Fee: {priority_fee} SOL")
            logger.info(f"Bribery Fee: {bribery_fee} SOL")

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
