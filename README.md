# Funding Rate Arbitrage Bot

A Python-based trading bot that exploits funding rate arbitrage opportunities on Binance. The bot monitors funding rates across multiple trading pairs and executes spot-futures arbitrage trades when profitable opportunities are identified.

## Features

- Monitors funding rates across multiple trading pairs on Binance
- Executes spot-futures arbitrage trades on the same exchange
- Risk management with position sizing and drawdown limits
- State persistence across restarts
- Comprehensive logging
- Graceful shutdown handling

## Prerequisites

- Python 3.8 or higher
- Binance account with API access (both spot and futures enabled)
- Sufficient balance for trading

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd funding-rate-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root with your Binance API credentials:
```
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_api_secret
```

## Configuration

The bot's behavior can be configured by modifying the parameters in `config.py`:

- `TRADING_CONFIG`: Trading parameters like position sizes, leverage, and funding rate thresholds
- `MONITORING_CONFIG`: Intervals for checking opportunities and monitoring positions
- `TRADING_PAIRS`: List of trading pairs to monitor
- `RISK_CONFIG`: Risk management parameters
- `LOG_CONFIG`: Logging configuration

## Usage

1. Start the bot:
```bash
python funding_bot.py
```

2. Monitor the logs in the console and in the `logs/trading_bot.log` file.

3. To stop the bot, press Ctrl+C. The bot will gracefully close all open positions before shutting down.

## Risk Warning

This bot involves trading with leverage and carries significant risk. Please ensure you understand the risks involved and only trade with funds you can afford to lose. The bot includes risk management features, but they cannot guarantee against losses.

## Disclaimer

This software is for educational purposes only. Use it at your own risk. The authors are not responsible for any financial losses incurred through the use of this software.

## License

MIT License 