import time
from typing import Dict, Optional, List
from loguru import logger
import random

class PaperTradingClient:
    def __init__(self, initial_balance: float = 1000.0):
        self.balance = initial_balance
        self.positions: Dict[str, Dict] = {}
        self.order_history: List[Dict] = []
        self.funding_rates: Dict[str, float] = {}
        
    def get_funding_rate(self, symbol: str) -> float:
        """Simulate getting funding rate with some randomness."""
        if symbol not in self.funding_rates:
            # Simulate a funding rate between -0.1% and -0.5%
            self.funding_rates[symbol] = random.uniform(-0.005, -0.001)
        return self.funding_rates[symbol]
        
    def get_order_book(self, symbol: str, limit: int = 10) -> Dict:
        """Simulate order book with reasonable spreads."""
        price = 100.0  # Simulated base price
        spread = price * 0.001  # 0.1% spread
        
        bids = [[price - spread, 1.0] for _ in range(limit)]
        asks = [[price + spread, 1.0] for _ in range(limit)]
        
        return {'bids': bids, 'asks': asks}
        
    def get_best_maker_price(self, symbol: str, side: str) -> Optional[float]:
        """Get simulated best maker price."""
        order_book = self.get_order_book(symbol)
        if side == 'BUY':
            return float(order_book['asks'][0][0]) * 0.999
        else:
            return float(order_book['bids'][0][0]) * 1.001
            
    def create_spot_order(self, symbol: str, order_type: str, side: str, 
                         amount: float, price: Optional[float] = None) -> Dict:
        """Simulate creating a spot order."""
        order_price = price or self.get_best_maker_price(symbol, side)
        
        # Calculate fees
        fee_rate = 0.00075  # 0.075% with BNB
        fee = amount * order_price * fee_rate
        
        # Convert USDT amount to asset amount for spot orders
        asset_amount = amount / order_price if side == 'BUY' else amount
        
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
            self.positions[symbol]['spot'] += asset_amount
            
        else:  # SELL
            if symbol not in self.positions or self.positions[symbol]['spot'] < asset_amount:
                raise ValueError(f"Insufficient spot position: {asset_amount} {symbol}")
            
            self.balance += (asset_amount * order_price) - fee
            self.positions[symbol]['spot'] -= asset_amount
            
            # Clean up empty positions
            if self.positions[symbol]['spot'] == 0 and self.positions[symbol]['futures'] == 0:
                del self.positions[symbol]
            
        self.order_history.append(order)
        logger.info(f"Paper trading: Created {side} spot order for {symbol}: {asset_amount} @ {order_price} (fee: {fee:.2f} USDT)")
        return order
        
    def create_futures_order(self, symbol: str, order_type: str, side: str, 
                           amount: float, price: Optional[float] = None) -> Dict:
        """Simulate creating a futures order."""
        order_price = price or self.get_best_maker_price(symbol, side)
        
        # Calculate fees
        fee_rate = 0.0004  # 0.04% taker fee
        fee = amount * order_price * fee_rate
        
        order = {
            'id': f"paper_futures_{len(self.order_history)}",
            'symbol': symbol,
            'type': order_type,
            'side': side,
            'amount': amount,
            'price': order_price,
            'fee': fee,
            'timestamp': int(time.time() * 1000),
            'status': 'closed'
        }
        
        # Track futures position
        if symbol not in self.positions:
            self.positions[symbol] = {'spot': 0, 'futures': 0}
            
        if side == 'SELL':
            self.positions[symbol]['futures'] += amount
        else:  # BUY
            if self.positions[symbol]['futures'] < amount:
                raise ValueError(f"Insufficient futures position: {amount} {symbol}")
            self.positions[symbol]['futures'] -= amount
            
        # Clean up empty positions
        if self.positions[symbol]['spot'] == 0 and self.positions[symbol]['futures'] == 0:
            del self.positions[symbol]
            
        self.order_history.append(order)
        logger.info(f"Paper trading: Created {side} futures order for {symbol}: {amount} @ {order_price} (fee: {fee:.2f} USDT)")
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
            'size': self.positions[symbol]['spot'],
            'futures_size': self.positions[symbol]['futures']
        }
        
    def check_liquidity(self, symbol: str, min_liquidity: float = None) -> bool:
        """Simulate liquidity check."""
        return True  # Always return True in paper trading
        
    def get_funding_rate_history(self, symbol: str, limit: int = 10) -> List[Dict]:
        """Get simulated funding rate history."""
        current_rate = self.get_funding_rate(symbol)
        history = []
        for i in range(limit):
            history.append({
                'fundingRate': current_rate * (1 + random.uniform(-0.1, 0.1)),
                'timestamp': int(time.time() * 1000) - (i * 8 * 3600 * 1000)  # 8 hours apart
            })
        return history
        
    def calculate_profitability_analysis(self, symbol: str, position_size: float) -> Dict:
        """Calculate simulated profitability analysis."""
        current_rate = self.get_funding_rate(symbol)
        history = self.get_funding_rate_history(symbol, 30)
        rates = [float(rate['fundingRate']) for rate in history]
        avg_rate = sum(rates) / len(rates)
        min_rate = min(rates)
        
        # Simulate fees
        spot_fee = 0.00075
        futures_fee = 0.0004
        total_fees = position_size * (spot_fee + futures_fee) * 2
        
        # Calculate expected profit
        expected_payments = 9  # 3 payments per day for 3 days
        expected_profit = position_size * abs(min_rate) * expected_payments
        
        return {
            'position_size': position_size,
            'avg_funding_rate': avg_rate,
            'min_funding_rate': min_rate,
            'expected_payments': expected_payments,
            'expected_funding_profit': expected_profit,
            'total_fees': total_fees,
            'break_even_rate': total_fees / (position_size * expected_payments),
            'payments_to_breakeven': total_fees / (position_size * abs(min_rate)),
            'worst_case_profit': position_size * abs(min_rate),
            'worst_case_net': position_size * abs(min_rate) - total_fees,
            'profitable': True,
            'days_to_hold': 3
        }
        
    def should_exit_position(self, symbol: str, position: Dict) -> bool:
        """Simulate position exit check."""
        current_rate = self.get_funding_rate(symbol)
        entry_rate = position['entry_rate']
        
        # Simulate random market conditions
        if random.random() < 0.1:  # 10% chance of exit signal
            return True
            
        return current_rate > entry_rate * 0.5
        
    def calculate_expected_profit(self, symbol: str, position_size: float, 
                                current_rate: float) -> float:
        """Calculate simulated expected profit."""
        analysis = self.calculate_profitability_analysis(symbol, position_size)
        return analysis['expected_funding_profit'] - analysis['total_fees'] 