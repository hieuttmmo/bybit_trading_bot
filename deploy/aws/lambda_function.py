import json
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from src.bot.trading import process_instruction, BybitTradingBot
from src.bot.telegram import (
    start, button_callback, handle_message,
    start_api_setup, receive_api_key, receive_api_secret,
    set_params, receive_leverage, receive_balance_percentage,
    cancel, start_position_close, handle_close_percentage,
    handle_close_all_positions, execute_close_all_positions
)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize bot application
application = Application.builder().token(os.environ['TELEGRAM_TOKEN']).build()

# Set up handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", start))

# Add conversation handlers
api_conv_handler = ConversationHandler(
    entry_points=[CommandHandler('setapi', start_api_setup)],
    states={
        'AWAITING_API_KEY': [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_api_key)],
        'AWAITING_API_SECRET': [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_api_secret)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)
application.add_handler(api_conv_handler)

params_conv_handler = ConversationHandler(
    entry_points=[CommandHandler('setparams', set_params)],
    states={
        'AWAITING_LEVERAGE': [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_leverage)],
        'AWAITING_BALANCE_PERCENTAGE': [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_balance_percentage)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)
application.add_handler(params_conv_handler)

# Add callback query handler
application.add_handler(CallbackQueryHandler(button_callback))

# Add message handler
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

async def process_update(event, context):
    """AWS Lambda handler function."""
    try:
        # Parse the update from Telegram
        if 'body' not in event:
            return {'statusCode': 400, 'body': 'No body found'}
            
        body = json.loads(event['body'])
        update = Update.de_json(body, application.bot)
        
        # Process the update
        await application.process_update(update)
        
        return {
            'statusCode': 200,
            'body': 'OK'
        }
        
    except Exception as e:
        logger.error(f"Error processing update: {str(e)}")
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }

def lambda_handler(event, context):
    """Main Lambda handler."""
    return process_update(event, context) 