import os
import json
from typing import Dict, Any
from dotenv import load_dotenv, set_key

class ConfigManager:
    def __init__(self, config_file: str = "bot_config.json"):
        self.config_file = config_file
        self.env_file = ".env"
        self._load_config()

    def _load_config(self):
        """Load configuration from JSON file."""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {
                "use_testnet": True,
                "leverage": 20,
                "balance_percentage": 0.05,
                "active_api": "testnet"  # or "mainnet"
            }
            self._save_config()

    def _save_config(self):
        """Save configuration to JSON file."""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        return self.config

    def update_config(self, key: str, value: Any) -> bool:
        """Update a configuration value."""
        if key in self.config:
            self.config[key] = value
            self._save_config()
            return True
        return False

    def set_api_keys(self, api_key: str, api_secret: str, is_testnet: bool = True) -> bool:
        """Set API keys in .env file."""
        try:
            prefix = "TESTNET_" if is_testnet else "MAINNET_"
            set_key(self.env_file, f"{prefix}BYBIT_API_KEY", api_key)
            set_key(self.env_file, f"{prefix}BYBIT_API_SECRET", api_secret)
            
            # Update active API setting
            self.config["active_api"] = "testnet" if is_testnet else "mainnet"
            self.config["use_testnet"] = is_testnet
            self._save_config()
            
            return True
        except Exception as e:
            print(f"Error setting API keys: {str(e)}")
            return False

    def get_active_api_keys(self) -> tuple:
        """Get currently active API keys."""
        load_dotenv()
        prefix = "TESTNET_" if self.config["use_testnet"] else "MAINNET_"
        api_key = os.getenv(f"{prefix}BYBIT_API_KEY")
        api_secret = os.getenv(f"{prefix}BYBIT_API_SECRET")
        return api_key, api_secret

    def switch_environment(self, use_testnet: bool) -> bool:
        """Switch between testnet and mainnet."""
        try:
            self.config["use_testnet"] = use_testnet
            self.config["active_api"] = "testnet" if use_testnet else "mainnet"
            self._save_config()
            return True
        except Exception as e:
            print(f"Error switching environment: {str(e)}")
            return False

    def get_environment(self) -> str:
        """Get current environment (testnet/mainnet)."""
        return "testnet" if self.config["use_testnet"] else "mainnet"

    def set_trading_params(self, leverage: int = None, balance_percentage: float = None) -> bool:
        """Set trading parameters."""
        try:
            if leverage is not None:
                self.config["leverage"] = leverage
            if balance_percentage is not None:
                self.config["balance_percentage"] = balance_percentage
            self._save_config()
            return True
        except Exception as e:
            print(f"Error setting trading parameters: {str(e)}")
            return False

    def get_trading_params(self) -> Dict[str, Any]:
        """Get current trading parameters."""
        return {
            "leverage": self.config["leverage"],
            "balance_percentage": self.config["balance_percentage"]
        } 