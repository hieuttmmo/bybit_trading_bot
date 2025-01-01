import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def set_webhook(webhook_url: str):
    """Set webhook for Telegram bot."""
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_TOKEN not found in environment variables")
        
    api_url = f"https://api.telegram.org/bot{token}/setWebhook"
    
    response = requests.post(
        api_url,
        json={'url': webhook_url}
    )
    
    if response.status_code == 200:
        print(f"Webhook set successfully: {response.json()}")
    else:
        print(f"Error setting webhook: {response.text}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python set_webhook.py <webhook_url>")
        print("Example: python set_webhook.py https://your-api-gateway-url/dev/webhook")
        sys.exit(1)
        
    webhook_url = sys.argv[1]
    set_webhook(webhook_url) 