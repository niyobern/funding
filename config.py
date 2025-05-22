from decouple import config
from typing import Dict, List
import os
from pathlib import Path
from loguru import logger

# Base paths
BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Paper trading mode
PAPER_TRADING = config('PAPER_TRADING', default=True, cast=bool)
PAPER_TRADING_BALANCE = config('PAPER_TRADING_BALANCE', default=1000.0, cast=float)

# Exchange API credentials
BINANCE_API_KEY = config('BINANCE_API_KEY', default='')
BINANCE_API_SECRET = config('BINANCE_API_SECRET', default='')

# Only validate API credentials if not in paper trading mode
if not PAPER_TRADING and (not BINANCE_API_KEY or not BINANCE_API_SECRET):
    logger.error("Binance API credentials not found! Please set BINANCE_API_KEY and BINANCE_API_SECRET environment variables.")
    raise ValueError("Missing Binance API credentials")

# Trading parameters
TRADING_CONFIG = {
    'MIN_FUNDING_RATE': -0.001,    # -0.1% (increased from -0.01%)
    'MAX_POSITION_PERCENT': 0.2,   # 20% of capital per trade
    'MAX_LEVERAGE': 5,             # Increased from 3
    'STOP_LOSS': 0.05,             # 5%
    'TAKE_PROFIT': 0.02,           # 2%
    'MIN_LIQUIDITY': 0.01,         # Minimum liquidity in BTC (about $400 at $40k BTC price)
    'MIN_POSITION_SIZE': 4,        # Minimum position size of $4 (adjusted to match current balance)
    'MAX_POSITION_SIZE': 1000,     # Maximum position size of $1000
    'USE_MAKER_ORDERS': True,      # Use maker orders to reduce fees
    'USE_BNB_FEES': True,          # Use BNB to pay fees for discounts
    'MIN_FUNDING_RATE_IMPROVEMENT': 0.3,  # Exit when funding rate improves by 30%
    'MAX_POSITION_DURATION': 72 * 3600,  # Hold positions for up to 72 hours (9 funding periods)
}

# Monitoring intervals (in seconds)
MONITORING_CONFIG = {
    'CHECK_INTERVAL': 60,          # Check every minute (reduced from 5 minutes)
    'HEARTBEAT_INTERVAL': 3600,    # 1 hour
    'POSITION_CHECK_INTERVAL': 10,  # 10 seconds
}

# Trading pairs to monitor (focusing on high volatility pairs)
TRADING_PAIRS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "AVAXUSDT",
    "MATICUSDT",
    "DOGEUSDT",
    "SHIBUSDT",
    "LINKUSDT",
    "UNIUSDT",
    "AAVEUSDT",
]

# Risk management
RISK_CONFIG = {
    'MAX_OPEN_POSITIONS': 3,       # Reduced from 5 to focus on best opportunities
    'MAX_DAILY_TRADES': 10,        # Reduced from 20 to focus on quality over quantity
    'MAX_DRAWDOWN': 0.05,          # Reduced from 10% to 5% for tighter risk control
    'MIN_PROFIT_THRESHOLD': 0.003, # 0.3% minimum profit target after fees
}

# Logging configuration
LOG_CONFIG = {
    'LOG_LEVEL': 'INFO',
    'LOG_FORMAT': '{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}',
    'LOG_FILE': str(LOGS_DIR / 'trading_bot.log'),
} 