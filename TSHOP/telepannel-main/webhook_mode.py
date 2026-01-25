#!/usr/bin/env python3
"""
Alternative startup script using webhook mode instead of polling.
This avoids the 409 conflict error when multiple instances try to poll.
"""

import os
from flask import Flask, request, abort
import telebot
from config import API_TOKENS, ADMIN_ID

# Create Flask app for webhook
app = Flask(__name__)

# Initialize bot
bot = telebot.TeleBot(API_TOKENS[0])

# Import all handlers
from other_handlers import *

# Webhook URL - you'll need to set this to your server's URL
WEBHOOK_URL = "https://your-server.com/webhook"  # Change this to your server URL

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming webhook requests"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        abort(403)

@app.route('/set_webhook')
def set_webhook():
    """Set the webhook URL"""
    result = bot.set_webhook(url=WEBHOOK_URL)
    return f"Webhook set: {result}"

@app.route('/remove_webhook')
def remove_webhook():
    """Remove the webhook"""
    result = bot.remove_webhook()
    return f"Webhook removed: {result}"

if __name__ == '__main__':
    print("🚀 Starting bot in webhook mode...")
    print("⚠️  Make sure to set your webhook URL in webhook_mode.py")
    print("📝 Visit /set_webhook to configure the webhook")
    
    # Run Flask app
    app.run(host='0.0.0.0', port=8443, debug=False)