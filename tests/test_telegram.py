import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from telegram import Update, User, Message, Chat, CallbackQuery
from telegram.ext import ContextTypes
import asyncio
from src.bot.telegram import (
    is_authorized, handle_message, button_callback,
    get_main_menu_keyboard, get_trading_keyboard,
    get_settings_keyboard, get_trading_params_keyboard
)

class TestTelegramHandlers(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Create mock objects
        self.user = MagicMock(spec=User)
        self.user.id = 123
        self.user.is_bot = False
        self.user.first_name = 'Test'
        
        self.chat = MagicMock(spec=Chat)
        self.chat.id = 123
        self.chat.type = 'private'
        
        self.message = MagicMock(spec=Message)
        self.message.message_id = 1
        self.message.date = None
        self.message.chat = self.chat
        self.message.from_user = self.user
        self.message.reply_text = AsyncMock()
        
        self.update = MagicMock(spec=Update)
        self.update.update_id = 1
        self.update.message = self.message
        self.update.effective_user = self.user
        
        self.context = MagicMock()
        self.context.user_data = {}
        
        # Mock the allowed users
        self.allowed_users_patcher = patch('src.bot.telegram.ALLOWED_USER_IDS', [123])
        self.allowed_users_patcher.start()

    def tearDown(self):
        """Clean up after tests"""
        self.allowed_users_patcher.stop()
        self.loop.close()

    def test_is_authorized(self):
        """Test user authorization"""
        self.assertTrue(is_authorized(123))  # Authorized user
        self.assertFalse(is_authorized(456))  # Unauthorized user

    @patch('src.bot.telegram.BybitTradingBot')
    def test_get_main_menu_keyboard(self, mock_bot):
        """Test main menu keyboard generation"""
        mock_bot.return_value.get_wallet_balance.return_value = 1000.0
        keyboard = get_main_menu_keyboard()
        self.assertIsNotNone(keyboard)
        # Verify keyboard buttons
        self.assertIn("Trading", str(keyboard))
        self.assertIn("Settings", str(keyboard))

    def test_get_trading_keyboard(self):
        """Test trading menu keyboard generation"""
        keyboard = get_trading_keyboard()
        self.assertIsNotNone(keyboard)
        # Verify keyboard buttons
        self.assertIn("New Trade", str(keyboard))
        self.assertIn("Active Positions", str(keyboard))

    def test_get_settings_keyboard(self):
        """Test settings menu keyboard generation"""
        keyboard = get_settings_keyboard()
        self.assertIsNotNone(keyboard)
        # Verify keyboard buttons
        self.assertIn("API Keys", str(keyboard))
        self.assertIn("Trading Parameters", str(keyboard))

    @patch('src.bot.telegram.process_instruction')
    def test_handle_message(self, mock_process):
        """Test message handling"""
        # Test valid trading instruction
        mock_process.return_value = (True, "Order placed successfully")
        
        # Create a new message mock for this test
        message = MagicMock(spec=Message)
        message.text = "LONG $BTC\nEntry 50000\nStl 45000\nTp 55000"
        message.reply_text = AsyncMock()
        
        update = MagicMock(spec=Update)
        update.message = message
        update.effective_user = self.user
        
        # Run the coroutine
        self.loop.run_until_complete(handle_message(update, self.context))
        message.reply_text.assert_called_once()
        args = message.reply_text.call_args[0]
        self.assertIn("Order placed successfully", args[0])

    def test_button_callback(self):
        """Test button callback handling"""
        # Create a callback query mock
        callback_query = MagicMock(spec=CallbackQuery)
        callback_query.id = '123'
        callback_query.from_user = self.user
        callback_query.chat_instance = '123'
        callback_query.message = self.message
        callback_query.data = 'menu_main'
        callback_query.answer = AsyncMock()
        callback_query.edit_message_text = AsyncMock()
        
        update = MagicMock(spec=Update)
        update.callback_query = callback_query
        
        # Run the coroutine
        self.loop.run_until_complete(button_callback(update, self.context))
        callback_query.edit_message_text.assert_called_once()
        
        # Check that the first positional argument contains "Main Menu"
        args = callback_query.edit_message_text.call_args[0]
        self.assertIn("Main Menu", args[0])

    @patch('src.bot.telegram.BybitTradingBot')
    def test_view_positions(self, mock_bot):
        """Test viewing positions"""
        # Mock bot response with all required fields and proper types
        mock_bot.return_value.get_active_positions.return_value = [{
            'symbol': 'BTCUSDT',
            'side': 'Buy',
            'size': 0.1,
            'entry_price': 50000.0,
            'current_price': 51000.0,
            'unrealized_pnl': 100.0,
            'position_value': 5000.0,
            'leverage': 5,
            'created_time': 1000000000000,
            'liq_price': 45000.0,
            'pnl_percentage': 2.0,
            'position_idx': 0,
            'mode': 'BothSide'
        }]
        
        # Mock wallet balance for the main menu
        mock_bot.return_value.get_wallet_balance.return_value = 10000.0
        
        # Create callback query mock
        callback_query = MagicMock(spec=CallbackQuery)
        callback_query.id = '123'
        callback_query.from_user = self.user
        callback_query.chat_instance = '123'
        callback_query.message = self.message
        callback_query.data = 'view_positions'
        callback_query.answer = AsyncMock()
        callback_query.edit_message_text = AsyncMock()
        
        update = MagicMock(spec=Update)
        update.callback_query = callback_query
        
        # Run the coroutine
        self.loop.run_until_complete(button_callback(update, self.context))
        
        # Verify the final message contains position info
        last_call = callback_query.edit_message_text.call_args_list[-1]
        message_text = last_call[0][0]
        
        # Check essential position information with exact formatting
        self.assertIn("BTCUSDT", message_text)
        self.assertIn("BUY", message_text)  # Check for uppercase BUY
        self.assertIn("100.00", message_text)  # PNL value with 2 decimals
        self.assertIn("5x", message_text)      # Leverage format
        self.assertIn("5,000.00", message_text)  # Position value with formatting

def run_async_test(coro):
    """Helper function to run async tests"""
    return asyncio.get_event_loop().run_until_complete(coro)

if __name__ == '__main__':
    unittest.main() 