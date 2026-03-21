# --- Telegram Bot Configuration ---
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram API Credentials (for Pyrogram/MTProto)
API_ID = int(os.environ.get("API_ID", "39622621"))
API_HASH = os.environ.get("API_HASH", "965c577f30cb3ab538335ba7f3a5a149")

API_TOKENS = [
    "8227637354:AAH6Uorxo2jGJ1Sc1N94jwfv8wvsnP6rvug"
]

ADMIN_IDS = [8409970602, 6127646960, 1513264586]

# backward compatibility for older code
ADMIN_ID = ADMIN_IDS[0] #2nd one me,3rd one your second id 

# --- Manual Payment Configuration ---
# Cryptocurrency payment addresses
CRYPTO_ADDRESSES = {
    "BTC": "bc1q3978v2ujjsu9zvesk0hg4ek7e8y2eaqnrtamqq",
    "BNB": "0x31ec2B679Da8c83Df067d7C7499862Abe311cf92",  # BEP-20
    "LTC": "ltc1qm8rty7jrjwurn9wcu3ahqlec3t9vjvuwezknuk",
    "TON": "UQDfw_HunAWrVOa2ihEoedb0qBH-022xAYamgIeMcgkFrI9Q",
    "USDT_TRC20": "TZJHZWrYzmXabgbMQRG1PSrJQH4fSdTkzE",  # TRC-20
    "USDT_ERC20": "0x31ec2B679Da8c83Df067d7C7499862Abe311cf92"  # ERC-20
}

# Legacy support - default to BTC address
CRYPTO_ADDRESS = CRYPTO_ADDRESSES["BTC"] 

# --- Force Join Configuration ---
# Set to True to use folder/invite links without membership verification
# Set to False to verify individual channel membership (requires FORCE_CHANNEL_IDS)
FORCE_JOIN_FOLDER_MODE = False  # Verify individual memberships

# Channel IDs for membership verification
# First 3 are channels, last 3 are groups
FORCE_CHANNEL_IDS = [
    -1003040244418,  # Channel 1
    -1002148162931,  # Channel 2
    -1003161447093,  # Channel 3
    -1002422874306,  # Group 1
    -1002759912121,  # Group 2
    -1003378601459   # Group 3
]

# --- Force Join Links (shown to users) ---
# Folder link that contains all 6 channels - users can join all at once
FORCE_CHANNEL_LINKS = ["https://t.me/addlist/C1dZ9Vmj53Y4Y2I1"]

# --- File & Database Configuration ---
DB_NAME = "shop_bot.db"  # Legacy SQLite (deprecated)
PRODUCTS_FILE = "products.json"  # Legacy JSON file (deprecated)

# --- Database Configuration ---
# Data is stored in local JSON files under the data/ directory
# No external database required

# --- Animated GIFs for different events ---
SUCCESS_GIF = "https://i.imgur.com/bZ3E0V0.gif"
REJECT_GIF = "https://i.imgur.com/2yHJHbB.gif"
PENDING_GIF = "https://i.imgur.com/m7b2E2A.gif"
WELCOME_GIF = "https://i.imgur.com/gQ2Yp6j.gif"

# --- GIF Source Groups ---
# If you want the bot to automatically collect GIFs from a group/channel,
# add the chat IDs here and tag GIF captions with #welcome, #success, #reject, or #pending.
# Example: MEDIA_SOURCE_GROUP_IDS = [-1001234567890]
MEDIA_SOURCE_GROUP_IDS = [-4882940898]

# --- Media behavior ---
# If False, the bot will NOT fall back to external GIF URLs and will only use stored file_ids.
# This ensures it never uses the old links once your pool has GIFs.
USE_GIF_URL_FALLBACK = False
