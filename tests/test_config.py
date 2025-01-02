import unittest
import os
import json
import tempfile
from pathlib import Path
from src.bot.config import ConfigManager

class TestConfigManager(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test config files
        self.test_dir = tempfile.mkdtemp()
        self.config_file = Path(self.test_dir) / 'test_config.json'
        self.config_manager = ConfigManager(config_file=self.config_file)

    def tearDown(self):
        # Clean up temporary files
        import shutil
        shutil.rmtree(self.test_dir)

    def test_default_config(self):
        """Test default configuration values"""
        self.assertEqual(self.config_manager.get_environment(), 'testnet')
        trading_params = self.config_manager.get_trading_params()
        self.assertEqual(trading_params['leverage'], 5)
        self.assertEqual(trading_params['balance_percentage'], 0.1)

    def test_switch_environment(self):
        """Test environment switching"""
        self.config_manager.switch_environment(False)  # Switch to mainnet
        self.assertEqual(self.config_manager.get_environment(), 'mainnet')
        self.config_manager.switch_environment(True)   # Switch to testnet
        self.assertEqual(self.config_manager.get_environment(), 'testnet')

    def test_set_trading_params(self):
        """Test setting trading parameters"""
        self.config_manager.set_trading_params(leverage=10, balance_percentage=0.2)
        params = self.config_manager.get_trading_params()
        self.assertEqual(params['leverage'], 10)
        self.assertEqual(params['balance_percentage'], 0.2)

    def test_config_persistence(self):
        """Test if configuration persists after saving"""
        self.config_manager.set_trading_params(leverage=15)
        
        # Create new instance with same config file
        new_manager = ConfigManager(config_file=self.config_file)
        params = new_manager.get_trading_params()
        self.assertEqual(params['leverage'], 15)

if __name__ == '__main__':
    unittest.main() 