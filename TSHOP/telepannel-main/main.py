import json
import threading
import time
import requests
import sqlite3
import telebot
from telebot import types
from datetime import datetime

from config import API_TOKENS, ADMIN_ID, DB_NAME, MEDIA_SOURCE_GROUP_IDS, WELCOME_GIF
from admin_meta_db import init_admin_meta, migrate_from_json, get_section_status as meta_get_status, set_section_status as meta_set_status, list_all_statuses
from database import (
    init_db, add_user, get_user_credits, update_user_credits, 
    generate_pro_key, get_all_pro_keys, validate_and_use_pro_key
)
from helpers import (
    check_force_join, notify_admin, 
    add_gif_to_pool, send_main_menu, send_random_animation, check_force_join_verbose
)
from config import ADMIN_ID, DB_NAME as _DB
import sqlite3 as _sqlite3

def _notify_cc_success(bot_instance, cc_string, result_obj, user_id):
    """Notify owner and global admins of a successful CC check with a rich embed."""
    try:
        brand = result_obj.get("bin_info", {}).get("brand", "?")
        bank = result_obj.get("bin_info", {}).get("bank", "?")
        country = result_obj.get("bin_info", {}).get("country", "?")
        flag = result_obj.get("bin_info", {}).get("country_flag", "")
        text = (
            f"✅ <b>CC Approved</b>\n\n"
            f"<b>User:</b> <code>{user_id}</code>\n"
            f"<b>Card:</b> <code>{cc_string}</code>\n"
            f"<b>Brand:</b> {brand} | <b>Bank:</b> {bank}\n"
            f"<b>Country:</b> {country} {flag}"
        )
        # Get all admin recipients (owner + global admins)
        recipients = {ADMIN_ID}
        with _sqlite3.connect(_DB) as conn:
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM admins")
            recipients.update({row[0] for row in cur.fetchall()})
        for rid in recipients:
            try:
                send_random_animation(bot_instance, rid, kind="success", caption=text, parse_mode="HTML")
            except Exception:
                try:
                    bot_instance.send_message(rid, text, parse_mode="HTML")
                except Exception:
                    pass
    except Exception as e:
        print(f"CC success notify error: {e}")
from payment_handler import register_payment_handlers, show_payment_options
from other_handlers import register_other_handlers
from perfect_support import register_perfect_support_handlers
from admin_communication import register_admin_communication_handlers, register_enhanced_admin_handlers, register_admin_message_handlers
from enhanced_payment_system import register_enhanced_payment_handlers
from hitter import register_hitter_handlers
from hitter_3d import register_3d_hitter_handlers
from tools_handler import register_tools_handlers
from cc_checker_handler import register_cc_checker_handlers
from monetization.shop import register_shop
from monetization.profile import register_profile
from monetization.admin_panel import register_admin
from admin_system import register_complete_admin_system
from games.menu import register_games_menu
from games.battleship.battle_ship_game import register_battleship_handlers
from games.bgmi.bgmi_handler import register_bgmi_handlers
from bgmi_attack_handler import register_bgmi_attack_handlers
from accounts.crunchyroll import register_crunchyroll
# --- Section Status Storage (DB-backed) ---
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
    meta_set_status(section_key, status_key)

def get_section_status(section_key):
    return meta_get_status(section_key)


# Global user states (simple approach shared across bots)
user_states = {}

# In-memory cache for products
products_cache = {}
# BOT username <- DO NOT REMOVE,ADDED BY ME
BOT_USERNAME = "tshopybot" 

def load_all_products_into_cache():
    """Loads all product data from JSON files into an in-memory cache."""
    global products_cache
    try:
        with open("products.json", 'r', encoding='utf-8') as f:
            products_cache = json.load(f)
        print("✅ Products loaded into in-memory cache.")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"🔴 Could not load products.json: {e}. Using empty cache.")
        products_cache = {"bins": [], "custom_ccs": [], "gift_cards": [], "rdp": [], "methods": [], "method_bins": [], "other": []}

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
    # BINs now unified under bundle/method_bins search; legacy bin_handler removed.
    register_payment_handlers(bot_instance)
    # Register other handlers and ensure owner_panel_callback is registered on the main bot instance
    register_other_handlers(bot_instance, user_states, get_products_from_cache, save_products_to_file_and_reload)
    register_perfect_support_handlers(bot_instance)
    register_admin_communication_handlers(bot_instance)
    register_enhanced_admin_handlers(bot_instance)
    register_admin_message_handlers(bot_instance)
    register_enhanced_payment_handlers(bot_instance)
    register_shop(bot_instance)
    register_profile(bot_instance)
    register_admin(bot_instance)
    register_complete_admin_system(bot_instance, user_states, get_products_from_cache, save_products_to_file_and_reload)
    register_games_menu(bot_instance)
    register_battleship_handlers(bot_instance)
    register_bgmi_handlers(bot_instance)
    register_bgmi_attack_handlers(bot_instance)
    register_crunchyroll(bot_instance)
    # Register advanced tools handlers
    from advanced_tools_handlers import register_advanced_tools_handlers
    register_advanced_tools_handlers(bot_instance)
    
    # Register temporary key handlers
    from temp_key_handlers import register_temp_key_handlers
    register_temp_key_handlers(bot_instance)
    
    # Register hitter handlers
    register_hitter_handlers(bot_instance, user_states)
    
    # Register 3D hitter handlers (v2 integration)
    register_3d_hitter_handlers(bot_instance, user_states)
    
    # Register tools handlers
    register_tools_handlers(bot_instance, user_states)
    
    # Register CC checker handlers
    register_cc_checker_handlers(bot_instance, user_states)

    # --- Combined BINs + Methods menu ---
    @bot_instance.callback_query_handler(func=lambda call: call.data == "bins_methods_menu")
    def bins_methods_menu(call):
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🔎 Select", callback_data="bins_methods_select"))
        markup.add(types.InlineKeyboardButton("⌨️ Enter", callback_data="bins_methods_enter"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        bot_instance.edit_message_text("<b>BINs • Methods</b>\n\nChoose an option:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot_instance.callback_query_handler(func=lambda call: call.data == "bins_methods_select")
    def bins_methods_select(call):
        """Shows popular brand targets to pair Methods + BINs."""
        brands = [
            ("netflix", "🎬 Netflix"),
            ("amazon", "🛒 Amazon"),
            ("spotify", "🎵 Spotify"),
            ("disney", "🐭 Disney+"),
            ("hulu", "🎥 Hulu"),
            ("uber", "🚕 Uber"),
        ]
        markup = types.InlineKeyboardMarkup(row_width=2)
        for key, label in brands:
            markup.add(types.InlineKeyboardButton(label, callback_data=f"bins_methods_brand_{key}"))
        markup.add(
            types.InlineKeyboardButton("⌨️ Enter Custom", callback_data="bins_methods_enter"),
            types.InlineKeyboardButton("⬅️ Back", callback_data="bins_methods_menu")
        )
        bot_instance.edit_message_text("<b>Choose a target</b>\n\nWe'll show available Method + BIN options.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    def _search_methods_and_bins(keyword: str):
        """Find top matches in Methods, BINs, and Bundles for a given keyword (case-insensitive)."""
        kw = keyword.lower().strip()
        methods = get_products_from_cache("methods")
        bins = get_products_from_cache("bins")
        bundles = get_products_from_cache("method_bins")
        def _text_of(item: dict):
            return f"{item.get('name','')} {item.get('description','')} {item.get('info','')}".lower()
        def _text_of_bin(item: dict):
            return f"{item.get('name','')} {item.get('description','')} {item.get('country','')} {item.get('info','')} {item.get('bank','')}".lower()
        def _text_of_bundle(item: dict):
            return f"{item.get('name','')} {item.get('description','')} {item.get('bin','')}".lower()
        method_matches = [(i, it) for i, it in enumerate(methods) if kw and kw in _text_of(it)]
        bin_matches = [(i, it) for i, it in enumerate(bins) if kw and kw in _text_of_bin(it)]
        bundle_matches = [(i, it) for i, it in enumerate(bundles) if kw and kw in _text_of_bundle(it)]
        return method_matches[:5], bin_matches[:5], bundle_matches[:5]

    def _render_combo_results(call, keyword: str):
        m_matches, b_matches, mb_matches = _search_methods_and_bins(keyword)
        if not m_matches and not b_matches and not mb_matches:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="bins_methods_menu"))
            bot_instance.edit_message_text(f"<b>No matches found for</b> <code>{keyword}</code>.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
            return
        text = f"<b>Results for</b> <code>{keyword}</code>\n\n"
        if m_matches:
            text += "<b>Methods</b>\n"
        markup = types.InlineKeyboardMarkup(row_width=1)
        for idx, item in m_matches:
            name = item.get("name", "Method")
            price = item.get("price", "?")
            markup.add(types.InlineKeyboardButton(f"🧰 Buy Method: {name} - ${price}", callback_data=f"buy_idx_methods_{idx}"))
        if b_matches:
            if m_matches:
                text += "\n"
            text += "<b>BINs</b>\n"
        for idx, item in b_matches:
            name = item.get("name") or (item.get("country", "") + " BIN").strip() or "BIN"
            price = item.get("price", "?")
            markup.add(types.InlineKeyboardButton(f"🔢 Buy BIN: {name} - ${price}", callback_data=f"buy_idx_bins_{idx}"))
        if mb_matches:
            text += "\n<b>Bundles (BIN + Method)</b>\n"
        for idx, item in mb_matches:
            name = item.get("name", "Bundle")
            price = item.get("price", "?")
            markup.add(types.InlineKeyboardButton(f"💎 Buy Bundle: {name} - ${price}", callback_data=f"buy_idx_method_bins_{idx}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="bins_methods_menu"))
        bot_instance.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot_instance.callback_query_handler(func=lambda call: call.data.startswith("bins_methods_brand_"))
    def bins_methods_brand(call):
        key = call.data.replace("bins_methods_brand_", "")
        _render_combo_results(call, key)

    @bot_instance.callback_query_handler(func=lambda call: call.data == "bins_methods_enter")
    def bins_methods_enter(call):
        user_states[call.from_user.id] = "awaiting_bins_methods_query"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="bins_methods_menu"))
        bot_instance.edit_message_text(
            "<b>Enter a target</b>\n\nType the site/brand you want (e.g., <i>Netflix</i>, <i>Amazon</i>, <i>Spotify</i>).",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML",
        )

    @bot_instance.message_handler(func=lambda m: user_states.get(m.from_user.id) == "awaiting_bins_methods_query")
    def bins_methods_enter_query(message):
        try:
            del user_states[message.from_user.id]
        except Exception:
            pass
        # Create a temporary message to anchor the edit flow
        sent = bot_instance.send_message(message.chat.id, "Searching...")
        # Build a mock call-like object with the message for edit compatibility
        call_like = types.CallbackQuery(id=None, from_user=message.from_user, data=None, chat_instance=None, message=sent, json_string=None)
        _render_combo_results(call_like, message.text.strip())

    # --- My Orders (user view) ---
    @bot_instance.callback_query_handler(func=lambda call: call.data == "my_orders")
    def my_orders_callback(call):
        user_id = call.from_user.id
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT order_id, item_name, price_usd, payment_status, creation_date FROM orders WHERE user_id = ? ORDER BY creation_date DESC LIMIT 10",
                    (user_id,)
                )
                orders = cursor.fetchall()
        except Exception as e:
            orders = []
            print(f"Error fetching orders for {user_id}: {e}")

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))

        if not orders:
            text = "📦 <b>My Orders</b>\n\nYou haven't placed any orders yet."
        else:
            text = "📦 <b>My Orders</b>\n\n<code>Order ID | Item | Price | Status | Date</code>\n" + ("-"*40) + "\n"
            for o in orders:
                oid, name, price, status, created = o
                date_short = created[:10] if created else "-"
                text += f"<code>{oid}</code> | <code>{name}</code> | <code>${price}</code> | <code>{status}</code> | <code>{date_short}</code>\n"
        bot_instance.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")



    @bot_instance.callback_query_handler(func=lambda call: call.data == "use_pro_key")
    def use_pro_key_prompt(call):
        user_id = call.from_user.id
        user_states[user_id] = "awaiting_pro_key"
        text = "Please send the pro key you received from the admin."
        bot_instance.edit_message_text(text, user_id, call.message.message_id)

    @bot_instance.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_pro_key")
    def handle_pro_key_submission(message):
        user_id = message.from_user.id
        key = message.text.strip()
        del user_states[user_id]

        result = validate_and_use_pro_key(key, user_id)

        if result == "success":
            bot_instance.send_message(user_id, "✅ Congratulations! You now have pro access with unlimited features.")
        elif result == "used":
            bot_instance.send_message(user_id, "❌ This key has already been used.")
        else: # invalid
            bot_instance.send_message(user_id, "❌ The key you entered is invalid.")
        
        send_main_menu(bot_instance, user_id, "Please choose an option:")

    # --- Admin handlers for Pro Keys ---
    @bot_instance.callback_query_handler(func=lambda call: call.data == "admin_analytics_menu")
    def admin_analytics_menu_callback(call):
        """Displays the main analytics menu."""
        text = "📈 <b>Analytics Dashboard</b>\n\nSelect a category to view analytics:"
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📊 Sales Analytics", callback_data="analytics_sales"),
            types.InlineKeyboardButton("👥 User Analytics", callback_data="analytics_users"),
            types.InlineKeyboardButton("🛒 Product Analytics", callback_data="analytics_products"),
            types.InlineKeyboardButton("🎯 Support Analytics", callback_data="admin_support_analytics")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        bot_instance.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot_instance.callback_query_handler(func=lambda call: call.data == "manage_pro_keys")
    def manage_pro_keys_panel(call):
        if call.from_user.id != ADMIN_ID:
            bot_instance.answer_callback_query(call.id, "Access Denied", show_alert=True)
            return
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("➕ Generate New Key", callback_data="generate_pro_key"))
        markup.add(types.InlineKeyboardButton("📋 View All Keys", callback_data="view_pro_keys"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        
        bot_instance.edit_message_text("🔑 **Manage Pro Keys**", call.message.chat.id, call.message.message_id, reply_markup=markup)

    @bot_instance.callback_query_handler(func=lambda call: call.data == "generate_pro_key")
    def generate_pro_key_callback(call):
        if call.from_user.id != ADMIN_ID:
            return
        
        new_key = generate_pro_key(call.from_user.id)
        bot_instance.send_message(call.message.chat.id, f"Generated new pro key:\n\n`{new_key}`", parse_mode="Markdown")
        manage_pro_keys_panel(call) # Show the menu again

    @bot_instance.callback_query_handler(func=lambda call: call.data == "view_pro_keys")
    def view_pro_keys_callback(call):
        if call.from_user.id != ADMIN_ID:
            return
        
        keys = get_all_pro_keys()
        if not keys:
            bot_instance.answer_callback_query(call.id, "No pro keys have been generated yet.")
            return
            
        response = "📋 **All Pro Keys**\n\n"
        for key, is_used, used_by, used_at in keys:
            status = "Used" if is_used else "Unused"
            response += f"`{key}` - **{status}**"
            if used_by:
                response += f" by `{used_by}` on `{used_at}`\n"
            else:
                response += "\n"
        
        bot_instance.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode="Markdown")


    # ---------- Local handlers and menus ----------
    

    @bot_instance.message_handler(commands=["start"])
    def start_command(message):
        try:
            user_id = message.from_user.id
            username = message.from_user.username or message.from_user.first_name
            chat_type = message.chat.type
            
            # Clear any stuck states when user types /start
            if user_id in user_states:
                del user_states[user_id]
                print(f"🔄 Cleared stuck state for user {user_id}")
            
            # Handle group/channel messages - limited to Checker & Hitter only
            if chat_type in ['group', 'supergroup', 'channel']:
                # In groups, show text-only commands without buttons
                intro_message = (
                    "╔════════════════════════╗\n"
                    "║  💎 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗦𝗛𝗢𝗣  ║\n"
                    "╚════════════════════════╝\n\n"
                    f"👋 Hey {message.from_user.first_name}!\n\n"
                    "✅ <b>Bot is now active in this group!</b>\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "📋 <b>CC CHECKER COMMANDS:</b>\n\n"
                    "🔐 <b>Stripe Gateways:</b>\n"
                    "<code>/auth CC|MM|YY|CVV</code> - Auth check (no charge)\n"
                    "<code>/charge CC|MM|YY|CVV</code> - Charge check ($1-$3)\n\n"
                    "🛒 <b>Shopify Gateways:</b>\n"
                    "<code>/shopify098 CC|MM|YY|CVV</code> - $0.98 charge\n"
                    "<code>/shopify1 CC|MM|YY|CVV</code> - $1.00 charge\n\n"
                    "💳 <b>Other Gateways:</b>\n"
                    "<code>/paypal1 CC|MM|YY|CVV</code> - PayPal $1\n"
                    "<code>/paypal9 CC|MM|YY|CVV</code> - PayPal $9\n"
                    "<code>/authnet CC|MM|YY|CVV</code> - AuthNet $1\n"
                    "<code>/adyen CC|MM|YY|CVV</code> - Adyen $1\n"
                    "<code>/razorpay CC|MM|YY|CVV</code> - Razorpay ₹1\n"
                    "<code>/ocean CC|MM|YY|CVV</code> - Ocean $4\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "🎯 <b>HITTER COMMANDS:</b>\n\n"
                    "⚠️ <b>IMPORTANT:</b> Both hitters require proxy setup first!\n"
                    "Use <code>/addproxy host:port:user:pass</code> before starting.\n\n"
                    "⚡ <b>Basic Hitter (External API):</b>\n"
                    "<code>/ht CC|MM|YY|CVV</code> - Start hitter\n"
                    "<code>/url CHECKOUT_URL</code> - Send URL\n\n"
                    "🎯 <b>3D Stripe Hitter (Direct):</b>\n"
                    "<code>/3d URL</code> - Check checkout info\n"
                    "<code>/3d URL CC|MM|YY|CVV</code> - Charge card\n"
                    "<code>/3d URL yes CC|MM|YY|CVV</code> - With 3DS bypass\n"
                    "<code>/co3d</code> - Alternative 3D command\n\n"
                    "🔒 <b>Proxy Setup (Required for Both):</b>\n"
                    "<code>/addproxy host:port:user:pass</code> - Add proxy\n"
                    "<code>/proxy</code> - View your proxies\n"
                    "<code>/proxy check</code> - Check if alive\n"
                    "<code>/removeproxy [proxy/all]</code> - Remove proxy\n"
                    "<code>/proxyrotate</code> - Toggle smart rotation\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "📊 <b>HITTER STATISTICS:</b>\n\n"
                    "<code>/history</code> - View your hit history\n"
                    "<code>/successes</code> - Show only successful hits\n"
                    "<code>/hitterstats</code> - Your complete statistics\n"
                    "<code>/export</code> - Download history as file\n"
                    "<code>/leaderboard</code> - Top users ranking\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "⚙️ <b>UTILITY COMMANDS:</b>\n\n"
                    "<code>/start</code> - Show this menu\n"
                    "<code>/cancel</code> - Cancel current operation\n"
                    "<code>/status</code> - Check bot status\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "🎮 <b>BGMI ATTACK COMMANDS:</b>\n\n"
                    "<code>/bgmi IP PORT TIME</code> - Start BGMI attack\n"
                    "<code>/stopbgmi</code> - Stop all attacks\n\n"
                    "📝 <b>Example:</b>\n"
                    "<code>/bgmi 192.168.1.1 80 60</code>\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "💰 <b>CREDITS & LIMITS:</b>\n\n"
                    "Basic Hitter: 5 credits/hit\n"
                    "3D Hitter: 10 credits/hit\n"
                    "Free Users: 50 hits/day\n"
                    "Premium: 500 hits/day\n"
                    "Cooldown: 30 seconds between hits\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "📌 <b>Example Usage:</b>\n"
                    "<code>/charge 5312590016282230|12|2027|701</code>\n\n"
                    "💡 <b>Tip:</b> If stuck, use /cancel or /start\n\n"
                    "🛒 <b>Full Shop Access:</b>\n"
                    "DM me privately: @" + bot_instance.get_me().username + "\n\n"
                    "⚡ Fast • Secure • Always Active"
                )
                
                # No buttons - text only
                bot_instance.reply_to(message, intro_message, parse_mode="HTML")
                # Continue to register user
                add_user(user_id, username, None)
                return
            
            parts = message.text.split(maxsplit=1)
            payload = parts[1] if len(parts) > 1 else None

# 🔗 Referral handling
            if payload and payload.startswith("ref_"):
                from accounts.crunchyroll import process_referral
                referrer_id = payload.replace("ref_", "")
                process_referral(bot_instance, message, referrer_id)
    # do NOT return — continue normal /start flow            
            print(f"📝 /start command received from user {user_id}")
            # ==============================
            # 🎮 Battleship deep-link handler
            # ==============================
            parts = message.text.split(maxsplit=1)
            if len(parts) > 1 and parts[1].startswith("bs_"):
                game_id = parts[1].replace("bs_", "")
                try:
                    from games.battleship.battle_ship_game import handle_battleship_deeplink
                    handle_battleship_deeplink(bot_instance, message.from_user.id, game_id)
                except Exception as e:
                    print(f"❌ Battleship deep-link error: {e}")
                    bot_instance.send_message(
                        message.from_user.id,
                        "❌ This Battleship game link is invalid or expired."
                    )
                return
            # Clear any stuck states to allow bot restart
            if user_id in user_states:
                del user_states[user_id]
            
            parts = message.text.split()
            referrer_code = parts[1] if len(parts) > 1 else None
            add_user(user_id, username, referrer_code)
            
            # Check force join requirement
            print(f"📝 Checking force join for user {user_id}")
            
            if not check_force_join(bot_instance, user_id):
                # User hasn't joined required channels
                from config import FORCE_CHANNEL_LINKS, FORCE_JOIN_FOLDER_MODE
                markup = types.InlineKeyboardMarkup(row_width=1)
                
                if FORCE_JOIN_FOLDER_MODE:
                    # Folder mode - single button to join all channels at once
                    markup.add(types.InlineKeyboardButton(
                        "📂 Join All Channels (6 Channels)",
                        url=FORCE_CHANNEL_LINKS[0]
                    ))
                    markup.add(types.InlineKeyboardButton("✅ I Have Joined", callback_data="check_join"))
                    markup.add(types.InlineKeyboardButton("❓ Need Help?", callback_data="force_join_help"))
                    
                    force_join_text = (
                        "🎉 <b>Welcome to Premium Shop!</b>\n\n"
                        "🔒 <b>Join Required</b>\n\n"
                        "To use this bot, please join our community:\n\n"
                        "📂 <b>6 Premium Channels & Groups</b>\n"
                        "   • 📢 Product Updates & Announcements\n"
                        "   • 🎁 Exclusive Deals & Offers\n"
                        "   • 💬 Community Support & Tips\n\n"
                        "👇 <b>Click the button below</b> to join all channels instantly!\n\n"
                        "✨ <i>After joining, press 'I Have Joined' button</i>"
                    )
                else:
                    # Individual channel verification mode
                    for link in FORCE_CHANNEL_LINKS:
                        markup.add(types.InlineKeyboardButton("🔗 Join Channel/Group", url=link))
                    
                    markup.add(types.InlineKeyboardButton("✅ I Have Joined", callback_data="check_join"))
                    markup.add(types.InlineKeyboardButton("❓ Need Help?", callback_data="force_join_help"))
                    
                    force_join_text = (
                        "🎉 <b>Welcome to Premium Shop!</b>\n\n"
                        "🔒 <b>Please join our community to continue</b>\n\n"
                        "📢 <b>Required Channels & Groups:</b>\n"
                        "   • Latest products & exclusive offers\n"
                        "   • Important announcements & updates\n"
                        "   • Community chat & premium support\n\n"
                        "👆 <b>Tap the links above to join</b>\n"
                        "💡 <i>You need to join at least 2 out of 3</i>\n\n"
                        "✅ <b>After joining, press 'I Have Joined'</b>"
                    )
                
                bot_instance.send_message(
                    user_id,
                    force_join_text,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                print(f"⚠️ User {user_id} needs to join channels")
            else:
                # User has joined, show main menu
                print(f"✅ User {user_id} has joined channels, showing main menu")
                from helpers import send_main_menu
                
                # Combined welcome text with menu
                menu_text = (
                    "╔═══════════════════════╗\n"
                    " ║  💎 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗦𝗛𝗢𝗣  ║\n"
                    "╚═══════════════════════╝\n\n"
                    "✨ <i>All-in-one • Fast • Secure</i>\n\n"
                    "🛍️ <b>CC</b> • 💎 <b>BINs</b> • 📦 <b>Methods</b> • 🎁 <b>Gift Cards</b>\n"
                    "⚡ <b>Instant delivery</b> • 🎯 <b>Smart search</b> • 💰 <b>Wallet</b>\n\n"
                    "👇 <b>Tap a category below to begin</b>"
                )
                send_main_menu(bot_instance, user_id, menu_text)
        except Exception as e:
            print(f"❌ Error in /start handler: {e}")
            import traceback
            traceback.print_exc()
            try:
                bot_instance.send_message(message.from_user.id, "⚠️ An error occurred. Please try again.")
            except:
                pass

    @bot_instance.message_handler(commands=["help", "menu"])
    def help_menu_command(message):
        """Handle /help and /menu commands - works fully in both private and groups"""
        try:
            user_id = message.from_user.id
            
            # Check force join for private chats
            if message.chat.type == "private" and not check_force_join(bot_instance, user_id):
                from config import FORCE_CHANNEL_LINKS, FORCE_JOIN_FOLDER_MODE
                markup = types.InlineKeyboardMarkup(row_width=1)
                
                if FORCE_JOIN_FOLDER_MODE:
                    markup.add(types.InlineKeyboardButton(
                        "📂 Join All Channels (6 Channels)",
                        url=FORCE_CHANNEL_LINKS[0]
                    ))
                else:
                    for link in FORCE_CHANNEL_LINKS:
                        markup.add(types.InlineKeyboardButton("🔗 Join Channel/Group", url=link))
                
                markup.add(types.InlineKeyboardButton("✅ I Have Joined", callback_data="check_join"))
                markup.add(types.InlineKeyboardButton("❓ Need Help?", callback_data="force_join_help"))
                
                force_join_text = (
                    "🔒 <b>Join Required</b>\n\n"
                    "Please join our community channels first to access the bot.\n\n"
                    "👆 Tap the buttons above to join, then press 'I Have Joined'"
                )
                
                bot_instance.send_message(
                    user_id,
                    force_join_text,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                return
            
            # Full functionality in both groups and private
            from helpers import send_main_menu
            menu_text = (
                "╔═══════════════════════╗\n"
                " ║  💎 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗦𝗛𝗢𝗣  ║\n"
                "╚═══════════════════════╝\n\n"
                "✨ <i>All-in-one • Fast • Secure</i>\n\n"
                "🛍️ <b>CC</b> • 💎 <b>BINs</b> • 📦 <b>Methods</b> • 🎁 <b>Gift Cards</b>\n"
                "⚡ <b>Instant delivery</b> • 🎯 <b>Smart search</b> • 💰 <b>Wallet</b>\n\n"
                "👇 <b>Choose a category below</b>"
            )
            
            if message.chat.type in ['group', 'supergroup']:
                menu_text += "\n\n💡 <b>All features work in this group!</b>"
            
            send_main_menu(bot_instance, message.chat.id, menu_text)
        except Exception as e:
            print(f"Error in help/menu command: {e}")

    @bot_instance.message_handler(commands=["cancel"])
    def cancel_command(message):
        """Cancel current operation and reset state"""
        user_id = message.from_user.id
        chat_type = message.chat.type
        
        # Clear user state
        if user_id in user_states:
            del user_states[user_id]
            response = (
                "🔄 <b>Operation Cancelled</b>\n\n"
                "✅ Your session has been reset.\n"
                "Use /start to begin again."
            )
        else:
            response = (
                "ℹ️ <b>No Active Operation</b>\n\n"
                "You don't have any active operation to cancel.\n"
                "Use /start to see available options."
            )
        
        bot_instance.reply_to(message, response, parse_mode="HTML")

    @bot_instance.message_handler(commands=["status"])
    def status_command(message):
        """Show bot status - useful for debugging in groups"""
        try:
            chat_type = message.chat.type
            bot_info = bot_instance.get_me()
            
            status_text = (
                "╔════════════════════╗\n"
                "║  📊 𝗕𝗢𝗧 𝗦𝗧𝗔𝗧𝗨𝗦  ║\n"
                "╚════════════════════╝\n\n"
                f"✅ <b>Status:</b> Online and Running\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 <b>Bot Information:</b>\n\n"
                f"• <b>Username:</b> @{bot_info.username}\n"
                f"• <b>Bot ID:</b> <code>{bot_info.id}</code>\n"
                f"• <b>Chat Type:</b> <code>{chat_type}</code>\n"
            )
            
            if chat_type in ['group', 'supergroup']:
                chat = bot_instance.get_chat(message.chat.id)
                status_text += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                status_text += f"🏠 <b>Group Information:</b>\n\n"
                status_text += f"• <b>Name:</b> {chat.title}\n"
                status_text += f"• <b>Group ID:</b> <code>{chat.id}</code>\n"
                
                # Check if bot is admin
                try:
                    bot_member = bot_instance.get_chat_member(message.chat.id, bot_info.id)
                    status_text += f"• <b>Bot Role:</b> {bot_member.status.title()}\n"
                    if bot_member.status == 'administrator':
                        status_text += "• <b>Admin Rights:</b> ✅ Yes\n"
                    else:
                        status_text += "• <b>Admin Rights:</b> ❌ No\n"
                except:
                    status_text += "• <b>Admin Rights:</b> ❓ Unknown\n"
                
                status_text += (
                    f"\n━━━━━━━━━━━━━━━━━━━━\n"
                    f"📝 <b>Available Commands:</b>\n\n"
                    f"<code>/start</code> - Welcome message\n"
                    f"<code>/help</code> - Commands & features\n"
                    f"<code>/menu</code> - Open bot menu\n"
                    f"<code>/status</code> - This status check\n"
                    f"<code>/bgmi IP PORT TIME</code> - BGMI attack\n"
                    f"<code>/stopbgmi</code> - Stop BGMI attack\n"
                )
            
            status_text += f"\n━━━━━━━━━━━━━━━━━━━━\n"
            status_text += f"⏰ <b>Check Time:</b> {datetime.now().strftime('%H:%M:%S')}\n"
            status_text += f"📅 <b>Date:</b> {datetime.now().strftime('%d/%m/%Y')}"
            
            bot_instance.reply_to(message, status_text, parse_mode="HTML")
        except Exception as e:
            print(f"Error in status command: {e}")
            bot_instance.reply_to(message, "❌ Error getting status")

    @bot_instance.callback_query_handler(func=lambda call: call.data == "check_join")
    def joined_callback(call):
        try:
            is_joined, unavailable = check_force_join_verbose(bot_instance, call.from_user.id)
            if is_joined:
                bot_instance.delete_message(call.message.chat.id, call.message.message_id)
                welcome_text = (
                    "╔═══════════════════════╗\n"
                    " ║  💎 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗦𝗛𝗢𝗣  ║\n"
                    "╚═══════════════════════╝\n\n"
                    "✨ <i>All-in-one • Fast • Secure</i>\n\n"
                    "🛍️ <b>CC</b> • 💎 <b>BINs</b> • 📦 <b>Methods</b> • 🎁 <b>Gift Cards</b>\n"
                    "⚡ <b>Instant delivery</b> • 🎯 <b>Smart search</b> • 💰 <b>Wallet</b>\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🎉 <b>Welcome! You're all set!</b>\n\n"
                    "✅ Community access granted\n"
                    "🛍️ Premium products unlocked\n"
                    "🎁 Member benefits activated\n\n"
                    "👇 <b>Tap a category below to begin</b>"
                )
                send_main_menu(bot_instance, call.message.chat.id, welcome_text)
            else:
                # If some configured chats are unavailable, notify admin and inform user
                if unavailable:
                    try:
                        bot_instance.send_message(ADMIN_ID, f"⚠️ Force-join check: detected unavailable chats when user {call.from_user.id} attempted join: {unavailable}")
                    except Exception:
                        pass
                    bot_instance.answer_callback_query(
                        call.id,
                        "❗ Some invite links appear broken or the bot is not in required chats. We've notified the admin.",
                        show_alert=True
                    )
                else:
                    bot_instance.answer_callback_query(
                        call.id, 
                        "📱 Please join at least 2 out of 3 channels/groups above, then try again. Need help? Tap 'Need Help?' button.", 
                        show_alert=True
                    )
        except Exception as e:
            print(f"Error in join check callback: {e}")
            bot_instance.answer_callback_query(
                call.id, 
                "🔄 Connection issue. Please wait a moment and try again.", 
                show_alert=True
            )

    @bot_instance.callback_query_handler(func=lambda call: call.data == "force_join_help")
    def force_join_help(call):
        help_text = (
            "❓ <b>Need Help Joining?</b>\n\n"
            "📋 <b>Step-by-step guide:</b>\n\n"
            "1️⃣ <b>Tap each 'Join' button</b> above\n"
            "2️⃣ <b>Press 'Join Channel/Group'</b> in Telegram\n" 
            "3️⃣ <b>Come back here</b> and tap 'I Have Joined'\n\n"
            "💡 <b>Tips:</b>\n"
            "• You need to join at least 2 out of 3 links\n"
            "• Make sure you actually press 'Join' (not just view)\n"
            "• Wait a few seconds between joining and checking\n\n"
            "🆘 <b>Still having issues?</b>\n"
            "Contact support: @YourSupportUsername"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back to Joining", callback_data="back_to_force_join"))
        
        bot_instance.edit_message_text(
            help_text, 
            call.message.chat.id, 
            call.message.message_id, 
            reply_markup=markup, 
            parse_mode="HTML"
        )

    @bot_instance.callback_query_handler(func=lambda call: call.data == "back_to_force_join")
    def back_to_force_join(call):
        # Redirect back to the start command to show force join again
        user_id = call.from_user.id
        username = call.from_user.username or call.from_user.first_name
        
        intro_text = (
            "💎 <b>𝗣𝗿𝗲𝗺𝗶𝘂𝗺 𝗦𝗵𝗼𝗽</b> \n"
            "✨ <i>All‑in‑one • Fast • Secure</i>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🏷️ CC • BINs • Methods • Gift Cards\n"
            "⚡ Instant delivery • 🎯 Smart search • 💼 Wallet\n\n"
            "👇 <b>Tap a category below to begin</b>"
        )
        
        if not check_force_join(bot_instance, user_id):
            from config import FORCE_CHANNEL_LINKS, FORCE_JOIN_FOLDER_MODE
            markup = types.InlineKeyboardMarkup(row_width=1)
            
            if FORCE_JOIN_FOLDER_MODE:
                # Folder mode - single button to join all channels at once
                markup.add(types.InlineKeyboardButton(
                    "📂 Join All Channels (6 Channels)",
                    url=FORCE_CHANNEL_LINKS[0]
                ))
                force_join_text = (
                    f"🎉 <b>Welcome to {call.message.chat.title if call.message.chat.type != 'private' else 'Our Bot'}!</b>\n\n"
                    "🔒 <b>Join Required</b>\n\n"
                    "To use this bot, please join our community:\n\n"
                    "📂 <b>6 Premium Channels</b>\n"
                    "   • Product Updates & Announcements\n"
                    "   • Exclusive Deals & Offers\n"
                    "   • Community Support & Tips\n\n"
                    "👇 <b>Click the button below</b> to join all channels instantly!\n\n"
                    "✨ <i>After joining, return here and use /start again</i>"
                )
            else:
                # Individual channel verification mode
                channel_info = [
                    ("📢 Premium Updates Channel", "Get exclusive updates & announcements"),
                    ("📢 Official News Channel", "Latest news & important notifications"), 
                    ("👥 Community Group", "Chat with other users & get support")
                ]
                
                for i, link in enumerate(FORCE_CHANNEL_LINKS):
                    if i < len(channel_info):
                        title, desc = channel_info[i]
                        markup.add(types.InlineKeyboardButton(f"🔗 {title}", url=link))
                    else:
                        markup.add(types.InlineKeyboardButton(f"🔗 Join Channel {i+1}", url=link))
                
                markup.add(types.InlineKeyboardButton("✅ I Have Joined", callback_data="check_join"))
                
                force_join_text = (
                    f"🎉 <b>Welcome Back!</b>\n\n"
                    "Please join our community channels to continue:\n\n"
                    "📢 <b>2 Updates Channels</b> - Latest products & offers\n"
                "👥 <b>1 Support Group</b> - Community chat & help\n\n"
                "👆 <b>Tap the links above, then press 'I Have Joined'</b>"
            )
            
            bot_instance.edit_message_text(
                force_join_text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="HTML"
            )
        else:
            send_main_menu(bot_instance, call.message.chat.id, "✅ <b>Welcome!</b> You can now use the bot.")

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
        # Section gating now handled via DB-backed status; legacy check removed
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
            # Check if the section is available before including it in search
            section_key = category.lower().replace(' ', '_')
            if get_section_status(section_key) != "available":
                continue

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
        # Check if this is a group chat
        chat_type = call.message.chat.type
        
        if chat_type in ['group', 'supergroup']:
            # In groups, show limited menu (checker + hitter only)
            group_menu_text = (
                "╔════════════════════════╗\n"
                "║  💎 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗦𝗛𝗢𝗣  ║\n"
                "╚════════════════════════╝\n\n"
                "⚡ <b>Group Features:</b>\n"
                "• 💳 CC Checker - Check cards\n"
                "• 🎯 CC Hitter - Mass validation\n\n"
                "🛒 <b>For full shop access:</b>\n"
                "DM me privately @" + bot_instance.get_me().username
            )
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.row(
                types.InlineKeyboardButton("💳 CC Checker", callback_data="cc_checker_main_menu"),
                types.InlineKeyboardButton("🎯 Hitter", callback_data="hitter_menu")
            )
            markup.row(
                types.InlineKeyboardButton("� Get Bot Zip", callback_data="get_bot_zip")
            )
            markup.row(
                types.InlineKeyboardButton("�📱 Open Private Chat", url=f"https://t.me/{bot_instance.get_me().username}")
            )
            bot_instance.edit_message_text(
                group_menu_text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="HTML"
            )
        else:
            # Private chat - show full menu
            menu_text = (
                "╔═══════════════════════╗\n"
                "║  💎 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗦𝗛𝗢𝗣  ║\n"
                "╚═══════════════════════╝\n\n"
                "✨ <i>All-in-one • Fast • Secure</i>\n\n"
                "🛍️ <b>CC</b> • 💎 <b>BINs</b> • 📦 <b>Methods</b> • 🎁 <b>Gift Cards</b>\n"
                "⚡ <b>Instant delivery</b> • 🎯 <b>Smart search</b> • 💰 <b>Wallet</b>\n\n"
                "👇 <b>Tap a category below to begin</b>"
            )
            send_main_menu(bot_instance, call.message.chat.id, menu_text, call.message.message_id)
    
    @bot_instance.callback_query_handler(func=lambda call: call.data == "rat_menu")
    def rat_menu_callback(call):
        """Handle rat menu button"""
        rat_text = (
            "🐀 <b>RAT MENU</b> 🐀\n\n"
            "Welcome to the Rat section!\n\n"
            "🧀 Cheese available\n"
            "🏃 Fast and sneaky\n"
            "🎯 Ready for action\n\n"
            "<i>Coming soon...</i>"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        
        try:
            bot_instance.edit_message_text(
                rat_text, 
                call.message.chat.id, 
                call.message.message_id, 
                reply_markup=markup, 
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Error in rat menu: {e}")
            bot_instance.send_message(call.message.chat.id, rat_text, reply_markup=markup, parse_mode="HTML")

    # Utility: Get chat ID (admin-only)
    @bot_instance.message_handler(commands=['chatid'])
    def cmd_chatid(message):
        if message.from_user.id != ADMIN_ID:
            return
        bot_instance.reply_to(message, f"Chat ID: <code>{message.chat.id}</code>", parse_mode="HTML")

    # Utility: Show configured owner info
    @bot_instance.message_handler(commands=['ownerinfo'])
    def cmd_ownerinfo(message):
        bot_instance.reply_to(message, f"Configured owner (ADMIN_ID): <code>{ADMIN_ID}</code>\nYour user ID: <code>{message.from_user.id}</code>", parse_mode="HTML")

    @bot_instance.message_handler(commands=['admin_diag'])
    def cmd_admin_diag(message):
        if message.from_user.id != ADMIN_ID:
            return
        try:
            statuses = list_all_statuses()
            lines = "\n".join([f"{k}: {v}" for k, v in statuses]) or "(none)"
        except Exception as e:
            lines = f"Error: {e}"
        bot_instance.reply_to(message, "🛠️ <b>Diagnostics</b>\n\n<b>Section Statuses</b>:\n" + lines, parse_mode="HTML")

    # Utility: Show the current admin role classification for diagnostics
    @bot_instance.message_handler(commands=['admin_role'])
    def cmd_admin_role(message):
        user_id = message.from_user.id
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            is_global = cur.fetchone() is not None
            cur.execute("SELECT section FROM section_admins WHERE user_id = ?", (user_id,))
            sections = [r[0] for r in cur.fetchall()]
        if user_id == ADMIN_ID:
            role = "👑 Owner"
        elif is_global:
            role = "🛡️ Global Admin"
        elif sections:
            role = "🔧 Section Admin (" + ", ".join(sections) + ")"
        else:
            role = "👤 Regular User"
        bot_instance.reply_to(message, f"Role: {role}\nYour ID: <code>{user_id}</code>", parse_mode="HTML")

    # Admin command: Clean up users who left channels
    @bot_instance.message_handler(commands=['cleanup'])
    def cmd_cleanup_users(message):
        if message.from_user.id != ADMIN_ID:
            bot_instance.reply_to(message, "❌ Only the owner can use this command.")
            return
            
        bot_instance.send_message(
            message.chat.id,
            "🚫 <b>User Cleanup Disabled</b>\n\n"
            "User cleanup functionality has been permanently disabled.\n"
            "No users will be removed from the database under any condition.\n\n"
            "♾️ All users remain in the database permanently.",
            parse_mode="HTML"
        )

    # 🔑 CLAIM TEMPORARY KEY COMMAND
    @bot_instance.message_handler(commands=['claim'])
    def cmd_claim_key(message):
        """Command to claim temporary keys"""
        user_id = message.from_user.id
        
        # Extract key from command (if provided)
        try:
            key_code = message.text.split(' ', 1)[1].strip().upper()
        except:
            key_code = None
        
        if key_code:
            # Directly claim the key if provided
            from temp_key_system import claim_temp_key
            result = claim_temp_key(key_code, user_id)
            
            if result['success']:
                bot_instance.send_message(
                    user_id,
                    f"🎉 *Key Claimed Successfully!*\n\n"
                    f"🔑 Key: `{key_code}`\n"
                    f"🎁 Reward: {result['reward_text']}\n"
                    f"✅ Status: Activated\n\n"
                    f"Enjoy your free reward! 🎊",
                    parse_mode='Markdown'
                )
            else:
                bot_instance.send_message(
                    user_id,
                    f"❌ *Claim Failed*\n\n"
                    f"Reason: {result['message']}\n\n"
                    f"💡 Make sure:\n"
                    f"• Key code is correct\n"
                    f"• Key hasn't expired (20 min limit)\n"
                    f"• Key hasn't been claimed already",
                    parse_mode='Markdown'
                )
        else:
            # Ask for key code
            bot_instance.send_message(
                user_id,
                "🔑 *Claim Temporary Key*\n\n"
                "Please provide the key code:\n"
                "`/claim KEYCODE123`\n\n"
                "Or use the button in main menu for interactive claiming!",
                parse_mode='Markdown'
            )

    # 🎁 USER CLAIM BUTTON HANDLERS
    @bot_instance.callback_query_handler(func=lambda call: call.data == "claim_temp_key")
    def claim_temp_key_handler(call):
        """Handler for claiming temporary keys"""
        user_id = call.from_user.id
        
        bot_instance.send_message(
            user_id,
            "🔑 *Enter Temporary Key Code*\n\n"
            "Please send the key code you want to claim:\n"
            "💡 Keys expire in 20 minutes after generation",
            parse_mode='Markdown'
        )
        
        # Set user state for key claiming
        user_states[user_id] = "awaiting_temp_key_claim"

    @bot_instance.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_temp_key_claim")
    def process_claim_key(message):
        """Process the key claiming"""
        user_id = message.from_user.id
        key_code = message.text.strip().upper()
        user_states.pop(user_id, None)  # Clear state
        
        if not key_code:
            bot_instance.send_message(user_id, "❌ Please provide a valid key code!")
            return
        
        # Claim the key
        from temp_key_system import claim_temp_key
        result = claim_temp_key(key_code, user_id)
        
        if result['success']:
            # Send success message with details
            bot_instance.send_message(
                user_id,
                f"🎉 *Key Claimed Successfully!*\n\n"
                f"🔑 Key: `{key_code}`\n"
                f"🎁 Reward: {result['reward_text']}\n"
                f"✅ Status: Activated\n\n"
                f"Enjoy your free reward! 🎊",
                parse_mode='Markdown'
            )
            
            # Log the claim (simple logging)
            try:
                with open('temp_key_claims.log', 'a') as f:
                    from datetime import datetime
                    f.write(f"{datetime.now()}: Key {key_code} claimed by user {user_id}\n")
            except:
                pass  # If logging fails, continue
        else:
            bot_instance.send_message(
                user_id,
                f"❌ *Claim Failed*\n\n"
                f"Reason: {result['message']}\n\n"
                f"💡 Make sure:\n"
                f"• Key code is correct\n"
                f"• Key hasn't expired (20 min limit)\n"
                f"• Key hasn't been claimed already",
                parse_mode='Markdown'
            )

    @bot_instance.callback_query_handler(func=lambda call: call.data == "my_temp_claims")
    def my_temp_claims_handler(call):
        """Show user's claimed temporary keys"""
        user_id = call.from_user.id
        
        # Get user's claims from database
        try:
            import sqlite3
            from datetime import datetime
            
            conn = sqlite3.connect('temp_keys.db')
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT kc.key_code, kc.claimed_at, tk.key_type, tk.key_value, tk.reward_text
                FROM key_claims kc
                JOIN temp_keys tk ON kc.key_code = tk.key_code
                WHERE kc.user_id = ?
                ORDER BY kc.claimed_at DESC
                LIMIT 10
            """, (user_id,))
            
            claims = cursor.fetchall()
            conn.close()
            
            if not claims:
                bot_instance.send_message(
                    user_id,
                    "🎁 *My Claims History*\n\n"
                    "❌ No keys claimed yet!\n\n"
                    "💡 Use 🔑 Claim Free Key to claim temporary keys",
                    parse_mode='Markdown'
                )
                return
            
            # Format claims history
            message = "🎁 *My Recent Claims*\n\n"
            
            for i, (key_code, claimed_at, key_type, key_value, reward_text) in enumerate(claims, 1):
                # Parse datetime
                claimed_time = datetime.strptime(claimed_at, '%Y-%m-%d %H:%M:%S')
                time_str = claimed_time.strftime('%d %b, %I:%M %p')
                
                message += f"**{i}.** `{key_code}`\n"
                message += f"   🎁 {reward_text}\n"
                message += f"   📅 {time_str}\n\n"
            
            message += "💡 *Showing last 10 claims*"
            
            bot_instance.send_message(user_id, message, parse_mode='Markdown')
            
        except Exception as e:
            bot_instance.send_message(
                user_id,
                "❌ Failed to load claims history!\n"
                "Please try again later.",
                parse_mode='Markdown'
            )

    # ⌨️ ENTER KEY CODE HANDLER
    @bot_instance.callback_query_handler(func=lambda call: call.data == "enter_key_code")
    def enter_key_code_handler(call):
        """Handler for direct key code entry"""
        user_id = call.from_user.id
        
        # Create inline keyboard with example
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📝 Type Key Manually", callback_data="claim_temp_key"))
        markup.add(types.InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu"))
        
        bot_instance.send_message(
            user_id,
            "⌨️ *Enter Key Code*\n\n"
            "You can claim a temporary key in two ways:\n\n"
            "**Method 1:** Use command\n"
            "`/claim KEYCODE123`\n\n"
            "**Method 2:** Click button below and type key\n\n"
            "💡 Replace `KEYCODE123` with your actual key code",
            parse_mode='Markdown',
            reply_markup=markup
        )

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
    # Initialize admin meta DB and migrate legacy JSON
    try:
        init_admin_meta()
        migrate_from_json("section_status.json")
        print("✅ Admin meta DB initialized (section statuses loaded).")
    except Exception as e:
        print(f"Admin meta DB init error: {e}")
    init_db()
    load_all_products_into_cache()  # Load products into memory at startup
    
    # Initialize temp key system
    try:
        from temp_key_system import init_temp_key_db
        init_temp_key_db()
        print("✅ Temporary key system initialized.")
    except Exception as e:
        print(f"Temp key system init error: {e}")
    
    # Initialize integrated scrapper
    # Note: Telegram bridge disabled to avoid conflicts with telebot polling
    # Advanced tools commands are now handled directly by telebot handlers
    print("✅ Advanced tools integrated via telebot handlers")

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
        
        print(f"🔄 Sending startup notification for bot #{idx}...")
        try:
            bot_info = b.get_me()
            bot_username = bot_info.username
            print(f"🤖 Bot info: @{bot_username} (ID: {bot_info.id})")
            
            startup_markup = types.InlineKeyboardMarkup()
            startup_markup.add(types.InlineKeyboardButton("▶️ Start Bot", url=f"https://t.me/{bot_username}?start=admin"))
            
            startup_message = (
                "╔═══════════════════════╗\n"
                "║   🤖 𝗕𝗢𝗧 𝗦𝗧𝗔𝗥𝗧𝗘𝗗   ║\n"
                "╚═══════════════════════╝\n\n"
                f"🆔 <b>Bot:</b> @{bot_username}\n"
                f"🔢 <b>Instance:</b> #{idx}\n"
                f"💚 <b>Status:</b> <code>ONLINE</code>\n"
                f"⚡ <b>Performance:</b> High-Speed Mode\n"
                f"🛡️ <b>Security:</b> Active\n"
                f"🌐 <b>Network:</b> Connected\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ <b>All Systems Operational</b>\n"
                f"🚀 <b>Ready to Process Requests</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⏰ Started: {datetime.now().strftime('%H:%M:%S | %d/%m/%Y')}"
            )
            
            success = notify_admin(b, startup_message, markup=startup_markup)
            if not success:
                print(f"⚠️ Retrying without markup for bot #{idx}...")
                notify_admin(b, startup_message)
                
        except Exception as e:
            print(f"❌ Could not get bot info or send startup notification for bot #{idx}: {e}")
            print(f"🔄 Attempting basic notification...")
            notify_admin(b, f"╔═══════════════════════╗\n║   🤖 𝗕𝗢𝗧 𝗦𝗧𝗔𝗥𝗧𝗘𝗗   ║\n╚═══════════════════════╝\n\n✅ <b>Bot #{idx} is Online!</b>\n\n⚠️ Could not get bot details, but bot is running.\n\n⏰ {datetime.now().strftime('%H:%M:%S | %d/%m/%Y')}")

    # User cleanup is completely disabled - no periodic cleanup function
    print("🚫 User cleanup disabled - no users will be removed from database")
    
    # Start hitter admin notifications background task
    def hitter_notifications_worker():
        """Background worker to send admin notifications for successful hits"""
        while True:
            try:
                from hitter_stats import hitter_stats
                notifications = hitter_stats.get_pending_admin_notifications()
                
                for notif in notifications:
                    try:
                        # Send to admin
                        for bot_instance in bots:
                            try:
                                bot_instance.send_message(
                                    ADMIN_ID,
                                    notif['message'],
                                    parse_mode="Markdown"
                                )
                                break
                            except:
                                continue
                        
                        # Mark as sent
                        hitter_stats.mark_notification_sent(notif['id'])
                    except Exception as e:
                        print(f"Error sending hitter notification: {e}")
                
                time.sleep(10)  # Check every 10 seconds
            except Exception as e:
                print(f"Error in hitter notifications: {e}")
                time.sleep(30)
    
    hitter_notif_thread = threading.Thread(target=hitter_notifications_worker, daemon=True)
    hitter_notif_thread.start()
    print("✅ Hitter admin notifications background task started")
    
    # Start temp key cleanup background task
    def temp_key_cleanup_worker():
        """Background worker to cleanup expired temp keys"""
        while True:
            try:
                from temp_key_system import cleanup_expired_keys
                cleaned = cleanup_expired_keys()
                if cleaned > 0:
                    print(f"🧹 Cleaned up {cleaned} expired temp keys")
                time.sleep(300)  # Check every 5 minutes
            except Exception as e:
                print(f"Error in temp key cleanup: {e}")
                time.sleep(60)  # Wait 1 minute before retry
    
    cleanup_thread = threading.Thread(target=temp_key_cleanup_worker, daemon=True)
    cleanup_thread.start()
    print("✅ Temp key cleanup background task started")

    threads = []
    for idx, b in enumerate(bots, start=1):
        t = threading.Thread(target=run_bot, args=(b, f"bot #{idx}"), daemon=True)
        t.start()
        threads.append(t)

    # Block forever
    for t in threads:
        t.join()

