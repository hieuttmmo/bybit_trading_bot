import unittest
from unittest.mock import patch, MagicMock
from src.bot.trading import BybitTradingBot, process_instruction

class TestBybitTradingBot(unittest.TestCase):
    def setUp(self):
        self.bot = BybitTradingbot(config_manager)
        
    @patch('src.bot.trading.BybitTradingBot.get_instrument_info')
    @patch('src.bot.trading.BybitTradingBot.set_leverage')
    @patch('src.bot.trading.BybitTradingBot.get_wallet_balance')
    def test_place_order(self, mock_balance, mock_leverage, mock_instrument):
        """Test placing a new order"""
        # Mock responses
        mock_instrument.return_value = {
            'lotSizeFilter': {'qtyStep': '0.001', 'minOrderQty': '0.001'}
        }
        mock_balance.return_value = 1000.0
        mock_leverage.return_value = True
        
        # Test market order
        with patch.object(self.bot, 'session') as mock_session:
            mock_session.get_tickers.return_value = {
                'retCode': 0,
                'result': {'list': [{'lastPrice': '50000.0'}]}
            }
            mock_session.place_order.return_value = {
                'retCode': 0,
                'result': {'orderId': 'test_id'}
            }
            
            success, message = self.bot.place_order(
                action="LONG",
                symbol="BTC",
                entry=0,  # Market order
                stl=45000,
                tp_prices=[55000, 60000]
            )
            
            self.assertTrue(success)
            self.assertIn("Order Placed Successfully", message)

    @patch('src.bot.trading.BybitTradingBot.get_active_positions')
    def test_close_position(self, mock_positions):
        """Test closing a position"""
        # Mock active positions response with all required fields and proper types
        mock_positions.return_value = [{
            'symbol': 'BTCUSDT',
            'size': 0.1,
            'side': 'Buy',
            'position_value': 5000.0,
            'entry_price': 50000.0,
            'current_price': 51000.0,
            'unrealized_pnl': 100.0,
            'leverage': 5,
            'position_idx': 0,
            'mode': 'BothSide'
        }]
        
        # Create a fresh session mock for each test
        session_mock = MagicMock()
        session_mock.get_positions.return_value = {
            'retCode': 0,
            'result': {
                'list': [{
                    'symbol': 'BTCUSDT',
                    'size': '0.1',
                    'side': 'Buy',
                    'position_value': '5000.0',
                    'avgPrice': '50000.0',
                    'unrealisedPnl': '100.0',
                    'leverage': '5',
                    'positionIdx': 0
                }]
            }
        }
        session_mock.place_order.return_value = {
            'retCode': 0,
            'result': {'orderId': 'test_id'},
            'retMsg': 'OK'
        }
        
        # Replace the bot's session with our mock
        self.bot.session = session_mock
        
        # Mock get_market_price to avoid API call
        with patch.object(self.bot, 'get_market_price', return_value=51000.0), \
             patch.object(self.bot, 'get_instrument_info', return_value={'lotSizeFilter': {'qtyStep': '0.001'}}):
            
            # Test closing position
            success, message = self.bot.close_position('BTCUSDT', 100)
            
            # Verify the order was placed correctly
            session_mock.place_order.assert_called_once()
            call_args = session_mock.place_order.call_args[1]
            
            # Verify order parameters
            expected_params = {
                'category': 'linear',
                'symbol': 'BTCUSDT',
                'side': 'Sell',
                'order_type': 'Market',
                'qty': '0.1',
                'reduce_only': True
            }
            
            for key, value in expected_params.items():
                self.assertEqual(call_args[key], value, f"Parameter {key} mismatch")
            
            # Verify success
            self.assertTrue(success)
            self.assertIn("Successfully closed", message)

    def test_process_instruction(self):
        """Test processing trading instructions"""
        with patch('src.bot.trading.BybitTradingBot.place_order') as mock_place_order:
            mock_place_order.return_value = (True, "Order placed successfully")
            
            # Test valid instruction
            success, message = process_instruction("""
            LONG $BTC
            Entry 50000
            Stl 45000
            Tp 55000 - 60000
            """)
            self.assertTrue(success)
            
            # Test invalid instruction
            success, message = process_instruction("Invalid format")
            self.assertFalse(success)
            self.assertIn("error", message.lower())

    @patch('src.bot.trading.BybitTradingBot.get_wallet_balance')
    def test_get_wallet_balance(self, mock_balance):
        """Test getting wallet balance"""
        mock_balance.return_value = 1000.0
        balance = self.bot.get_wallet_balance()
        self.assertEqual(balance, 1000.0)

    @patch('src.bot.trading.BybitTradingBot.get_active_positions')
    def test_get_active_positions(self, mock_positions):
        """Test getting active positions"""
        mock_data = [{
            'symbol': 'BTCUSDT',
            'side': 'Buy',
            'size': '0.1',
            'position_value': 5000.0,
            'entry_price': 50000.0,
            'unrealized_pnl': 100.0
        }]
        mock_positions.return_value = mock_data
        
        positions = self.bot.get_active_positions()
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]['symbol'], 'BTCUSDT')

if __name__ == '__main__':
    unittest.main() 