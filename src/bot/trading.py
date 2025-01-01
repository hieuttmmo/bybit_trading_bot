import os
from pybit.unified_trading import HTTP
import re
from typing import List, Tuple
from decimal import Decimal, ROUND_DOWN
from dotenv import load_dotenv
from .config import ConfigManager

# Initialize config manager
config_manager = ConfigManager()

class BybitTradingBot:
    def __init__(self):
        # Load configuration
        config = config_manager.get_config()
        api_key, api_secret = config_manager.get_active_api_keys()
        
        if not api_key or not api_secret:
            raise ValueError("API keys not configured. Please use /setapi command to configure them.")

        # Initialize Bybit client
        self.session = HTTP(
            testnet=config["use_testnet"],
            api_key=api_key,
            api_secret=api_secret
        )

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

    def get_wallet_balance(self) -> float:
        """Get the USDT wallet balance."""
        try:
            wallet_info = self.session.get_wallet_balance(
                accountType="UNIFIED",
                coin="USDT"
            )
            balance = float(wallet_info['result']['list'][0]['totalWalletBalance'])
            print(f"Wallet balance: {balance} USDT")  # Debug print
            return balance
        except Exception as e:
            raise Exception(f"Error getting wallet balance: {str(e)}")

    def set_leverage(self, symbol: str):
        """Set leverage for the symbol."""
        try:
            config = config_manager.get_config()
            leverage = config["leverage"]
            self.session.set_leverage(
                category="linear",
                symbol=f"{symbol}USDT",
                buyLeverage=str(leverage),
                sellLeverage=str(leverage)
            )
            print(f"Leverage set to {leverage}x")  # Debug print
        except Exception as e:
            # If error is about leverage already set, we can ignore it
            if "leverage not modified" not in str(e).lower():
                raise Exception(f"Error setting leverage: {str(e)}")

    def calculate_position_quantity(self, entry_price: float, lot_size: float) -> float:
        """Calculate the position quantity based on wallet balance and entry price."""
        config = config_manager.get_config()
        wallet_balance = self.get_wallet_balance()
        position_value = wallet_balance * config["balance_percentage"] * config["leverage"]
        quantity = position_value / entry_price
        rounded_quantity = self.round_to_lot_size(quantity, lot_size)
        print(f"Calculated quantity: {quantity}, Rounded quantity: {rounded_quantity}")  # Debug print
        return rounded_quantity

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
            
            # For market orders (entry = 0), get current price
            if entry == 0:
                ticker = self.session.get_tickers(
                    category="linear",
                    symbol=f"{symbol}USDT"
                )
                if ticker['retCode'] != 0:
                    raise Exception("Failed to get current price")
                
                # Use last traded price for quantity calculation
                entry = float(ticker['result']['list'][0]['lastPrice'])
                print(f"Using market price: {entry}")
            
            # Calculate total quantity based on wallet balance
            total_quantity = self.calculate_position_quantity(entry, lot_size)
            
            # Calculate position sizes for each TP
            position_sizes = self.calculate_position_sizes(total_quantity, len(tp_prices), lot_size)
            
            print(f"Total quantity: {total_quantity} {symbol}")
            print(f"Position sizes for TPs: {position_sizes}")
            
            config = config_manager.get_config()
            
            # Place the main entry order
            order_type = "Market" if entry == 0 else "Limit"
            main_order_params = {
                "category": "linear",
                "symbol": f"{symbol}USDT",
                "side": side,
                "order_type": order_type,
                "qty": str(total_quantity),
                "position_idx": 0,  # 0 for one-way mode
                "stop_loss": str(stl),
                "time_in_force": "GTC",
                "leverage": str(config["leverage"])
            }
            
            # Add price only for limit orders
            if order_type == "Limit":
                main_order_params["price"] = str(entry)
            
            main_order = self.session.place_order(**main_order_params)
            print(f"Main order placed: {main_order}")  # Debug print
            
            if main_order['retCode'] != 0:
                raise Exception(f"Error placing main order: {main_order['retMsg']}")
            
            # For market orders, wait for position to be opened
            if order_type == "Market":
                if not self.wait_for_position(f"{symbol}USDT", side):
                    raise Exception("Timeout waiting for position to be opened")
            
            # Place take profit orders as conditional orders
            tp_errors = []
            for tp_price, position_size in zip(tp_prices, position_sizes):
                try:
                    tp_side = "Sell" if action == "LONG" else "Buy"
                    tp_order = self.session.place_order(
                        category="linear",
                        symbol=f"{symbol}USDT",
                        side=tp_side,
                        order_type="Limit",
                        qty=str(position_size),
                        price=str(tp_price),
                        position_idx=0,
                        time_in_force="GTC",
                        reduce_only=True,
                        trigger_by="LastPrice",
                        trigger_price=str(tp_price),
                        trigger_direction=1 if action == "LONG" else 2
                    )
                    print(f"TP order placed: {tp_order}")  # Debug print
                    
                    if tp_order['retCode'] != 0:
                        tp_errors.append(f"TP at {tp_price}: {tp_order['retMsg']}")
                except Exception as e:
                    tp_errors.append(f"TP at {tp_price}: {str(e)}")
            
            entry_type = "market" if entry == 0 else "limit"
            success_msg = f"{entry_type.title()} order placed successfully with {config['leverage']}x leverage and {total_quantity:.4f} {symbol} position size"
            
            if tp_errors:
                success_msg += "\nWarning: Some TP orders failed:\n" + "\n".join(tp_errors)
            else:
                success_msg += f"\nTake profits set at: {', '.join([str(tp) for tp in tp_prices])}"
            
            return True, success_msg
            
        except Exception as e:
            return False, f"Error placing orders: {str(e)}"

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
                    
                    # Safely convert values with fallbacks for empty strings
                    entry_price = float(pos['avgPrice']) if pos['avgPrice'] else 0
                    position_value = size * entry_price
                    unrealized_pnl = float(pos['unrealisedPnl']) if pos['unrealisedPnl'] else 0
                    pnl_percentage = (unrealized_pnl / position_value) * 100 if position_value != 0 else 0
                    
                    # Format liquidation price
                    liq_price = float(pos['liqPrice']) if pos['liqPrice'] and pos['liqPrice'] != '0' else None
                    mark_price = float(pos['markPrice']) if pos['markPrice'] else current_price
                    leverage = pos['leverage'] if pos['leverage'] else '1'
                    
                    positions.append({
                        'symbol': pos['symbol'],
                        'side': pos['side'],
                        'size': size,
                        'entry_price': entry_price,
                        'current_price': current_price,
                        'unrealized_pnl': unrealized_pnl,
                        'pnl_percentage': pnl_percentage,
                        'leverage': leverage,
                        'liq_price': liq_price,
                        'position_value': position_value,
                        'mark_price': mark_price
                    })
                except Exception as e:
                    print(f"Error processing position {pos['symbol']}: {str(e)}")
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
                
            position = response['result']['list'][0]
            if float(position['size']) == 0:
                return False, "No active position found"
                
            # Get instrument info for lot size
            instrument_info = self.get_instrument_info(symbol)
            lot_size = self.get_lot_size(instrument_info)
                
            # Calculate quantity to close
            total_size = float(position['size'])
            close_size = total_size * (percentage / 100)
            close_size = self.round_to_lot_size(close_size, lot_size)
            
            # Determine side for closing order (opposite of position side)
            close_side = "Sell" if position['side'] == "Buy" else "Buy"
            
            # Place market order to close
            close_order = self.session.place_order(
                category="linear",
                symbol=symbol,
                side=close_side,
                order_type="Market",
                qty=str(close_size),
                reduce_only=True
            )
            
            if close_order['retCode'] != 0:
                raise Exception(f"Error closing position: {close_order['retMsg']}")
            
            return True, f"Successfully closed {percentage}% of {symbol} position"
            
        except Exception as e:
            return False, f"Error closing position: {str(e)}"

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
