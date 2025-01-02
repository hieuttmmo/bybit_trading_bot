import json
import os
import shutil
from pathlib import Path

class ConfigManager:
    """Manage bot configuration."""
    
    def __init__(self, config_file=None):
        """Initialize with optional specific config file path."""
        self.config_file = Path(config_file) if config_file else Path(__file__).parent.parent.parent / 'config' / 'bot_config.json'
        
        # Create config directory if it doesn't exist
        os.makedirs(self.config_file.parent, exist_ok=True)
        
        # If config file doesn't exist in config dir, try to copy from root
        if not self.config_file.exists():
            root_config = Path(__file__).parent.parent.parent / 'bot_config.json'
            if root_config.exists():
                shutil.copy(root_config, self.config_file)
                print(f"Copied bot_config.json from {root_config} to {self.config_file}")
        
        self._load_config()
    
    def _load_config(self):
        """Load configuration from file."""
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
                
            # Ensure trading params exist with defaults
            if 'trading_params' not in self.config:
                self.config['trading_params'] = {}
            
            # Set defaults if not present
            trading_params = self.config['trading_params']
            if 'leverage' not in trading_params:
                trading_params['leverage'] = 5
            if 'balance_percentage' not in trading_params:
                trading_params['balance_percentage'] = 0.1
                
            # Save if we added any defaults
            self._save_config()
                
        except FileNotFoundError:
            self.config = {
                'environment': 'testnet',
                'trading_params': {
                    'leverage': 5,
                    'balance_percentage': 0.1
                }
            }
            self._save_config()
    
    def _save_config(self):
        """Save configuration to file."""
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)
    
    def get_environment(self) -> str:
        """Get current environment (testnet/mainnet)."""
        return self.config.get('environment', 'testnet')
    
    def switch_environment(self, use_testnet: bool):
        """Switch between testnet and mainnet."""
        self.config['environment'] = 'testnet' if use_testnet else 'mainnet'
        self._save_config()
    
    def get_trading_params(self) -> dict:
        """Get trading parameters with defaults."""
        params = self.config.get('trading_params', {})
        return {
            'leverage': params.get('leverage', 5),
            'balance_percentage': params.get('balance_percentage', 0.1)
        }
    
    def set_trading_params(self, leverage=None, balance_percentage=None):
        """Set trading parameters."""
        if 'trading_params' not in self.config:
            self.config['trading_params'] = {}
        
        if leverage is not None:
            self.config['trading_params']['leverage'] = leverage
        
        if balance_percentage is not None:
            self.config['trading_params']['balance_percentage'] = balance_percentage
        
        self._save_config()
        return True
    
    def get_active_api_keys(self) -> tuple:
        """Get active API keys based on environment."""
        env = self.get_environment()
        if env == 'testnet':
            api_key = os.getenv('TESTNET_API_KEY')
            api_secret = os.getenv('TESTNET_API_SECRET')
        else:
            api_key = os.getenv('MAINNET_API_KEY')
            api_secret = os.getenv('MAINNET_API_SECRET')
        return api_key, api_secret
    
    def set_api_keys(self, api_key: str, api_secret: str, is_testnet: bool) -> bool:
        """Set API keys in environment file."""
        env_file = Path(self.config_file).parent / '.env'
        
        try:
            # Read current env file
            if env_file.exists():
                with open(env_file, 'r') as f:
                    lines = f.readlines()
            else:
                lines = []
            
            # Update or add API keys
            prefix = 'TESTNET_' if is_testnet else 'MAINNET_'
            key_updated = False
            secret_updated = False
            
            for i, line in enumerate(lines):
                if line.startswith(f'{prefix}API_KEY='):
                    lines[i] = f'{prefix}API_KEY={api_key}\n'
                    key_updated = True
                elif line.startswith(f'{prefix}API_SECRET='):
                    lines[i] = f'{prefix}API_SECRET={api_secret}\n'
                    secret_updated = True
            
            # Add new lines if not updated
            if not key_updated:
                lines.append(f'{prefix}API_KEY={api_key}\n')
            if not secret_updated:
                lines.append(f'{prefix}API_SECRET={api_secret}\n')
            
            # Write back to file
            os.makedirs(os.path.dirname(env_file), exist_ok=True)
            with open(env_file, 'w') as f:
                f.writelines(lines)
            
            return True
        except Exception as e:
            print(f"Error setting API keys: {str(e)}")
            return False 