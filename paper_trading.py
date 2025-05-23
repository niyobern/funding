import time
from typing import Dict, Optional, List
from loguru import logger
import random
from config import TRADING_CONFIG
from exchange_clients import BinanceClient

class PaperTradingClient:
    def __init__(self, initial_balance: float = 1000.0):
        self.balance = initial_balance
        self.positions: Dict[str, Dict] = {}
        self.order_history: List[Dict] = []
        # Use real Binance client for market data
        self.real_binance = BinanceClient()
        
    def get_funding_rate(self, symbol: str) -> float:
        """Get real funding rate from Binance."""
        return self.real_binance.get_funding_rate(symbol)
        
    def get_order_book(self, symbol: str, limit: int = 10) -> Dict:
        """Get real order book from Binance."""
        return self.real_binance.get_order_book(symbol, limit)
        
    def get_best_maker_price(self, symbol: str, side: str) -> Optional[float]:
        """Get real best maker price from Binance."""
        return self.real_binance.get_best_maker_price(symbol, side)
        
    def create_spot_order(self, symbol: str, order_type: str, side: str, 
                         amount: float, price: Optional[float] = None) -> Dict:
        """Simulate creating a spot order."""
        # Get real price from Binance
        order_price = price or self.get_best_maker_price(symbol, side)
        
        # Calculate fees based on real rates
        fee_rate = 0.00075  # 0.075% with BNB
        
        # Handle amount conversion
        # If amount is very small (< 0.1), assume it's already in asset terms
        # Otherwise, assume it's in USDT and convert to asset terms
        if amount > 0.1:  # This is likely USDT amount
            asset_amount = amount / order_price if side == 'BUY' else amount
        else:  # This is likely already in asset terms
            asset_amount = amount
            
        fee = asset_amount * order_price * fee_rate
        
        order = {
            'id': f"paper_spot_{len(self.order_history)}",
            'symbol': symbol,
            'type': order_type,
            'side': side,
            'amount': asset_amount,  # Store in asset terms
            'price': order_price,
            'fee': fee,
            'timestamp': int(time.time() * 1000),
            'status': 'closed'
        }
        
        # Update balance and track position
        if side == 'BUY':
            total_cost = (asset_amount * order_price) + fee
            if total_cost > self.balance:
                raise ValueError(f"Insufficient balance: {self.balance} USDT, needed: {total_cost} USDT")
            self.balance -= total_cost
            
            # Track spot position in asset terms
            if symbol not in self.positions:
                self.positions[symbol] = {'spot': 0, 'futures': 0}
            self.positions[symbol]['spot'] = asset_amount  # Store exact amount
            
        else:  # SELL
            if symbol not in self.positions or self.positions[symbol]['spot'] < asset_amount:
                raise ValueError(f"Insufficient spot position: {asset_amount} {symbol}")
            
            self.balance += (asset_amount * order_price) - fee
            self.positions[symbol]['spot'] = 0  # Clear position
            
            # Clean up empty positions
            if self.positions[symbol]['spot'] == 0 and self.positions[symbol]['futures'] == 0:
                del self.positions[symbol]
            
        self.order_history.append(order)
        logger.info(f"Paper trading: Created {side} spot order for {symbol}: {asset_amount} @ {order_price} (fee: {fee:.2f} USDT)")
        logger.info(f"Current balance: {self.balance:.2f} USDT")
        return order
        
    def create_futures_order(self, symbol: str, order_type: str, side: str, 
                           amount: float, price: Optional[float] = None) -> Dict:
        """Simulate creating a futures order."""
        # Get real price from Binance
        order_price = price or self.get_best_maker_price(symbol, side)
        
        # Calculate fees based on real rates
        fee_rate = 0.0004  # 0.04% taker fee
        
        # Convert USDT amount to asset amount for futures orders
        asset_amount = amount / order_price
        fee = asset_amount * order_price * fee_rate
        
        order = {
            'id': f"paper_futures_{len(self.order_history)}",
            'symbol': symbol,
            'type': order_type,
            'side': side,
            'amount': asset_amount,  # Store in asset terms
            'price': order_price,
            'fee': fee,
            'timestamp': int(time.time() * 1000),
            'status': 'closed'
        }
        
        # Track futures position
        if symbol not in self.positions:
            self.positions[symbol] = {'spot': 0, 'futures': 0}
            
        if side == 'SELL':
            self.positions[symbol]['futures'] = asset_amount  # Store exact amount
        else:  # BUY
            if self.positions[symbol]['futures'] < asset_amount:
                raise ValueError(f"Insufficient futures position: {asset_amount} {symbol}")
            self.positions[symbol]['futures'] = 0  # Clear position
            
        # Clean up empty positions
        if self.positions[symbol]['spot'] == 0 and self.positions[symbol]['futures'] == 0:
            del self.positions[symbol]
            
        self.order_history.append(order)
        logger.info(f"Paper trading: Created {side} futures order for {symbol}: {asset_amount} @ {order_price} (fee: {fee:.2f} USDT)")
        return order
        
    def get_balance(self, currency: str = 'USDT') -> float:
        """Get simulated balance."""
        return self.balance
        
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Simulate setting leverage."""
        logger.info(f"Paper trading: Set leverage for {symbol} to {leverage}x")
        return True
        
    def get_position(self, symbol: str) -> Dict:
        """Get simulated position."""
        if symbol not in self.positions:
            return {}
        return {
            'symbol': symbol,
            'size': self.positions[symbol]['spot'],  # Already in asset terms
            'futures_size': self.positions[symbol]['futures']  # Already in asset terms
        }
        
    def check_liquidity(self, symbol: str, min_liquidity: float = None) -> bool:
        """Check real liquidity from Binance."""
        return self.real_binance.check_liquidity(symbol, min_liquidity)
        
    def get_funding_rate_history(self, symbol: str, limit: int = 10) -> List[Dict]:
        """Get real funding rate history from Binance."""
        return self.real_binance.get_funding_rate_history(symbol, limit)
        
    def calculate_profitability_analysis(self, symbol: str, position_size: float) -> Dict:
        """Calculate real profitability analysis using Binance data."""
        return self.real_binance.calculate_profitability_analysis(symbol, position_size)
        
    def should_exit_position(self, symbol: str, position: Dict) -> bool:
        from config import TRADING_CONFIG  # Ensure always available
        current_rate = self.get_funding_rate(symbol)
        entry_rate = position.get('entry_rate', 0)
        
        # Exit if funding rate has improved significantly
        if current_rate > entry_rate * 0.5:  # If rate has improved by 50%
            logger.info(f"Exiting {symbol} position: funding rate improved from {entry_rate*100:.4f}% to {current_rate*100:.4f}%")
            return True
            
        # Exit if funding rate has normalized (close to zero)
        if current_rate >= -0.00005:  # -0.005%
            logger.info(f"Exiting {symbol} position: funding rate normalized to {current_rate*100:.4f}%")
            return True
            
        # Exit if position has been open too long
        position_age = time.time() - position.get('entry_time', 0)
        if position_age > TRADING_CONFIG['MAX_POSITION_DURATION']:
            logger.info(f"Exiting {symbol} position: reached maximum duration of {TRADING_CONFIG['MAX_POSITION_DURATION']/3600:.1f} hours")
            return True
            
        return False
        
    def calculate_expected_profit(self, symbol: str, position_size: float, 
                                current_rate: float) -> float:
        """Calculate real expected profit using Binance data."""
        return self.real_binance.calculate_expected_profit(symbol, position_size, current_rate) 