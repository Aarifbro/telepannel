# --- Telegram Bot Configuration ---
API_TOKENS = [
    "7595637986:AAGJj6AftCmDTg6pr2E1K-W0Kt05qM4SkEE"
]
ADMIN_ID = 1513264586 # Enter your numeric user ID

# --- Manual Payment Configuration ---
# Enter the crypto address users will send payments to.
CRYPTO_ADDRESS = "bc1qe5l2pzz3nytre346e04tjnjsa9ztz5tzz9gzfy" 

# --- Force Join Configuration ---
# To force users to join multiple channels, put all the IDs in a list.
FORCE_CHANNEL_IDS = [
    -1003176211335,
    -1002148162931
]

# --- Force Join Links (corresponds to FORCE_CHANNEL_IDS) ---
FORCE_CHANNEL_LINKS = [
    "https://t.me/+-YGFDtuSOTAwMDVh",
    "https://t.me/+TW0_zanpogpmYjJl",
    "https://t.me/+aKnhzgoNsN45Mzg1"
]

# --- File & Database Configuration ---
DB_NAME = "shop_bot.db"
PRODUCTS_FILE = "products.json"

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