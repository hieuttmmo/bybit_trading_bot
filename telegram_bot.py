import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
from dotenv import load_dotenv
from bybit_trading_bot import process_instruction, BybitTradingBot
from config_manager import ConfigManager
from typing import Tuple, List

# Load environment variables
load_dotenv()

# Get Telegram token from environment variable
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
ALLOWED_USER_IDS = [int(id.strip()) for id in os.getenv('ALLOWED_TELEGRAM_USERS', '').split(',') if id.strip()]

if not TELEGRAM_TOKEN:
    raise ValueError("Please set TELEGRAM_TOKEN in your .env file")

if not ALLOWED_USER_IDS:
    raise ValueError("Please set ALLOWED_TELEGRAM_USERS in your .env file")

# Initialize config manager
config_manager = ConfigManager()

# States for conversation handler
AWAITING_API_KEY, AWAITING_API_SECRET, AWAITING_LEVERAGE, AWAITING_BALANCE_PERCENTAGE, AWAITING_CLOSE_PERCENTAGE = range(5)

def is_authorized(user_id: int) -> bool:
    """Check if user is authorized to use the bot."""
    return user_id in ALLOWED_USER_IDS

def get_main_menu_keyboard():
    """Get the main menu keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Trading", callback_data='menu_trading'),
            InlineKeyboardButton("⚙️ Settings", callback_data='menu_settings')
        ],
        [
            InlineKeyboardButton("📈 Status", callback_data='menu_status'),
            InlineKeyboardButton("❓ Help", callback_data='menu_help')
        ]
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
    keyboard = [
        [InlineKeyboardButton(f"🔢 Leverage: {params['leverage']}x", callback_data='set_leverage')],
        [InlineKeyboardButton(f"💰 Balance %: {params['balance_percentage'] * 100}%", callback_data='set_balance')],
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
    keyboard = []
    # Common percentages in rows of 3
    percentages = [25, 50, 75, 100]
    row = []
    for pct in percentages:
        row.append(InlineKeyboardButton(f"{pct}%", callback_data=f'close_pct_{symbol}_{pct}'))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    # Add custom percentage option and cancel
    keyboard.append([
        InlineKeyboardButton("Custom %", callback_data=f'close_custom_{symbol}'),
        InlineKeyboardButton("Cancel", callback_data='view_positions')
    ])
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
            "Main Menu - Please select an option:",
            reply_markup=get_main_menu_keyboard()
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
    
    elif data == 'switch_env':
        await query.edit_message_text(
            "🌍 Select Environment:",
            reply_markup=get_environment_keyboard()
        )
    
    elif data.startswith('switch_'):
        env = data.split('_')[1]
        use_testnet = env == 'testnet'
        config_manager.switch_environment(use_testnet)
        await query.edit_message_text(
            f"Switched to {env.upper()} ✅\n\nSettings Menu:",
            reply_markup=get_settings_keyboard()
        )
    
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
        await update.message.reply_text("API keys configured successfully!")
    else:
        await update.message.reply_text("Failed to configure API keys. Please try again.")
    
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
            await update.message.reply_text("Now, enter the balance percentage (1-100):")
            return AWAITING_BALANCE_PERCENTAGE
        else:
            await update.message.reply_text("Leverage must be between 1 and 20. Try again:")
            return AWAITING_LEVERAGE
    except ValueError:
        await update.message.reply_text("Please enter a valid number. Try again:")
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
    """Cancel the current conversation."""
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming trading instructions."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return

    message_text = update.message.text

    # Check if the message looks like a trading instruction
    if any(action in message_text.upper().split('\n')[0] for action in ['LONG', 'SHORT']):
        try:
            # Send acknowledgment
            await update.message.reply_text("Processing your trading instruction...")
            
            # Process the instruction
            success, message = process_instruction(message_text)
            
            if success:
                await update.message.reply_text(f"✅ Trade executed successfully!\n{message}")
            else:
                await update.message.reply_text(f"❌ Error executing trade:\n{message}")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    else:
        # Message doesn't look like a trading instruction
        await update.message.reply_text("Invalid instruction format. Please use the format shown in /help")

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
    """Handle the closing percentage input."""
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
        bot = BybitTradingBot()
        success, message = bot.close_position(symbol, percentage)
        
        # Send result
        if success:
            result_message = f"✅ {message}"
        else:
            result_message = f"❌ {message}"
            
        # Update positions view
        positions_message, keyboard = get_active_positions()
        await update.effective_message.reply_text(
            result_message + "\n\n" + positions_message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return ConversationHandler.END
        
    except ValueError:
        await update.effective_message.reply_text("Please enter a valid number between 1 and 100:")
        return AWAITING_CLOSE_PERCENTAGE
    except Exception as e:
        await update.effective_message.reply_text(f"Error: {str(e)}")
        return ConversationHandler.END

def get_trading_history() -> str:
    """Get trading history from Bybit."""
    try:
        bot = BybitTradingBot()
        history = bot.get_trading_history()
        
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
    return f"{num:,.{decimals}f}"

def get_active_positions() -> Tuple[str, List[List[InlineKeyboardButton]]]:
    """Get and format active positions. Returns tuple of (message, keyboard)."""
    try:
        bot = BybitTradingBot()
        positions = bot.get_active_positions()
        
        if not positions:
            return "No active positions found.", [[InlineKeyboardButton("« Back to Trading", callback_data='menu_trading')]]
            
        message = "📊 Active Positions:\n\n"
        keyboard = []
        
        for pos in positions:
            # Format PNL with color emoji
            pnl_emoji = "🟢" if pos['unrealized_pnl'] > 0 else "🔴"
            pnl_text = f"{pnl_emoji} {format_number(pos['unrealized_pnl'])} USDT ({format_number(pos['pnl_percentage'])}%)"
            
            # Format side with color
            side_emoji = "🟢" if pos['side'] == "Buy" else "🔴"
            side_text = f"{side_emoji} {'LONG' if pos['side'] == 'Buy' else 'SHORT'}"
            
            # Calculate price movement
            price_change = ((pos['current_price'] - pos['entry_price']) / pos['entry_price']) * 100
            price_emoji = "📈" if price_change > 0 else "📉"
            
            message += f"{'='*40}\n"
            message += f"{side_text} {pos['symbol']}\n\n"
            
            message += f"💰 PNL: {pnl_text}\n"
            message += f"📊 Position Value: {format_number(pos['position_value'])} USDT\n"
            message += f"📐 Size: {format_number(pos['size'])} {pos['symbol'].replace('USDT', '')}\n\n"
            
            message += f"📍 Entry: {format_number(pos['entry_price'])} USDT\n"
            message += f"{price_emoji} Current: {format_number(pos['current_price'])} USDT ({format_number(price_change)}%)\n"
            if pos['liq_price']:
                message += f"⚠️ Liq. Price: {format_number(pos['liq_price'])} USDT\n"
            
            message += f"🔧 Leverage: {pos['leverage']}x\n\n"
            
            # Add close button for this position
            keyboard.append([InlineKeyboardButton(f"🔴 Close {pos['symbol']}", callback_data=f"close_{pos['symbol']}")])
        
        # Add close all button if there are multiple positions
        if len(positions) > 1:
            keyboard.append([InlineKeyboardButton("🔴 Close All Positions", callback_data='close_all_positions')])
        
        # Add refresh and back buttons
        keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data='view_positions')])
        keyboard.append([InlineKeyboardButton("« Back to Trading", callback_data='menu_trading')])
        
        return message, keyboard
        
    except Exception as e:
        error_msg = f"Error fetching positions: {str(e)}"
        error_keyboard = [[InlineKeyboardButton("« Back to Trading", callback_data='menu_trading')]]
        return error_msg, error_keyboard

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
        bot = BybitTradingBot()
        success, message = bot.close_all_positions()
        
        # Get updated positions
        positions_message, keyboard = get_active_positions()
        
        # Show result
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
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Back to Trading", callback_data='menu_trading')
            ]])
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