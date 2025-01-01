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

# Copy service file
sudo cp bybit_bot.service /etc/systemd/system/

# Create .env file
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Please edit .env file with your configuration"
    nano .env
fi

# Set proper permissions
chmod +x telegram_bot.py
chmod +x bybit_trading_bot.py

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable bybit_bot
sudo systemctl start bybit_bot

# Show status
sudo systemctl status bybit_bot

echo "Deployment complete! Check the status above."
echo "Use 'sudo systemctl status bybit_bot' to check status"
echo "Use 'sudo journalctl -u bybit_bot -f' to view logs" 