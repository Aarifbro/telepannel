import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Bot configuration"""
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
    DB_PATH = os.getenv('DB_PATH', 'escrow_bot.db')
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required in .env file")
        if not cls.ADMIN_ID:
            raise ValueError("ADMIN_ID is required in .env file")
        return True
