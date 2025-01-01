# Bybit Trading Bot

A Telegram-based trading bot for Bybit cryptocurrency exchange, supporting both testnet and mainnet environments.

## Project Structure

```
bybit_trading_bot/
├── src/                    # Source code
│   ├── bot/               # Bot implementation
│   │   ├── trading.py     # Trading logic
│   │   ├── telegram.py    # Telegram interface
│   │   └── config.py      # Configuration management
│   └── utils/             # Utility functions
├── deploy/                # Deployment configurations
│   ├── aws/              # AWS Lambda deployment
│   │   ├── lambda_function.py
│   │   ├── serverless.yml
│   │   └── set_webhook.py
│   └── server/           # Traditional server deployment
│       ├── bybit_bot.service
│       └── deploy.sh
├── config/               # Configuration files
│   ├── .env.example
│   └── bot_config.json
└── requirements/         # Dependencies
    ├── base.txt         # Common requirements
    ├── dev.txt          # Development requirements
    └── prod.txt         # Production requirements
```

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
# For development:
pip install -r requirements/dev.txt

# For production:
pip install -r requirements/prod.txt
```

4. Create a `.env` file in the config directory:
```bash
cp config/.env.example config/.env
# Edit config/.env with your configuration
```

## Deployment Options

### 1. AWS Lambda (Serverless)

1. Install Serverless Framework:
```bash
npm install -g serverless
npm install --save-dev serverless-python-requirements
```

2. Deploy:
```bash
cd deploy/aws
serverless deploy
```

3. Set up webhook:
```bash
python set_webhook.py https://your-api-url/dev/webhook
```

### 2. Traditional Server

1. Copy service file:
```bash
sudo cp deploy/server/bybit_bot.service /etc/systemd/system/
```

2. Deploy:
```bash
cd deploy/server
./deploy.sh
```

## Usage

1. Start the bot (for local development):
```bash
python -m src.bot.telegram
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

- Never share your `config/.env` file
- Keep your API keys secure
- Use testnet for testing
- Set appropriate API key permissions in Bybit

## License

MIT License 