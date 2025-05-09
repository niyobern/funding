import ccxt
from typing import Dict, Optional, Tuple, List
import time
from loguru import logger
from config import BINANCE_API_KEY, BINANCE_API_SECRET, TRADING_CONFIG

class BinanceClient:
    def __init__(self):
        # Initialize spot client
        self.spot = ccxt.binance({
            'apiKey': BINANCE_API_KEY,
            'secret': BINANCE_API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'useSpotWallet': True,
                'useBNBFees': TRADING_CONFIG['USE_BNB_FEES'],
            }
        })
        
        # Initialize futures client
        self.futures = ccxt.binance({
            'apiKey': BINANCE_API_KEY,
            'secret': BINANCE_API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
            }
        })
        
    def get_funding_rate(self, symbol: str) -> float:
        """Get the current funding rate for a symbol."""
        try:
            ticker = self.futures.fetch_ticker(symbol)
            return float(ticker.get('fundingRate', 0))
        except Exception as e:
            logger.error(f"Error fetching funding rate for {symbol}: {str(e)}")
            return 0.0
            
    def get_order_book(self, symbol: str, limit: int = 10) -> Dict:
        """Get the order book for a symbol."""
        try:
            return self.spot.fetch_order_book(symbol, limit)
        except Exception as e:
            logger.error(f"Error fetching order book for {symbol}: {str(e)}")
            return {'bids': [], 'asks': []}
            
    def get_best_maker_price(self, symbol: str, side: str) -> Optional[float]:
        """Get the best price for a maker order."""
        try:
            order_book = self.get_order_book(symbol)
            if side == 'BUY':
                # For buy orders, we need to be below the best ask
                return float(order_book['asks'][0][0]) * 0.999  # 0.1% below best ask
            else:
                # For sell orders, we need to be above the best bid
                return float(order_book['bids'][0][0]) * 1.001  # 0.1% above best bid
        except Exception as e:
            logger.error(f"Error getting best maker price for {symbol}: {str(e)}")
            return None
            
    def create_spot_order(self, symbol: str, order_type: str, side: str, 
                         amount: float, price: Optional[float] = None) -> Dict:
        """Create a spot order."""
        try:
            # Always use market orders for spot
            return self.spot.create_order(
                symbol=symbol,
                type='MARKET',
                side=side,
                amount=amount
            )
        except Exception as e:
            logger.error(f"Error creating spot order for {symbol}: {str(e)}")
            return {}
            
    def create_futures_order(self, symbol: str, order_type: str, side: str, 
                           amount: float, price: Optional[float] = None) -> Dict:
        """Create a futures order."""
        try:
            # Always use market orders for futures to ensure reliable execution
            return self.futures.create_order(
                symbol=symbol,
                type='MARKET',
                side=side,
                amount=amount
            )
        except Exception as e:
            logger.error(f"Error creating futures order for {symbol}: {str(e)}")
            return {}
            
    def get_balance(self, currency: str = 'USDT') -> float:
        """Get the balance for a specific currency."""
        try:
            balance = self.spot.fetch_balance()
            return float(balance.get(currency, {}).get('free', 0))
        except Exception as e:
            logger.error(f"Error fetching balance for {currency}: {str(e)}")
            return 0.0
            
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set the leverage for a symbol."""
        try:
            self.futures.set_leverage(leverage, symbol)
            return True
        except Exception as e:
            logger.error(f"Error setting leverage for {symbol}: {str(e)}")
            return False
            
    def get_position(self, symbol: str) -> Dict:
        """Get the current position for a symbol."""
        try:
            positions = self.futures.fetch_positions([symbol])
            return positions[0] if positions else {}
        except Exception as e:
            logger.error(f"Error fetching position for {symbol}: {str(e)}")
            return {}
            
    def check_liquidity(self, symbol: str, min_liquidity: float = None) -> bool:
        """Check if there's sufficient liquidity for trading."""
        if min_liquidity is None:
            min_liquidity = TRADING_CONFIG['MIN_LIQUIDITY']
            
        order_book = self.get_order_book(symbol)
        bids = order_book.get('bids', [])
        asks = order_book.get('asks', [])
        
        if not bids or not asks:
            return False
            
        bid_liquidity = sum(float(bid[1]) for bid in bids[:10])
        ask_liquidity = sum(float(ask[1]) for ask in asks[:10])
        
        return min(bid_liquidity, ask_liquidity) >= min_liquidity
        
    def get_funding_rate_history(self, symbol: str, limit: int = 10) -> List[Dict]:
        """Get historical funding rates for a symbol."""
        try:
            return self.futures.fetch_funding_rate_history(symbol, limit=limit)
        except Exception as e:
            logger.error(f"Error fetching funding rate history for {symbol}: {str(e)}")
            return []
            
    def calculate_profitability_analysis(self, symbol: str, position_size: float) -> Dict:
        """Calculate detailed profitability analysis for a position."""
        try:
            # Get historical funding rates
            history = self.get_funding_rate_history(symbol, limit=30)  # Last 30 periods
            if not history:
                return {
                    'error': 'No funding rate history available',
                    'profitable': False
                }
            
            # Calculate average and min funding rates
            rates = [float(rate['fundingRate']) for rate in history]
            avg_rate = sum(rates) / len(rates)
            min_rate = min(rates)
            
            # Calculate expected funding payments
            days_to_hold = TRADING_CONFIG['MAX_POSITION_DURATION'] / (24 * 3600)
            expected_payments = days_to_hold * 3  # 3 payments per day
            
            # Calculate trading fees
            spot_fee = 0.00075  # 0.075% with BNB
            futures_fee = 0.0004  # 0.04% taker fee
            total_fees = position_size * (spot_fee + futures_fee) * 2  # *2 for entry and exit
            
            # Calculate break-even funding rate
            break_even_rate = total_fees / (position_size * expected_payments)
            
            # Calculate worst-case scenario (funding rate rises after 1 payment)
            worst_case_payments = 1
            worst_case_profit = position_size * abs(min_rate) * worst_case_payments
            worst_case_net = worst_case_profit - total_fees
            
            # Calculate how many payments needed to break even
            payments_to_breakeven = total_fees / (position_size * abs(min_rate))
            
            return {
                'position_size': position_size,
                'avg_funding_rate': avg_rate,
                'min_funding_rate': min_rate,
                'expected_payments': expected_payments,
                'expected_funding_profit': position_size * abs(min_rate) * expected_payments,
                'total_fees': total_fees,
                'break_even_rate': break_even_rate,
                'payments_to_breakeven': payments_to_breakeven,
                'worst_case_profit': worst_case_profit,
                'worst_case_net': worst_case_net,
                'profitable': worst_case_net > 0,  # Only profitable if we can break even in worst case
                'days_to_hold': days_to_hold
            }
            
        except Exception as e:
            logger.error(f"Error calculating profitability analysis: {str(e)}")
            return {
                'error': str(e),
                'profitable': False
            }
            
    def should_exit_position(self, symbol: str, position: Dict) -> bool:
        """Determine if we should exit a position based on current conditions."""
        try:
            current_rate = self.get_funding_rate(symbol)
            entry_rate = position['entry_rate']
            entry_time = position['entry_time']
            current_time = time.time()
            
            # Get profitability analysis
            analysis = self.calculate_profitability_analysis(symbol, position['spot_size'])
            
            # Calculate how many funding payments we've received
            hours_held = (current_time - entry_time) / 3600
            payments_received = int(hours_held / 8)  # Funding payments every 8 hours
            
            # Calculate current profit
            current_profit = position['spot_size'] * abs(entry_rate) * payments_received
            
            # If we haven't received enough payments to break even
            if payments_received < analysis['payments_to_breakeven']:
                # Exit if funding rate has improved significantly
                if current_rate > entry_rate * 0.5:  # Funding rate has improved by 50%
                    logger.warning(f"Exiting {symbol} early: Funding rate improved before break-even")
                    logger.warning(f"Current rate: {current_rate*100:.4f}%, Entry rate: {entry_rate*100:.4f}%")
                    logger.warning(f"Payments received: {payments_received}, Needed: {analysis['payments_to_breakeven']:.1f}")
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"Error checking exit conditions: {str(e)}")
            return False
            
    def calculate_expected_profit(self, symbol: str, position_size: float, 
                                current_rate: float) -> float:
        """Calculate expected profit from funding rate payments."""
        try:
            analysis = self.calculate_profitability_analysis(symbol, position_size)
            return analysis.get('net_profit', 0.0)
        except Exception as e:
            logger.error(f"Error calculating expected profit for {symbol}: {str(e)}")
            return 0.0 