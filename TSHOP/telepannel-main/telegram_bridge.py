# Telegram Bot Integration
# Bridge between python-telegram-bot commands and telebot handlers

import asyncio
import logging
from functools import wraps
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)

# Import command handlers from modules
from cc_checker import cmd_auth, cmd_charge
from card_generator import cmd_gen
from bin_lookup import cmd_bin
from sms_bomber import cmd_bomb

class TelegramBotBridge:
    """Bridge to run python-telegram-bot commands alongside telebot"""
    
    def __init__(self, token):
        self.token = token
        self.application = None
        self.loop = None
        
    async def setup(self):
        """Setup the telegram bot application"""
        self.application = Application.builder().token(self.token).build()
        
        # Register command handlers
        self.application.add_handler(CommandHandler("auth", cmd_auth))
        self.application.add_handler(CommandHandler("charge", cmd_charge))
        self.application.add_handler(CommandHandler("gen", cmd_gen))
        self.application.add_handler(CommandHandler("bin", cmd_bin))
        self.application.add_handler(CommandHandler("bomb", cmd_bomb))
        
        # Initialize application
        await self.application.initialize()
        await self.application.start()
        
        logger.info("✅ Python-telegram-bot bridge initialized")
        
    async def start_polling(self):
        """Start polling for updates"""
        if self.application:
            await self.application.updater.start_polling()
            logger.info("▶️ Python-telegram-bot polling started")
    
    async def stop(self):
        """Stop the application"""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("⏹️ Python-telegram-bot stopped")

# Global bridge instance
_bridge_instance = None

def get_bridge_instance(token):
    """Get or create bridge instance"""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = TelegramBotBridge(token)
    return _bridge_instance

def start_bridge_async(token):
    """Start the bridge in async mode"""
    import threading
    
    def run_bridge():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        bridge = get_bridge_instance(token)
        
        try:
            loop.run_until_complete(bridge.setup())
            loop.run_until_complete(bridge.start_polling())
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            loop.run_until_complete(bridge.stop())
            loop.close()
    
    bridge_thread = threading.Thread(target=run_bridge, daemon=True)
    bridge_thread.start()
    logger.info("🚀 Bridge thread started")
    
    return bridge_thread
