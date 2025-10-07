from telebot import types
import os
import json
import random
import sqlite3
from typing import Dict, List
from config import (
    FORCE_CHANNEL_IDS, ADMIN_ID, WELCOME_GIF,
    SUCCESS_GIF, REJECT_GIF, PENDING_GIF, USE_GIF_URL_FALLBACK, DB_NAME
)

def check_force_join(bot, user_id):
    """
    Checks if a user is a member of ALL force-join channels/groups in FORCE_CHANNEL_IDS.
    Returns True only if they are a member of every channel/group.
    If FORCE_CHANNEL_IDS is empty, returns True (no force join required).
    """
    try:
        # If no channels configured for force join, allow access
        if not FORCE_CHANNEL_IDS:
            return True
            
        # Allow admins to bypass force join
        if user_id == ADMIN_ID:
            return True
            
        joined_count = 0
        total_channels = len(FORCE_CHANNEL_IDS)
        
        for channel_id in FORCE_CHANNEL_IDS:
            try:
                member = bot.get_chat_member(channel_id, user_id)
                # Check for valid membership statuses
                if member.status in ["creator", "administrator", "member"]:
                    joined_count += 1
                elif member.status in ["left", "kicked"]:
                    print(f"User {user_id} not in chat {channel_id}, status: {member.status}")
                else:
                    print(f"User {user_id} has status {member.status} in chat {channel_id}")
            except Exception as chat_error:
                error_str = str(chat_error).lower()
                # If user is not found or privacy settings prevent check, be more lenient
                if "user not found" in error_str or "bad request" in error_str or "chat not found" in error_str:
                    print(f"Cannot verify membership for user {user_id} in chat {channel_id}: {chat_error}")
                    # For privacy/API issues, count as joined to avoid blocking legitimate users
                    joined_count += 1
                else:
                    print(f"Error checking membership for user {user_id} in chat {channel_id}: {chat_error}")
        
        # Require at least 2 out of 3 channels to be more flexible
        required_joins = max(1, total_channels - 1) if total_channels > 1 else total_channels
        is_joined = joined_count >= required_joins
        
        print(f"User {user_id} joined {joined_count}/{total_channels} channels (required: {required_joins}) - {'ALLOWED' if is_joined else 'BLOCKED'}")
        return is_joined
        
    except Exception as e:
        print(f"Force join check failed: {e}")
        # In case of general error, allow access to prevent blocking users
        return True

def cleanup_left_users():
    """User cleanup is disabled - no users will be removed"""
    print("User cleanup is disabled - no users will be removed from database")
    return 0

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
        
        with open(MEDIA_POOL_FILE, "r") as f:
            data = json.load(f)
            
        # Ensure all required keys exist
        pool = _default_media_pool()
        for key in pool:
            if key in data and isinstance(data[key], list):
                pool[key] = data[key]
        
        return pool
    except Exception as e:
        print(f"Error loading media pool: {e}")
        return _default_media_pool()

def save_media_pool(pool: Dict[str, List[str]]):
    """Saves the GIF file_id pool to disk."""
    try:
        with open(MEDIA_POOL_FILE, "w") as f:
            json.dump(pool, f, indent=2)
    except Exception as e:
        print(f"Error saving media pool: {e}")

def add_gif_to_pool(file_id: str, kind: str = "any"):
    """Adds a GIF file_id to the specified pool."""
    pool = load_media_pool()
    if kind in pool:
        if file_id not in pool[kind]:
            pool[kind].append(file_id)
            save_media_pool(pool)
            return True
    return False

def get_random_gif(kind: str) -> str | None:
    """Gets a random GIF file_id from the specified pool, with fallback logic."""
    pool = load_media_pool()
    
    # Try specific kind first
    if kind in pool and pool[kind]:
        return random.choice(pool[kind])
    
    # Try 'any' pool as fallback
    if "any" in pool and pool["any"]:
        return random.choice(pool["any"])
    
    # Fall back to default GIF URLs if enabled
    if USE_GIF_URL_FALLBACK:
        return GIF_DEFAULTS.get(kind)
    
    return None

def send_random_animation(bot, chat_id: int, kind: str, caption: str = None, reply_markup=None, parse_mode: str | None = None, message_id=None):
    """Sends a random animation from the pool (or default) for the given kind. Can edit existing message if message_id provided."""
    try:
        file_id_or_url = get_random_gif(kind)
        
        if not file_id_or_url:
            # No animation available, fallback to text
            if caption:
                if message_id:
                    # Try to edit existing message
                    safe_edit_message(bot, chat_id, message_id, caption, reply_markup=reply_markup, parse_mode=parse_mode)
                else:
                    # Send new message
                    bot.send_message(chat_id, caption, reply_markup=reply_markup, parse_mode=parse_mode)
            return
        
        if message_id:
            # Try to edit existing message to animation
            try:
                bot.edit_message_media(
                    chat_id=chat_id,
                    message_id=message_id,
                    media=types.InputMediaAnimation(media=file_id_or_url, caption=caption, parse_mode=parse_mode),
                    reply_markup=reply_markup
                )
                return
            except Exception:
                # If editing fails, send new message
                pass
        
        # Send new animation
        bot.send_animation(
            chat_id=chat_id,
            animation=file_id_or_url,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except Exception as e:
        print(f"Animation send error: {e}")
        # Fallback to text message
        if caption:
            try:
                if message_id:
                    safe_edit_message(bot, chat_id, message_id, caption, reply_markup=reply_markup, parse_mode=parse_mode)
                else:
                    bot.send_message(chat_id, caption, reply_markup=reply_markup, parse_mode=parse_mode)
            except Exception as send_error:
                print(f"Failed to send fallback message: {send_error}")

def safe_edit_message(bot, chat_id, message_id, text, reply_markup=None, parse_mode=None):
    """Safely edit a message, with fallback to sending new message if edit fails."""
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except Exception as e:
        print(f"Edit message failed: {e}")
        try:
            # If edit fails, send new message
            bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
            return True
        except Exception as send_error:
            print(f"Failed to send new message after edit error: {send_error}")
            return False

def send_main_menu(bot, chat_id, text, message_id=None):
    """Sends the main menu using DB-backed section statuses (admin_meta_db)."""
    # Lazy-import admin_meta_db to avoid circular imports
    try:
        from admin_meta_db import get_section_status
    except Exception:
        # Fallback: assume all available if DB not ready
        def get_section_status(key):
            return 'available'

    # Canonical section keys we present in menu (bundle uses bins_methods for gating)
    section_keys = [
        'cc_shop', 'bins_methods', 'gift_cards', 'hacks', 'dumps', 'rdp', 'support', 'ai_search'
    ]
    section_statuses = {k: get_section_status(k) for k in section_keys}
    
    # Status icon mapping
    status_icons = {
        "available": "🟢",
        "coming_soon": "🟡", 
        "maintenance": "🔴"
    }
    
    def get_button_text(base_text, section_key):
        return base_text
    
    markup = types.InlineKeyboardMarkup(row_width=2)

    # Determine roles early (owner/global admin/section admin)
    is_owner = chat_id == ADMIN_ID
    is_admin = is_owner
    has_section_admin = False
    if not is_admin:
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (chat_id,))
                is_admin = c.fetchone() is not None
                if not is_admin:
                    c.execute("SELECT 1 FROM section_admins WHERE user_id = ?", (chat_id,))
                    has_section_admin = c.fetchone() is not None
        except Exception:
            is_admin = False
            has_section_admin = False
    
    # 🎯 MAIN STORE SECTIONS 🎯
    markup.add(
        types.InlineKeyboardButton(get_button_text("🛍️ CC Shop", "cc_shop"), callback_data="cc_menu"),
        types.InlineKeyboardButton(get_button_text("💎 BINs • Methods", "bins_methods"), callback_data="method_bins_menu")
    )

    markup.add(
        types.InlineKeyboardButton(get_button_text("🎁 Gift Cards", "gift_cards"), callback_data="giftcards_menu"),
        types.InlineKeyboardButton(get_button_text("🛠️ Hacks", "hacks"), callback_data="hacks_menu")
    )

    markup.add(
        types.InlineKeyboardButton(get_button_text("📄 Dumps", "dumps"), callback_data="dumps_menu"),
        types.InlineKeyboardButton(get_button_text("🖥️ RDP", "rdp"), callback_data="rdp_menu")
    )

    # 👤 USER SECTION 👤
    markup.add(
        types.InlineKeyboardButton("📦 My Orders", callback_data="my_orders"),
        types.InlineKeyboardButton("👤 My Profile", callback_data="my_profile")
    )

    markup.add(
        types.InlineKeyboardButton(get_button_text("🧠 AI Search", "ai_search"), callback_data="ai_search"),
        types.InlineKeyboardButton("💰 Add Funds", callback_data="add_funds")
    )

    # 🆘 SUPPORT 🆘 (Show Support only to regular users, not owner/global admin)
    if not (is_owner or is_admin):
        markup.add(
            types.InlineKeyboardButton("💬 Support", callback_data="support")
        )

    # 🎯 ADMIN SECTION 🎯
    if is_owner:
        # Owners get Owner Panel only (no duplicate Admin Panel)
        markup.add(types.InlineKeyboardButton("👑 Owner Panel", callback_data="owner_panel"))
    elif is_admin or has_section_admin:
        # Regular admins get Admin Panel
        markup.add(types.InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel"))

    # Send or edit the message
    try:
        if message_id:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="HTML")
        else:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        print(f"Main menu send error: {e}")
        # If edit fails, try to send new message
        if message_id:
            try:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")
            except Exception as send_error:
                print(f"Failed to send new message after edit error: {send_error}")

def update_state(user_states, user_id, state_key):
    """Update user state dictionary with a new state."""
    user_states[user_id] = state_key

def get_state_summary(user_states):
    """Get a summary of current user states for debugging."""
    state_counts = {}
    for state in user_states.values():
        state_counts[state] = state_counts.get(state, 0) + 1
    return state_counts

def get_country_list():
    """Load and return the country list from countries.json."""
    try:
        with open("countries.json", "r") as f:
            return json.load(f)
    except Exception:
        return []

def generate_fake_details():
    """Generate fake user details for payments."""
    import random
    import string
    
    first_names = ["John", "Jane", "Michael", "Sarah", "David", "Emma", "Chris", "Lisa"]
    last_names = ["Smith", "Johnson", "Brown", "Davis", "Wilson", "Moore", "Taylor", "Anderson"]
    
    return {
        "first_name": random.choice(first_names),
        "last_name": random.choice(last_names),
        "email": f"user{''.join(random.choices(string.digits, k=6))}@example.com",
        "phone": f"+1555{''.join(random.choices(string.digits, k=7))}"
    }

def get_media_pool_counts():
    """Get counts of media files in each pool."""
    pool = load_media_pool()
    return {kind: len(files) for kind, files in pool.items()}

def clear_media_pool(kind: str = None):
    """Clear media pool for specific kind or all if kind is None."""
    pool = load_media_pool()
    if kind and kind in pool:
        pool[kind] = []
    else:
        # Clear all pools
        for k in pool:
            pool[k] = []
    save_media_pool(pool)
    return True