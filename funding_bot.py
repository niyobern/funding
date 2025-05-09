import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger
import sys
import signal
import json
from pathlib import Path

from config import (
    TRADING_CONFIG, MONITORING_CONFIG,
    TRADING_PAIRS, RISK_CONFIG, LOG_CONFIG
)
from exchange_clients import BinanceClient

class FundingRateBot:
    def __init__(self):
        # Initialize exchange client
        self.binance = BinanceClient()
        
        # Initialize state
        self.active_positions: Dict[str, Dict] = {}
        self.last_check = 0
        self.daily_trades = 0
        self.daily_trades_reset = datetime.now()
        self.initial_balance = self.binance.get_balance()
        
        # Setup logging
        self._setup_logging()
        
        # Load state if exists
        self._load_state()
        
    def _setup_logging(self):
        """Setup logging configuration."""
        logger.remove()  # Remove default handler
        logger.add(
            sys.stdout,
            format=LOG_CONFIG['LOG_FORMAT'],
            level=LOG_CONFIG['LOG_LEVEL']
        )
        logger.add(
            LOG_CONFIG['LOG_FILE'],
            format=LOG_CONFIG['LOG_FORMAT'],
            level=LOG_CONFIG['LOG_LEVEL'],
            rotation="1 day"
        )
        
    def _load_state(self):
        """Load bot state from file if exists."""
        state_file = Path("bot_state.json")
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    self.active_positions = state.get('active_positions', {})
                    self.daily_trades = state.get('daily_trades', 0)
                    self.daily_trades_reset = datetime.fromisoformat(
                        state.get('daily_trades_reset', datetime.now().isoformat())
                    )
            except Exception as e:
                logger.error(f"Error loading state: {str(e)}")
                
    def _save_state(self):
        """Save bot state to file."""
        try:
            state = {
                'active_positions': self.active_positions,
                'daily_trades': self.daily_trades,
                'daily_trades_reset': self.daily_trades_reset.isoformat()
            }
            with open("bot_state.json", 'w') as f:
                json.dump(state, f)
        except Exception as e:
            logger.error(f"Error saving state: {str(e)}")
            
    def check_risk_limits(self) -> bool:
        """Check if we're within risk limits."""
        # Reset daily trades counter if needed
        if datetime.now() - self.daily_trades_reset > timedelta(days=1):
            self.daily_trades = 0
            self.daily_trades_reset = datetime.now()
            
        # Check maximum open positions
        if len(self.active_positions) >= RISK_CONFIG['MAX_OPEN_POSITIONS']:
            logger.warning("Maximum number of open positions reached")
            return False
            
        # Check daily trade limit
        if self.daily_trades >= RISK_CONFIG['MAX_DAILY_TRADES']:
            logger.warning("Maximum daily trades reached")
            return False
            
        # Check drawdown
        current_balance = self.binance.get_balance()
        drawdown = (self.initial_balance - current_balance) / self.initial_balance
        if drawdown >= RISK_CONFIG['MAX_DRAWDOWN']:
            logger.warning(f"Maximum drawdown reached: {drawdown:.2%}")
            return False
            
        return True
        
    def check_opportunities(self):
        """Check for funding rate arbitrage opportunities."""
        current_time = time.time()
        if current_time - self.last_check < MONITORING_CONFIG['CHECK_INTERVAL']:
            return
            
        self.last_check = current_time
        
        if not self.check_risk_limits():
            return
            
        for symbol in TRADING_PAIRS:
            try:
                # Get funding rate
                funding_rate = self.binance.get_funding_rate(symbol)
                
                # Check for opportunities
                if funding_rate <= TRADING_CONFIG['MIN_FUNDING_RATE']:
                    self.evaluate_trade(symbol, funding_rate)
                    
            except Exception as e:
                logger.error(f"Error checking {symbol}: {str(e)}")
                
    def evaluate_trade(self, symbol: str, funding_rate: float):
        """Evaluate and execute a trade if conditions are met."""
        # Check liquidity
        if not self.binance.check_liquidity(symbol):
            logger.warning(f"Insufficient liquidity for {symbol}")
            return
            
        # Calculate position size
        usdt_balance = self.binance.get_balance()
        position_size = min(
            usdt_balance * TRADING_CONFIG['MAX_POSITION_SIZE'],
            TRADING_CONFIG['MAX_POSITION_SIZE']
        )
        
        if position_size < TRADING_CONFIG['MIN_POSITION_SIZE']:
            logger.warning(f"Position size too small for {symbol}")
            return
            
        # Calculate profitability analysis
        analysis = self.binance.calculate_profitability_analysis(symbol, position_size)
        
        if not analysis.get('profitable', False):
            logger.warning(f"Trade not profitable for {symbol}")
            logger.warning(f"Break-even funding rate: {analysis.get('break_even_rate', 0)*100:.4f}%")
            logger.warning(f"Current funding rate: {funding_rate*100:.4f}%")
            logger.warning(f"Payments needed to break even: {analysis.get('payments_to_breakeven', 0):.1f}")
            return
            
        # Log profitability details
        logger.info(f"Profitability analysis for {symbol}:")
        logger.info(f"Position size: ${position_size:.2f}")
        logger.info(f"Average funding rate: {analysis['avg_funding_rate']*100:.4f}%")
        logger.info(f"Minimum funding rate: {analysis['min_funding_rate']*100:.4f}%")
        logger.info(f"Expected funding payments: {analysis['expected_payments']}")
        logger.info(f"Expected funding profit: ${analysis['expected_funding_profit']:.2f}")
        logger.info(f"Total fees: ${analysis['total_fees']:.2f}")
        logger.info(f"Payments needed to break even: {analysis['payments_to_breakeven']:.1f}")
        logger.info(f"Worst-case profit: ${analysis['worst_case_profit']:.2f}")
        logger.info(f"Worst-case net: ${analysis['worst_case_net']:.2f}")
        logger.info(f"Days to hold: {analysis['days_to_hold']:.1f}")
            
        # Execute the trade
        self.execute_arbitrage(symbol, funding_rate, position_size)
        
    def execute_arbitrage(self, symbol: str, funding_rate: float, size: float):
        """Execute the arbitrage trade."""
        try:
            # Set leverage
            self.binance.set_leverage(symbol, TRADING_CONFIG['MAX_LEVERAGE'])
            
            # Open spot position (always market order)
            spot_order = self.binance.create_spot_order(
                symbol=symbol,
                order_type='MARKET',
                side='BUY',
                amount=size
            )
            
            # Open futures position (let exchange client decide based on price advantage)
            futures_order = self.binance.create_futures_order(
                symbol=symbol,
                order_type='MARKET',  # This will be overridden if limit order is possible
                side='SELL',
                amount=size
            )
                
            # Record the position
            self.active_positions[symbol] = {
                'spot_size': size,
                'futures_size': size,
                'entry_rate': funding_rate,
                'entry_time': time.time(),
                'spot_order': spot_order,
                'futures_order': futures_order,
                'expected_profit': self.binance.calculate_expected_profit(symbol, size, funding_rate)
            }
            
            self.daily_trades += 1
            self._save_state()
            
            logger.info(f"Opened position for {symbol}")
            logger.info(f"Funding rate: {funding_rate*100:.4f}%")
            logger.info(f"Expected profit: {self.active_positions[symbol]['expected_profit']:.2f} USDT")
            
        except Exception as e:
            logger.error(f"Trade execution failed: {str(e)}")
            
    def monitor_positions(self):
        """Monitor and manage open positions."""
        for symbol in list(self.active_positions.keys()):
            try:
                position = self.active_positions[symbol]
                
                # Check if we should exit the position
                if self.binance.should_exit_position(symbol, position):
                    self.close_position(symbol)
                    continue
                
                # Check other exit conditions
                current_rate = self.binance.get_funding_rate(symbol)
                if (current_rate >= -0.00005 or  # Funding rate has normalized
                    time.time() - position['entry_time'] > TRADING_CONFIG['MAX_POSITION_DURATION']):  # Position open for too long
                    self.close_position(symbol)
                    
            except Exception as e:
                logger.error(f"Error monitoring position for {symbol}: {str(e)}")
                
    def close_position(self, symbol: str):
        """Close a position."""
        if symbol not in self.active_positions:
            return
            
        position = self.active_positions[symbol]
        
        try:
            # Close spot position (always market order)
            self.binance.create_spot_order(
                symbol=symbol,
                order_type='MARKET',
                side='SELL',
                amount=position['spot_size']
            )
            
            # Close futures position (let exchange client decide based on price advantage)
            self.binance.create_futures_order(
                symbol=symbol,
                order_type='MARKET',  # This will be overridden if limit order is possible
                side='BUY',
                amount=position['futures_size']
            )
                
            logger.info(f"Closed position for {symbol}")
            logger.info(f"Expected profit: {position['expected_profit']:.2f} USDT")
            del self.active_positions[symbol]
            self._save_state()
            
        except Exception as e:
            logger.error(f"Failed to close position for {symbol}: {str(e)}")
            
    def run(self):
        """Main bot loop."""
        logger.info("Starting Funding Rate Arbitrage Bot")
        
        def signal_handler(signum, frame):
            logger.info("Shutting down...")
            if self.active_positions:
                logger.info("Closing all open positions...")
                for symbol in list(self.active_positions.keys()):
                    self.close_position(symbol)
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        while True:
            try:
                self.check_opportunities()
                self.monitor_positions()
                time.sleep(MONITORING_CONFIG['POSITION_CHECK_INTERVAL'])
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                time.sleep(60)  # Wait a minute before retrying
                
if __name__ == "__main__":
    bot = FundingRateBot()
    bot.run() 