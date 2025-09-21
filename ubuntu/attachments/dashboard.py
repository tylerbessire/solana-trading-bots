import streamlit as st
import pandas as pd
import plotly.graph_objs as go
import plotly.express as px
from datetime import datetime
import asyncio
import websockets
import json
from trade_tracker import TradeTracker
from tybot import set_bot_running_state, register_trade_callback
import logging

logging.getLogger("watchdog").setLevel(logging.CRITICAL)
# Set up logging with more detailed format
logging.basicConfig(
    level=logging.ERROR,  # Set to INFO to reduce debug log noise
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(),
              logging.FileHandler('bot_debug.log')])
logger = logging.getLogger(__name__)

# Initialize session state variables
if 'trade_tracker' not in st.session_state:
    st.session_state.trade_tracker = TradeTracker()
    logger.info("Initialized trade tracker")

if 'layout_preferences' not in st.session_state:
    st.session_state.layout_preferences = {
        'metrics': ['profit', 'trades', 'winrate', 'holdtime', 'risk'],
        'charts': ['performance', 'distribution', 'timing'],
        'chart_style': 'dark',
        'metrics_per_row': 3
    }
    logger.debug("Set default layout preferences")

if 'bot_running' not in st.session_state:
    st.session_state.bot_running = False
    logger.debug("Bot status initialized to stopped")

if 'connection_status' not in st.session_state:
    st.session_state.connection_status = "disconnected"
    logger.debug("Connection status initialized to disconnected")

if 'debug_messages' not in st.session_state:
    st.session_state.debug_messages = []
    logger.debug("Debug messages list initialized")

st.set_page_config(page_title="Solana Trading Bot Dashboard",
                   page_icon="📈",
                   layout="wide")

with open('assets/custom.css') as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)


async def trade_update_callback(token_mint,
                                action,
                                price,
                                amount,
                                profit=None):
    """Handle trade updates and logging"""
    message = f"Trade callback: {token_mint}, {action}, {price}, {amount}, {profit}"
    logger.info(message)
    st.session_state.debug_messages.append(
        f"{datetime.now().strftime('%H:%M:%S')} - {message}")

    if action == "connection_status":
        st.session_state.connection_status = price
        logger.info(f"Connection status updated to: {price}")
        return

    if action == "price_update":
        st.session_state.trade_tracker.update_price(token_mint, price)
        logger.debug(f"Price updated for {token_mint}: {price}")
        return

    if action == "buy":
        # Record the buy trade
        st.session_state.trade_tracker.add_trade(token_mint, price, amount,
                                                 action)
        logger.info(f"Buy recorded: {amount} of {token_mint} at {price}")

        # Immediately trigger a sell with the same amount
        await trade_update_callback(token_mint, "sell", price, amount)
    elif action == "sell":
        st.session_state.trade_tracker.add_trade(token_mint, price, amount,
                                                 action)
        logger.info(f"Sell recorded: {amount} of {token_mint} at {price}")
        if profit is not None:
            logger.info(f"Trade profit: {profit}")


async def initialize_bot():
    """Initialize bot connection with enhanced logging"""
    logger.info("Initializing bot connection...")
    try:
        success = await register_trade_callback(trade_update_callback)
        if not success:
            error_msg = "Failed to register trade callback"
            logger.error(error_msg)
            st.session_state.debug_messages.append(
                f"{datetime.now().strftime('%H:%M:%S')} - ERROR: {error_msg}")
            return False

        logger.info("Trade callback registered successfully")
        st.session_state.debug_messages.append(
            f"{datetime.now().strftime('%H:%M:%S')} - Trade callback registered"
        )

        set_bot_running_state(True)
        logger.info("Bot running state set to True")
        st.session_state.debug_messages.append(
            f"{datetime.now().strftime('%H:%M:%S')} - Bot started")
        return True
    except Exception as e:
        error_msg = f"Error initializing bot: {str(e)}"
        logger.error(error_msg, exc_info=True)
        st.session_state.debug_messages.append(
            f"{datetime.now().strftime('%H:%M:%S')} - ERROR: {error_msg}")
        return False


def main():
    st.title("🚀 Solana Trading Bot Dashboard")

    # Bot Control Section
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### 🎮 Bot Control")
        st.markdown(
            "Control the trading bot's operations and monitor its status in real-time."
        )
    with col2:
        if not st.session_state.bot_running:
            if st.button("🟢 Start Bot", type="primary", key="start_bot"):
                logger.info("Starting bot...")
                st.session_state.debug_messages.append(
                    f"{datetime.now().strftime('%H:%M:%S')} - Starting bot...")

                async def start_bot():
                    success = await initialize_bot()
                    if success:
                        st.session_state.bot_running = True
                        logger.info("Bot started successfully")
                        st.session_state.debug_messages.append(
                            f"{datetime.now().strftime('%H:%M:%S')} - Bot started successfully"
                        )
                    else:
                        logger.error("Failed to start bot")
                        st.error(
                            "Failed to start bot. Check the debug logs below.")
                        st.session_state.debug_messages.append(
                            f"{datetime.now().strftime('%H:%M:%S')} - ERROR: Failed to start bot"
                        )

                asyncio.run(start_bot())

        else:
            if st.button("🔴 Stop Bot", type="secondary", key="stop_bot"):
                logger.info("Stopping bot...")
                st.session_state.debug_messages.append(
                    f"{datetime.now().strftime('%H:%M:%S')} - Stopping bot...")
                st.session_state.bot_running = False
                set_bot_running_state(False)

    # Status Display
    status_color = "🟢" if st.session_state.connection_status == "connected" else "🔴"
    st.markdown(
        f'<div class="bot-status {st.session_state.connection_status}">'
        f'Connection Status: {status_color} {st.session_state.connection_status.capitalize()}'
        f'</div>',
        unsafe_allow_html=True)

    status_class = "running" if st.session_state.bot_running else "stopped"
    status_text = "🟢 Running" if st.session_state.bot_running else "🔴 Stopped"
    st.markdown(
        f'<div class="bot-status {status_class}">Bot Status: {status_text}</div>',
        unsafe_allow_html=True)

    # Instant Trade Actions
    st.markdown("### 🛠️ Instant Trade Actions")
    st.write("Monitoring immediate buy-sell actions in real-time")
    if st.session_state.trade_tracker.get_completed_trades_count() > 0:
        st.write(st.session_state.trade_tracker.get_trade_history())

    # Debug Logs Section with Enhanced Display
    st.markdown("### 📝 Debug Logs")

    # Add log filter
    log_filter = st.selectbox(
        "Filter logs by type:",
        ["All", "WebSocket", "Trade", "Analysis", "Error"],
        key="log_filter")

    # Filter and display logs
    if st.session_state.debug_messages:
        filtered_logs = st.session_state.debug_messages
        if log_filter != "All":
            filtered_logs = [
                log for log in st.session_state.debug_messages
                if log_filter.lower() in log.lower()
            ]

        # Display logs with syntax highlighting
        log_text = "\n".join(filtered_logs[-100:])  # Show last 100 messages
        st.code(log_text, language="plain")

        # Add clear logs button
        if st.button("Clear Logs"):
            st.session_state.debug_messages = []
            logger.info("Debug logs cleared")
    else:
        st.info("Start the bot to see debug logs.")


if __name__ == "__main__":
    main()
