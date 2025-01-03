import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
from dotenv import load_dotenv
from .trading import process_instruction, BybitTradingBot
from .config import ConfigManager
from typing import Tuple, List
import pathlib
from datetime import datetime

# Get the absolute path to the config directory
CONFIG_DIR = pathlib.Path(__file__).parent.parent.parent / 'config'
ENV_FILE = CONFIG_DIR / '.env'
CONFIG_FILE = CONFIG_DIR / 'bot_config.json'

print(f"Loading config from: {CONFIG_DIR}")
print(f"ENV file path: {ENV_FILE}")
print(f"Config file path: {CONFIG_FILE}")

# Create config directory if it doesn't exist
os.makedirs(CONFIG_DIR, exist_ok=True)

# Load environment variables from specific .env file
if not ENV_FILE.exists():
    # If .env doesn't exist in config dir, try to copy from root
    root_env = pathlib.Path(__file__).parent.parent.parent / '.env'
    if root_env.exists():
        import shutil
        shutil.copy(root_env, ENV_FILE)
        print(f"Copied .env from {root_env} to {ENV_FILE}")

load_dotenv(dotenv_path=ENV_FILE)

# Get Telegram token from environment variable
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
ALLOWED_USER_IDS = [int(id.split('#')[0].strip()) for id in os.getenv('ALLOWED_TELEGRAM_USERS', '').split(',') if id.strip()]

if not TELEGRAM_TOKEN:
    raise ValueError(f"Please set TELEGRAM_TOKEN in your .env file at {ENV_FILE}")

if not ALLOWED_USER_IDS:
    raise ValueError(f"Please set ALLOWED_TELEGRAM_USERS in your .env file at {ENV_FILE}")

# Initialize config manager with specific config file
config_manager = ConfigManager(config_file=CONFIG_FILE)

# Initialize bot instance once
trading_bot = None

def initialize_trading_bot():
    """Initialize or reinitialize the trading bot with current config."""
    global trading_bot
    trading_bot = BybitTradingBot(config_manager)
    return trading_bot

# Initial bot initialization
trading_bot = initialize_trading_bot()

# States for conversation handler
AWAITING_API_KEY, AWAITING_API_SECRET, AWAITING_LEVERAGE, AWAITING_BALANCE_PERCENTAGE, AWAITING_CLOSE_PERCENTAGE = range(5)

def is_authorized(user_id: int) -> bool:
    """Check if user is authorized to use the bot."""
    return user_id in ALLOWED_USER_IDS

def get_main_menu_keyboard():
    """Get the enhanced main menu keyboard with status."""
    try:
        balance = trading_bot.get_wallet_balance()
        env = config_manager.get_environment().upper()
        balance_text = f"💰 Balance: ${format_number(balance)} USDT"
    except Exception as e:
        print(f"Error fetching balance: {str(e)}")
        balance_text = "💰 Balance: Loading..."
        env = "UNKNOWN"

    keyboard = [
        [InlineKeyboardButton(f"🌍 {env} Mode", callback_data='switch_env')],
        [InlineKeyboardButton(balance_text, callback_data='balance_info')],
        [InlineKeyboardButton("📊 Trading", callback_data='menu_trading')],
        [
            InlineKeyboardButton("📈 Positions", callback_data='view_positions'),
            InlineKeyboardButton("⚙️ Settings", callback_data='menu_settings')
        ],
        [InlineKeyboardButton("❓ Help", callback_data='menu_help')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_settings_keyboard():
    """Get the settings menu keyboard."""
    env = config_manager.get_environment().upper()
    keyboard = [
        [InlineKeyboardButton(f"🌍 Environment: {env}", callback_data='switch_env')],
        [InlineKeyboardButton("🔑 API Keys", callback_data='setup_api')],
        [InlineKeyboardButton("📊 Trading Parameters", callback_data='setup_params')],
        [InlineKeyboardButton("« Back to Main Menu", callback_data='menu_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_trading_keyboard():
    """Get the trading menu keyboard."""
    keyboard = [
        [InlineKeyboardButton("📝 New Trade", callback_data='new_trade')],
        [InlineKeyboardButton("📊 Active Positions", callback_data='view_positions')],
        [InlineKeyboardButton("📜 Trade History", callback_data='trade_history')],
        [InlineKeyboardButton("« Back to Main Menu", callback_data='menu_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_environment_keyboard():
    """Get environment selection keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🔵 Testnet", callback_data='switch_testnet'),
            InlineKeyboardButton("🔴 Mainnet", callback_data='switch_mainnet')
        ],
        [InlineKeyboardButton("« Back to Settings", callback_data='menu_settings')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_trading_params_keyboard():
    """Get trading parameters configuration keyboard."""
    params = config_manager.get_trading_params()
    # Get values with defaults if not set
    leverage = params.get('leverage', 5)
    balance_pct = params.get('balance_percentage', 0.1)
    
    keyboard = [
        [InlineKeyboardButton(f"🔧 Leverage: {leverage}x", callback_data='set_leverage')],
        [InlineKeyboardButton(f"💰 Balance %: {balance_pct * 100:.1f}%", callback_data='set_balance')],
        [InlineKeyboardButton("« Back to Settings", callback_data='menu_settings')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_leverage_keyboard():
    """Get leverage selection keyboard."""
    keyboard = []
    row = []
    for lev in [1, 2, 3, 5, 10, 15, 20]:
        row.append(InlineKeyboardButton(f"{lev}x", callback_data=f'leverage_{lev}'))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("« Back", callback_data='setup_params')])
    return InlineKeyboardMarkup(keyboard)

def get_balance_percentage_keyboard():
    """Get balance percentage selection keyboard."""
    keyboard = []
    row = []
    for pct in [1, 2, 5, 10, 15, 20, 25, 50]:
        row.append(InlineKeyboardButton(f"{pct}%", callback_data=f'balance_{pct}'))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("« Back", callback_data='setup_params')])
    return InlineKeyboardMarkup(keyboard)

def get_position_keyboard(symbol: str):
    """Get keyboard for position actions."""
    keyboard = [
        [
            InlineKeyboardButton("🔴 Close Position", callback_data=f'close_{symbol}'),
            InlineKeyboardButton("🔄 Refresh", callback_data='view_positions')
        ],
        [InlineKeyboardButton("« Back to Trading", callback_data='menu_trading')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_close_position_keyboard(symbol: str):
    """Get keyboard for position closing options."""
    keyboard = [
        [
            InlineKeyboardButton("25%", callback_data=f'close_pct_{symbol}_25'),
            InlineKeyboardButton("50%", callback_data=f'close_pct_{symbol}_50'),
            InlineKeyboardButton("75%", callback_data=f'close_pct_{symbol}_75')
        ],
        [
            InlineKeyboardButton("100%", callback_data=f'close_pct_{symbol}_100'),
            InlineKeyboardButton("Custom %", callback_data=f'close_custom_{symbol}')
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data='view_positions'),
            InlineKeyboardButton("« Cancel", callback_data='view_positions')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return

    welcome_text = """Welcome to the Bybit Trading Bot! 🚀

Please select an option from the menu below:"""
    
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu_keyboard())

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == 'menu_main':
        await query.edit_message_text(
            "Main Menu:",
            reply_markup=get_main_menu_keyboard()
        )
    
    elif data == 'switch_env':
        # Show environment selection keyboard
        await query.edit_message_text(
            "🌍 Select Environment:",
            reply_markup=get_environment_keyboard()
        )
    
    elif data.startswith('switch_'):
        env = data.split('_')[1]
        use_testnet = env == 'testnet'
        try:
            # Switch environment in config
            config_manager.switch_environment(use_testnet)
            
            # Reinitialize the trading bot with new environment
            initialize_trading_bot()
            
            # Get current balance to show in message
            try:
                balance = trading_bot.get_wallet_balance()
                balance_text = f"\nBalance: ${format_number(balance)} USDT"
            except:
                balance_text = "\nFetching balance..."
            
            # Create a unique message each time
            timestamp = datetime.now().strftime("%H:%M:%S")
            await query.edit_message_text(
                f"✅ Switched to {env.upper()} mode at {timestamp}{balance_text}\n\nMain Menu:",
                reply_markup=get_main_menu_keyboard()  # Return to main menu after switching
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error switching to {env.upper()}: {str(e)}\n\nMain Menu:",
                reply_markup=get_main_menu_keyboard()  # Return to main menu on error
            )
    
    elif data == 'quick_trade':
        await query.edit_message_text(
            "⚡️ Quick Trade Menu\nSelect a quick trade option:",
            reply_markup=get_quick_trade_keyboard()
        )
    
    elif data.startswith('quick_'):
        # Handle quick trade actions
        action, direction, symbol = data.split('_')  # quick_buy_btc or quick_sell_btc
        symbol = symbol.upper() + "USDT"
        
        try:
            # Get current market price
            params = config_manager.get_trading_params()
            
            # Format the instruction
            side = "LONG" if direction == "buy" else "SHORT"
            instruction = f"{side} ${symbol}\nEntry 0\n"  # 0 means market price
            
            # Calculate stop loss (2% for now)
            current_price = trading_bot.get_market_price(symbol)
            sl_price = current_price * 0.98 if direction == "buy" else current_price * 1.02
            instruction += f"Stl {sl_price:.1f}\n"
            
            # Calculate take profits (2% and 4%)
            if direction == "buy":
                tp1 = current_price * 1.02
                tp2 = current_price * 1.04
            else:
                tp1 = current_price * 0.98
                tp2 = current_price * 0.96
            instruction += f"Tp {tp1:.1f} - {tp2:.1f}"
            
            # Process the quick trade
            success, result = process_instruction(instruction, trading_bot)
            
            # Show result and positions
            positions_message, keyboard = get_active_positions()
            await query.edit_message_text(
                f"⚡️ Quick Trade Executed!\n\n{result}\n\n{positions_message}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error executing quick trade: {str(e)}",
                reply_markup=get_quick_trade_keyboard()
            )
    
    elif data == 'balance_info':
        try:
            
            balance = trading_bot.get_wallet_balance()
            positions = trading_bot.get_active_positions()
            
            total_pnl = sum(pos['unrealized_pnl'] for pos in positions)
            total_position_value = sum(pos['position_value'] for pos in positions)
            
            message = f"""💰 Balance Information:

Available Balance: ${format_number(balance)} USDT
Positions Value: ${format_number(total_position_value)} USDT
Unrealized PNL: ${format_number(total_pnl)} USDT
Active Positions: {len(positions)}

Risk Level: {"🟢 Low" if total_position_value < balance * 0.5 else "🟡 Medium" if total_position_value < balance * 0.8 else "🔴 High"}"""
            
            await query.edit_message_text(
                message,
                reply_markup=get_main_menu_keyboard()
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error fetching balance: {str(e)}",
                reply_markup=get_main_menu_keyboard()
            )
    
    elif data.startswith('update_sltp_'):
        symbol = data.split('_')[2]
        # Show SL/TP update options
        keyboard = [
            [
                InlineKeyboardButton("-1%", callback_data=f'sl_minus_{symbol}'),
                InlineKeyboardButton("SL", callback_data=f'sl_current_{symbol}'),
                InlineKeyboardButton("+1%", callback_data=f'sl_plus_{symbol}')
            ],
            [
                InlineKeyboardButton("-1%", callback_data=f'tp_minus_{symbol}'),
                InlineKeyboardButton("TP", callback_data=f'tp_current_{symbol}'),
                InlineKeyboardButton("+1%", callback_data=f'tp_plus_{symbol}')
            ],
            [InlineKeyboardButton("« Back", callback_data='view_positions')]
        ]
        await query.edit_message_text(
            f"🎯 Adjust Stop Loss/Take Profit for {symbol}:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == 'menu_settings':
        await query.edit_message_text(
            "⚙️ Settings Menu\nConfigure your bot settings here:",
            reply_markup=get_settings_keyboard()
        )
    
    elif data == 'menu_trading':
        await query.edit_message_text(
            "📊 Trading Menu\nManage your trades here:",
            reply_markup=get_trading_keyboard()
        )
    
    elif data == 'menu_status':
        # Get current status
        env = config_manager.get_environment()
        params = config_manager.get_trading_params()
        api_key, _ = config_manager.get_active_api_keys()
        
        status_text = f"""📊 Bot Status:

🌍 Environment: {env.upper()}
📈 Trading Parameters:
   • Leverage: {params['leverage']}x
   • Balance: {params['balance_percentage'] * 100}%
🔑 API: {'Configured ✅' if api_key else 'Not Configured ❌'}

Select an option:"""
        
        keyboard = [
            [InlineKeyboardButton("« Back to Main Menu", callback_data='menu_main')]
        ]
        await query.edit_message_text(status_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == 'menu_help':
        help_text = """❓ Help Menu

📝 Trading Format:
LONG/SHORT $SYMBOL
Entry <price>  (use 0 for market price)
Stl <price>
Tp <price1> - <price2> - ...

Examples:
1. Limit Order:
LONG $BTC
Entry 43500
Stl 42800
Tp 44000 - 44500 - 45000

2. Market Order:
SHORT $ETH
Entry 0
Stl 2100
Tp 1950 - 1900 - 1850

Select an option:"""
        
        keyboard = [
            [InlineKeyboardButton("« Back to Main Menu", callback_data='menu_main')]
        ]
        await query.edit_message_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == 'setup_api':
        await query.edit_message_text(
            "🔑 API Key Setup\n\nPlease use the /setapi command to configure your API keys securely."
        )
    
    elif data == 'setup_params':
        await query.edit_message_text(
            "📊 Trading Parameters\nSelect a parameter to configure:",
            reply_markup=get_trading_params_keyboard()
        )
    
    elif data == 'set_leverage':
        await query.edit_message_text(
            "🔢 Select Leverage:",
            reply_markup=get_leverage_keyboard()
        )
    
    elif data == 'set_balance':
        await query.edit_message_text(
            "💰 Select Balance Percentage:",
            reply_markup=get_balance_percentage_keyboard()
        )
    
    elif data.startswith('leverage_'):
        leverage = int(data.split('_')[1])
        config_manager.set_trading_params(leverage=leverage)
        await query.edit_message_text(
            f"Leverage updated to {leverage}x ✅\n\nTrading Parameters:",
            reply_markup=get_trading_params_keyboard()
        )
    
    elif data.startswith('balance_'):
        percentage = float(data.split('_')[1])
        config_manager.set_trading_params(balance_percentage=percentage/100)
        await query.edit_message_text(
            f"Balance percentage updated to {percentage}% ✅\n\nTrading Parameters:",
            reply_markup=get_trading_params_keyboard()
        )
    
    elif data == 'new_trade':
        await query.edit_message_text(
            """📝 New Trade

Please send your trade instruction in the following format:

LONG/SHORT $SYMBOL
Entry <price>  (use 0 for market price)
Stl <price>
Tp <price1> - <price2> - ...

Examples:
1. Limit Order:
LONG $BTC
Entry 43500
Stl 42800
Tp 44000 - 44500 - 45000

2. Market Order:
SHORT $ETH
Entry 0
Stl 2100
Tp 1950 - 1900 - 1850""",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Trading", callback_data='menu_trading')]])
        )
    
    elif data == 'view_positions':
        await query.edit_message_text(
            "📊 Fetching active positions...",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Refresh", callback_data='view_positions'),
                InlineKeyboardButton("« Back to Trading", callback_data='menu_trading')
            ]])
        )
        message, keyboard = get_active_positions()
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == 'trade_history':
        await query.edit_message_text(
            "📜 Fetching trading history...",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Trading", callback_data='menu_trading')]])
        )
        history = get_trading_history()
        await query.edit_message_text(
            history,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Trading", callback_data='menu_trading')]])
        )
    
    elif data.startswith('close_'):
        symbol = data.split('_')[1]
        positions = get_active_positions()
        await query.edit_message_text(
            positions,
            reply_markup=get_position_keyboard(symbol)
        )
        return await start_position_close(update, context)
    
    elif data == 'close_all_positions':
        await handle_close_all_positions(update, context)
    
    elif data == 'confirm_close_all':
        await execute_close_all_positions(update, context)

async def start_api_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the API setup process."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return ConversationHandler.END

    env = config_manager.get_environment()
    await update.message.reply_text(f"Please enter your Bybit {env} API key:")
    return AWAITING_API_KEY

async def receive_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive API key and ask for API secret."""
    context.user_data['api_key'] = update.message.text
    await update.message.reply_text("Now, please enter your API secret:")
    return AWAITING_API_SECRET

async def receive_api_secret(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive API secret and complete setup."""
    api_key = context.user_data['api_key']
    api_secret = update.message.text
    is_testnet = config_manager.get_environment() == 'testnet'
    
    if config_manager.set_api_keys(api_key, api_secret, is_testnet):
        await update.message.reply_text(
            "API keys configured successfully!",
            reply_markup=get_settings_keyboard()
        )
    else:
        await update.message.reply_text(
            "Failed to configure API keys. Please try again.",
            reply_markup=get_settings_keyboard()
        )
    
    return ConversationHandler.END

async def set_params(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the process of setting trading parameters."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return ConversationHandler.END

    await update.message.reply_text("Please enter the leverage (1-20):")
    return AWAITING_LEVERAGE

async def receive_leverage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive leverage and ask for balance percentage."""
    try:
        leverage = int(update.message.text)
        if 1 <= leverage <= 20:
            context.user_data['leverage'] = leverage
            await update.message.reply_text(
                "Please enter the balance percentage to use (1-100):",
                reply_markup=get_trading_params_keyboard()
            )
            return AWAITING_BALANCE_PERCENTAGE
        else:
            await update.message.reply_text(
                "Please enter a valid leverage between 1 and 20:",
                reply_markup=get_trading_params_keyboard()
            )
            return AWAITING_LEVERAGE
    except ValueError:
        await update.message.reply_text(
            "Please enter a valid number between 1 and 20:",
            reply_markup=get_trading_params_keyboard()
        )
        return AWAITING_LEVERAGE

async def receive_balance_percentage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive balance percentage and complete setup."""
    try:
        percentage = float(update.message.text)
        if 1 <= percentage <= 100:
            leverage = context.user_data['leverage']
            config_manager.set_trading_params(
                leverage=leverage,
                balance_percentage=percentage/100
            )
            await update.message.reply_text(f"Trading parameters updated:\nLeverage: {leverage}x\nBalance Percentage: {percentage}%")
            return ConversationHandler.END
        else:
            await update.message.reply_text("Percentage must be between 1 and 100. Try again:")
            return AWAITING_BALANCE_PERCENTAGE
    except ValueError:
        await update.message.reply_text("Please enter a valid number. Try again:")
        return AWAITING_BALANCE_PERCENTAGE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the current conversation and show main menu."""
    if update.message:
        await update.message.reply_text(
            "Operation cancelled.",
            reply_markup=get_main_menu_keyboard()
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            "Operation cancelled.",
            reply_markup=get_main_menu_keyboard()
        )
    return ConversationHandler.END

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return

    message = update.message.text
    try:
        success, result = process_instruction(message, trading_bot)
        await update.message.reply_text(
            result,
            parse_mode=None,  # Disable markdown formatting
            reply_markup=get_trading_keyboard()
        )
    except Exception as e:
        await update.message.reply_text(
            f"Error processing instruction: {str(e)}",
            parse_mode=None,  # Disable markdown formatting
            reply_markup=get_trading_keyboard()
        )

async def start_position_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the position closing process."""
    query = update.callback_query
    await query.answer()
    
    # Store symbol in context
    symbol = query.data.split('_')[1]
    context.user_data['closing_symbol'] = symbol
    
    await query.edit_message_text(
        f"Select percentage to close for {symbol}:",
        reply_markup=get_close_position_keyboard(symbol)
    )
    return AWAITING_CLOSE_PERCENTAGE

async def handle_close_percentage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the close percentage input."""
    try:
        symbol = context.user_data.get('closing_symbol')
        if not symbol:
            await update.effective_message.reply_text("Error: No position selected")
            return ConversationHandler.END

        if update.callback_query:
            query = update.callback_query
            await query.answer()
            
            if query.data.startswith('close_pct_'):
                # Handle preset percentage selection
                percentage = float(query.data.split('_')[-1])
            elif query.data == 'view_positions':
                # Handle cancel button
                message, keyboard = get_active_positions()
                await query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return ConversationHandler.END
            elif query.data.startswith('close_custom_'):
                # Handle custom percentage request
                await query.edit_message_text(
                    f"Enter a custom percentage to close for {symbol} (1-100):",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("Cancel", callback_data='view_positions')
                    ]])
                )
                return AWAITING_CLOSE_PERCENTAGE
            else:
                return ConversationHandler.END
        else:
            # Handle custom percentage input
            percentage = float(update.message.text)
            if not (0 < percentage <= 100):
                await update.message.reply_text("Percentage must be between 1 and 100. Try again:")
                return AWAITING_CLOSE_PERCENTAGE
        
        # Close position
        
        success, message = trading_bot.close_position(symbol, percentage)
        
        # Send result
        if success:
            result_message = f"✅ {message}"
        else:
            result_message = f"❌ {message}"
            
        # Update positions view
        positions_message, keyboard = get_active_positions()
        if isinstance(update, Update) and update.message:
            await update.message.reply_text(
                positions_message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        elif update.callback_query:
            await update.callback_query.edit_message_text(
                positions_message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except ValueError:
        await update.effective_message.reply_text("Please enter a valid number between 1 and 100:")
        return AWAITING_CLOSE_PERCENTAGE
    except Exception as e:
        error_message = f"Error: {str(e)}"
        if isinstance(update, Update) and update.message:
            await update.message.reply_text(
                error_message,
                reply_markup=get_trading_keyboard()
            )
        elif update.callback_query:
            await update.callback_query.edit_message_text(
                error_message,
                reply_markup=get_trading_keyboard()
            )
    
    return ConversationHandler.END

def get_trading_history() -> str:
    """Get trading history from Bybit."""
    try:
        history = trading_bot.get_trading_history()
        
        if not history:
            return "No trading history found."
            
        message = "📜 Recent Trading History:\n\n"
        for trade in history:
            side = "🟢 LONG" if trade['side'] == "Buy" else "🔴 SHORT"
            status = "✅" if trade['state'] == "Filled" else "⏳"
            message += f"{status} {side} {trade['symbol']}\n"
            message += f"    Price: {trade['price']} USDT\n"
            message += f"    Size: {trade['qty']} {trade['symbol'].replace('USDT', '')}\n"
            message += f"    Time: {trade['created_time']}\n\n"
        
        return message
    except Exception as e:
        return f"Error fetching trading history: {str(e)}"

def format_number(num: float, decimals: int = 2) -> str:
    """Format number with appropriate decimals and commas."""
    try:
        # Handle None or invalid values
        if num is None:
            return "0.00"
            
        # Convert to float if string
        if isinstance(num, str):
            num = float(num)
            
        # Store sign
        is_negative = num < 0
        abs_num = abs(num)
        
        # Format the absolute number with commas and decimals
        formatted = f"{abs_num:,.{decimals}f}"
        
        # Add negative sign if needed
        return f"-{formatted}" if is_negative else formatted
        
    except (ValueError, TypeError):
        return "0.00"

def get_quick_trade_keyboard():
    """Get quick trade options keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("⚡️ Market Buy BTC", callback_data='quick_buy_btc'),
            InlineKeyboardButton("⚡️ Market Sell BTC", callback_data='quick_sell_btc')
        ],
        [
            InlineKeyboardButton("⚡️ Market Buy ETH", callback_data='quick_buy_eth'),
            InlineKeyboardButton("⚡️ Market Sell ETH", callback_data='quick_sell_eth')
        ],
        [InlineKeyboardButton("« Back to Main Menu", callback_data='menu_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def calculate_risk_level(liq_distance: float) -> str:
    """Calculate risk level based on liquidation distance percentage."""
    if liq_distance >= 50:
        return "🟢 LOW RISK"
    elif liq_distance >= 25:
        return "🟡 MEDIUM RISK"
    elif liq_distance >= 10:
        return "🔴 HIGH RISK"
    else:
        return "💀 EXTREME RISK"

def format_position_message(pos) -> str:
    """Enhanced position message formatting."""
    # Calculate duration
    try:
        from datetime import datetime
        created_time = datetime.fromtimestamp(pos.get('created_time', 0) / 1000)
        duration = datetime.now() - created_time
        duration_str = f"{duration.days}d {duration.seconds//3600}h {(duration.seconds//60)%60}m"
    except:
        duration_str = "N/A"

    # Calculate risk level based on liquidation distance
    try:
        distance_to_liq = abs(pos['current_price'] - pos['liq_price']) / pos['current_price'] * 100
        risk_level = calculate_risk_level(distance_to_liq)
    except:
        risk_level = "⚪️ UNKNOWN"

    # Format the message
    side_emoji = "🟢" if pos['side'] == "Buy" else "🔴"
    pnl_emoji = "📈" if pos['unrealized_pnl'] > 0 else "📉"
    
    message = f"""{'='*40}
{side_emoji} {pos['side'].upper()} {pos['symbol']}

💰 PNL: {pnl_emoji} {format_number(pos['unrealized_pnl'])} USDT ({format_number(pos['pnl_percentage'])}%)
📊 Position Value: {format_number(pos['position_value'])} USDT
📐 Size: {format_number(pos['size'])} {pos['symbol'].replace('USDT', '')}

📍 Entry: {format_number(pos['entry_price'])} USDT
💹 Current: {format_number(pos['current_price'])} USDT
⚠️ Liq. Price: {format_number(pos['liq_price'])} USDT

⏱️ Duration: {duration_str}
🔧 Leverage: {pos['leverage']}x
⚠️ Risk Level: {risk_level}
{'='*40}"""
    
    return message

def format_positions_message(positions: list) -> str:
    """Format positions list into a readable message with comprehensive position data."""
    if not positions:
        return "📊 No active positions found"
        
    # Calculate totals
    total_unrealised_pnl = sum(float(pos.get('unrealisedPnl', '0')) for pos in positions)
    total_position_value = sum(float(pos.get('positionValue', '0')) for pos in positions)
    total_margin = sum(float(pos.get('positionIM', '0')) for pos in positions)
    
    # Format header with totals
    message = "📊 POSITIONS SUMMARY\n" + "=" * 40 + "\n\n"
    message += f"💰 Total Unrealized PNL: {format_number(total_unrealised_pnl)} USDT\n"
    message += f"📊 Total Position Value: {format_number(total_position_value)} USDT\n"
    message += f"💫 Total Initial Margin: {format_number(total_margin)} USDT\n"
    message += f"📈 Active Positions: {len(positions)}\n\n"
    message += "=" * 40 + "\n"
    
    # Format each position
    for pos in positions:
        try:
            # Extract basic position information
            symbol = pos.get('symbol', 'Unknown')
            side = pos.get('side', 'Unknown')
            side_emoji = "🟢" if side == "Buy" else "🔴"
            position_status = pos.get('positionStatus', 'Normal')
            
            # Position size and value
            size = float(pos.get('size', '0'))
            position_value = float(pos.get('positionValue', '0'))
            leverage = pos.get('leverage', '1')
            
            # Price information
            entry_price = float(pos.get('avgPrice', '0'))
            mark_price = float(pos.get('markPrice', '0'))
            liq_price = pos.get('liqPrice', '')
            
            # PNL calculations
            unrealised_pnl = float(pos.get('unrealisedPnl', '0'))
            cum_realised_pnl = float(pos.get('cumRealisedPnl', '0'))
            pnl_percentage = (unrealised_pnl / position_value * 100) if position_value > 0 else 0
            
            # Margin information
            position_mm = float(pos.get('positionMM', '0'))  # Maintenance margin
            position_im = float(pos.get('positionIM', '0'))  # Initial margin
            
            # Format position header
            message += f"\n{side_emoji} {side.upper()} {symbol}\n"
            
            # Position status and mode
            status_emoji = "✅" if position_status == "Normal" else "⚠️" if position_status == "Liq" else "⛔️"
            message += f"Status: {status_emoji} {position_status}\n"
            
            # PNL section
            pnl_emoji = "📈" if unrealised_pnl > 0 else "📉"
            message += f"\n💰 Unrealized PNL: {pnl_emoji} {format_number(unrealised_pnl)} USDT ({format_number(pnl_percentage, 2)}%)\n"
            message += f"💵 Cumulative Realized PNL: {format_number(cum_realised_pnl)} USDT\n"
            
            # Position details
            message += f"\n📊 Position Details:\n"
            message += f"• Size: {format_number(size, 4)} {symbol.replace('USDT', '')}\n"
            message += f"• Value: {format_number(position_value)} USDT\n"
            message += f"• Leverage: {leverage}x\n"
            
            # Price information
            message += f"\n💹 Price Information:\n"
            message += f"• Entry: {format_number(entry_price)} USDT\n"
            message += f"• Mark: {format_number(mark_price)} USDT\n"
            if liq_price and liq_price != '':
                liq_distance = abs((float(liq_price) - mark_price) / mark_price * 100)
                message += f"• Liquidation: {format_number(float(liq_price))} USDT ({format_number(liq_distance, 2)}% away)\n"
                
                # Calculate risk level based on liquidation distance
                risk_level = calculate_risk_level(liq_distance)
            else:
                risk_level = "⚪️ UNKNOWN"
            
            # Margin information
            message += f"\n💫 Margin Information:\n"
            message += f"• Initial Margin: {format_number(position_im)} USDT\n"
            message += f"• Maintenance Margin: {format_number(position_mm)} USDT\n"
            
            # Risk assessment
            message += f"\n⚠️ Risk Level: {risk_level}\n"
            
            # Position duration
            try:
                created_time = int(pos.get('createdTime', '0')) / 1000
                if created_time > 0:
                    from datetime import datetime
                    duration = datetime.now() - datetime.fromtimestamp(created_time)
                    duration_str = f"{duration.days}d {duration.seconds//3600}h {(duration.seconds//60)%60}m"
                    message += f"⏱️ Duration: {duration_str}\n"
            except Exception as e:
                print(f"Error calculating duration: {str(e)}")
            
            message += "=" * 40 + "\n"
            
        except Exception as e:
            print(f"Error formatting position {pos.get('symbol', 'Unknown')}: {str(e)}")
            continue
    
    return message

def get_active_positions() -> Tuple[str, List[List[InlineKeyboardButton]]]:
    """Enhanced get and format active positions."""
    try:
        
        positions = trading_bot.get_active_positions()
        
        # Format the positions message
        message = format_positions_message(positions)
        
        # Create buttons for each position
        buttons = []
        if positions:
            for pos in positions:
                symbol = pos.get('symbol', '')
                if symbol:
                    buttons.append([
                        InlineKeyboardButton(f"Close {symbol}", callback_data=f"close_{symbol}")
                    ])
        
        # Add refresh and back buttons
        nav_buttons = [
            InlineKeyboardButton("🔄 Refresh", callback_data="view_positions"),
            InlineKeyboardButton("« Back to Trading", callback_data="menu_trading")
        ]
        buttons.append(nav_buttons)
        
        return message, buttons
        
    except Exception as e:
        error_msg = f"❌ Error fetching positions: {str(e)}"
        error_buttons = [[
            InlineKeyboardButton("🔄 Retry", callback_data="view_positions"),
            InlineKeyboardButton("« Back to Main", callback_data="menu_main")
        ]]
        return error_msg, error_buttons

async def handle_close_all_positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle closing all positions."""
    query = update.callback_query
    await query.answer()
    
    # Show confirmation keyboard
    await query.edit_message_text(
        "⚠️ Are you sure you want to close ALL positions?",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, Close All", callback_data='confirm_close_all'),
                InlineKeyboardButton("❌ Cancel", callback_data='view_positions')
            ]
        ])
    )

async def execute_close_all_positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Execute closing all positions after confirmation."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "Closing all positions...",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Please wait...", callback_data='dummy')
        ]])
    )
    
    try:
        
        success, message = trading_bot.close_all_positions()
        
        # Get updated positions
        positions_message, keyboard = get_active_positions()
        
        # Show result and keep the menu
        if success:
            await query.edit_message_text(
                f"✅ {message}\n\n{positions_message}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text(
                f"❌ {message}\n\n{positions_message}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except Exception as e:
        await query.edit_message_text(
            f"❌ Error: {str(e)}",
            reply_markup=get_trading_keyboard()  # Show trading menu on error
        )

def main() -> None:
    """Start the Telegram bot."""
    # Create the Application
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add conversation handlers
    api_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('setapi', start_api_setup)],
        states={
            AWAITING_API_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_api_key)],
            AWAITING_API_SECRET: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_api_secret)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    params_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('setparams', set_params)],
        states={
            AWAITING_LEVERAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_leverage)],
            AWAITING_BALANCE_PERCENTAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_balance_percentage)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Add close position conversation handler
    close_position_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_position_close, pattern=r'^close_.*')],
        states={
            AWAITING_CLOSE_PERCENTAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_close_percentage),
                CallbackQueryHandler(handle_close_percentage, pattern=r'^(close_pct_|close_custom_|view_positions)')
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CallbackQueryHandler(button_callback, pattern=r'^view_positions$')
        ],
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(api_conv_handler)
    application.add_handler(params_conv_handler)
    application.add_handler(close_position_handler)
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the bot
    print("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 