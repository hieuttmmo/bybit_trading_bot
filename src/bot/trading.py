import os
from pybit.unified_trading import HTTP
import re
from typing import List, Tuple
from decimal import Decimal, ROUND_DOWN
from dotenv import load_dotenv
from .config import ConfigManager
import json
from datetime import datetime

# Initialize config manager
config_manager = ConfigManager()

class BybitTradingBot:
    def __init__(self):
        # Load configuration
        api_key, api_secret = config_manager.get_active_api_keys()
        
        if not api_key or not api_secret:
            raise ValueError("API keys not configured. Please use /setapi command to configure them.")

        # Initialize Bybit client
        self.session = HTTP(
            testnet=config_manager.get_environment() == 'testnet',
            api_key=api_key,
            api_secret=api_secret
        )
        
        # Store trading parameters
        self.trading_params = config_manager.get_trading_params()
    
    def get_wallet_balance(self) -> float:
        """Get wallet balance."""
        try:
            response = self.session.get_wallet_balance(
                accountType="UNIFIED",
                coin="USDT"
            )
            return float(response['result']['list'][0]['totalAvailableBalance'])
        except Exception as e:
            raise Exception(f"Error getting wallet balance: {str(e)}")
    
    def set_leverage(self, symbol: str):
        """Set leverage for a symbol."""
        try:
            # Ensure symbol has USDT suffix
            if not symbol.endswith('USDT'):
                symbol = f"{symbol}USDT"
                
            leverage = self.trading_params.get('leverage', 5)
            response = self.session.set_leverage(
                category="linear",
                symbol=symbol,  # Use full symbol with USDT
                buyLeverage=str(leverage),
                sellLeverage=str(leverage)
            )
            
            if response['retCode'] != 0:
                raise Exception(f"{response['retMsg']} (ErrCode: {response['retCode']}) (ErrTime: {datetime.now().strftime('%H:%M:%S')}).")
            
            return True
            
        except Exception as e:
            print(f"Error setting leverage: {str(e)}")
            if hasattr(self.session, 'last_request_data'):
                print(f"Request → POST https://api-testnet.bybit.com/v5/position/set-leverage: {json.dumps(self.session.last_request_data)}.")
            return False
    
    def calculate_position_quantity(self, entry_price: float, lot_size: float) -> float:
        """Calculate position quantity based on wallet balance and risk parameters."""
        try:
            balance = self.get_wallet_balance()
            balance_percentage = self.trading_params.get('balance_percentage', 0.1)
            leverage = self.trading_params.get('leverage', 5)
            
            # Calculate position value
            position_value = balance * balance_percentage * leverage
            
            # Calculate quantity
            quantity = position_value / entry_price
            
            # Round to lot size
            return self.round_to_lot_size(quantity, lot_size)
        except Exception as e:
            raise Exception(f"Error calculating position quantity: {str(e)}")

    def get_instrument_info(self, symbol: str) -> dict:
        """Get instrument information including lot size and price filters."""
        try:
            # Remove USDT if it's already in the symbol
            clean_symbol = symbol.replace('USDT', '')
            
            response = self.session.get_instruments_info(
                category="linear",
                symbol=f"{clean_symbol}USDT"
            )
            instrument = response['result']['list'][0]
            print(f"Instrument info: {instrument}")  # Debug print
            return instrument
        except Exception as e:
            raise Exception(f"Error getting instrument info: {str(e)}")

    def get_lot_size(self, instrument_info: dict) -> float:
        """Extract lot size from instrument info."""
        try:
            lot_size = float(instrument_info['lotSizeFilter']['qtyStep'])
            print(f"Lot size: {lot_size}")  # Debug print
            return lot_size
        except KeyError:
            raise Exception("Could not find lot size in instrument info")

    def round_to_lot_size(self, quantity: float, lot_size: float) -> float:
        """Round quantity to valid lot size."""
        return float(Decimal(str(quantity)).quantize(Decimal(str(lot_size)), rounding=ROUND_DOWN))

    def parse_instruction(self, instruction: str) -> Tuple[str, str, float, float, List[float]]:
        """Parse the trading instruction from user input."""
        lines = instruction.strip().split('\n')
        
        # Parse first line for action and symbol
        first_line = lines[0].strip()
        action, symbol = first_line.split()
        symbol = symbol.replace('$', '')  # Remove $ if present
        
        # Parse entry, stop loss, and take profit prices
        entry = float(re.search(r'Entry\s+(\d+\.?\d*)', instruction).group(1))
        stl = float(re.search(r'Stl\s+(\d+\.?\d*)', instruction).group(1))
        
        # Parse take profit prices
        tp_line = re.search(r'Tp\s+([\d\.\s\-]+)', instruction).group(1)
        tp_prices = [float(price.strip()) for price in tp_line.split('-')]
        
        return action, symbol, entry, stl, tp_prices

    def calculate_position_sizes(self, total_quantity: float, num_tps: int, lot_size: float) -> List[float]:
        """Calculate position size for each take profit level."""
        percentage_per_tp = 100 / num_tps
        raw_sizes = [total_quantity * (percentage_per_tp / 100) for _ in range(num_tps)]
        rounded_sizes = [self.round_to_lot_size(size, lot_size) for size in raw_sizes]
        print(f"TP sizes before rounding: {raw_sizes}")  # Debug print
        print(f"TP sizes after rounding: {rounded_sizes}")  # Debug print
        return rounded_sizes

    def wait_for_position(self, symbol: str, side: str, max_attempts: int = 5) -> bool:
        """Wait for position to be opened and return True if successful."""
        import time
        
        for attempt in range(max_attempts):
            try:
                position = self.session.get_positions(
                    category="linear",
                    symbol=symbol
                )
                
                if position['retCode'] == 0 and position['result']['list']:
                    actual_position = position['result']['list'][0]
                    size = float(actual_position['size']) if actual_position['size'] else 0
                    
                    if size > 0 and actual_position['side'] == side:
                        print(f"Position verified after {attempt + 1} attempts")
                        return True
                
                print(f"Waiting for position to be opened (attempt {attempt + 1}/{max_attempts})")
                time.sleep(2)  # Wait 2 seconds between checks
                
            except Exception as e:
                print(f"Error checking position: {str(e)}")
                time.sleep(2)
                
        return False

    def place_order(self, action: str, symbol: str, entry: float, stl: float, tp_prices: List[float]):
        """Place the main order and corresponding take profit orders."""
        # Convert action to side
        side = "Buy" if action.upper() == "LONG" else "Sell"
        
        try:
            # Get instrument info for lot size
            instrument_info = self.get_instrument_info(symbol)
            lot_size = self.get_lot_size(instrument_info)
            
            # Set leverage first
            self.set_leverage(symbol)
            
            # For market orders (entry = 0), get current price for quantity calculation only
            if entry == 0:
                ticker = self.session.get_tickers(
                    category="linear",
                    symbol=f"{symbol}USDT"
                )
                if ticker['retCode'] != 0:
                    raise Exception("Failed to get current price")
                
                # Use last traded price for quantity calculation only
                market_price = float(ticker['result']['list'][0]['lastPrice'])
                print(f"Using market price for calculation: {market_price}")
                entry = market_price  # Store for TP/SL percentage calculations
            
            # Calculate total quantity based on wallet balance
            total_quantity = self.calculate_position_quantity(entry, lot_size)
            
            # Calculate position sizes for each TP
            position_sizes = self.calculate_position_sizes(total_quantity, len(tp_prices), lot_size)
            
            print(f"Total quantity: {total_quantity} {symbol}")
            print(f"Position sizes for TPs: {position_sizes}")
            
            # Get leverage from trading params
            leverage = self.trading_params.get('leverage', 5)
            
            # Place the main entry order with SL only first
            is_market = entry == 0
            order_type = "Market" if is_market else "Limit"
            
            # Prepare main order parameters
            main_order_params = {
                "category": "linear",
                "symbol": f"{symbol}USDT",
                "side": side,
                "orderType": order_type,
                "qty": str(total_quantity),
                "positionIdx": 0,  # 0 for one-way mode
                "timeInForce": "GTC",
                "stopLoss": str(stl),
                "slTriggerBy": "LastPrice",
                "slOrderType": "Market",
                "tpslMode": "Partial",  # Set to Partial initially
                "leverage": str(leverage)
            }
            
            # Add price only for limit orders
            if not is_market:
                main_order_params["price"] = str(entry)
                main_order_params["timeInForce"] = "PostOnly"  # Use PostOnly for limit orders
            else:
                main_order_params["timeInForce"] = "IOC"  # Use IOC for market orders
            
            main_order = self.session.place_order(**main_order_params)
            print(f"Main order placed: {main_order}")  # Debug print
            
            if main_order['retCode'] != 0:
                raise Exception(f"Error placing main order: {main_order['retMsg']}")
            
            order_id = main_order['result']['orderId']
            
            # For market orders, wait for position to be opened
            if is_market:
                import time
                max_attempts = 10
                position_opened = False
                
                for attempt in range(max_attempts):
                    try:
                        position = self.session.get_positions(
                            category="linear",
                            symbol=f"{symbol}USDT"
                        )
                        
                        if position['retCode'] == 0 and position['result']['list']:
                            actual_position = position['result']['list'][0]
                            size = float(actual_position['size']) if actual_position['size'] else 0
                            
                            if size > 0 and actual_position['side'] == side:
                                print(f"Position verified after {attempt + 1} attempts")
                                position_opened = True
                                break
                        
                        print(f"Waiting for position to be opened (attempt {attempt + 1}/{max_attempts})")
                        time.sleep(1)  # Wait 1 second between checks
                        
                    except Exception as e:
                        print(f"Error checking position: {str(e)}")
                        time.sleep(1)
                
                if not position_opened:
                    raise Exception("Timeout waiting for position to be opened")
            
            # Now amend the order to add take profits
            tp_errors = []
            for tp_price in tp_prices:
                try:
                    amend_params = {
                        "category": "linear",
                        "symbol": f"{symbol}USDT",
                        "orderId": order_id,
                        "takeProfit": str(tp_price),
                        "tpTriggerBy": "LastPrice",
                        "tpOrderType": "Limit",
                        "tpLimitPrice": str(tp_price)
                    }
                    
                    amend_order = self.session.amend_order(**amend_params)
                    print(f"TP amended: {amend_order}")  # Debug print
                    
                    if amend_order['retCode'] != 0:
                        tp_errors.append(f"TP at {tp_price}: {amend_order['retMsg']}")
                except Exception as e:
                    if hasattr(self.session, 'last_request_data'):
                        tp_errors.append(f"TP at {tp_price}: {str(e)}\nRequest → POST https://api-testnet.bybit.com/v5/order/amend: {json.dumps(self.session.last_request_data)}.")
                    else:
                        tp_errors.append(f"TP at {tp_price}: {str(e)}")
            
            entry_type = "market" if is_market else "limit"
            side_emoji = "🟢" if action.upper() == "LONG" else "🔴"
            
            # Calculate percentages
            sl_pct = ((stl - entry) / entry * 100)
            sl_direction = "⬇️" if sl_pct < 0 else "⬆️"
            
            success_msg = f"""✅ *Order Placed Successfully!*

{side_emoji} *Position:* {action} {symbol.replace('USDT', '')}
💰 *Size:* {total_quantity:.4f} {symbol.replace('USDT', '')}
📊 *Type:* {entry_type.title()} Order
🔧 *Leverage:* {leverage}x

📍 *Entry:* {entry:,.2f} USDT
🛑 *Stop Loss:* {stl:,.2f} USDT ({sl_direction} {abs(sl_pct):.2f}%)

🎯 *Take Profit Targets:*"""

            # Calculate and add TP percentages
            for i, tp in enumerate(tp_prices, 1):
                tp_pct = ((tp - entry) / entry * 100)
                direction = "⬆️" if tp_pct > 0 else "⬇️"
                success_msg += f"\n   {i}. {tp:,.2f} USDT ({direction} {abs(tp_pct):.2f}%)"
            
            if tp_errors:
                success_msg += "\n\n⚠️ *Warning:* Some TP orders failed:\n" + "\n".join(tp_errors)
            
            # Add risk warning if leverage is high
            if leverage > 10:
                success_msg += "\n\n⚠️ *High Leverage Warning:*\nTrading with high leverage increases both potential profits and losses!"
            
            # Add estimated PnL info
            success_msg += f"\n\n💹 *Estimated PnL:*"
            success_msg += f"\n   • Stop Loss: {sl_direction} {abs(sl_pct):.2f}%"
            avg_tp_pct = sum(((tp - entry) / entry * 100) for tp in tp_prices) / len(tp_prices)
            tp_direction = "⬆️" if avg_tp_pct > 0 else "⬇️"
            success_msg += f"\n   • Average TP: {tp_direction} {abs(avg_tp_pct):.2f}%"
            
            return True, success_msg
            
        except Exception as e:
            error_msg = f"""❌ *Order Failed!*

*Error:* {str(e)}

*Please check:*
• Available balance
• Position size
• Leverage settings
• Price limits"""
            return False, error_msg

    def get_trading_history(self) -> list:
        """Get recent trading history."""
        try:
            # Get order history
            response = self.session.get_order_history(
                category="linear",
                limit=20  # Get last 20 orders
            )
            
            if response['retCode'] == 0:
                orders = response['result']['list']
                return [{
                    'symbol': order['symbol'],
                    'side': order['side'],
                    'price': order['price'],
                    'qty': order['qty'],
                    'state': order['orderStatus'],
                    'created_time': order['createdTime']
                } for order in orders]
            return []
            
        except Exception as e:
            print(f"Error getting trading history: {str(e)}")
            return []

    def get_active_positions(self) -> list:
        """Get active positions with detailed information."""
        try:
            # Get positions
            response = self.session.get_positions(
                category="linear",
                settleCoin="USDT"
            )
            
            if response['retCode'] != 0:
                raise Exception(f"Error from Bybit: {response['retMsg']}")

            positions = []
            for pos in response['result']['list']:
                # Skip positions with 0 size
                try:
                    size = float(pos['size']) if pos['size'] else 0
                    if size == 0:
                        continue
                    
                    # Get current market price
                    ticker = self.session.get_tickers(
                        category="linear",
                        symbol=pos['symbol']
                    )
                    current_price = float(ticker['result']['list'][0]['lastPrice'])
                    
                    # Map data exactly according to V5 API documentation
                    position_data = pos
                    print(position_data)
                    # Get TP/SL orders
                    try:
                        tp_sl_orders = self.session.get_open_orders(
                            category="linear",
                            symbol=pos['symbol']
                        )
                        
                        # Initialize TP/SL arrays
                        take_profits = []
                        stop_losses = []
                        
                        if tp_sl_orders['retCode'] == 0:
                            for order in tp_sl_orders['result']['list']:
                                if order.get('stopOrderType') == 'TakeProfit':
                                    take_profits.append(float(order['triggerPrice']))
                                elif order.get('stopOrderType') == 'StopLoss':
                                    stop_losses.append(float(order['triggerPrice']))
                        
                        # Add TP/SL arrays to position data
                        position_data['takeProfits'] = take_profits
                        position_data['stopLosses'] = stop_losses
                        
                    except Exception as e:
                        print(f"Error getting TP/SL orders: {str(e)}")
                        position_data['takeProfits'] = []
                        position_data['stopLosses'] = []
                    
                    positions.append(position_data)
                    
                except Exception as e:
                    print(f"Error processing position {pos.get('symbol', 'Unknown')}: {str(e)}")
                    continue
            
            return positions
            
        except Exception as e:
            print(f"Error getting positions: {str(e)}")
            raise e

    def close_position(self, symbol: str, percentage: float = 100) -> Tuple[bool, str]:
        """Close a position with specified percentage."""
        try:
            # Ensure symbol has USDT suffix
            if not symbol.endswith('USDT'):
                symbol = f"{symbol}USDT"
            
            # Get current position
            response = self.session.get_positions(
                category="linear",
                symbol=symbol
            )
            
            if response['retCode'] != 0:
                raise Exception(f"Error from Bybit: {response['retMsg']}")
                
            if not response['result']['list']:
                return False, f"No active position found for {symbol}"
                
            position = response['result']['list'][0]
            position_size = float(position.get('size', '0'))
            
            if position_size == 0:
                return False, f"No active position found for {symbol}"
                
            # Get instrument info for lot size
            instrument_info = self.get_instrument_info(symbol)
            lot_size = self.get_lot_size(instrument_info)
                
            # Calculate quantity to close
            close_size = position_size * (percentage / 100)
            close_size = self.round_to_lot_size(close_size, lot_size)
            
            if close_size == 0:
                return False, f"Calculated close size is too small (minimum lot size: {lot_size})"
            
            # Determine side for closing order (opposite of position side)
            position_side = position.get('side')
            if not position_side:
                raise Exception("Could not determine position side")
                
            close_side = "Sell" if position_side == "Buy" else "Buy"
            
            # Place market order to close
            close_order = self.session.place_order(
                category="linear",
                symbol=symbol,
                side=close_side,
                orderType="Market",
                qty=str(close_size),
                reduceOnly=True,
                timeInForce="IOC"
            )
            
            if close_order['retCode'] != 0:
                raise Exception(f"Error closing position: {close_order['retMsg']}")
            
            success_msg = f"Successfully closed {percentage}% of {symbol} position"
            print(f"Close order response: {close_order}")  # Debug print
            return True, success_msg
            
        except Exception as e:
            error_msg = f"Error closing position: {str(e)}"
            print(error_msg)  # Debug print
            if hasattr(self.session, 'last_request_data'):
                print(f"Last request data: {self.session.last_request_data}")
            return False, error_msg

    def close_all_positions(self) -> Tuple[bool, str]:
        """Close all active positions."""
        try:
            # Get all positions
            response = self.session.get_positions(
                category="linear",
                settleCoin="USDT"
            )
            
            if response['retCode'] != 0:
                raise Exception(f"Error from Bybit: {response['retMsg']}")
            
            positions = response['result']['list']
            closed_positions = []
            errors = []
            
            for pos in positions:
                try:
                    size = float(pos['size']) if pos['size'] else 0
                    if size == 0:
                        continue
                        
                    symbol = pos['symbol']
                    success, message = self.close_position(symbol, 100)  # Close 100% of each position
                    
                    if success:
                        closed_positions.append(symbol)
                    else:
                        errors.append(f"{symbol}: {message}")
                        
                except Exception as e:
                    errors.append(f"{pos['symbol']}: {str(e)}")
            
            if not closed_positions and not errors:
                return True, "No active positions to close"
            
            message = ""
            if closed_positions:
                message += f"Successfully closed positions: {', '.join(closed_positions)}"
            if errors:
                message += f"\nErrors closing positions:\n" + "\n".join(errors)
            
            return len(errors) == 0, message
            
        except Exception as e:
            return False, f"Error closing all positions: {str(e)}"

    def get_market_price(self, symbol: str) -> float:
        """Get current market price for a symbol."""
        try:
            # Ensure symbol has USDT suffix
            if not symbol.endswith('USDT'):
                symbol = f"{symbol}USDT"
            
            ticker = self.session.get_tickers(
                category="linear",
                symbol=symbol
            )
            
            if ticker['retCode'] != 0:
                raise Exception(f"Error getting market price: {ticker['retMsg']}")
            
            return float(ticker['result']['list'][0]['lastPrice'])
            
        except Exception as e:
            raise Exception(f"Error getting market price: {str(e)}")

def process_instruction(instruction: str):
    """Process the trading instruction and execute the trade."""
    bot = BybitTradingBot()
    try:
        action, symbol, entry, stl, tp_prices = bot.parse_instruction(instruction)
        success, message = bot.place_order(action, symbol, entry, stl, tp_prices)
        return success, message
    except Exception as e:
        return False, f"Error processing instruction: {str(e)}"

# Example usage
if __name__ == "__main__":
    example_instruction = """LONG $APT
Entry 8.844
Stl 4
Tp 9 - 10 - 11"""
    
    success, message = process_instruction(example_instruction)
    print(f"Success: {success}")
    print(f"Message: {message}")
