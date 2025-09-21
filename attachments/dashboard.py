import streamlit as st
import pandas as pd
from datetime import datetime
import asyncio
import logging
import queue
import threading
from optimized_rent_spot_bot import OptimizedRentSpotBot
from decimal import Decimal
import time
from concurrent.futures import ThreadPoolExecutor

# Initialize critical session state variables first
if 'update_queue' not in st.session_state:
    st.session_state.update_queue = queue.Queue()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('bot_debug.log')]
)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="RentSpot Trading Dashboard",
    page_icon="📈",
    layout="wide"
)

# Initialize remaining session state variables
if 'bot' not in st.session_state:
    st.session_state.bot = None

if 'bot_task' not in st.session_state:
    st.session_state.bot_task = None

if 'executor' not in st.session_state:
    st.session_state.executor = ThreadPoolExecutor(max_workers=1)

if 'bot_running' not in st.session_state:
    st.session_state.bot_running = False

if 'active_trades' not in st.session_state:
    st.session_state.active_trades = {}

if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []

if 'log_messages' not in st.session_state:
    st.session_state.log_messages = []

if 'connection_status' not in st.session_state:
    st.session_state.connection_status = "disconnected"

# Trading Parameters
if 'initial_amount' not in st.session_state:
    st.session_state.initial_amount = 0.00010101

if 'main_amount' not in st.session_state:
    st.session_state.main_amount = 0.001

if 'slippage' not in st.session_state:
    st.session_state.slippage = 5

if 'max_active_tokens' not in st.session_state:
    st.session_state.max_active_tokens = 30

class UpdateMessage:
    def __init__(self, update_type, data):
        self.update_type = update_type
        self.data = data
        self.timestamp = datetime.now()

def safe_log(message: str, level: str = "INFO"):
    """Thread-safe logging that queues updates"""
    try:
        st.session_state.update_queue.put(
            UpdateMessage("log", {"message": message, "level": level})
        )
        if level == "ERROR":
            logger.error(message)
        else:
            logger.info(message)
    except Exception as e:
        logger.error(f"Error in safe_log: {str(e)}")

def process_updates():
    """Process queued updates in the main thread"""
    try:
        updates_processed = 0
        while not st.session_state.update_queue.empty() and updates_processed < 100:
            update = st.session_state.update_queue.get_nowait()
            
            if update.update_type == "log":
                if len(st.session_state.log_messages) >= 1000:
                    st.session_state.log_messages = st.session_state.log_messages[-900:]
                st.session_state.log_messages.append(
                    f"{update.timestamp.strftime('%H:%M:%S')} - {update.data['message']}"
                )
                
            elif update.update_type == "trade":
                data = update.data
                if data["action"] == "connection_status":
                    st.session_state.connection_status = data["price"]
                    
                elif data["action"] == "buy":
                    st.session_state.active_trades[data["token_mint"]] = {
                        "entry_time": data["timestamp"],
                        "entry_price": data["price"],
                        "amount": data["amount"],
                        "current_price": data["price"],
                        "pnl": 0
                    }
                    
                elif data["action"] == "sell":
                    if data["token_mint"] in st.session_state.active_trades:
                        trade = st.session_state.active_trades[data["token_mint"]].copy()
                        trade["exit_time"] = data["timestamp"]
                        trade["exit_price"] = data["price"]
                        trade["pnl"] = data["profit"] if data["profit"] is not None else 0
                        st.session_state.trade_history.append(trade)
                        del st.session_state.active_trades[data["token_mint"]]
                        
                elif data["action"] == "price_update":
                    if data["token_mint"] in st.session_state.active_trades:
                        st.session_state.active_trades[data["token_mint"]]["current_price"] = data["price"]
            
            updates_processed += 1
            
    except Exception as e:
        logger.error(f"Error processing updates: {str(e)}")

def render_sidebar():
    """Render sidebar with trading parameters"""
    with st.sidebar:
        st.header("Trading Parameters")
        
        new_initial = st.number_input(
            "Initial Buy Amount (SOL)",
            min_value=0.00001,
            max_value=0.001,
            value=float(st.session_state.initial_amount),
            step=0.00001,
            format="%.8f"
        )
        
        new_main = st.number_input(
            "Main Trade Amount (SOL)",
            min_value=0.001,
            max_value=0.1,
            value=float(st.session_state.main_amount),
            step=0.001
        )
        
        new_slippage = st.number_input(
            "Slippage %",
            min_value=1,
            max_value=20,
            value=st.session_state.slippage,
            step=1
        )
        
        new_max_tokens = st.number_input(
            "Max Active Tokens",
            min_value=1,
            max_value=100,
            value=st.session_state.max_active_tokens,
            step=1
        )

        if (new_initial != st.session_state.initial_amount or
            new_main != st.session_state.main_amount or
            new_slippage != st.session_state.slippage or
            new_max_tokens != st.session_state.max_active_tokens):
            
            st.session_state.initial_amount = new_initial
            st.session_state.main_amount = new_main
            st.session_state.slippage = new_slippage
            st.session_state.max_active_tokens = new_max_tokens
            
            if st.session_state.bot:
                st.session_state.bot.initial_amount = Decimal(str(new_initial))
                st.session_state.bot.main_amount = Decimal(str(new_main))
                st.session_state.bot.slippage = new_slippage
                st.session_state.bot.max_active_tokens = new_max_tokens

async def trade_callback(token_mint, action, price, amount, profit=None):
    """Queue trade updates instead of directly modifying session state"""
    try:
        update_data = {
            "token_mint": token_mint,
            "action": action,
            "price": price,
            "amount": amount,
            "profit": profit,
            "timestamp": datetime.now()
        }
        st.session_state.update_queue.put(
            UpdateMessage("trade", update_data)
        )
    except Exception as e:
        logger.error(f"Error in trade callback: {str(e)}")

async def run_bot_forever():
    """Run bot in a separate thread"""
    try:
        bot = OptimizedRentSpotBot()
        bot.initial_amount = Decimal(str(st.session_state.initial_amount))
        bot.main_amount = Decimal(str(st.session_state.main_amount))
        bot.slippage = st.session_state.slippage
        bot.max_active_tokens = st.session_state.max_active_tokens
        
        await bot.register_trade_callback(trade_callback)
        st.session_state.bot = bot
        safe_log("Bot started successfully")
        
        await bot.start()
    except Exception as e:
        safe_log(f"Bot error: {str(e)}", "ERROR")
        st.session_state.bot_running = False
    finally:
        st.session_state.bot_running = False
        safe_log("Bot stopped")

def start_bot_thread():
    """Start bot in a separate thread"""
    if not st.session_state.bot_running:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        def run_bot():
            loop.run_until_complete(run_bot_forever())
            
        st.session_state.bot_task = st.session_state.executor.submit(run_bot)
        st.session_state.bot_running = True
        safe_log("Starting bot...")

def stop_bot_thread():
    """Stop bot and cleanup"""
    if st.session_state.bot_running:
        if st.session_state.bot:
            asyncio.run(st.session_state.bot.stop())
        if st.session_state.bot_task:
            st.session_state.bot_task.cancel()
        st.session_state.bot_running = False
        st.session_state.bot = None
        st.session_state.bot_task = None
        safe_log("Bot stopped")

def render_active_trades():
    """Render active trades section"""
    st.header("🔄 Active Trades")
    
    if not st.session_state.active_trades:
        st.info("No active trades")
        return
        
    for token_mint, trade in st.session_state.active_trades.items():
        with st.container():
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.write(f"Token: {token_mint[:8]}...")
                st.write(f"Entry: {trade['entry_price']:.6f} SOL")
            
            with col2:
                st.write(f"Current: {trade['current_price']:.6f} SOL")
                pnl_color = "profit" if trade['pnl'] >= 0 else "loss"
                st.markdown(f"PnL: <span class='{pnl_color}'>{trade['pnl']:.2f}%</span>", 
                          unsafe_allow_html=True)
            
            with col3:
                duration = datetime.now() - trade['entry_time']
                st.write(f"Time: {duration.seconds}s")
            
            with col4:
                if st.button(f"Sell {token_mint[:6]}", key=f"sell_{token_mint}"):
                    if st.session_state.bot:
                        asyncio.run(st.session_state.bot.execute_sell(token_mint))

def render_trade_history():
    """Render trade history section"""
    st.header("📜 Trade History")
    
    if not st.session_state.trade_history:
        st.info("No completed trades yet")
        return
    
    df = pd.DataFrame(st.session_state.trade_history)
    
    # Summary metrics
    total_trades = len(df)
    if not df.empty and 'pnl' in df.columns:
        winning_trades = len(df[df['pnl'] > 0])
        win_rate = (winning_trades / total_trades) * 100
        avg_profit = df['pnl'].mean()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Trades", total_trades)
        col2.metric("Win Rate", f"{win_rate:.1f}%")
        col3.metric("Avg Profit", f"{avg_profit:.1f}%")
    
    st.dataframe(df)

def render_logs():
    """Render log section"""
    st.header("📝 Activity Log")
    
    if not st.session_state.log_messages:
        st.info("No activity logged yet")
        return
    
    with st.container():
        for log in reversed(st.session_state.log_messages[-100:]):  # Show last 100 logs
            st.text(log)

def main():
    st.title("🚀 RentSpot Trading Dashboard")
    
    # Process any queued updates at the start of each rerun
    process_updates()
    
    # Render sidebar
    render_sidebar()
    
    # Bot control section
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header("🎮 Bot Control")
    with col2:
        if not st.session_state.bot_running:
            if st.button("🟢 Start Bot", type="primary"):
                start_bot_thread()
        else:
            if st.button("🔴 Stop Bot"):
                stop_bot_thread()

    # Status Display
    status_color = "🟢" if st.session_state.connection_status == "connected" else "🔴"
    st.markdown(
        f'<div class="bot-status {st.session_state.connection_status}">'
        f'Connection Status: {status_color} {st.session_state.connection_status.capitalize()}'
        f'</div>',
        unsafe_allow_html=True
    )

    status_class = "running" if st.session_state.bot_running else "stopped"
    status_text = "🟢 Running" if st.session_state.bot_running else "🔴 Stopped"
    st.markdown(
        f'<div class="bot-status {status_class}">Bot Status: {status_text}</div>',
        unsafe_allow_html=True
    )
    
    # Main content tabs
    tab1, tab2, tab3 = st.tabs(["Active Trades", "Trade History", "Logs"])
    
    with tab1:
        render_active_trades()
    with tab2:
        render_trade_history()
    with tab3:
        render_logs()
    
    # Auto-refresh if bot is running (every 5 seconds instead of 1)
    if st.session_state.bot_running:
        time.sleep(5)
        st.rerun()

if __name__ == "__main__":
    main()
