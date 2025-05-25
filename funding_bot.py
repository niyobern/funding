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
    TRADING_PAIRS, RISK_CONFIG, LOG_CONFIG,
    PAPER_TRADING, PAPER_TRADING_BALANCE
)
from exchange_clients import BinanceClient
from paper_trading import PaperTradingClient
from trading_reports import TradingReports

class FundingRateBot:
    def __init__(self):
        try:
            # Initialize exchange client based on mode
            if PAPER_TRADING:
                logger.info(f"Initializing bot in PAPER TRADING mode with balance: {PAPER_TRADING_BALANCE} USDT")
                self.binance = PaperTradingClient(initial_balance=PAPER_TRADING_BALANCE)
            else:
                logger.info("Initializing bot in LIVE TRADING mode")
                self.binance = BinanceClient()
            
            # Initialize state
            self.active_positions: Dict[str, Dict] = {}
            self.last_check = 0
            self.daily_trades = 0
            self.daily_trades_reset = datetime.now()
            self.initial_balance = self.binance.get_balance()
            
            if self.initial_balance < TRADING_CONFIG['MIN_POSITION_SIZE']:
                raise ValueError(f"Initial balance {self.initial_balance} USDT is below minimum position size {TRADING_CONFIG['MIN_POSITION_SIZE']} USDT")
            
            # Setup logging
            self._setup_logging()
            
            # Initialize reporting
            self.reports = TradingReports()
            self.reports.set_initial_balance(self.initial_balance)
            
            # Load state if exists
            self._load_state()
            
            logger.info(f"Bot initialized with balance: {self.initial_balance:.2f} USDT")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {str(e)}")
            raise
            
    def _setup_logging(self):
        """Setup logging configuration."""
        try:
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
            logger.info("Logging setup completed")
        except Exception as e:
            logger.error(f"Failed to setup logging: {str(e)}")
            raise
            
    def _load_state(self):
        """Load bot state from file if exists."""
        state_file = Path("bot_state.json")
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    # Load positions but validate them
                    loaded_positions = state.get('active_positions', {})
                    self.active_positions = {}
                    
                    # Validate each position and enforce limit
                    valid_positions = 0
                    for symbol, position in loaded_positions.items():
                        # Check if we've hit the position limit
                        if valid_positions >= RISK_CONFIG['MAX_OPEN_POSITIONS']:
                            logger.warning(f"Position limit reached during state load, skipping {symbol}")
                            continue
                            
                        # Check if position still exists in exchange
                        current_position = self.binance.get_position(symbol)
                        if current_position and current_position.get('size', 0) > 0:
                            self.active_positions[symbol] = position
                            valid_positions += 1
                        else:
                            logger.warning(f"Removing invalid position for {symbol} during state load")
                    
                    self.daily_trades = state.get('daily_trades', 0)
                    self.daily_trades_reset = datetime.fromisoformat(
                        state.get('daily_trades_reset', datetime.now().isoformat())
                    )
                logger.info(f"Loaded state: {len(self.active_positions)} active positions, {self.daily_trades} daily trades")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid state file format: {str(e)}")
                self._reset_state()
            except Exception as e:
                logger.error(f"Error loading state: {str(e)}")
                self._reset_state()
        else:
            # If bot_state.json does not exist, reset state to empty
            self._reset_state()
                
    def _reset_state(self):
        """Reset bot state to initial values."""
        self.active_positions = {}
        self.daily_trades = 0
        self.daily_trades_reset = datetime.now()
        logger.info("Bot state reset to initial values")
                
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
            logger.debug("Bot state saved successfully")
        except Exception as e:
            logger.error(f"Error saving state: {str(e)}")
            
    def check_risk_limits(self) -> bool:
        """Check if we're within risk limits."""
        try:
            # Reset daily trades counter if needed
            if datetime.now() - self.daily_trades_reset > timedelta(days=1):
                self.daily_trades = 0
                self.daily_trades_reset = datetime.now()
                logger.info("Daily trades counter reset")
                
            # Check maximum open positions
            current_positions = len(self.active_positions)
            if current_positions >= RISK_CONFIG['MAX_OPEN_POSITIONS']:
                logger.warning(f"Maximum number of open positions reached ({current_positions}/{RISK_CONFIG['MAX_OPEN_POSITIONS']})")
                return False
                
            # Check daily trade limit
            if self.daily_trades >= RISK_CONFIG['MAX_DAILY_TRADES']:
                logger.warning(f"Maximum daily trades reached ({self.daily_trades}/{RISK_CONFIG['MAX_DAILY_TRADES']})")
                return False
                
            # Check drawdown
            current_balance = self.binance.get_balance()
            drawdown = (self.initial_balance - current_balance) / self.initial_balance
            if drawdown >= RISK_CONFIG['MAX_DRAWDOWN']:
                logger.warning(f"Maximum drawdown reached: {drawdown:.2%} (limit: {RISK_CONFIG['MAX_DRAWDOWN']:.2%})")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking risk limits: {str(e)}")
            return False
            
    def check_opportunities(self):
        """Check for funding rate arbitrage opportunities."""
        try:
            current_time = time.time()
            if current_time - self.last_check < MONITORING_CONFIG['CHECK_INTERVAL']:
                return
                
            self.last_check = current_time
            
            # Check risk limits before looking for opportunities
            if not self.check_risk_limits():
                return
                
            logger.info("\n=== Current Funding Rates ===")
            for symbol in TRADING_PAIRS:
                try:
                    # Get funding rate
                    funding_rate = self.binance.get_funding_rate(symbol)
                    status = "OPPORTUNITY" if funding_rate <= TRADING_CONFIG['MIN_FUNDING_RATE'] else "SKIP"
                    logger.info(f"{symbol}: {funding_rate*100:.4f}% (threshold: {TRADING_CONFIG['MIN_FUNDING_RATE']*100:.4f}%) - {status}")
                    
                    # Check for opportunities
                    if funding_rate <= TRADING_CONFIG['MIN_FUNDING_RATE']:
                        logger.info(f"Found opportunity for {symbol} with funding rate: {funding_rate*100:.4f}%")
                        self.evaluate_trade(symbol, funding_rate)
                        
                except Exception as e:
                    logger.error(f"Error checking {symbol}: {str(e)}")
                    continue
            logger.info("=== End of Funding Rates ===\n")
                    
        except Exception as e:
            logger.error(f"Error checking opportunities: {str(e)}")
            
    def evaluate_trade(self, symbol: str, funding_rate: float):
        """Evaluate and execute a trade if conditions are met."""
        try:
            # Check risk limits again before executing trade
            if not self.check_risk_limits():
                logger.warning(f"Skipping trade for {symbol} due to risk limits")
                return
                
            # Check liquidity
            if not self.binance.check_liquidity(symbol):
                logger.warning(f"Insufficient liquidity for {symbol}")
                return
                
            # Calculate position size
            usdt_balance = self.binance.get_balance()
            position_size = min(
                usdt_balance * TRADING_CONFIG['MAX_POSITION_PERCENT'],  # Percentage of balance
                TRADING_CONFIG['MAX_POSITION_SIZE']  # Absolute maximum
            )
            
            if position_size < TRADING_CONFIG['MIN_POSITION_SIZE']:
                logger.warning(f"Position size too small for {symbol}: {position_size:.2f} USDT")
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
            
        except Exception as e:
            logger.error(f"Error evaluating trade for {symbol}: {str(e)}")
            
    def execute_arbitrage(self, symbol: str, funding_rate: float, size: float):
        """Execute the arbitrage trade."""
        try:
            # Set leverage
            if not self.binance.set_leverage(symbol, TRADING_CONFIG['MAX_LEVERAGE']):
                raise ValueError(f"Failed to set leverage for {symbol}")
            
            # Get current price for size conversion
            price = self.binance.get_best_maker_price(symbol, 'BUY')
            asset_size = size / price  # Convert USDT size to asset size
            
            # Open spot position (always market order)
            spot_order = self.binance.create_spot_order(
                symbol=symbol,
                order_type='MARKET',
                side='BUY',
                amount=asset_size  # Use asset size instead of USDT size
            )
            
            # Record spot trade
            self.reports.record_trade({
                'symbol': symbol,
                'type': 'OPEN',
                'side': 'BUY',
                'amount': size,  # Keep USDT amount for reporting
                'price': spot_order['price'],
                'fees': spot_order['fee'],
                'funding_rate': funding_rate
            })
            
            # Open futures position (let exchange client decide based on price advantage)
            futures_order = self.binance.create_futures_order(
                symbol=symbol,
                order_type='MARKET',  # This will be overridden if limit order is possible
                side='SELL',
                amount=asset_size  # Use asset size instead of USDT size
            )
            
            # Record futures trade
            self.reports.record_trade({
                'symbol': symbol,
                'type': 'OPEN',
                'side': 'SELL',
                'amount': size,  # Keep USDT amount for reporting
                'price': futures_order['price'],
                'fees': futures_order['fee'],
                'funding_rate': funding_rate
            })
                
            # Record the position
            self.active_positions[symbol] = {
                'spot_size': asset_size,  # Store in asset terms
                'futures_size': asset_size,  # Store in asset terms
                'entry_rate': funding_rate,
                'entry_time': time.time(),
                'spot_order': spot_order,
                'futures_order': futures_order,
                'expected_profit': self.binance.calculate_expected_profit(symbol, size, funding_rate)
            }
            
            self.daily_trades += 1
            self._save_state()
            
            # Print live update with actual balance
            self.reports.print_live_updates(self.binance.get_balance())
            
            logger.info(f"Opened position for {symbol}")
            logger.info(f"Funding rate: {funding_rate*100:.4f}%")
            logger.info(f"Expected profit: {self.active_positions[symbol]['expected_profit']:.2f} USDT")
            
        except Exception as e:
            logger.error(f"Trade execution failed for {symbol}: {str(e)}")
            # Try to close any partially opened positions
            self._handle_failed_trade(symbol)
            
    def _handle_failed_trade(self, symbol: str):
        """Handle a failed trade by closing any partially opened positions."""
        try:
            # Check if we have a spot position
            spot_position = self.binance.get_position(symbol)
            if spot_position and float(spot_position.get('size', 0)) > 0:
                self.binance.create_spot_order(
                    symbol=symbol,
                    order_type='MARKET',
                    side='SELL',
                    amount=float(spot_position['size'])  # Already in asset terms
                )
                logger.info(f"Closed partial spot position for {symbol}")
                
            # Check if we have a futures position
            futures_position = self.binance.get_position(symbol)
            if futures_position and float(futures_position.get('futures_size', 0)) > 0:
                self.binance.create_futures_order(
                    symbol=symbol,
                    order_type='MARKET',
                    side='BUY',
                    amount=float(futures_position['futures_size'])  # Already in asset terms
                )
                logger.info(f"Closed partial futures position for {symbol}")
                
        except Exception as e:
            logger.error(f"Error handling failed trade for {symbol}: {str(e)}")

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
        # Only close if we have a spot position and size > 0
        spot_position = self.binance.get_position(symbol)
        if not spot_position or spot_position.get('size', 0) <= 0:
            logger.warning(f"No spot position to close for {symbol}")
            # Clean up the position from our tracking
            del self.active_positions[symbol]
            self._save_state()
            return
        try:
            # Close spot position (always market order)
            spot_order = self.binance.create_spot_order(
                symbol=symbol,
                order_type='MARKET',
                side='SELL',
                amount=position['spot_size']  # Already in asset terms
            )
            # Record spot close
            self.reports.record_trade({
                'symbol': symbol,
                'type': 'CLOSE',
                'side': 'SELL',
                'amount': position['spot_size'] * spot_order['price'],  # Convert to USDT for reporting
                'price': spot_order['price'],
                'fees': spot_order['fee'],
                'profit': (spot_order['price'] - position['spot_order']['price']) * position['spot_size'] - spot_order['fee']
            })
            # Close futures position (let exchange client decide based on price advantage)
            futures_order = self.binance.create_futures_order(
                symbol=symbol,
                order_type='MARKET',  # This will be overridden if limit order is possible
                side='BUY',
                amount=position['futures_size']  # Already in asset terms
            )
            # Record futures close
            self.reports.record_trade({
                'symbol': symbol,
                'type': 'CLOSE',
                'side': 'BUY',
                'amount': position['futures_size'] * futures_order['price'],  # Convert to USDT for reporting
                'price': futures_order['price'],
                'fees': futures_order['fee'],
                'profit': (position['futures_order']['price'] - futures_order['price']) * position['futures_size'] - futures_order['fee']
            })
            logger.info(f"Closed position for {symbol}")
            logger.info(f"Expected profit: {position['expected_profit']:.2f} USDT")
            # Print live update with actual balance
            self.reports.print_live_updates(self.binance.get_balance())
            # Clean up the position
            del self.active_positions[symbol]
            self._save_state()
        except Exception as e:
            logger.error(f"Failed to close position for {symbol}: {str(e)}")
            # If we get an error about insufficient position, clean up our tracking
            if "Insufficient spot position" in str(e):
                del self.active_positions[symbol]
                self._save_state()
            
    def run(self):
        """Main bot loop."""
        logger.info("Starting Funding Rate Arbitrage Bot")
        
        def signal_handler(signum, frame):
            logger.info("Shutting down...")
            if self.active_positions:
                logger.info("Closing all open positions...")
                for symbol in list(self.active_positions.keys()):
                    self.close_position(symbol)
                    
            # Generate final performance report
            self.reports.generate_performance_report()
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        while True:
            try:
                logger.info("Starting main loop iteration...")
                self.check_opportunities()
                logger.info("Finished checking opportunities")
                self.monitor_positions()
                logger.info("Finished monitoring positions")
                logger.info(f"Sleeping for {MONITORING_CONFIG['POSITION_CHECK_INTERVAL']} seconds...")
                time.sleep(MONITORING_CONFIG['POSITION_CHECK_INTERVAL'])
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                logger.error(f"Error type: {type(e)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                time.sleep(60)  # Wait a minute before retrying
                
if __name__ == "__main__":
    bot = FundingRateBot()
    bot.run() 