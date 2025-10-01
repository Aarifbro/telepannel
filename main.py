import json
import threading
import time
import requests
import sqlite3
import telebot
from telebot import types

from config import API_TOKENS, ADMIN_ID, DB_NAME, WELCOME_GIF, MEDIA_SOURCE_GROUP_IDS
from database import init_db, add_user, load_products
from helpers import check_force_join, notify_admin, send_random_animation, add_gif_to_pool
from cc_handler import register_cc_handlers
from bin_handler import register_bin_handlers
from payment_handler import register_payment_handlers, show_payment_options
from other_handlers import register_other_handlers


# --- Section Status Storage ---
SECTION_STATUS_FILE = "section_status.json"
SECTION_STATUS_OPTIONS = [
    ("coming_soon", "🟡 Coming Soon"),
    ("error", "🔴 Error"),
    ("maintenance", "🛠️ Under Maintenance"),
    ("available", "🟢 Available")
]
SECTION_KEYS = [
    ("gift_cards", "Gift Cards"),
    ("dumps", "Dumps"),
    ("hacks", "Hacks"),
    ("cc", "Credit Cards"),
    ("bins", "BINs"),
    ("rdp", "RDP"),
    ("methods", "Methods"),
    ("other", "Other")
]


def set_section_status(section_key, status_key):
    try:
        with open(SECTION_STATUS_FILE, "r") as f:
            data = json.load(f)
    except Exception:
        data = {}
    data[section_key] = status_key
    with open(SECTION_STATUS_FILE, "w") as f:
        json.dump(data, f)


def get_section_status(section_key):
    try:
        with open(SECTION_STATUS_FILE, "r") as f:
            data = json.load(f)
            return data.get(section_key, "coming_soon")
    except Exception:
        return "coming_soon"


# Global user states (simple approach shared across bots)
user_states = {}
# In-memory cache for products
products_cache = {}

def load_all_products_into_cache():
    """Loads all product data from JSON files into an in-memory cache."""
    global products_cache
    try:
        with open("products.json", 'r', encoding='utf-8') as f:
            products_cache = json.load(f)
        print("✅ Products loaded into in-memory cache.")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"🔴 Could not load products.json: {e}. Using empty cache.")
        products_cache = {"bins": [], "ready_ccs": [], "gift_cards": [], "rdp": [], "methods": [], "other": []}

def get_products_from_cache(category=None):
    """Returns all products or products from a specific category from the cache."""
    if category:
        return products_cache.get(category, [])
    return products_cache

def save_products_to_file_and_reload(new_data):
    """Saves new data to the file and reloads the cache."""
    global products_cache
    try:
        with open("products.json", 'w', encoding='utf-8') as f:
            json.dump(new_data, f, indent=4)
        products_cache = new_data
        print("✅ products.json updated and cache reloaded.")
    except Exception as e:
        print(f"🔴 Failed to save products and reload cache: {e}")


def register_all_handlers(bot_instance):
    # Register handlers from other modules
    register_cc_handlers(bot_instance, user_states)
    register_bin_handlers(bot_instance)
    register_payment_handlers(bot_instance)
    register_other_handlers(bot_instance, user_states, get_products_from_cache, save_products_to_file_and_reload)

    # ---------- Local handlers and menus ----------
    def send_main_menu(chat_id, text, message_id=None):
        bot_instance.send_chat_action(chat_id, 'typing')
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("💳 Cards", callback_data="cc_menu"),
            types.InlineKeyboardButton("📦 BINs", callback_data="bin_menu"),
            types.InlineKeyboardButton("🎁 Gift Cards", callback_data="giftcards_menu"),
            types.InlineKeyboardButton("💾 Dumps", callback_data="dumps_menu"),
            types.InlineKeyboardButton("🕵️ Hacks", callback_data="hacks_menu"),
            types.InlineKeyboardButton("🖥️ RDP", callback_data="rdp_menu"),
            types.InlineKeyboardButton("✨ Other", callback_data="other_menu"),
            types.InlineKeyboardButton("🧠 AI Search", callback_data="ai_search"),
            types.InlineKeyboardButton("👤 Personal Area", callback_data="personal_area"),
            types.InlineKeyboardButton("🆘 Support", callback_data="support"),
            types.InlineKeyboardButton("📜 Rules", callback_data="rules")
        )
        
        is_owner = chat_id == ADMIN_ID
        is_global_admin = False
        is_section_admin = False
        try:
            if not is_owner:
                with sqlite3.connect(DB_NAME) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (chat_id,))
                    is_global_admin = cursor.fetchone() is not None
                    cursor.execute("SELECT 1 FROM section_admins WHERE user_id = ?", (chat_id,))
                    is_section_admin = cursor.fetchone() is not None
        except Exception:
            pass

        if is_owner:
            markup.add(types.InlineKeyboardButton("🛠️ Status Manage", callback_data="status_manage"))
            markup.add(
                types.InlineKeyboardButton("👑 Owner Panel", callback_data="owner_panel"),
                types.InlineKeyboardButton("🔐 Admin Panel", callback_data="admin_panel")
            )
        elif is_global_admin or is_section_admin:
            markup.add(types.InlineKeyboardButton("🔐 Admin Panel", callback_data="admin_panel"))

        try:
            if message_id:
                bot_instance.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
            else:
                bot_instance.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            pass

    @bot_instance.message_handler(commands=["start"])
    def start_command(message):
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        parts = message.text.split()
        referrer_code = parts[1] if len(parts) > 1 else None
        add_user(user_id, username, referrer_code)
        intro_text = (
            "🎉 <b>Welcome to the Premium Shop</b> 💜👑\n"
            "✨ <b>Everything you need in one place.</b>\n\n"
            "👇 <b>Use the buttons below to navigate.</b>"
        )
        if not check_force_join(bot_instance, user_id):
            from config import FORCE_CHANNEL_LINKS
            markup = types.InlineKeyboardMarkup()
            for link in FORCE_CHANNEL_LINKS:
                markup.add(types.InlineKeyboardButton("🔗 Join Channel/Group", url=link))
            markup.add(types.InlineKeyboardButton("✅ I Have Joined", callback_data="check_join"))
            force_join_text = f"{intro_text}\n\n⚠️ To get full access, you must first join all our partner channels/groups."
            try:
                send_random_animation(bot_instance, user_id, kind="welcome", caption=force_join_text, reply_markup=markup, parse_mode="HTML")
            except Exception:
                bot_instance.send_message(user_id, force_join_text, reply_markup=markup, parse_mode="HTML")
        else:
            try:
                send_random_animation(bot_instance, user_id, kind="welcome", caption=intro_text, parse_mode="HTML")
            except Exception:
                bot_instance.send_message(user_id, intro_text, parse_mode="HTML")
            send_main_menu(user_id, "👇 **Please choose an option from the menu to begin.**")

    @bot_instance.callback_query_handler(func=lambda call: call.data == "check_join")
    def joined_callback(call):
        if check_force_join(bot_instance, call.from_user.id):
            bot_instance.delete_message(call.message.chat.id, call.message.message_id)
            send_main_menu(call.message.chat.id, "✅ **Thank you for joining!** You can now use the bot.")
        else:
            bot_instance.answer_callback_query(call.id, "❌ You haven't joined the channel yet.", show_alert=True)

    @bot_instance.callback_query_handler(func=lambda call: call.data == "manage_orders_panel")
    def manage_orders_panel(call):
        user_id = call.from_user.id
        is_global_admin = False
        section_admin_sections = []
        is_owner = user_id == ADMIN_ID
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            is_global_admin = cursor.fetchone() is not None
            cursor.execute("SELECT section FROM section_admins WHERE user_id = ?", (user_id,))
            section_admin_sections = [row[0] for row in cursor.fetchall()]
        if not (is_owner or is_global_admin or section_admin_sections):
            bot_instance.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        all_sections = [
            ("cc", "Credit Cards"),
            ("bins", "BINs"),
            ("gift_cards", "Gift Cards"),
            ("dumps", "Dumps"),
            ("hacks", "Hacks"),
            ("rdp", "RDP"),
            ("methods", "Methods"),
            ("other", "Other")
        ]
        if is_owner or is_global_admin:
            markup.add(types.InlineKeyboardButton("View All Orders", callback_data="admin_orders"))
            for section_key, section_label in all_sections:
                markup.add(types.InlineKeyboardButton(f"Manage {section_label} Orders", callback_data=f"admin_orders_{section_key}"))
        else:
            for section in section_admin_sections:
                label = next((lbl for key, lbl in all_sections if key == section), None)
                if label:
                    markup.add(types.InlineKeyboardButton(f"Manage {label} Orders", callback_data=f"admin_orders_{section}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        bot_instance.edit_message_text("<b>📦 Manage Orders Panel</b>\n\nSelect which orders to manage:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # Buy Hacks main menu
    @bot_instance.callback_query_handler(func=lambda call: call.data == "hacks_menu")
    def hacks_menu(call):
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🎣 Premium Phishing Kits", callback_data="phishing_kits_menu"))
        markup.add(types.InlineKeyboardButton("📚 Methods", callback_data="method_menu"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        bot_instance.edit_message_text("<b>🛡️ Buy Hacks</b>\n\nSelect a category:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # Premium Phishing Kits submenu
    @bot_instance.callback_query_handler(func=lambda call: call.data == "phishing_kits_menu")
    def phishing_kits_menu(call):
        products = get_products_from_cache("phishing_kits")
        markup = types.InlineKeyboardMarkup(row_width=1)
        if not products:
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="hacks_menu"))
            bot_instance.edit_message_text("<b>🎣 Premium Phishing Kits</b>\n\nNo kits available at the moment.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
            return
        for idx, item in enumerate(products):
            name = item.get("name", "Unnamed Kit")
            price = item.get("price", "?")
            markup.add(types.InlineKeyboardButton(f"🛒 {name} - ${price}", callback_data=f"phishing_kit_detail_{idx}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="hacks_menu"))
        bot_instance.edit_message_text("<b>🎣 Premium Phishing Kits</b>\n\nSelect a kit to view details:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # Show phishing kit details and buy button
    @bot_instance.callback_query_handler(func=lambda call: call.data.startswith("phishing_kit_detail_"))
    def phishing_kit_detail(call):
        idx = int(call.data.split("_")[-1])
        products = get_products_from_cache("phishing_kits")
        if idx >= len(products):
            bot_instance.answer_callback_query(call.id, "Invalid selection.", show_alert=True)
            return
        item = products[idx]
        name = item.get("name", "Unnamed Kit")
        price = item.get("price", "?")
        desc = item.get("description", "No description.")
        text = f"<b>{name}</b>\n\n<b>Price:</b> ${price}\n<b>Description:</b> {desc}\n\nTo purchase, click the button below."
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💸 Buy Now", callback_data=f"buy_phishing_kit_{idx}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Kits", callback_data="phishing_kits_menu"))
        markup.add(types.InlineKeyboardButton("⬅️ Main Menu", callback_data="main_menu"))
        bot_instance.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # --- Payment Option: Add Screenshot Upload and Confirmation ---
    @bot_instance.callback_query_handler(func=lambda call: call.data.startswith("buy_phishing_kit_"))
    def buy_phishing_kit(call):
        idx = int(call.data.split("_")[-1])
        products = get_products_from_cache("phishing_kits")
        if idx >= len(products):
            bot_instance.answer_callback_query(call.id, "Invalid selection.", show_alert=True)
            return
        item = products[idx]
        price = item.get("price", 0)
        name = item.get("name", "Unnamed Kit")
        show_payment_options(bot_instance, call, name, price, item, "phishing_kits_menu")

    # Section status helpers and panels
    def get_section_status_label(section_key):
        status_key = get_section_status(section_key)
        return next((label for key, label in SECTION_STATUS_OPTIONS if key == status_key), "🟡 Coming Soon")

    @bot_instance.callback_query_handler(func=lambda call: call.data == "giftcards_menu")
    def giftcards_status_panel(call):
        status_key = get_section_status("gift_cards")
        if status_key == "available":
            from other_handlers import create_dynamic_product_menu
            create_dynamic_product_menu(call, "gift_cards")
        else:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
            status_label = get_section_status_label("gift_cards")
            bot_instance.edit_message_text(f"🎁 Gift Cards\n\n<b>Status:</b> {status_label}", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot_instance.callback_query_handler(func=lambda call: call.data == "status_manage")
    def status_manage_panel(call):
        if call.from_user.id != ADMIN_ID:
            bot_instance.answer_callback_query(call.id, "❌ Only the owner can access this.", show_alert=True)
            return
        markup = types.InlineKeyboardMarkup()
        for section_key, section_label in SECTION_KEYS:
            status_label = get_section_status_label(section_key)
            markup.add(types.InlineKeyboardButton(f"{section_label}: {status_label}", callback_data=f"set_status_{section_key}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        bot_instance.edit_message_text("<b>Status Manage</b>\n\nSelect a section to update its status:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot_instance.callback_query_handler(func=lambda call: call.data.startswith("set_status_"))
    def set_section_status_panel(call):
        if call.from_user.id != ADMIN_ID:
            bot_instance.answer_callback_query(call.id, "❌ Only the owner can access this.", show_alert=True)
            return
        section_key = call.data.replace("set_status_", "")
        markup = types.InlineKeyboardMarkup()
        for status_key, status_label in SECTION_STATUS_OPTIONS:
            markup.add(types.InlineKeyboardButton(status_label, callback_data=f"set_section_status_{section_key}_{status_key}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="status_manage"))
        current_status = get_section_status(section_key)
        current_label = next((label for k, label in SECTION_STATUS_OPTIONS if k == current_status), "🟡 Coming Soon")
        section_label = next((lbl for k, lbl in SECTION_KEYS if k == section_key), section_key)
        bot_instance.edit_message_text(f"<b>Status Manage</b>\n\nSection: {section_label}\nCurrent status: {current_label}\n\nChoose a new status:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot_instance.callback_query_handler(func=lambda call: call.data.startswith("set_section_status_"))
    def set_section_status_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot_instance.answer_callback_query(call.id, "❌ Only the owner can access this.", show_alert=True)
            return
        parts = call.data.replace("set_section_status_", "").split("_")
        section_key = parts[0]
        status_key = "_".join(parts[1:])
        set_section_status(section_key, status_key)
        bot_instance.answer_callback_query(call.id, "Section status updated!", show_alert=True)
        status_manage_panel(call)

    # Dumps
    @bot_instance.callback_query_handler(func=lambda call: call.data == "dumps_menu")
    def dumps_menu(call):
        products = get_products_from_cache("dumps")
        markup = types.InlineKeyboardMarkup(row_width=1)
        if not products:
            markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
            bot_instance.edit_message_text("<b>💾 Dumps</b>\n\n<i>No dumps available at the moment.</i>", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
            return
        for idx, item in enumerate(products):
            name = item.get("name", "Unnamed Dump")
            price = item.get("price", "?")
            markup.add(types.InlineKeyboardButton(f"🛒 {name} - ${price}", callback_data=f"dumps_detail_{idx}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        text = "<b>💾 Dumps</b>\n\nSelect a dump from the list below.\n\nAll dumps are checked and quality guaranteed."
        bot_instance.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot_instance.callback_query_handler(func=lambda call: call.data.startswith("dumps_detail_"))
    def dumps_detail(call):
        idx = int(call.data.split("_")[-1])
        products = get_products_from_cache("dumps")
        if idx >= len(products):
            bot_instance.answer_callback_query(call.id, "Invalid selection.", show_alert=True)
            return
        item = products[idx]
        name = item.get("name", "Unnamed Dump")
        price = item.get("price", "?")
        desc = item.get("description", "No description.")
        text = f"<b>{name}</b>\n\n<b>Price:</b> ${price}\n<b>Description:</b> {desc}\n\nTo purchase, click the button below."
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💸 Buy Now", callback_data=f"buy_dump_{idx}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Dumps List", callback_data="dumps_menu"))
        markup.add(types.InlineKeyboardButton("⬅️ Main Menu", callback_data="main_menu"))
        bot_instance.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot_instance.callback_query_handler(func=lambda call: call.data.startswith("buy_dump_"))
    def buy_dump_callback(call):
        idx = int(call.data.split("_")[-1])
        products = get_products_from_cache("dumps")
        if idx >= len(products):
            bot_instance.answer_callback_query(call.id, "Invalid selection.", show_alert=True)
            return
        item = products[idx]
        price = item.get("price", 0)
        name = item.get("name", "Unnamed Dump")
        show_payment_options(bot_instance, call, name, price, item, "dumps_menu")

    @bot_instance.callback_query_handler(func=lambda call: call.data == "ai_search")
    def ai_search_prompt(call):
        """Prompts the user to enter their search query."""
        user_states[call.from_user.id] = "awaiting_ai_search"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Cancel", callback_data="main_menu"))
        bot_instance.edit_message_text(
            "🧠 **AI Smart Search**\n\nWhat are you looking for? You can search for anything, like `Netflix BIN`, `USA VISA card`, or `phishing guide`.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

    @bot_instance.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_ai_search")
    def handle_ai_search(message):
        """Performs the AI search and displays results."""
        del user_states[message.from_user.id]
        query = message.text.lower()
        all_products = get_products_from_cache()
        
        results = []
        # Iterate through all categories and items
        for category, items in all_products.items():
            for index, item in enumerate(items):
                # Create a searchable text block for each item
                search_block = f"{item.get('name', '')} {item.get('description', '')} {item.get('bin', '')} {item.get('country', '')} {item.get('info', '')} {item.get('bank', '')}".lower()
                
                # Simple keyword matching
                if all(word in search_block for word in query.split()):
                    # Add category and index to identify the item later
                    item['category'] = category
                    item['index'] = index
                    results.append(item)

        if not results:
            bot_instance.send_message(message.chat.id, "Sorry, I couldn't find any items matching your search.")
            return

        # Display results
        markup = types.InlineKeyboardMarkup(row_width=1)
        text = f"🧠 **Search Results for:** `{query}`\n\n"
        for item in results[:20]: # Limit to 20 results
            name = item.get("name", "Unnamed")
            price = item.get("price", "?")
            # Use the original category and index for the callback
            callback_data = f"buy_idx_{item['category']}_{item['index']}"
            markup.add(types.InlineKeyboardButton(f"🛒 {name} - ${price}", callback_data=callback_data))
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        bot_instance.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

    @bot_instance.callback_query_handler(func=lambda call: call.data == "main_menu")
    def main_menu_callback(call):
        send_main_menu(call.message.chat.id, "✅ Welcome back! Please choose an option:", call.message.message_id)

    # Utility: Get chat ID (admin-only)
    @bot_instance.message_handler(commands=['chatid'])
    def cmd_chatid(message):
        if message.from_user.id != ADMIN_ID:
            return
        bot_instance.reply_to(message, f"Chat ID: <code>{message.chat.id}</code>", parse_mode="HTML")

    # --- Auto-ingest GIFs from configured groups using hashtags ---
    @bot_instance.message_handler(content_types=['animation'])
    def ingest_group_gifs(message):
        try:
            if message.chat and message.chat.id in set(MEDIA_SOURCE_GROUP_IDS or []):
                caption = (message.caption or "").lower()
                kind = None
                if "#welcome" in caption:
                    kind = "welcome"
                elif "#success" in caption:
                    kind = "success"
                elif "#reject" in caption:
                    kind = "reject"
                elif "#pending" in caption:
                    kind = "pending"
                # store to specific pool if tagged, else to 'any' pool
                from helpers import add_gif_to_pool
                use_kind = kind if kind else "any"
                count = add_gif_to_pool(use_kind, message.animation.file_id)
                # acknowledge in group via reply if possible
                try:
                    if kind:
                        bot_instance.reply_to(message, f"✅ Saved to '{use_kind}' pool. Total: {count}")
                    else:
                        bot_instance.reply_to(message, f"✅ Saved to general GIF pool. Total: {count}")
                except Exception:
                    pass
        except Exception as e:
            print(f"GIF ingest error: {e}")

    # --- Admin: Add GIF to pool ---
    @bot_instance.message_handler(func=lambda m: m.from_user and m.from_user.id == ADMIN_ID and m.caption and m.caption.lower().startswith("/addgif"), content_types=['animation'])
    def admin_add_gif(message):
        try:
            parts = message.caption.split()
            if len(parts) < 2:
                bot_instance.reply_to(message, "Usage: /addgif <welcome|success|reject|pending> (send as caption with the GIF)")
                return
            kind = parts[1].lower()
            file_id = message.animation.file_id if message.animation else None
            if not file_id:
                bot_instance.reply_to(message, "Please send this command as a caption on an animated GIF.")
                return
            count = add_gif_to_pool(kind, file_id)
            bot_instance.reply_to(message, f"✅ Added GIF to '{kind}' pool. Total now: {count}")
        except Exception as e:
            bot_instance.reply_to(message, f"Error adding GIF: {e}")

def run_bot(bot_instance, name):
    """Bot runner with improved resilience and network settings."""
    while True:
        try:
            print(f"▶️ Starting polling for {name}...")
            # Use a shorter timeout and keep-alive for better network performance
            bot_instance.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=30)
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError, telebot.apihelper.ApiTelegramException) as e:
            print(f"🔴 Network error in {name}: {e}. Retrying in 10 seconds...")
            time.sleep(10)
        except Exception as e:
            print(f"An unexpected error occurred in {name}: {e}. Retrying in 20 seconds...")
            time.sleep(20)


if __name__ == '__main__':
    print("🤖 Starting bots...")
    init_db()
    load_all_products_into_cache()  # Load products into memory at startup

    # Optimize HTTP session reuse
    try:
        # Keep sessions alive for longer to reduce connection overhead
        telebot.apihelper.SESSION_TIME_TO_LIVE = 60
        # Create a persistent session object
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=retry_strategy)
        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        telebot.apihelper.session = session
        print("✅ Custom requests session configured with retries.")

    except Exception as e:
        print(f"Could not configure advanced session management: {e}")

    # Create bot instances with a larger thread pool for faster handler processing
    bots = [telebot.TeleBot(token, num_threads=16) for token in API_TOKENS]
    for idx, b in enumerate(bots, start=1):
        register_all_handlers(b)
        try:
            bot_username = b.get_me().username
            startup_markup = types.InlineKeyboardMarkup()
            startup_markup.add(types.InlineKeyboardButton("▶️ Start Bot", url=f"https://t.me/{bot_username}?start=admin"))
            notify_admin(b, f"✅ **Bot #{idx} is Online!**", markup=startup_markup)
        except Exception as e:
            print(f"Could not send startup notification for bot #{idx}: {e}")
            try:
                notify_admin(b, f"✅ **Bot #{idx} is Online!** (No button)")
            except Exception:
                pass

    threads = []
    for idx, b in enumerate(bots, start=1):
        t = threading.Thread(target=run_bot, args=(b, f"bot #{idx}"), daemon=True)
        t.start()
        threads.append(t)

    # Block forever
    for t in threads:
        t.join()

