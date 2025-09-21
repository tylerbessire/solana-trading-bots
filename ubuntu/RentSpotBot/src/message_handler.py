"""
Message handler for processing WebSocket trade events from pump.fun
"""
from typing import Dict, Optional, Any
from dataclasses import dataclass
import json
import logging
import asyncio
from .solana_transaction import SolanaTransactionHandler

logger = logging.getLogger(__name__)

@dataclass
class TradeEvent:
    signature: str
    mint: str
    tx_type: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradeEvent':
        """
        Create TradeEvent from dictionary data

        Args:
            data: Dictionary containing trade event data

        Returns:
            TradeEvent instance
        """
        return cls(
            signature=data['signature'],
            mint=data['mint'],
            tx_type=data['txType']
        )

class MessageHandler:
    def __init__(self):
        self.transaction_handler = SolanaTransactionHandler()
        self.trade_count = 0
        self.max_trades = 5
        self.logger = logging.getLogger(__name__)

    def process_message(self, message: str) -> Optional[TradeEvent]:
        """
        Process incoming WebSocket message and convert to TradeEvent if applicable

        Args:
            message: Raw WebSocket message

        Returns:
            Optional[TradeEvent]: Processed trade event or None if not a trade
        """
        try:
            # Parse message as JSON if it's a string
            if isinstance(message, str):
                data = json.loads(message)
            else:
                data = message  # Message is already parsed

            # Log received message type
            self.logger.debug(f"Processing message: {data}")

            # Check if this is a trade event
            if isinstance(data, dict) and all(key in data for key in ['signature', 'mint', 'txType']):
                self.logger.info(f"Found trade event: {data['txType']} for token {data['mint']}")
                return TradeEvent(
                    signature=data['signature'],
                    mint=data['mint'],
                    tx_type=data['txType']
                )
            else:
                self.logger.debug("Message is not a trade event")
                return None

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse message as JSON: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            return None

    async def handle_trade_event(self, event: TradeEvent) -> None:
        """
        Handle processed trade event

        Args:
            event: Processed TradeEvent object
        """
        # Log trade details
        self.logger.info(
            f"Trade Event Details:\n"
            f"Type: {event.tx_type}\n"
            f"Mint: {event.mint}\n"
            f"Signature: {event.signature}"
        )

        # Execute trade strategy based on event type
        if event.tx_type == "buy":
            await self.handle_buy_event(event)
        elif event.tx_type == "sell":
            await self.handle_sell_event(event)

    async def handle_buy_event(self, event: TradeEvent) -> None:
        """
        Handle buy event by executing a buy transaction

        Args:
            event: Processed TradeEvent object
        """
        if self.trade_count >= self.max_trades:
            self.logger.info("Maximum number of test trades reached")
            return

        try:
            self.logger.info(f"Executing buy trade {self.trade_count + 1}/{self.max_trades}")
            signature = await self.transaction_handler.execute_buy(
                token_mint=event.mint,
                amount_sol=0.0001,  # Minimal investment
                priority_fee=0.00001,  # Minimal priority fee
                bribery_fee=0.00001  # Minimal bribery fee
            )
            self.trade_count += 1
            self.logger.info(f"Buy transaction executed. Signature: {signature}")

            # If this was a successful buy, immediately execute a sell
            if signature:
                await self.handle_sell_event(event)
        except Exception as e:
            self.logger.error(f"Failed to execute buy transaction: {e}")
            raise

    async def handle_sell_event(self, event: TradeEvent) -> None:
        """
        Handle sell trade events by executing an immediate sell

        Args:
            event: Trade event containing token information
        """
        if self.trade_count >= self.max_trades:
            self.logger.info("Maximum number of test trades reached")
            return

        try:
            # Execute sell trade immediately after buy
            self.logger.info(f"Executing sell trade for {event.mint}")

            # Execute the transaction
            tx_signature = await self.transaction_handler.execute_sell(
                token_mint=event.mint,
                priority_fee=0.00001,
                bribery_fee=0.00001
            )

            self.logger.info(
                f"Sell trade executed successfully:\n"
                f"Transaction: {tx_signature}"
            )
        except Exception as e:
            self.logger.error(f"Failed to execute sell trade: {e}")
