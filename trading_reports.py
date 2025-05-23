import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
from loguru import logger
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

class TradingReports:
    def __init__(self, reports_dir: str = "reports"):
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(exist_ok=True)
        self.trades_file = self.reports_dir / "trades.json"
        self.performance_file = self.reports_dir / "performance.json"
        self.trades: List[Dict] = []
        self.performance: Dict = {
            'initial_balance': 0,
            'current_balance': 0,
            'total_profit': 0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_fees': 0,
            'max_drawdown': 0,
            'daily_profits': {},
            'trade_history': []
        }
        self._load_data()
        
    def _load_data(self):
        """Load existing trade and performance data."""
        if self.trades_file.exists():
            with open(self.trades_file, 'r') as f:
                self.trades = json.load(f)
                
        if self.performance_file.exists():
            with open(self.performance_file, 'r') as f:
                self.performance = json.load(f)
                
    def _save_data(self):
        """Save trade and performance data."""
        with open(self.trades_file, 'w') as f:
            json.dump(self.trades, f, indent=2)
            
        with open(self.performance_file, 'w') as f:
            json.dump(self.performance, f, indent=2)
            
    def record_trade(self, trade_data: Dict):
        """Record a new trade."""
        trade = {
            'id': len(self.trades),
            'timestamp': datetime.now().isoformat(),
            'symbol': trade_data['symbol'],
            'type': trade_data['type'],  # 'OPEN' or 'CLOSE'
            'side': trade_data['side'],
            'amount': trade_data['amount'],
            'price': trade_data['price'],
            'fees': trade_data['fees'],
            'funding_rate': trade_data.get('funding_rate', 0),
            'profit': trade_data.get('profit', 0)
        }
        
        self.trades.append(trade)
        self._update_performance(trade)
        self._save_data()
        
    def _update_performance(self, trade: Dict):
        """Update performance metrics based on new trade."""
        if trade['type'] == 'OPEN':
            self.performance['total_trades'] += 1
            self.performance['total_fees'] += trade['fees']
            
        elif trade['type'] == 'CLOSE':
            profit = trade['profit']
            self.performance['total_profit'] += profit
            self.performance['current_balance'] += profit
            
            if profit > 0:
                self.performance['winning_trades'] += 1
            else:
                self.performance['losing_trades'] += 1
                
            # Update daily profits
            date = datetime.fromisoformat(trade['timestamp']).date().isoformat()
            self.performance['daily_profits'][date] = self.performance['daily_profits'].get(date, 0) + profit
            
            # Update max drawdown
            if self.performance['current_balance'] < self.performance['initial_balance']:
                drawdown = (self.performance['initial_balance'] - self.performance['current_balance']) / self.performance['initial_balance']
                self.performance['max_drawdown'] = max(self.performance['max_drawdown'], drawdown)
                
        # Record trade in history
        self.performance['trade_history'].append(trade)
        
    def set_initial_balance(self, balance: float):
        """Set the initial balance for performance tracking."""
        self.performance['initial_balance'] = balance
        self.performance['current_balance'] = balance
        self._save_data()
        
    def get_performance_summary(self) -> Dict:
        """Get a summary of trading performance."""
        if self.performance['total_trades'] == 0:
            return {
                'status': 'No trades executed yet',
                'initial_balance': self.performance['initial_balance'],
                'current_balance': self.performance['current_balance']
            }
            
        win_rate = (self.performance['winning_trades'] / self.performance['total_trades']) * 100
        
        return {
            'initial_balance': self.performance['initial_balance'],
            'current_balance': self.performance['current_balance'],
            'total_profit': self.performance['total_profit'],
            'total_trades': self.performance['total_trades'],
            'winning_trades': self.performance['winning_trades'],
            'losing_trades': self.performance['losing_trades'],
            'win_rate': f"{win_rate:.2f}%",
            'total_fees': self.performance['total_fees'],
            'max_drawdown': f"{self.performance['max_drawdown']*100:.2f}%",
            'profit_factor': abs(self.performance['total_profit'] / self.performance['total_fees']) if self.performance['total_fees'] > 0 else 0
        }
        
    def generate_performance_report(self):
        """Generate a detailed performance report with charts."""
        if not self.trades:
            logger.warning("No trades to generate report for")
            return
        # Ensure reports directory exists
        self.reports_dir.mkdir(exist_ok=True)
        # Create report directory
        report_dir = self.reports_dir / datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir.mkdir(exist_ok=True)
        
        # Generate summary
        summary = self.get_performance_summary()
        with open(report_dir / "summary.txt", 'w') as f:
            f.write("Trading Performance Summary\n")
            f.write("=========================\n\n")
            for key, value in summary.items():
                f.write(f"{key.replace('_', ' ').title()}: {value}\n")
                
        # Generate trade history
        df = pd.DataFrame(self.trades)
        df.to_csv(report_dir / "trade_history.csv", index=False)
        
        # Generate charts
        self._generate_charts(df, report_dir)
        
        logger.info(f"Performance report generated in {report_dir}")
        
    def _generate_charts(self, df: pd.DataFrame, report_dir: Path):
        """Generate performance charts."""
        # Set style
        sns.set_style("whitegrid")
        plt.rcParams['figure.figsize'] = [12, 6]
        
        # Daily P&L
        df['date'] = pd.to_datetime(df['timestamp']).dt.date
        daily_pnl = df[df['type'] == 'CLOSE'].groupby('date')['profit'].sum()
        
        plt.figure()
        daily_pnl.plot(kind='bar')
        plt.title('Daily Profit/Loss')
        plt.xlabel('Date')
        plt.ylabel('Profit/Loss (USDT)')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(report_dir / "daily_pnl.png")
        plt.close()
        
        # Cumulative P&L
        plt.figure()
        daily_pnl.cumsum().plot()
        plt.title('Cumulative Profit/Loss')
        plt.xlabel('Date')
        plt.ylabel('Cumulative Profit/Loss (USDT)')
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(report_dir / "cumulative_pnl.png")
        plt.close()
        
        # Trade distribution by symbol
        plt.figure()
        df[df['type'] == 'CLOSE']['symbol'].value_counts().plot(kind='pie', autopct='%1.1f%%')
        plt.title('Trade Distribution by Symbol')
        plt.tight_layout()
        plt.savefig(report_dir / "trade_distribution.png")
        plt.close()
        
    def print_live_updates(self, current_balance=None):
        """Print live trading updates."""
        if not self.trades:
            return
        latest_trade = self.trades[-1]
        summary = self.get_performance_summary()
        logger.info("\n=== Live Trading Update ===")
        logger.info(f"Latest Trade: {latest_trade['symbol']} {latest_trade['type']} {latest_trade['side']}")
        logger.info(f"Amount: {latest_trade['amount']} @ {latest_trade['price']}")
        logger.info(f"Fees: {latest_trade['fees']} USDT")
        if current_balance is not None:
            logger.info(f"Current Balance: {current_balance:.2f} USDT")
        else:
            logger.info(f"Current Balance: {summary['current_balance']:.2f} USDT")
        logger.info(f"Total Profit: {summary['total_profit']:.2f} USDT")
        logger.info(f"Win Rate: {summary['win_rate']}")
        logger.info("========================") 