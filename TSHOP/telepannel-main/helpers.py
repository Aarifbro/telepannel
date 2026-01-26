from telebot import types
import telebot
import telebot.apihelper
import os
import json
import random
import sqlite3
from typing import Dict, List
from config import (
    FORCE_CHANNEL_IDS, ADMIN_ID, WELCOME_GIF,
    SUCCESS_GIF, REJECT_GIF, PENDING_GIF, USE_GIF_URL_FALLBACK, DB_NAME
)
FORCE_LINKS_CACHE_FILE = "force_links_cache.json"

ADMIN_IDS = [8409970602, 6127646960, 1513264586]

# backward compatibility for older code
ADMIN_ID = ADMIN_IDS[0]

def cache_force_links(links: List[str]):
    try:
        with open(FORCE_LINKS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"links": links}, f)
    except Exception as e:
        print(f"Failed to cache force links: {e}")


def load_cached_force_links() -> List[str]:
    try:
        if not os.path.exists(FORCE_LINKS_CACHE_FILE):
            return []
        with open(FORCE_LINKS_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("links", [])
    except Exception as e:
        print(f"Failed to load cached force links: {e}")
        return []


def get_cached_force_links(bot) -> List[str]:
    """Attempt to create or refresh invite links for FORCE_CHANNEL_IDS.
    If export_chat_invite_link is not permitted or fails, fall back to cached links from disk.
    Returns a list of links aligned with FORCE_CHANNEL_IDS.
    """
    links = []
    for cid in FORCE_CHANNEL_IDS:
        try:
            # Try to get a chat-specific invite link (bot must be admin in chat)
            info = bot.get_chat(cid)
            try:
                link = bot.export_chat_invite_link(cid)
            except Exception as e:
                # If we cannot export (no permission), try to use username link (if exists)
                username = getattr(info, 'username', None)
                if username:
                    link = f"https://t.me/{username}"
                else:
                    raise
            links.append(link)
        except Exception as e:
            print(f"Could not refresh invite link for {cid}: {e}")
            links.append(None)

    # If any link is None, attempt to fill from cache
    if any(l is None for l in links):
        cached = load_cached_force_links()
        # only replace None entries if cached available
        for i, l in enumerate(links):
            if l is None and i < len(cached) and cached[i]:
                links[i] = cached[i]

    # Save what we have
    try:
        cache_force_links([l or "" for l in links])
    except Exception:
        pass
    return links

def check_force_join(bot, user_id):
    """
    Checks if a user is a member of ALL force-join channels/groups in FORCE_CHANNEL_IDS.
    Returns True only if they are a member of every channel/group.
    If FORCE_CHANNEL_IDS is empty, returns True (no force join required).
    """
    try:
        # If no channels configured for force join, allow access
        if not FORCE_CHANNEL_IDS:
            print(f"⚠️ No FORCE_CHANNEL_IDS configured - allowing access for user {user_id}")
            return True
            
        # Allow admins to bypass force join
        if user_id == ADMIN_ID:
            print(f"👑 Admin {user_id} bypassing force join check")
            return True
            
        joined_count = 0
        total_channels = len(FORCE_CHANNEL_IDS)
        failed_channels = []
        
        for channel_id in FORCE_CHANNEL_IDS:
            try:
                member = bot.get_chat_member(channel_id, user_id)
                # Check for valid membership statuses
                if member.status in ["creator", "administrator", "member"]:
                    joined_count += 1
                    print(f"✅ User {user_id} is {member.status} in chat {channel_id}")
                elif member.status in ["left", "kicked"]:
                    failed_channels.append(channel_id)
                    print(f"❌ User {user_id} not in chat {channel_id}, status: {member.status}")
                else:
                    print(f"⚠️ User {user_id} has status {member.status} in chat {channel_id}")
            except Exception as chat_error:
                error_str = str(chat_error).lower()
                # Handle specific error cases
                if "user not found" in error_str:
                    print(f"⚠️ User {user_id} not found in chat {channel_id} - user may have privacy settings")
                    failed_channels.append(channel_id)
                elif "chat not found" in error_str:
                    print(f"❌ Chat {channel_id} not found - bot may not be in channel or channel doesn't exist")
                    # Don't count this channel in the requirement
                    total_channels -= 1
                elif "bot was kicked" in error_str or "bot is not a member" in error_str:
                    print(f"❌ Bot is not member of chat {channel_id}")
                    # Don't count this channel in the requirement
                    total_channels -= 1
                else:
                    print(f"⚠️ Error checking membership for user {user_id} in chat {channel_id}: {chat_error}")
                    failed_channels.append(channel_id)
        
        # Require user to join at least 2 out of 3 channels (or all if less than 3)
        if total_channels <= 0:
            print(f"⚠️ No valid channels to check - allowing access")
            return True
            
        required_joins = max(1, total_channels - 1) if total_channels > 1 else total_channels
        is_joined = joined_count >= required_joins
        
        print(f"📊 User {user_id} joined {joined_count}/{total_channels} channels (required: {required_joins}) - {'✅ ALLOWED' if is_joined else '❌ BLOCKED'}")
        
        if not is_joined and failed_channels:
            print(f"   Failed channels: {failed_channels}")
        
        return is_joined
        
    except Exception as e:
        print(f"❌ Force join check failed with error: {e}")
        import traceback
        traceback.print_exc()
        # In case of general error, allow access to prevent blocking users
        return True


def check_force_join_verbose(bot, user_id):
    """
    More verbose check that returns (is_joined, unavailable_channels).
    unavailable_channels = list of channel ids where the bot could not verify the chat (chat not found or bot removed).
    This does NOT change legacy behavior; callers can use the unavailable list to surface link problems.
    """
    unavailable = []
    try:
        if not FORCE_CHANNEL_IDS:
            return True, unavailable
        if user_id == ADMIN_ID:
            return True, unavailable

        joined_count = 0
        total_channels = len(FORCE_CHANNEL_IDS)
        failed_channels = []
        
        for channel_id in FORCE_CHANNEL_IDS:
            try:
                member = bot.get_chat_member(channel_id, user_id)
                if member.status in ["creator", "administrator", "member"]:
                    joined_count += 1
                    print(f"✅ User {user_id} is {member.status} in chat {channel_id}")
                else:
                    # user not a member
                    failed_channels.append(channel_id)
                    print(f"❌ User {user_id} has status {member.status} in chat {channel_id}")
            except Exception as chat_error:
                error_str = str(chat_error).lower()
                # If we cannot access the chat metadata (chat not found / bot not in chat), mark as unavailable
                if "chat not found" in error_str or "bot was kicked" in error_str or "bot is not a member" in error_str:
                    unavailable.append(channel_id)
                    total_channels -= 1  # Don't count unavailable channels
                    print(f"⚠️ Channel {channel_id} is unavailable: {chat_error}")
                else:
                    # For other errors (privacy/user not found), treat as not joined
                    failed_channels.append(channel_id)
                    print(f"❌ Force join check error for user {user_id} in {channel_id}: {chat_error}")

        if total_channels <= 0:
            return True, unavailable
            
        required_joins = max(1, total_channels - 1) if total_channels > 1 else total_channels
        is_joined = joined_count >= required_joins
        
        print(f"📊 User {user_id} joined {joined_count}/{total_channels} channels (required: {required_joins}) - {'✅ ALLOWED' if is_joined else '❌ BLOCKED'}")
        if not is_joined:
            print(f"   Failed channels: {failed_channels}")
        if unavailable:
            print(f"   Unavailable channels: {unavailable}")
            
        return is_joined, unavailable
    except Exception as e:
        print(f"❌ Verbose force join check failed: {e}")
        import traceback
        traceback.print_exc()
        return True, unavailable

def cleanup_left_users():
    """User cleanup is disabled - no users will be removed"""
    print("User cleanup is disabled - no users will be removed from database")
    return 0

def notify_admin(bot, message, markup=None, parse_mode="HTML"):
    """
    Sends a notification message to the admin, with an optional keyboard.
    This is used for startup notifications, crash alerts, and new orders.
    """
    try:
        print(f"📤 Attempting to notify admin (ID: {ADMIN_ID}): {message[:50]}...")
        result = bot.send_message(ADMIN_ID, message, parse_mode=parse_mode, reply_markup=markup)
        print(f"✅ Admin notification sent successfully (Message ID: {result.message_id})")
        return True
    except telebot.apihelper.ApiTelegramException as e:
        if e.error_code == 403:
            print(f"❌ Admin notification failed: Bot was blocked by admin (ID: {ADMIN_ID}). Error: {e}")
            print("💡 Solution: Admin needs to unblock the bot or start a conversation with it.")
        elif e.error_code == 400:
            print(f"❌ Admin notification failed: Invalid admin ID ({ADMIN_ID}) or bad request. Error: {e}")
            print("💡 Solution: Check if ADMIN_ID in config.py is correct.")
        else:
            print(f"❌ Admin notification failed with Telegram API error {e.error_code}: {e}")
        return False
    except Exception as e:
        print(f"❌ Admin notification failed with unexpected error: {e}")
        return False

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
            print(f"📁 Creating new media pool file...")
            default_pool = _default_media_pool()
            save_media_pool(default_pool)
            return default_pool
        
        with open(MEDIA_POOL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Ensure all required keys exist and are lists
        pool = _default_media_pool()
        for key in pool:
            if key in data:
                if isinstance(data[key], list):
                    # Ensure all items are strings and remove duplicates
                    pool[key] = list(set([str(v) for v in data[key] if v]))
                else:
                    pool[key] = []
        
        print(f"📂 Media pool loaded: {sum(len(v) for v in pool.values())} total GIFs")
        return pool
    except Exception as e:
        print(f"Error loading media pool: {e}")
        import traceback
        traceback.print_exc()
        return _default_media_pool()

def save_media_pool(pool: Dict[str, List[str]]):
    """Saves the GIF file_id pool to disk."""
    try:
        # Ensure pool has valid structure before saving
        validated_pool = {}
        for key, value in pool.items():
            if isinstance(value, list):
                # Remove duplicates and ensure all are strings
                validated_pool[key] = list(set([str(v) for v in value if v]))
            else:
                validated_pool[key] = []
        
        with open(MEDIA_POOL_FILE, "w", encoding="utf-8") as f:
            json.dump(validated_pool, f, indent=2, ensure_ascii=False)
        print(f"💾 Media pool saved: {sum(len(v) for v in validated_pool.values())} total GIFs")
    except Exception as e:
        print(f"Error saving media pool: {e}")
        import traceback
        traceback.print_exc()

def add_gif_to_pool(file_id: str, kind: str = "any"):
    """Adds a GIF file_id to the specified pool. Returns the count of GIFs in that pool."""
    pool = load_media_pool()
    if kind in pool:
        if file_id not in pool[kind]:
            pool[kind].append(file_id)
            save_media_pool(pool)
            print(f"✅ Added GIF to '{kind}' pool. File ID: {file_id[:20]}...")
        return len(pool[kind])
    return 0

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

def get_welcome_message(user_name="User"):
    """Generate a dynamic welcome message."""
    import datetime
    current_hour = datetime.datetime.now().hour
    
    if 5 <= current_hour < 12:
        greeting = "🌅 Good morning"
    elif 12 <= current_hour < 17:
        greeting = "☀️ Good afternoon"
    elif 17 <= current_hour < 21:
        greeting = "🌆 Good evening"
    else:
        greeting = "🌙 Good night"
    
    welcome_msg = f"""🎯 <b>Welcome to TelePanel Shop!</b>

{greeting}, <b>{user_name}</b>! 👋

🛍️ <b>Your one-stop shop for:</b>
• Premium Credit Cards & BINs
• Gift Cards & Digital Products
• Exclusive Hacking Tools & Methods
• RDP & Dumps Services

💎 <b>Why choose us?</b>
✅ 24/7 Customer Support
✅ Instant Delivery
✅ Secure Payments
✅ Money-back Guarantee

<i>Select a category below to get started:</i>"""
    
    return welcome_msg

def send_main_menu(bot, chat_id, text, message_id=None):
    """Sends the main menu using DB-backed section statuses (admin_meta_db)."""
    # Lazy-import admin_meta_db to avoid circular imports
    try:
        from admin_meta_db import get_section_status
    except Exception:
        # Fallback: assume all available if DB not ready
        def get_section_status(key):
            return 'available'

    # Menu layout simplified - no status indicators needed
    
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
    
    # 🛒 STORE SECTIONS
    markup.add(
        types.InlineKeyboardButton("🛍️ CC Shop", callback_data="cc_menu"),
        types.InlineKeyboardButton("💎 BINs & Methods", callback_data="method_bins_menu")
    )
    
    markup.add(
        types.InlineKeyboardButton("🎁 Gift Cards", callback_data="giftcards_menu"),
        types.InlineKeyboardButton("🛠️ Hacks", callback_data="hacks_menu")
    )
    
    # 🎮 GAMES
    markup.add(
        types.InlineKeyboardButton("🎮 Games", callback_data="games_menu")
    )
    
    markup.add(
        types.InlineKeyboardButton("📄 Dumps", callback_data="dumps_menu"),
        types.InlineKeyboardButton("🖥️ RDP", callback_data="rdp_menu")
    )
    markup.add(
        types.InlineKeyboardButton("📦 Accounts", callback_data="open_accounts")
    )
    markup.add(
        types.InlineKeyboardButton("🔨 Dumping Toolkit", callback_data="dumping_toolkit_menu"),
        types.InlineKeyboardButton("🎓 Courses", callback_data="courses_menu")
    )

    # 🔧 ADVANCED TOOLS
    markup.add(
        types.InlineKeyboardButton("🔧 Advanced Tools", callback_data="advanced_tools_menu"),
        types.InlineKeyboardButton("💳 CC Checker", callback_data="cc_checker_main_menu")
    )
    
    markup.add(
        types.InlineKeyboardButton("🎯 Hitter", callback_data="hitter_menu"),
        types.InlineKeyboardButton("🎮 BGMI Attack", callback_data="bgmi_attack_menu")
    )
    
    markup.add(
        types.InlineKeyboardButton("�🛠️ Tools", callback_data="tools_menu")
    )

    # 📊 ANALYTICS & UTILITIES
    markup.add(
        types.InlineKeyboardButton("🧠 AI Search", callback_data="ai_search"),
        types.InlineKeyboardButton("📈 Statistics", callback_data="user_stats")
    )

    # 👤 ACCOUNT MANAGEMENT
    markup.add(
        types.InlineKeyboardButton("👤 My Profile", callback_data="personal_area"),
        types.InlineKeyboardButton("💰 Add Funds", callback_data="add_funds")
    )
    
    markup.add(
        types.InlineKeyboardButton("📦 My Orders", callback_data="my_orders"),
        types.InlineKeyboardButton("💳 Balance History", callback_data="balance_history")
    )
    
    # 🎁 SPECIAL FEATURES
    markup.add(
        types.InlineKeyboardButton("🎁 My Claims", callback_data="my_temp_claims"),
        types.InlineKeyboardButton("⌨️ Enter Key Code", callback_data="enter_key_code")
    )

    # 🆘 SUPPORT 🆘 (Show Support only to regular users, not owner/global admin)
    if not (is_owner or is_admin):
        markup.add(
            types.InlineKeyboardButton("💬 Support", callback_data="support")
        )
    
    # 🐀 RAT BUTTON 🐀
    markup.add(types.InlineKeyboardButton("🐀 Rat", callback_data="rat_menu"))

    # 🎯 ADMIN SECTION 🎯
    if is_owner:
        # Owners get Owner Panel only (no duplicate Admin Panel)
        markup.add(types.InlineKeyboardButton("👑 Owner Panel", callback_data="owner_panel"))
    elif is_admin or has_section_admin:
        # Regular admins get Admin Panel
        markup.add(types.InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel"))
        markup.add(types.InlineKeyboardButton("🛠️ Admin-acc Panel",callback_data="open_admin"))
    # Send or edit the message
    try:
        if message_id:
            msg = bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="HTML")
        else:
            msg = bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")
            
    except Exception as e:
        print(f"Main menu send error: {e}")
        # If edit fails, try to send new message
        if message_id:
            try:
                msg = bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")
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

def lookup_bin_info(bin_number):
    """
    Lookup BIN information using binlist.net API or fallback to local data.
    Returns dict with: brand, type, level, bank, country, country_flag
    """
    import requests
    
    try:
        # Try binlist.net API first (free, no auth needed)
        response = requests.get(f"https://lookup.binlist.net/{bin_number[:6]}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            
            # Extract relevant information
            brand = data.get("scheme", "UNKNOWN").upper()
            card_type = data.get("type", "UNKNOWN").upper()
            level = data.get("brand", "UNKNOWN").upper()
            bank = data.get("bank", {}).get("name", "UNKNOWN")
            country_info = data.get("country", {})
            country = country_info.get("name", "UNKNOWN")
            country_code = country_info.get("alpha2", "")
            
            # Get country flag emoji
            flag = ""
            if country_code:
                # Convert country code to flag emoji
                flag = "".join(chr(127397 + ord(c)) for c in country_code.upper())
            
            return {
                "brand": brand,
                "type": card_type,
                "level": level,
                "bank": bank,
                "country": country,
                "country_flag": flag,
                "country_code": country_code
            }
    except Exception as e:
        print(f"BIN lookup failed: {e}")
    
    # Fallback to default values if API fails
    return {
        "brand": "VISA",
        "type": "CREDIT",
        "level": "CLASSIC",
        "bank": "Unknown Bank",
        "country": "United States",
        "country_flag": "🇺🇸",
        "country_code": "US"
    }

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

def generate_cc_from_bin(bin_number):
    """Generate a credit card number from BIN with full details including BIN lookup info."""
    import random
    
    # Get BIN information
    bin_info = lookup_bin_info(bin_number)
    
    # Pad BIN to 6 digits if shorter
    bin_prefix = str(bin_number).zfill(6)[:6]
    
    # Generate remaining digits (Luhn algorithm)
    def luhn_checksum(card_number):
        def digits_of(n):
            return [int(d) for d in str(n)]
        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d * 2))
        return checksum % 10
    
    # Generate 9 random digits + check digit (total 16 digits)
    base = bin_prefix + ''.join([str(random.randint(0, 9)) for _ in range(9)])
    check_digit = (10 - luhn_checksum(int(base + '0'))) % 10
    cc_number = base + str(check_digit)
    
    # Generate random CVV and expiry
    cvv = ''.join([str(random.randint(0, 9)) for _ in range(3)])
    exp_month = random.randint(1, 12)
    exp_year = random.randint(2025, 2030)
    
    return {
        "cc_number": cc_number,
        "cvv": cvv,
        "exp_month": f"{exp_month:02d}",
        "exp_year": str(exp_year),
        "bin_info": bin_info
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

# helpers.py

def safe_edit_message(bot, call, text, reply_markup=None):
    """
    Safely edits a message.
    If Telegram rejects the edit (same content), sends a new message instead.
    """
    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    except Exception:
        bot.send_message(
            call.message.chat.id,
            text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )


