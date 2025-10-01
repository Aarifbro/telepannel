import os
import json
import random
from typing import Dict, List
from config import FORCE_CHANNEL_IDS, ADMIN_ID, WELCOME_GIF, SUCCESS_GIF, REJECT_GIF, PENDING_GIF, USE_GIF_URL_FALLBACK

def check_force_join(bot, user_id):
    """
    Checks if a user is a member of ALL force-join channels/groups in FORCE_CHANNEL_IDS.
    Returns True only if they are a member of every channel/group.
    """
    try:
        for channel_id in FORCE_CHANNEL_IDS:
            member = bot.get_chat_member(channel_id, user_id)
            if member.status in ["left", "kicked"]:
                return False
        return True
    except Exception as e:
        print(f"Force join check failed: {e}")
        return False

def notify_admin(bot, message, markup=None):
    """
    Sends a notification message to the admin, with an optional keyboard.
    This is used for startup notifications, crash alerts, and new orders.
    """
    try:
        bot.send_message(ADMIN_ID, message, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Failed to notify admin: {e}")

# -------------------------------
# GIF Pool Management Utilities
# -------------------------------

MEDIA_POOL_FILE = "media_pool.json"

GIF_DEFAULTS = {
    "welcome": WELCOME_GIF,
    "success": SUCCESS_GIF,
    "reject": REJECT_GIF,
    "pending": PENDING_GIF,
    # Generic pool for untagged GIFs from groups
    "any": None,
}

def _default_media_pool() -> Dict[str, List[str]]:
    return {k: [] for k in GIF_DEFAULTS.keys()}

def load_media_pool() -> Dict[str, List[str]]:
    """Loads the GIF file_id pool from disk, returns default structure if missing/corrupt."""
    try:
        if not os.path.exists(MEDIA_POOL_FILE):
            return _default_media_pool()
        with open(MEDIA_POOL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure all expected keys exist
        for k in GIF_DEFAULTS.keys():
            data.setdefault(k, [])
        return data
    except Exception as e:
        print(f"Failed to load media pool: {e}")
        return _default_media_pool()

def save_media_pool(pool: Dict[str, List[str]]):
    """Persists the GIF file_id pool to disk."""
    try:
        with open(MEDIA_POOL_FILE, "w", encoding="utf-8") as f:
            json.dump(pool, f, indent=2)
    except Exception as e:
        print(f"Failed to save media pool: {e}")

def add_gif_to_pool(kind: str, file_id: str) -> int:
    """Adds a GIF file_id to the pool for the given kind. Returns new count for that kind."""
    kind = kind.lower()
    if kind not in GIF_DEFAULTS:
        raise ValueError(f"Unsupported GIF kind '{kind}'. Use one of: {', '.join(GIF_DEFAULTS.keys())}")
    pool = load_media_pool()
    if file_id not in pool[kind]:
        pool[kind].append(file_id)
        save_media_pool(pool)
    return len(pool[kind])

def get_random_gif(kind: str) -> str:
    """Returns a random file_id from the pool for kind, or the default configured URL if empty."""
    kind = kind.lower()
    pool = load_media_pool()
    items = pool.get(kind, [])
    if items:
        return random.choice(items)
    # Fallback to 'any' pool
    any_items = pool.get("any", [])
    if any_items:
        return random.choice(any_items)
    # fallback to configured URL (Telegram accepts either file_id or URL) if enabled
    if USE_GIF_URL_FALLBACK:
        return GIF_DEFAULTS.get(kind)
    # No fallback: force caller to handle with text
    return None

def get_media_pool_counts() -> Dict[str, int]:
    """Returns a map of kind -> count for GIF pools."""
    pool = load_media_pool()
    return {k: len(v) for k, v in pool.items()}

def clear_media_pool(kind: str | None = None) -> Dict[str, int]:
    """Clears a specific pool kind or all pools if kind is None or 'all'. Returns new counts."""
    pool = load_media_pool()
    if kind is None or kind.lower() == 'all':
        pool = _default_media_pool()
    else:
        k = kind.lower()
        if k in pool:
            pool[k] = []
    save_media_pool(pool)
    return {k: len(v) for k, v in pool.items()}

def send_random_animation(bot, chat_id: int, kind: str, caption: str = None, reply_markup=None, parse_mode: str | None = None):
    """Sends a random animation from the pool (or default) for the given kind."""
    try:
        file_id_or_url = get_random_gif(kind)
        if not file_id_or_url:
            # As a last resort, just skip animation and send text
            if caption:
                bot.send_message(chat_id, caption, reply_markup=reply_markup, parse_mode=parse_mode)
            return
        bot.send_animation(chat_id, file_id_or_url, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        print(f"Failed to send animation '{kind}': {e}")
        # Fallback to text
        if caption:
            try:
                bot.send_message(chat_id, caption, reply_markup=reply_markup, parse_mode=parse_mode)
            except Exception:
                pass

def get_country_list():
    """
    Returns a comprehensive list of countries with their corresponding flag emojis.
    This list is used in the 'Customize CC' section.
    """
    return {
        # Asia & Middle East
        "Afghanistan": "🇦🇫", "Bahrain": "🇧🇭", "Bangladesh": "🇧🇩", "Bhutan": "🇧🇹", 
        "Brunei": "🇧🇳", "Cambodia": "🇰🇭", "China": "🇨🇳", "India": "🇮🇳", 
        "Indonesia": "🇮🇩", "Iran": "🇮🇷", "Iraq": "🇮🇶", "Israel": "🇮🇱", 
        "Japan": "🇯🇵", "Jordan": "🇯🇴", "Kazakhstan": "🇰🇿", "Kuwait": "🇰🇼", 
        "Kyrgyzstan": "🇰🇬", "Laos": "🇱🇦", "Lebanon": "🇱🇧", "Malaysia": "🇲🇾", 
        "Maldives": "🇲🇻", "Mongolia": "🇲🇳", "Nepal": "🇳🇵", "Oman": "🇴🇲", 
        "Pakistan": "🇵🇰", "Philippines": "🇵🇭", "Qatar": "🇶🇦", "Saudi Arabia": "🇸🇦", 
        "Singapore": "🇸🇬", "South Korea": "🇰🇷", "Sri Lanka": "🇱🇰", "Syria": "🇸🇾", 
        "Taiwan": "🇹🇼", "Thailand": "🇹🇭", "Turkey": "🇹🇷", "Turkmenistan": "🇹🇲", 
        "United Arab Emirates": "🇦🇪", "Uzbekistan": "🇺🇿", "Vietnam": "🇻🇳", "Yemen": "🇾🇪",

        # Europe
        "Albania": "🇦🇱", "Andorra": "🇦🇩", "Austria": "🇦🇹", "Belarus": "🇧🇾", 
        "Belgium": "🇧🇪", "Bosnia & Herzegovina": "🇧🇦", "Bulgaria": "🇧🇬", 
        "Croatia": "🇭🇷", "Cyprus": "🇨🇾", "Czech Republic": "🇨🇿", "Denmark": "🇩🇰", 
        "Estonia": "🇪🇪", "Finland": "🇫🇮", "France": "🇫🇷", "Germany": "🇩🇪", 
        "Greece": "🇬🇷", "Hungary": "🇭🇺", "Iceland": "🇮🇸", "Ireland": "🇮🇪", 
        "Italy": "🇮🇹", "Latvia": "🇱🇻", "Liechtenstein": "🇱🇮", "Lithuania": "🇱🇹", 
        "Luxembourg": "🇱🇺", "Malta": "🇲🇹", "Moldova": "🇲🇩", "Monaco": "🇲🇨", 
        "Montenegro": "🇲🇪", "Netherlands": "🇳🇱", "North Macedonia": "🇲🇰", 
        "Norway": "🇳🇴", "Poland": "🇵🇱", "Portugal": "🇵🇹", "Romania": "🇷🇴", 
        "Russia": "🇷🇺", "San Marino": "🇸🇲", "Serbia": "🇷🇸", "Slovakia": "🇸🇰", 
        "Slovenia": "🇸🇮", "Spain": "🇪🇸", "Sweden": "🇸🇪", "Switzerland": "🇨🇭", 
        "Ukraine": "🇺🇦", "United Kingdom": "🇬🇧", "Vatican City": "🇻🇦",

        # North & South America
        "Antigua & Barbuda": "🇦🇬", "Argentina": "🇦🇷", "Bahamas": "🇧🇸", "Barbados": "🇧🇧", 
        "Belize": "🇧🇿", "Bolivia": "🇧🇴", "Brazil": "🇧🇷", "Canada": "🇨🇦", 
        "Chile": "🇨🇱", "Colombia": "🇨🇴", "Costa Rica": "🇨🇷", "Cuba": "🇨🇺", 
        "Dominica": "🇩🇲", "Dominican Republic": "🇩🇴", "Ecuador": "🇪🇨", 
        "El Salvador": "🇸🇻", "Grenada": "🇬🇩", "Guatemala": "🇬🇹", "Guyana": "🇬🇾", 
        "Haiti": "🇭🇹", "Honduras": "🇭🇳", "Jamaica": "🇯🇲", "Mexico": "🇲🇽", 
        "Nicaragua": "🇳🇮", "Panama": "🇵🇦", "Paraguay": "🇵🇾", "Peru": "🇵🇪", 
        "St. Kitts & Nevis": "🇰🇳", "St. Lucia": "🇱🇨", "St. Vincent & Grenadines": "🇻🇨", 
        "Suriname": "🇸🇷", "Trinidad & Tobago": "🇹🇹", "United States": "🇺🇸", 
        "Uruguay": "🇺🇾", "Venezuela": "🇻🇪",

        # Africa
        "Algeria": "🇩🇿", "Angola": "🇦🇴", "Benin": "🇧🇯", "Botswana": "🇧🇼", 
        "Burkina Faso": "🇧🇫", "Cameroon": "🇨🇲", "Chad": "🇹🇩", "Congo": "🇨🇬", 
        "Egypt": "🇪🇬", "Ethiopia": "🇪🇹", "Gabon": "🇬🇦", "Ghana": "🇬🇭", 
        "Kenya": "🇰🇪", "Libya": "🇱🇾", "Madagascar": "🇲🇬", "Mali": "🇲🇱", 
        "Morocco": "🇲🇦", "Mozambique": "🇲🇿", "Namibia": "🇳🇦", "Nigeria": "🇳🇬", 
        "Senegal": "🇸🇳", "Somalia": "🇸🇴", "South Africa": "🇿🇦", "Sudan": "🇸🇩", 
        "Tanzania": "🇹🇿", "Tunisia": "🇹🇳", "Uganda": "🇺🇬", "Zambia": "🇿🇲", 
        "Zimbabwe": "🇿🇼",

        # Oceania
        "Australia": "🇦🇺", "Fiji": "🇫🇯", "New Zealand": "🇳🇿", "Papua New Guinea": "🇵🇬",
        "Samoa": "🇼🇸", "Solomon Islands": "🇸🇧", "Tonga": "🇹🇴", "Vanuatu": "🇻🇺"
    }

def generate_fake_details(_specs: str | None = None):
    """
    Generates fake name details for an order to be displayed after a successful payment.
    This adds a layer of realism to the product delivery message.
    """
    first_names = ["John", "Michael", "David", "James", "Robert", "William"]
    last_names = ["Smith", "Jones", "Williams", "Brown", "Davis", "Miller"]
    return {"name": f"{random.choice(first_names)} {random.choice(last_names)}"}

def update_state(state_str, index, value):
    """
    Updates a state string used in the multi-step 'Customize CC' flow.
    Example: "VISA~None~None~None" -> "VISA~Credit~None~None"
    """
    parts = state_str.split('~')
    parts[index] = str(value) if value is not None else "None"
    return '~'.join(parts)

def get_state_summary(state_str):
    """
    Creates a user-friendly summary from the CC customization state string.
    This is shown to the user at each step of the customization process.
    """
    parts = state_str.split('~')
    brand, mode, country, level = parts[0], parts[1], parts[2], parts[3]
    summary = ""
    if brand != "None": summary += f"**Brand:** `{brand}`\n"
    if mode != "None": summary += f"**Mode:** `{mode}`\n"
    if country != "None": summary += f"**Country:** `{country}`\n"
    if level != "None": summary += f"**Level:** `{level}`\n"
    return summary if summary else "No selections made yet.\n"

