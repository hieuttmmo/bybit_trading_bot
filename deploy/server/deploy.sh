#!/bin/bash

# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3-pip python3-venv git

# Create project directory
mkdir -p ~/bybit_trading_bot
cd ~/bybit_trading_bot

# Clone the repository (replace with your repository URL)
git clone https://github.com/yourusername/bybit_trading_bot.git .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create config directory
mkdir -p config

# Create .env file in config directory if it doesn't exist
if [ ! -f config/.env ]; then
    echo "Creating config/.env file..."
    cat > config/.env << EOL
# API Configuration
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here

# Telegram Bot Configuration
TELEGRAM_TOKEN=your_telegram_token_here
ALLOWED_TELEGRAM_USERS=your_telegram_user_id_here

# Environment-specific API Keys
TESTNET_API_KEY=your_testnet_api_key_here
TESTNET_API_SECRET=your_testnet_api_secret_here
MAINNET_API_KEY=your_mainnet_api_key_here
MAINNET_API_SECRET=your_mainnet_api_secret_here
EOL
    echo "Please edit config/.env file with your configuration"
    nano config/.env
fi

# Create bot_config.json if it doesn't exist
if [ ! -f config/bot_config.json ]; then
    echo "Creating config/bot_config.json file..."
    cat > config/bot_config.json << EOL
{
    "environment": "testnet",
    "trading_params": {
        "leverage": 5,
        "balance_percentage": 0.1
    }
}
EOL
fi

# Copy service file
sudo cp deploy/server/bybit_bot.service /etc/systemd/system/

# Set proper permissions
chmod 600 config/.env
chmod 600 config/bot_config.json

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable bybit_bot
sudo systemctl start bybit_bot

# Show status
sudo systemctl status bybit_bot

echo "Deployment complete! Check the status above."
echo "Use 'sudo systemctl status bybit_bot' to check status"
echo "Use 'sudo journalctl -u bybit_bot -f' to view logs"
echo "Configuration files are in the config/ directory:"
echo "- config/.env for API keys and tokens"
echo "- config/bot_config.json for bot settings" 