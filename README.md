# Bybit Trading Bot

A Telegram-based trading bot for Bybit cryptocurrency exchange, supporting both testnet and mainnet environments.

## Features

- Telegram bot interface for easy trading
- Support for LONG and SHORT positions
- Market and limit orders
- Multiple take-profit levels
- Stop loss orders
- Position management (view, close individual or all positions)
- Real-time trading status and history
- Environment switching (testnet/mainnet)
- Configurable leverage and position sizing

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/bybit_trading_bot.git
cd bybit_trading_bot
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with your configuration:
```env
# Telegram Bot Configuration
TELEGRAM_TOKEN=your_telegram_bot_token
ALLOWED_TELEGRAM_USERS=your_telegram_user_id

# Bybit API Configuration
TESTNET_API_KEY=your_testnet_api_key
TESTNET_API_SECRET=your_testnet_api_secret
MAINNET_API_KEY=your_mainnet_api_key
MAINNET_API_SECRET=your_mainnet_api_secret
```

## Usage

1. Start the bot:
```bash
python telegram_bot.py
```

2. Open your Telegram client and start chatting with the bot.

3. Use the following format for trading instructions:
```
LONG/SHORT $SYMBOL
Entry <price>  (use 0 for market price)
Stl <price>
Tp <price1> - <price2> - ...
```

Example:
```
LONG $BTC
Entry 43500
Stl 42800
Tp 44000 - 44500 - 45000
```

## Configuration

The bot supports various configuration options through the Telegram interface:
- Switch between testnet and mainnet
- Set leverage (1-20x)
- Set position size (% of balance)
- Configure API keys

## Security

- Never share your `.env` file
- Keep your API keys secure
- Use testnet for testing
- Set appropriate API key permissions in Bybit

## License

MIT License 