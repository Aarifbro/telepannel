import threading
import time
import uuid
from telebot import types
import sqlite3
import json
import random
from datetime import datetime
from config import DB_NAME, ADMIN_ID
from database import get_user_details, load_products, save_products, get_user_balance, update_user_balance
from helpers import add_gif_to_pool, get_media_pool_counts, clear_media_pool, send_random_animation
from status_handler import handle_unavailable_section
from temp_key_system import generate_temp_key, claim_temp_key, get_active_keys, cleanup_expired_keys, get_user_claims
ADMIN_IDS = [8409970602, 6127646960, 1513264586]

# backward compatibility for older code
ADMIN_ID = ADMIN_IDS[0]

def safe_edit_message(bot, chat_id, message_id, text, reply_markup=None, parse_mode=None):
    """Safely edit a message, handling the 'message not modified' error"""
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        if "message is not modified" in str(e):
            # Message content is the same, just ignore
            pass
        else:
            # Some other error, re-raise it
            raise e

# A dictionary to map internal category keys to their user-friendly, display-ready names.
# This makes it easy to change how categories are presented to the user without changing the code logic.
CATEGORY_NAMES = {
    "cc_shop": "🛍️ CC Shop",
    "custom_ccs": "🎛️ Custom CC",
    # Unified bundle category replacing legacy bins/methods variations
    "method_bins": "💎 BIN+Method Bundle",
    "gift_cards": "🎁 Gift Cards",
    "hacks": "🔧 Hacks",
    "dumps": "💾 Dumps",
    "rdp": "🖥️ RDPs",
    "dumping_toolkit": "🔨 Dumping Toolkit",
    "other": "📦 Other Items"
}

# Categories where media/link-based items are NOT allowed via admin add; only JSON text is accepted
RESTRICTED_MEDIA_CATEGORIES = {"custom_ccs", "gift_cards"}

def register_other_handlers(bot, user_states, get_products_from_cache, save_products_to_file_and_reload):
    # --- Bot Stats (Owner & Global Admins) ---
    @bot.callback_query_handler(func=lambda call: call.data == "owner_bot_stats")
    def owner_bot_stats(call):
        user_id = call.from_user.id
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            is_global_admin = c.fetchone() is not None
        if user_id != ADMIN_ID and not is_global_admin:
            bot.answer_callback_query(call.id, "❌ Only owner or global admin can access this.", show_alert=True)
            return
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users")
            total_users = c.fetchone()[0]
            c.execute("SELECT COUNT(*), COALESCE(SUM(price_usd),0) FROM orders")
            total_orders, total_revenue = c.fetchone()
            c.execute("SELECT item_name, COUNT(*) as cnt FROM orders GROUP BY item_name ORDER BY cnt DESC LIMIT 5")
            top_products = c.fetchall()
        text = (
            "📊 <b>Bot Stats</b>\n\n"
            f"👥 <b>Total Users:</b> {total_users}\n"
            f"🛒 <b>Total Orders:</b> {total_orders}\n"
            f"💰 <b>Total Revenue:</b> ${total_revenue:.2f}\n\n"
            "<b>Top Products:</b>\n" + ("No orders yet." if not top_products else "\n".join([f"{i+1}. {name} ({cnt})" for i, (name, cnt) in enumerate(top_products)]))
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_panel" if user_id == ADMIN_ID else "admin_panel"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # --- New Owner Panel Handlers ---
    @bot.callback_query_handler(func=lambda call: call.data == "owner_broadcast")
    def owner_broadcast_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Only the owner can access this.", show_alert=True)
            return
            
        broadcast_text = """📢 <b>Broadcast Message</b>

🔊 <b>Send message to all users</b>

This feature allows you to send a message to all registered users of the bot.

⚠️ <b>Important:</b>
• Messages will be sent to all active users
• Please be responsible with this feature
• Avoid spam and respect users' experience

<i>Feature coming soon! Full broadcast system will be implemented.</i>"""
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Owner Panel", callback_data="owner_panel"))
        
        bot.edit_message_text(broadcast_text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "owner_restart_bot")
    def owner_restart_bot_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Only the owner can access this.", show_alert=True)
            return
            
        restart_text = """🔄 <b>Bot Restart</b>

⚠️ <b>System Restart Control</b>

This will restart the bot system. All current operations will be interrupted.

<b>Before restarting:</b>
• Save any important ongoing processes
• Inform users about scheduled maintenance
• Ensure no critical operations are running

<i>⚠️ Use with caution - this affects all users!</i>"""
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🔄 Confirm Restart", callback_data="confirm_restart"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="owner_panel")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Owner Panel", callback_data="owner_panel"))
        
        bot.edit_message_text(restart_text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "owner_system_logs")
    def owner_system_logs_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Only the owner can access this.", show_alert=True)
            return
            
        # Try to read recent logs
        try:
            import os
            log_files = ["bot.log", "error.log", "system.log"]
            log_content = "📋 <b>System Logs</b>\n\n"
            
            found_logs = False
            for log_file in log_files:
                if os.path.exists(log_file):
                    try:
                        with open(log_file, 'r') as f:
                            lines = f.readlines()
                            recent_lines = lines[-10:] if len(lines) > 10 else lines
                            if recent_lines:
                                log_content += f"<b>{log_file}:</b>\n"
                                log_content += "".join(recent_lines)[-1000:]  # Limit length
                                log_content += "\n\n"
                                found_logs = True
                    except Exception:
                        continue
            
            if not found_logs:
                log_content += "<i>No log files found or logs are empty.</i>\n\n"
                log_content += "📊 <b>Current Session Info:</b>\n"
                log_content += f"• Bot is running normally\n"
                log_content += f"• Admin notifications working\n"
                log_content += f"• Database accessible\n"
            
        except Exception as e:
            log_content = f"📋 <b>System Logs</b>\n\n❌ Error reading logs: {str(e)}"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🔄 Refresh Logs", callback_data="owner_system_logs"),
            types.InlineKeyboardButton("🗑️ Clear Logs", callback_data="clear_system_logs")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Owner Panel", callback_data="owner_panel"))
        
        try:
            bot.edit_message_text(log_content, call.message.chat.id, call.message.message_id, 
                                 reply_markup=markup, parse_mode="HTML")  
        except Exception:
            # If message is too long, send summary
            summary = "📋 <b>System Logs</b>\n\n✅ System is running normally.\n\nUse refresh to check for updates."
            bot.edit_message_text(summary, call.message.chat.id, call.message.message_id, 
                                 reply_markup=markup, parse_mode="HTML")

    # --- Temporary Key System Handlers ---
    @bot.callback_query_handler(func=lambda call: call.data == "temp_key_manager")
    def temp_key_manager_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only access", show_alert=True)
            return
        
        # Clean up expired keys first
        cleanup_expired_keys()
        
        # Get active keys
        active_keys = get_active_keys()
        
        key_text = """🎁 <b>Temporary Key Manager</b>

🔑 <b>20-Minute Key System</b>

Generate temporary keys that expire in 20 minutes. Users can claim them for free products!

"""
        
        if active_keys:
            key_text += f"📊 <b>Active Keys ({len(active_keys)}):</b>\n\n"
            for key in active_keys[:5]:  # Show last 5 keys
                status_emoji = "✅" if key["status"] == "Active" else ("🔒" if key["status"] == "Claimed" else "❌")
                key_text += f"{status_emoji} <code>{key['key_code']}</code>\n"
                key_text += f"   📦 {key['product_type']} • {key['status']}\n\n"
            
            if len(active_keys) > 5:
                key_text += f"<i>... and {len(active_keys) - 5} more keys</i>\n\n"
        else:
            key_text += "📭 <i>No active keys found</i>\n\n"
        
        key_text += "<i>🚀 Generate new keys to reward your users!</i>"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🔑 Generate New Key", callback_data="generate_temp_key"),
            types.InlineKeyboardButton("📊 View All Keys", callback_data="view_all_temp_keys")
        )
        markup.add(
            types.InlineKeyboardButton("🧹 Cleanup Expired", callback_data="cleanup_temp_keys"),
            types.InlineKeyboardButton("📈 Key Statistics", callback_data="temp_key_stats")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Owner Panel", callback_data="owner_panel"))
        
        bot.edit_message_text(key_text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "generate_temp_key")
    def generate_temp_key_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only access", show_alert=True)
            return
        
        generate_text = """🔑 <b>Generate Temporary Key</b>

⏱️ <b>Key Duration: 20 Minutes</b>

Select the type of product to give away:

🛍️ <b>CC Shop Items</b> - Credit cards
💎 <b>BIN+Method</b> - BIN and method bundle  
🎁 <b>Gift Cards</b> - Digital gift cards
🔧 <b>Hacks</b> - Hacking tools
💾 <b>Dumps</b> - Card dumps
🖥️ <b>RDP</b> - Remote desktop access
💰 <b>Credits</b> - Free balance credits

<i>Choose wisely - users will get this for free! 🎁</i>"""
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🛍️ CC Shop", callback_data="gen_key_cc_shop"),
            types.InlineKeyboardButton("💎 BIN+Method", callback_data="gen_key_method_bins")
        )
        markup.add(
            types.InlineKeyboardButton("🎁 Gift Cards", callback_data="gen_key_gift_cards"),
            types.InlineKeyboardButton("🔧 Hacks", callback_data="gen_key_hacks")
        )
        markup.add(
            types.InlineKeyboardButton("💾 Dumps", callback_data="gen_key_dumps"),
            types.InlineKeyboardButton("🖥️ RDP", callback_data="gen_key_rdp")
        )
        markup.add(
            types.InlineKeyboardButton("💰 Free Credits", callback_data="gen_key_credits"),
            types.InlineKeyboardButton("🎲 Random Item", callback_data="gen_key_random")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Key Manager", callback_data="temp_key_manager"))
        
        bot.edit_message_text(generate_text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")

    # Temp key handlers moved to temp_key_handlers.py
        
        key_type = call.data.replace("gen_key_", "")
        
        # Temp key generation moved to temp_key_handlers.py
        pass

    # --- One-time legacy merge: bins/methods/bin_methods/bins_methods -> method_bins ---
    try:
        data = load_products()
        changed = False
        bundle_list = data.get("method_bins", [])
        legacy_keys = ["bins", "methods", "bin_methods", "bins_methods"]
        for lk in legacy_keys:
            if lk in data and lk != "method_bins" and data[lk]:
                existing_ids = {item.get('id') for item in bundle_list if isinstance(item, dict)}
                next_id = (max(existing_ids) + 1) if existing_ids else 1
                for item in data[lk]:
                    if isinstance(item, dict):
                        it = dict(item)
                        it['id'] = next_id; next_id += 1
                        bundle_list.append(it)
                del data[lk]
                changed = True
        if changed:
            data['method_bins'] = bundle_list
            save_products(data)
            save_products_to_file_and_reload(data)
            print("[migration] Merged legacy bins/methods categories into method_bins")
    except Exception as e:
        print(f"Legacy merge failed: {e}")
    # --- Generic Buy Handler for Dynamic Menus ---
    @bot.callback_query_handler(func=lambda call: call.data.startswith("buy_idx_"))
    def buy_item_callback(call):
        """
        Handles the 'Buy' button press for any item from a dynamically generated menu.
        It parses the category and item index from the callback data, retrieves the
        item from the cache, and then shows the payment options to the user.
        """
        try:
            # Support categories with underscores, e.g., method_bins
            payload = call.data.replace("buy_idx_", "", 1)
            category_key, index_str = payload.rsplit('_', 1)
            item_index = int(index_str)

            products = get_products_from_cache(category_key)
            
            if item_index >= len(products):
                bot.answer_callback_query(call.id, "This item is no longer available. Please try again.", show_alert=True)
                return

            item = products[item_index]
            price = item.get("price", 0)
            name = item.get("name", "Unnamed Item")

            # Map back callback safely (fix for bins+methods combined flow)
            back_map = {
                "methods": "method_menu",
                "rdp": "rdp_menu",
                "other": "other_menu",
                "method_bins": "method_bins_menu",
                "bins": "bins_methods_menu",
                "custom_ccs": "custom_cc_menu",
                "gift_cards": "giftcards_menu",
                "dumps": "dumps_menu",
                "hacks": "hacks_menu",
                "dumping_toolkit": "dumping_toolkit_menu",
                "courses": "courses_menu",
            }
            back_menu_callback = back_map.get(category_key, "main_menu")
            
            # Hand off to the payment handler
            from payment_handler import show_payment_options
            show_payment_options(bot, call, name, price, item, back_menu_callback)

        except (IndexError, ValueError) as e:
            print(f"Error handling generic buy callback: {e}. Data: {call.data}")
            bot.answer_callback_query(call.id, "An error occurred. Please go back and try again.", show_alert=True)

    # --- Owner Panel ---
    @bot.callback_query_handler(func=lambda call: call.data == "owner_panel")
    def owner_panel_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Only the owner can access this panel.", show_alert=True)
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        # Row 1: Core Management
        markup.add(
            types.InlineKeyboardButton("👥 Admin Management", callback_data="owner_admin_management"),
            types.InlineKeyboardButton("⚙️ Admin Control Panel", callback_data="admin_panel")
        )
        
        # Row 2: Statistics & Monitoring
        markup.add(
            types.InlineKeyboardButton("📊 Bot Statistics", callback_data="owner_bot_stats"),
            types.InlineKeyboardButton("📋 System Logs", callback_data="owner_system_logs")
        )
        
        # Row 3: Communication Tools
        markup.add(
            types.InlineKeyboardButton("💬 User Chat", callback_data="owner_user_chat"),
            types.InlineKeyboardButton("📢 Broadcast", callback_data="owner_broadcast")
        )
        
        # Row 4: System Management
        markup.add(
            types.InlineKeyboardButton("🎁 Key Manager", callback_data="temp_key_manager"),
            types.InlineKeyboardButton("🔄 Restart Bot", callback_data="owner_restart_bot")
        )
        
        # Row 5: Back Button
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        
        owner_text = """👑 <b>Owner Control Panel</b>

🔐 <b>Welcome, Bot Owner!</b>

<b>Management:</b>
• 👥 Admin Management - Add/Remove/View admins
• ⚙️ Admin Control Panel - Full admin control access
• 📊 Bot Statistics - User & system stats
• 📋 System Logs - Monitor bot activity

<b>Communication:</b>
• 💬 User Chat - Direct messaging
• 📢 Broadcast - Send to all users

<b>System:</b>
• 🎁 Key Manager - Generate/manage keys
• 🔄 Restart Bot - Reboot the system

<i>⚠️ Handle with care - affects all users</i>"""
        
        try:
            bot.edit_message_text(owner_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            bot.send_message(call.message.chat.id, owner_text, reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda c: c.data == "open_accounts")
    def open_accounts_menu(call):
        kb = types.InlineKeyboardMarkup(row_width=1)

        kb.add(
            types.InlineKeyboardButton(
                "🍥 Crunchyroll",
                callback_data="accounts_crunchyroll"
            ),
            types.InlineKeyboardButton(
                "⬅️ Back",
                callback_data="back_to_main"
            )
        )

        bot.edit_message_text(
            "<b>📦 ACCOUNTS</b>\n\nSelect an account giveaway:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=kb
        )
    @bot.callback_query_handler(func=lambda call: call.data == "owner_admin_management")
    def owner_admin_management_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Only the owner can access this panel.", show_alert=True)
            return
            
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        # Global Admin Management  
        markup.add(types.InlineKeyboardButton("═══ 🌟 GLOBAL ADMINS ═══", callback_data="noop"))
        markup.add(
            types.InlineKeyboardButton("➕ Add Admin", callback_data="owner_add_admin"),
            types.InlineKeyboardButton("➖ Remove Admin", callback_data="owner_remove_admin")
        )
        markup.add(types.InlineKeyboardButton("📋 View All Admins", callback_data="owner_list_admins"))
        
        # Section Admin Management
        markup.add(types.InlineKeyboardButton("═══ ⚡ SECTION ADMINS ═══", callback_data="noop"))
        markup.add(
            types.InlineKeyboardButton("➕ Add Section Admin", callback_data="owner_add_section_admin"),
            types.InlineKeyboardButton("➖ Remove Section Admin", callback_data="owner_remove_section_admin")
        )
        markup.add(types.InlineKeyboardButton("📋 View Section Admins", callback_data="owner_list_section_admins"))
        
        # Info & Stats
        markup.add(
            types.InlineKeyboardButton("ℹ️ Permissions Info", callback_data="admin_permissions"),
            types.InlineKeyboardButton("📊 Admin Stats", callback_data="admin_activity")
        )
        
        # Back button
        markup.add(types.InlineKeyboardButton("⬅️ Back to Owner Panel", callback_data="owner_panel"))
        
        # Get current admin counts
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM admins")
                global_count = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM section_admins")
                section_count = c.fetchone()[0]
        except:
            global_count = 0
            section_count = 0
        
        admin_text = f"""👥 <b>Admin Management Hub</b>

📊 <b>Current Status:</b>
• 🌟 Global Admins: {global_count}
• ⚡ Section Admins: {section_count}
• 👑 Owner: You

━━━━━━━━━━━━━━━━━━

🌟 <b>Global Admins:</b>
• Full bot control & management
• User & product management
• All features unlocked
• Complete system access

⚡ <b>Section Admins:</b>
• Specific section control
• Limited to assigned areas
• Product management only
• Perfect for team work

<i>Choose an action to manage administrators</i>"""
        
        try:
            bot.edit_message_text(admin_text, call.message.chat.id, call.message.message_id, 
                                 reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            bot.send_message(call.message.chat.id, admin_text, reply_markup=markup, parse_mode="HTML")

    # Handle noop callback for separator buttons
    @bot.callback_query_handler(func=lambda call: call.data == "noop")
    def noop_callback(call):
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data == "admin_permissions")
    def admin_permissions_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only access", show_alert=True)
            return
            
        permissions_text = """🔧 <b>Admin Permissions Guide</b>

🌟 <b>Global Admin Powers:</b>
✅ Full user management
✅ Product management (all categories)
✅ Section control
✅ Payment processing
✅ Broadcast messages
✅ Statistics & analytics
✅ Support system access

⚡ <b>Section Admin Powers:</b>
✅ Assigned section only
✅ Limited product management
✅ Section statistics
✅ User support for section
❌ No global control
❌ No user ban/credits

<i>Permissions are automatically assigned</i>"""
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_admin_management"))
        
        bot.edit_message_text(permissions_text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_activity")
    def admin_activity_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only access", show_alert=True)
            return
            
        # Get admin activity stats
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM admins")
                global_admins = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM section_admins")
                section_admins = c.fetchone()[0]
        except:
            global_admins = 0
            section_admins = 0
            
        activity_text = f"""📊 <b>Admin Statistics</b>

👥 <b>Current Team:</b>
• 🌟 Global Admins: {global_admins}
• ⚡ Section Admins: {section_admins}
• 👑 Owner: 1 (You)
• 📊 Total: {global_admins + section_admins + 1}

✅ <b>System Status:</b>
• User support: Active
• Monitoring: Running
• Security: Protected

<i>Your team is keeping the bot running!</i>"""
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="admin_activity"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_admin_management"))
        
        bot.edit_message_text(activity_text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")

    # --- Section Status Manager (Owner & Global Admins) ---
    @bot.callback_query_handler(func=lambda call: call.data == "section_status_manager")
    def section_status_manager(call):
        # Only owner or global admin
        user_id = call.from_user.id
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            is_global_admin = c.fetchone() is not None
        if user_id != ADMIN_ID and not is_global_admin:
            bot.answer_callback_query(call.id, "❌ Only owner or global admin can access this.", show_alert=True)
            return
        # Load section statuses
        try:
            with open("section_status.json", "r") as f:
                statuses = json.load(f)
        except Exception:
            statuses = {}
        # Define all sections to manage
        sections = [
            ("cc_shop", "🛍️ CC Shop"),
            ("bins_methods", "💎 BIN+Method Bundle"),
            ("gift_cards", "🎁 Gift Cards"),
            ("hacks", "🔧 Hacks"),
            ("dumps", "💾 Dumps"),
            ("rdp", "🖥️ RDPs"),
            ("support", "🆘 Support"),
            ("ai_search", "🤖 AI Search"),
        ]
        status_icons = {
            "available": "🟢 Available",
            "maintenance": "🛠️ Maintenance",
            "coming_soon": "🟡 Coming Soon",
            "disabled": "🔴 Disabled"
        }
        text = "<b>Section Status Manager</b>\n\nToggle the status of each section.\n\n"
        markup = types.InlineKeyboardMarkup(row_width=1)
        for key, label in sections:
            status = statuses.get(key, "available")
            icon = status_icons.get(status, status)
            markup.add(types.InlineKeyboardButton(f"{label}: {icon}", callback_data=f"toggle_section_status_{key}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_panel" if user_id == ADMIN_ID else "admin_panel"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("toggle_section_status_"))
    def toggle_section_status(call):
        user_id = call.from_user.id
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            is_global_admin = c.fetchone() is not None
        if user_id != ADMIN_ID and not is_global_admin:
            bot.answer_callback_query(call.id, "❌ Only owner or global admin can access this.", show_alert=True)
            return
        section_key = call.data.replace("toggle_section_status_", "")
        # Load and update status
        try:
            with open("section_status.json", "r") as f:
                statuses = json.load(f)
        except Exception:
            statuses = {}
        current = statuses.get(section_key, "available")
        order = ["available", "maintenance", "coming_soon", "disabled"]
        next_status = order[(order.index(current) + 1) % len(order)]
        statuses[section_key] = next_status
        with open("section_status.json", "w") as f:
            json.dump(statuses, f, indent=2)
        bot.answer_callback_query(call.id, f"{section_key} → {next_status}")
        # Refresh manager
        section_status_manager(call)
        
        # (Removed misplaced markup/edit_message_text block)

    # Section Admin Management - Optimized with proper section selection
    @bot.callback_query_handler(func=lambda call: call.data == "owner_add_section_admin")
    def owner_add_section_admin_prompt(call):
        # Check if user is owner or global admin
        user_id = call.from_user.id
        is_owner = user_id == ADMIN_ID
        is_global_admin = False
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            is_global_admin = cursor.fetchone() is not None
        
        if not (is_owner or is_global_admin):
            bot.answer_callback_query(call.id, "❌ Only owner and global admins can manage section admins", show_alert=True)
            return
        
        user_states[call.from_user.id] = "awaiting_new_section_admin_id"
        markup = types.InlineKeyboardMarkup()
        back_btn = "owner_panel" if is_owner else "admin_panel"
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=back_btn))
        bot.edit_message_text(
            "📝 <b>Add Section Admin</b>\n\n"
            "Send the <b>User ID</b> of the person you want to make a section admin.\n\n"
            "Example: <code>123456789</code>\n\n"
            "⚠️ After sending the User ID, you'll choose the section from a list.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_new_section_admin_id")
    def owner_add_section_admin_get_userid(message):
        try:
            user_id = int(message.text.strip())
            # Store user_id temporarily and ask for section selection
            user_states[message.from_user.id] = f"awaiting_section_for_admin_{user_id}"
            
            # Import SECTION_KEYS from main
            from main import SECTION_KEYS
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("═══ SELECT SECTION ═══", callback_data="noop"))
            
            for section_key, section_label in SECTION_KEYS:
                markup.add(types.InlineKeyboardButton(
                    f"📁 {section_label}",
                    callback_data=f"assign_section_{user_id}_{section_key}"
                ))
            
            markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="owner_panel"))
            
            bot.send_message(
                message.chat.id,
                f"✅ <b>User ID:</b> <code>{user_id}</code>\n\n"
                f"📋 <b>Select a section to assign admin rights:</b>",
                reply_markup=markup,
                parse_mode="HTML"
            )
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid User ID. Please send a valid number.")
            return

    @bot.callback_query_handler(func=lambda call: call.data.startswith("assign_section_"))
    def assign_section_to_admin(call):
        try:
            parts = call.data.replace("assign_section_", "").split("_", 1)
            new_admin_id = int(parts[0])
            section = parts[1]
            
            # Import SECTION_KEYS to validate
            from main import SECTION_KEYS
            valid_sections = [s[0] for s in SECTION_KEYS]
            
            if section not in valid_sections:
                bot.answer_callback_query(call.id, "❌ Invalid section!", show_alert=True)
                return
            
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM section_admins WHERE user_id = ? AND section = ?", (new_admin_id, section))
                if cursor.fetchone():
                    bot.answer_callback_query(call.id, f"⚠️ User is already admin for {section}!", show_alert=True)
                    return
                
                cursor.execute("INSERT INTO section_admins (user_id, section, added_by) VALUES (?, ?, ?)", 
                              (new_admin_id, section, call.from_user.id))
                conn.commit()
            
            # Get section label
            section_label = next((label for key, label in SECTION_KEYS if key == section), section)
            
            bot.edit_message_text(
                f"✅ <b>Section Admin Added!</b>\n\n"
                f"👤 <b>User ID:</b> <code>{new_admin_id}</code>\n"
                f"📁 <b>Section:</b> {section_label}\n"
                f"🔐 <b>Access:</b> Can manage {section_label} orders and products\n\n"
                f"✨ Changes are effective immediately!",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML"
            )
            
            # Clear state
            if call.from_user.id in user_states:
                del user_states[call.from_user.id]
            
        except Exception as e:
            print(f"Error assigning section admin: {e}")
            bot.answer_callback_query(call.id, "❌ Error assigning admin!", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data == "owner_remove_section_admin")
    def owner_remove_section_admin_prompt(call):
        # Check if user is owner or global admin
        user_id = call.from_user.id
        is_owner = user_id == ADMIN_ID
        is_global_admin = False
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            is_global_admin = cursor.fetchone() is not None
        
        if not (is_owner or is_global_admin):
            bot.answer_callback_query(call.id, "❌ Only owner and global admins can manage section admins", show_alert=True)
            return
        
        # Get all section admins
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, section FROM section_admins ORDER BY section, user_id")
            section_admins = cursor.fetchall()
        
        if not section_admins:
            bot.answer_callback_query(call.id, "ℹ️ No section admins found!", show_alert=True)
            return
        
        # Import SECTION_KEYS for proper labels
        from main import SECTION_KEYS
        section_labels = {key: label for key, label in SECTION_KEYS}
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("═══ SELECT ADMIN TO REMOVE ═══", callback_data="noop"))
        
        for admin_user_id, section in section_admins:
            section_label = section_labels.get(section, section.title())
            markup.add(types.InlineKeyboardButton(
                f"❌ {section_label} - User {admin_user_id}",
                callback_data=f"remove_section_admin_{admin_user_id}_{section}"
            ))
        
        back_btn = "owner_panel" if is_owner else "admin_panel"
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=back_btn))
        
        bot.edit_message_text(
            "📋 <b>Section Admins List</b>\n\n"
            "Select an admin to remove:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("remove_section_admin_"))
    def remove_section_admin_confirm(call):
        try:
            parts = call.data.replace("remove_section_admin_", "").split("_", 1)
            admin_user_id = int(parts[0])
            section = parts[1]
            
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM section_admins WHERE user_id = ? AND section = ?", (admin_user_id, section))
                conn.commit()
            
            # Get section label
            from main import SECTION_KEYS
            section_label = next((label for key, label in SECTION_KEYS if key == section), section.title())
            
            bot.edit_message_text(
                f"✅ <b>Section Admin Removed!</b>\n\n"
                f"👤 <b>User ID:</b> <code>{admin_user_id}</code>\n"
                f"📁 <b>Section:</b> {section_label}\n\n"
                f"🔓 This user no longer has admin access to {section_label}.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML"
            )
            
        except Exception as e:
            print(f"Error removing section admin: {e}")
            bot.answer_callback_query(call.id, "❌ Error removing admin!", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data == "owner_list_section_admins")
    def owner_list_section_admins(call):
        # Check if user is owner or global admin
        user_id = call.from_user.id
        is_owner = user_id == ADMIN_ID
        is_global_admin = False
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            is_global_admin = cursor.fetchone() is not None
        
        if not (is_owner or is_global_admin):
            bot.answer_callback_query(call.id, "❌ Only owner and global admins can view section admins", show_alert=True)
            return
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, section, added_at FROM section_admins ORDER BY section, user_id")
            admins = cursor.fetchall()
        
        if not admins:
            bot.answer_callback_query(call.id, "ℹ️ No section admins assigned yet.", show_alert=True)
            return
        
        # Import SECTION_KEYS for proper section labels
        from main import SECTION_KEYS
        section_labels = {key: label for key, label in SECTION_KEYS}
        
        # Group by section
        sections_dict = {}
        for user_id, section, added_at in admins:
            if section not in sections_dict:
                sections_dict[section] = []
            sections_dict[section].append((user_id, added_at))
        
        text = "📋 <b>Section Admins List</b>\n\n"
        
        for section_key in sorted(sections_dict.keys()):
            section_label = section_labels.get(section_key, section_key.title())
            text += f"📁 <b>{section_label}</b>\n"
            for user_id, added_at in sections_dict[section_key]:
                text += f"  • User ID: <code>{user_id}</code>\n"
            text += "\n"
        
        text += f"━━━━━━━━━━━━━━━━━━━━\n"
        text += f"<b>Total:</b> {len(admins)} section admin(s)\n"
        text += f"<b>Sections:</b> {len(sections_dict)} section(s)"
        
        markup = types.InlineKeyboardMarkup()
        back_btn = "owner_panel" if is_owner else "admin_panel"
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=back_btn))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "owner_remove_admin")
    def owner_remove_admin_prompt(call):
        user_states[call.from_user.id] = "awaiting_remove_admin_id"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_panel"))
        bot.edit_message_text("Send the <b>User ID</b> of the user you want to remove from admins.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_remove_admin_id")
    def owner_remove_admin(message):
        try:
            user_id = int(message.text.strip())
            if user_id == ADMIN_ID:
                bot.send_message(message.chat.id, "❌ You cannot remove the owner.")
                return
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid format. Please send a numeric User ID.")
            return
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            # Check if the user is actually an admin
            cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            if cursor.fetchone():
                cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
                conn.commit()
                bot.send_message(message.chat.id, f"✅ User <code>{user_id}</code> removed from global admins.", parse_mode="HTML")
            else:
                bot.send_message(message.chat.id, f"User <code>{user_id}</code> is not a global admin.", parse_mode="HTML")
        
        del user_states[message.from_user.id]

    @bot.callback_query_handler(func=lambda call: call.data == "owner_add_admin")
    def owner_add_admin_prompt(call):
        user_states[call.from_user.id] = "awaiting_new_admin_id"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_panel"))
        bot.edit_message_text("Send the <b>User ID</b> of the user you want to add as admin.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_new_admin_id")
    def owner_add_admin(message):
        try:
            if message.from_user.id != ADMIN_ID:
                return
            uid = int(message.text.strip())
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (uid,))
                if cursor.fetchone():
                    bot.send_message(message.chat.id, f"User <code>{uid}</code> is already a global admin.", parse_mode="HTML")
                else:
                    cursor.execute("INSERT INTO admins (user_id, added_by) VALUES (?, ?)", (uid, message.from_user.id))
                    conn.commit()
                    bot.send_message(message.chat.id, f"✅ User <code>{uid}</code> added as a global admin.", parse_mode="HTML")

                    # Welcome DM to the new admin
                    try:
                        bot.send_message(uid, "👋 You have been added as a <b>Global Admin</b>. Open the bot and tap '🛠️ Admin Panel' to get started.", parse_mode="HTML")
                    except Exception:
                        pass

                    # Announce to all users in background
                    def _announce_new_admin(new_admin_id: int):
                        try:
                            with sqlite3.connect(DB_NAME) as conn2:
                                c2 = conn2.cursor()
                                c2.execute("SELECT user_id FROM users WHERE COALESCE(is_active,1)=1")
                                all_users = [r[0] for r in c2.fetchall()]
                                c2.execute("SELECT user_id FROM admins")
                                admin_ids = [str(r[0]) for r in c2.fetchall()]
                        except Exception as e:
                            print(f"Announce admin DB error: {e}")
                            return

                        admin_list = "\n".join([f"• <code>{aid}</code>" for aid in admin_ids])
                        text = (
                            "🎉 <b>New Support Admin Joined</b>\n\n"
                            f"A new support admin has joined the team.\n"
                            f"<b>Admin ID:</b> <code>{new_admin_id}</code>\n\n"
                            "You can contact our admins using these IDs:\n" + admin_list
                        )
                        for uid2 in all_users:
                            try:
                                send_random_animation(bot, uid2, kind="welcome", caption=text, parse_mode="HTML")
                            except Exception as e:
                                # Fall back to plain message
                                try:
                                    bot.send_message(uid2, text, parse_mode="HTML")
                                except Exception:
                                    pass
                            time.sleep(0.05)

                    threading.Thread(target=_announce_new_admin, args=(uid,), daemon=True).start()
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Failed to add admin: {e}")
        finally:
            try:
                del user_states[message.from_user.id]
            except Exception:
                pass

    @bot.callback_query_handler(func=lambda call: call.data == "owner_list_admins")
    def owner_list_admins(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Only the owner can access this panel.", show_alert=True)
            return
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, added_at FROM admins ORDER BY added_at DESC")
            rows = cursor.fetchall()
        text = "<b>Global Admins:</b>\n"
        if not rows:
            text += "No global admins found."
        else:
            for r in rows:
                text += f"<code>{r[0]}</code> | added: <code>{(r[1] or '')[:19]}</code>\n"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Owner Panel", callback_data="owner_panel"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
    """
    Registers all callback handlers for the non-CC/BIN sections of the bot.
    
    This function acts as the central registration point for a variety of features, including:
    - Static informational pages like "Support" and "Rules".
    - Dynamic product menus for categories like "Gift Cards", "RDPs", etc., which are populated from products.json.
    - The entire Admin Panel, which provides the bot owner with tools to manage products, view orders, and see user statistics directly from the Telegram chat.
    """

    def create_dynamic_product_menu(call, category_key):
        """
        A general, reusable function to create a menu for any product category.
        
        This function dynamically reads the `products.json` file, finds the requested category,
        and generates a button for each item. It uses an index-based callback (`buy_idx_{category_key}_{index}`)
        to prevent the "BUTTON_DATA_INVALID" error from Telegram by keeping the callback data small and efficient.
        """
        bot.send_chat_action(call.message.chat.id, 'typing')
        # Load the entire product database.
        products = get_products_from_cache(category_key)
        title = CATEGORY_NAMES.get(category_key, "Products")
        
        # If the category is empty, inform the user gracefully instead of showing a blank menu.
        if not products:
            bot.answer_callback_query(call.id, f"There are no products in the {title} category at the moment.", show_alert=True)
            return

        # Create the inline keyboard markup.
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        # Build descriptive text for custom_ccs category
        if category_key == "custom_ccs":
            # Extract page number from callback data if paginated
            page = 0
            if hasattr(call, 'data') and 'page_' in call.data:
                try:
                    page = int(call.data.split('page_')[1].split('_')[0])
                except:
                    page = 0
            
            # Pagination settings
            items_per_page = 8
            total_items = len(products)
            total_pages = (total_items + items_per_page - 1) // items_per_page
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, total_items)
            
            text_lines = [f"🎛️ <b>{title}</b>\n"]
            text_lines.append(f"Page {page + 1}/{total_pages}\n")
            
            # Show cards in text format with numbers
            for i, index in enumerate(range(start_idx, end_idx), 1):
                item = products[index]
                item_name = item.get("name")
                price = item.get("price")
                country_flag = item.get("country_flag", "")
                card_type = item.get("card_type", "")
                level = item.get("level", "")
                
                # Shorten card type
                short_type = ""
                if card_type:
                    if "VISA" in card_type.upper():
                        short_type = "VISA"
                    elif "MASTER" in card_type.upper():
                        short_type = "MC"
                    elif "AMEX" in card_type.upper():
                        short_type = "AMEX"
                    else:
                        short_type = card_type
                
                # Build card info line
                card_info = f"{country_flag} {item_name}"
                if short_type:
                    card_info += f" • {short_type}"
                if level:
                    card_info += f" • {level}"
                
                text_lines.append(f"{i}. {card_info} - <b>${price}</b>")
            
            text = "\n".join(text_lines)
            
            # Create numbered buttons (2 columns)
            markup = types.InlineKeyboardMarkup(row_width=4)
            buttons = []
            for i in range(start_idx, end_idx):
                btn_num = i - start_idx + 1
                buttons.append(types.InlineKeyboardButton(
                    str(btn_num), 
                    callback_data=f"buy_idx_{category_key}_{i}"
                ))
            markup.add(*buttons)
            
            # Navigation buttons
            nav_buttons = []
            if page > 0:
                nav_buttons.append(types.InlineKeyboardButton(
                    "⬅️ Prev", 
                    callback_data=f"custom_cc_menu_page_{page-1}"
                ))
            if page < total_pages - 1:
                nav_buttons.append(types.InlineKeyboardButton(
                    "Next ➡️", 
                    callback_data=f"custom_cc_menu_page_{page+1}"
                ))
            if nav_buttons:
                markup.row(*nav_buttons)
            
            markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="cc_menu"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
        else:
            # Standard display for other categories
            for index, item in enumerate(products):
                item_name = item.get("name")
                price = item.get("price")
                callback_data = f"buy_idx_{category_key}_{index}"
                markup.add(types.InlineKeyboardButton(f"🛒 {item_name} - ${price}", callback_data=callback_data))
            
            markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
            text = f"🎁 **{title}**\n\nPlease select a product to purchase from the list below."
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    def get_category_markup(category):
        """Generates the markup for a specific category management menu."""
        products = load_products()
        items = products.get(category, [])
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        # Use the new wizard for adding items
        markup.add(types.InlineKeyboardButton(f"➕ Add Item", callback_data=f"start_wizard_{category}"))

        # List items for deletion
        if items:
            # Add a button to clear all items in the category
            markup.add(types.InlineKeyboardButton(f"🗑️ Clear All Items in {CATEGORY_NAMES.get(category, category)}", callback_data=f"clear_cat_{category}"))

            for item in items[:20]:  # Show max 20 items for deletion
                item_id = item.get('id', 'N/A')

                # Create a representative name for the item
                if category in ['custom_ccs']:
                    item_name = f"CC #{item_id} ({item.get('bin', '...')}...)"
                elif category == 'gift_cards':
                    item_name = item.get('name', f'Card #{item_id}')
                elif category in ('bin_methods', 'method_bins'):
                    item_name = item.get('name') or f"Bundle #{item_id}"
                else:
                    item_name = item.get('name', f'Item #{item_id}')

                raw_price = item.get('price', 'N/A')
                if isinstance(raw_price, (int, float)):
                    price_str = f"{int(raw_price)}" if raw_price == int(raw_price) else f"{raw_price:.2f}"
                else:
                    price_str = str(raw_price)
                display_text = f"❌ {item_name} - ${price_str}"

                markup.add(types.InlineKeyboardButton(display_text, callback_data=f"delete_item_{category}_{item_id}"))

        # Navigation
        if category in ["custom_ccs"]:
            markup.add(types.InlineKeyboardButton("⬅️ Back to CC Shop", callback_data="custom_cc_menu"))
        else:
            markup.add(types.InlineKeyboardButton("⬅️ Back to Products", callback_data="admin_products_menu"))
            
        return markup

    # =============================
    # ===== Product Add Wizard ====
    # =============================
    @bot.callback_query_handler(func=lambda call: call.data.startswith("start_wizard_"))
    def start_wizard(call):
        category = call.data.replace("start_wizard_", "")
        # Basic permission: only owner or global admin (section admins cannot add products globally here)
        user_id = call.from_user.id
        # allow owner
        if user_id == ADMIN_ID:
            allowed = True
        else:
            allowed = False
            # global admin check
            try:
                with sqlite3.connect(DB_NAME) as conn:
                    c = conn.cursor(); c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
                    if c.fetchone():
                        allowed = True
                    else:
                        # allow section admins for this specific category
                        c.execute("SELECT 1 FROM section_admins WHERE user_id = ? AND section = ?", (user_id, category))
                        if c.fetchone():
                            allowed = True
            except Exception:
                allowed = False
        if not allowed:
            bot.answer_callback_query(call.id, "❌ Not authorized", show_alert=True)
            return
        user_states[call.from_user.id] = f"wizard_name_{category}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cat_menu_{category}"))
        bot.edit_message_text(
            f"🧪 <b>Add New Item</b>\n\nCategory: <code>{CATEGORY_NAMES.get(category, category)}</code>\n\nSend the <b>name/title</b> of the new item.",
            call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML"
        )

    @bot.message_handler(func=lambda m: isinstance(user_states.get(m.from_user.id, ''), str) and user_states.get(m.from_user.id, '').startswith("wizard_name_"))
    def wizard_get_name(message):
        state = user_states.get(message.from_user.id)
        category = state.replace("wizard_name_", "")
        name = message.text.strip()
        user_states[message.from_user.id] = f"wizard_price_{category}::{name}"
        bot.send_message(message.chat.id, f"💲 Great. Now send the <b>price</b> in USD for <code>{name}</code> (numbers only).", parse_mode="HTML")

    @bot.message_handler(func=lambda m: isinstance(user_states.get(m.from_user.id, ''), str) and user_states.get(m.from_user.id, '').startswith("wizard_price_"))
    def wizard_get_price(message):
        state = user_states.get(message.from_user.id)
        try:
            header, rest = state.split("_", 1)  # wizard + remaining
            # state format: wizard_price_{category}::{name}
            meta = rest.replace("price_", "")
            category, name = meta.split("::", 1)
        except Exception:
            bot.send_message(message.chat.id, "State error. Restart wizard.")
            user_states.pop(message.from_user.id, None)
            return
        try:
            price = float(message.text.strip())
            if price < 0:
                raise ValueError
        except Exception:
            bot.reply_to(message, "❌ Invalid price. Send a positive number (e.g., 25 or 19.99).")
            return
        user_states[message.from_user.id] = f"wizard_desc_{category}::{name}::{price}"
        bot.send_message(message.chat.id, "📝 Optional: Send a description (or type '-' to skip).")

    @bot.message_handler(func=lambda m: isinstance(user_states.get(m.from_user.id, ''), str) and user_states.get(m.from_user.id, '').startswith("wizard_desc_"))
    def wizard_get_desc(message):
        state = user_states.get(message.from_user.id)
        try:
            _, rest = state.split("_", 1)
            meta = rest.replace("desc_", "")
            category, name, price = meta.split("::", 2)
            price = float(price)
        except Exception:
            bot.send_message(message.chat.id, "State error. Aborting.")
            user_states.pop(message.from_user.id, None)
            return
        desc = None if message.text.strip() == '-' else message.text.strip()
        # Persist item
        try:
            data = load_products()
            items = data.get(category, [])
            # Generate next id
            next_id = (max([it.get('id', 0) for it in items]) + 1) if items else 1
            new_item = {"id": next_id, "name": name, "price": price}
            if desc:
                new_item["description"] = desc
            items.append(new_item)
            data[category] = items
            save_products(data)
            save_products_to_file_and_reload(data)
            if category == 'method_bins':
                user_states[message.from_user.id] = f"wizard_file_method_bins::{category}::{next_id}"
                bot.send_message(message.chat.id, f"✅ Added <b>{name}</b> (ID {next_id}).\n\n📎 Now send a document to attach (delivered to buyers) or type <code>skip</code> to finish.", parse_mode="HTML")
            elif category == 'dumps':
                # Allow attaching a document for dumps similarly to method_bins
                user_states[message.from_user.id] = f"wizard_file_dumps::{category}::{next_id}"
                bot.send_message(message.chat.id, f"✅ Added <b>{name}</b> (ID {next_id}).\n\n📎 Now send a document to attach (will be stored as the dump delivery) or type <code>skip</code> to finish.", parse_mode="HTML")
            elif category == 'dumping_toolkit':
                # Allow attaching a document for dumping_toolkit similarly to dumps
                user_states[message.from_user.id] = f"wizard_file_dumping_toolkit::{category}::{next_id}"
                bot.send_message(message.chat.id, f"✅ Added <b>{name}</b> (ID {next_id}).\n\n📎 Now send a document, photo, or video to attach (will be delivered to buyers) or type <code>skip</code> to finish.", parse_mode="HTML")
            elif category == 'courses':
                # Allow attaching files for courses
                user_states[message.from_user.id] = f"wizard_file_courses::{category}::{next_id}"
                bot.send_message(message.chat.id, f"✅ Added <b>{name}</b> (ID {next_id}).\n\n📎 Now send a document, video, or photo to attach (course materials) or type <code>skip</code> to finish.", parse_mode="HTML")
            else:
                bot.send_message(message.chat.id, f"✅ Added <b>{name}</b> (ID {next_id}) to <code>{CATEGORY_NAMES.get(category, category)}</code>.", parse_mode="HTML")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Failed to save item: {e}")
        finally:
            # Keep awaiting file-attached states for both method_bins and dumps
            cur_state = user_states.get(message.from_user.id, '')
            if not (isinstance(cur_state, str) and (cur_state.startswith('wizard_file_method_bins::') or cur_state.startswith('wizard_file_dumps::') or cur_state.startswith('wizard_file_dumping_toolkit::') or cur_state.startswith('wizard_file_courses::'))):
                user_states.pop(message.from_user.id, None)
                try:
                    markup = get_category_markup(category)
                    bot.send_message(message.chat.id, f"📦 <b>{CATEGORY_NAMES.get(category, 'Category')}</b> updated.", parse_mode="HTML", reply_markup=markup)
                except Exception:
                    pass

    # Optional file attachment handler (document) for method_bins items
    @bot.message_handler(content_types=['document'], func=lambda m: isinstance(user_states.get(m.from_user.id,''), str) and user_states.get(m.from_user.id,'').startswith('wizard_file_method_bins::'))
    def wizard_method_bins_file(message):
        state = user_states.get(message.from_user.id)
        try:
            _, category, item_id = state.split('::', 2)
            item_id = int(item_id)
        except Exception:
            bot.reply_to(message, 'State error (file). Aborting.')
            user_states.pop(message.from_user.id, None)
            return
        file_id = message.document.file_id if message.document else None
        if not file_id:
            bot.reply_to(message, 'No document detected. Send a file or type skip.')
            return
        try:
            data = load_products(); items = data.get(category, [])
            for it in items:
                if it.get('id') == item_id:
                    it['delivery_type'] = 'tg_document'
                    it['delivery_content'] = file_id
                    break
            data[category] = items
            save_products(data); save_products_to_file_and_reload(data)
            bot.reply_to(message, '📎 File attached and item updated.')
        except Exception as e:
            bot.reply_to(message, f'Failed to attach file: {e}')
        finally:
            user_states.pop(message.from_user.id, None)
            try:
                markup = get_category_markup(category)
                bot.send_message(message.chat.id, f"📦 <b>{CATEGORY_NAMES.get(category, 'Category')}</b> updated.", parse_mode="HTML", reply_markup=markup)
            except Exception:
                pass

    @bot.message_handler(func=lambda m: isinstance(user_states.get(m.from_user.id,''), str) and user_states.get(m.from_user.id,'').startswith('wizard_file_method_bins::'))
    def wizard_method_bins_file_skip(message):
        if message.text and message.text.lower().strip() == 'skip':
            state = user_states.get(message.from_user.id)
            try:
                _, category, _ = state.split('::', 2)
            except Exception:
                category = 'method_bins'
            bot.reply_to(message, '✅ Finished without attaching file.')
            user_states.pop(message.from_user.id, None)
            try:
                markup = get_category_markup(category)
                bot.send_message(message.chat.id, f"📦 <b>{CATEGORY_NAMES.get(category, 'Category')}</b> updated.", parse_mode="HTML", reply_markup=markup)
            except Exception:
                pass
        else:
            bot.reply_to(message, 'Send a document to attach or type skip.')

    # Optional file attachment handler (document) for dumps items
    @bot.message_handler(content_types=['document', 'photo', 'video', 'animation', 'text'], func=lambda m: isinstance(user_states.get(m.from_user.id,''), str) and user_states.get(m.from_user.id,'').startswith('wizard_file_dumps::'))
    def wizard_dumps_file(message):
        state = user_states.get(message.from_user.id)
        try:
            _, category, item_id = state.split('::', 2)
            item_id = int(item_id)
        except Exception:
            bot.reply_to(message, 'State error (file). Aborting.')
            user_states.pop(message.from_user.id, None)
            return

        details = None
        # Document
        if getattr(message, 'document', None):
            details = {"type": "document", "file_id": message.document.file_id, "file_name": getattr(message.document, 'file_name', None)}
        # Photo
        elif getattr(message, 'photo', None):
            details = {"type": "photo", "file_id": message.photo[-1].file_id}
        # Animation
        elif getattr(message, 'animation', None):
            details = {"type": "animation", "file_id": message.animation.file_id}
        # Video
        elif getattr(message, 'video', None):
            details = {"type": "video", "file_id": message.video.file_id}
        # Forwarded message
        elif getattr(message, 'forward_from', None) or getattr(message, 'forward_from_chat', None):
            details = {"type": "forward", "forward_from_chat_id": getattr(getattr(message, 'forward_from_chat', None), 'id', None), "forward_from_id": getattr(getattr(message, 'forward_from', None), 'id', None), "forward_message_id": getattr(message, 'forward_from_message_id', None)}
        # Text fallback (URL or plain text)
        elif getattr(message, 'text', None):
            details = {"type": "text", "text": message.text}

        if not details:
            bot.reply_to(message, 'No supported content detected. Send a document/photo/video/animation/forwarded message or type skip.')
            return

        try:
            data = load_products(); items = data.get(category, [])
            for it in items:
                if it.get('id') == item_id:
                    # Save under delivery_details for more flexibility
                    it['delivery_type'] = f"tg_{details.get('type') if details.get('type') != 'text' else 'text'}"
                    it['delivery_content'] = details
                    break
            data[category] = items
            save_products(data); save_products_to_file_and_reload(data)
            bot.reply_to(message, '📎 Content attached and item updated.')
        except Exception as e:
            bot.reply_to(message, f'Failed to attach content: {e}')
        finally:
            user_states.pop(message.from_user.id, None)
            try:
                markup = get_category_markup(category)
                bot.send_message(message.chat.id, f"📦 <b>{CATEGORY_NAMES.get(category, 'Category')}</b> updated.", parse_mode="HTML", reply_markup=markup)
            except Exception:
                pass

    @bot.message_handler(func=lambda m: isinstance(user_states.get(m.from_user.id,''), str) and user_states.get(m.from_user.id,'').startswith('wizard_file_dumps::'))
    def wizard_dumps_file_skip(message):
        if message.text and message.text.lower().strip() == 'skip':
            state = user_states.get(message.from_user.id)
            try:
                _, category, _ = state.split('::', 2)
            except Exception:
                category = 'dumps'
            bot.reply_to(message, '✅ Finished without attaching file.')
            user_states.pop(message.from_user.id, None)
            try:
                markup = get_category_markup(category)
                bot.send_message(message.chat.id, f"📦 <b>{CATEGORY_NAMES.get(category, 'Category')}</b> updated.", parse_mode="HTML", reply_markup=markup)
            except Exception:
                pass
        else:
            bot.reply_to(message, 'Send a document to attach or type skip.')

    # Optional file attachment handler (document) for dumping_toolkit items
    @bot.message_handler(content_types=['document', 'photo', 'video', 'animation', 'text'], func=lambda m: isinstance(user_states.get(m.from_user.id,''), str) and user_states.get(m.from_user.id,'').startswith('wizard_file_dumping_toolkit::'))
    def wizard_dumping_toolkit_file(message):
        state = user_states.get(message.from_user.id)
        try:
            _, category, item_id = state.split('::', 2)
            item_id = int(item_id)
        except Exception:
            bot.reply_to(message, 'State error (file). Aborting.')
            user_states.pop(message.from_user.id, None)
            return

        details = None
        # Document
        if getattr(message, 'document', None):
            details = {"type": "document", "file_id": message.document.file_id, "file_name": getattr(message.document, 'file_name', None)}
        # Photo
        elif getattr(message, 'photo', None):
            details = {"type": "photo", "file_id": message.photo[-1].file_id}
        # Animation
        elif getattr(message, 'animation', None):
            details = {"type": "animation", "file_id": message.animation.file_id}
        # Video
        elif getattr(message, 'video', None):
            details = {"type": "video", "file_id": message.video.file_id}
        # Forwarded message
        elif getattr(message, 'forward_from', None) or getattr(message, 'forward_from_chat', None):
            details = {"type": "forward", "forward_from_chat_id": getattr(getattr(message, 'forward_from_chat', None), 'id', None), "forward_from_id": getattr(getattr(message, 'forward_from', None), 'id', None), "forward_message_id": getattr(message, 'forward_from_message_id', None)}
        # Text fallback (URL or plain text)
        elif getattr(message, 'text', None):
            txt = message.text.strip()
            if txt.lower() == 'skip':
                # Handle skip here instead of separate handler
                bot.reply_to(message, '✅ Finished without attaching file.')
                user_states.pop(message.from_user.id, None)
                try:
                    markup = get_category_markup(category)
                    bot.send_message(message.chat.id, f"📦 <b>{CATEGORY_NAMES.get(category, 'Category')}</b> updated.", parse_mode="HTML", reply_markup=markup)
                except Exception:
                    pass
                return
            details = {"type": "text", "text": txt}

        if not details:
            bot.reply_to(message, 'No supported content detected. Send a document/photo/video/animation or type skip.')
            return

        try:
            data = load_products(); items = data.get(category, [])
            for it in items:
                if it.get('id') == item_id:
                    # Save under delivery_details for more flexibility
                    it['delivery_type'] = f"tg_{details.get('type') if details.get('type') != 'text' else 'text'}"
                    it['delivery_content'] = details
                    break
            data[category] = items
            save_products(data); save_products_to_file_and_reload(data)
            bot.reply_to(message, '📎 Content attached and item updated.')
        except Exception as e:
            bot.reply_to(message, f'Failed to attach content: {e}')
        finally:
            user_states.pop(message.from_user.id, None)
            try:
                markup = get_category_markup(category)
                bot.send_message(message.chat.id, f"📦 <b>{CATEGORY_NAMES.get(category, 'Category')}</b> updated.", parse_mode="HTML", reply_markup=markup)
            except Exception:
                pass

    @bot.message_handler(content_types=['document', 'photo', 'video', 'animation', 'text'], func=lambda m: isinstance(user_states.get(m.from_user.id,''), str) and user_states.get(m.from_user.id,'').startswith('wizard_file_courses::'))
    def wizard_courses_file(message):
        state = user_states.get(message.from_user.id)
        try:
            _, category, item_id = state.split('::', 2)
            item_id = int(item_id)
        except Exception:
            bot.reply_to(message, 'State error (file). Aborting.')
            user_states.pop(message.from_user.id, None)
            return

        details = None
        # Document
        if getattr(message, 'document', None):
            details = {"type": "document", "file_id": message.document.file_id, "file_name": getattr(message.document, 'file_name', None)}
        # Photo
        elif getattr(message, 'photo', None):
            details = {"type": "photo", "file_id": message.photo[-1].file_id}
        # Animation
        elif getattr(message, 'animation', None):
            details = {"type": "animation", "file_id": message.animation.file_id}
        # Video
        elif getattr(message, 'video', None):
            details = {"type": "video", "file_id": message.video.file_id}
        # Forwarded message
        elif getattr(message, 'forward_from', None) or getattr(message, 'forward_from_chat', None):
            details = {"type": "forward", "forward_from_chat_id": getattr(getattr(message, 'forward_from_chat', None), 'id', None), "forward_from_id": getattr(getattr(message, 'forward_from', None), 'id', None), "forward_message_id": getattr(message, 'forward_from_message_id', None)}
        # Text fallback (URL or plain text)
        elif getattr(message, 'text', None):
            txt = message.text.strip()
            if txt.lower() == 'skip':
                bot.reply_to(message, '✅ Finished without attaching file.')
                user_states.pop(message.from_user.id, None)
                try:
                    markup = get_category_markup(category)
                    bot.send_message(message.chat.id, f"📦 <b>{CATEGORY_NAMES.get(category, 'Category')}</b> updated.", parse_mode="HTML", reply_markup=markup)
                except Exception:
                    pass
                return
            details = {"type": "text", "text": txt}

        if not details:
            bot.reply_to(message, 'No supported content detected. Send a document/photo/video/animation or type skip.')
            return

        try:
            data = load_products(); items = data.get(category, [])
            for it in items:
                if it.get('id') == item_id:
                    it['delivery_type'] = f"tg_{details.get('type') if details.get('type') != 'text' else 'text'}"
                    it['delivery_content'] = details
                    break
            data[category] = items
            save_products(data); save_products_to_file_and_reload(data)
            bot.reply_to(message, '📎 Content attached and item updated.')
        except Exception as e:
            bot.reply_to(message, f'Failed to attach content: {e}')
        finally:
            user_states.pop(message.from_user.id, None)
            try:
                markup = get_category_markup(category)
                bot.send_message(message.chat.id, f"📦 <b>{CATEGORY_NAMES.get(category, 'Category')}</b> updated.", parse_mode="HTML", reply_markup=markup)
            except Exception:
                pass

    @bot.message_handler(content_types=['document', 'photo', 'video', 'animation', 'text'], func=lambda m: isinstance(user_states.get(m.from_user.id,''), str) and user_states.get(m.from_user.id,'').startswith('wizard_file_courses::'))
    def wizard_courses_file(message):
        state = user_states.get(message.from_user.id)
        try:
            _, category, item_id = state.split('::', 2)
            item_id = int(item_id)
        except Exception:
            bot.reply_to(message, 'State error (file). Aborting.')
            user_states.pop(message.from_user.id, None)
            return

        details = None
        # Document
        if getattr(message, 'document', None):
            details = {"type": "document", "file_id": message.document.file_id, "file_name": getattr(message.document, 'file_name', None)}
        # Photo
        elif getattr(message, 'photo', None):
            details = {"type": "photo", "file_id": message.photo[-1].file_id}
        # Animation
        elif getattr(message, 'animation', None):
            details = {"type": "animation", "file_id": message.animation.file_id}
        # Video
        elif getattr(message, 'video', None):
            details = {"type": "video", "file_id": message.video.file_id}
        # Forwarded message
        elif getattr(message, 'forward_from', None) or getattr(message, 'forward_from_chat', None):
            details = {"type": "forward", "forward_from_chat_id": getattr(getattr(message, 'forward_from_chat', None), 'id', None), "forward_from_id": getattr(getattr(message, 'forward_from', None), 'id', None), "forward_message_id": getattr(message, 'forward_from_message_id', None)}
        # Text fallback (URL or plain text)
        elif getattr(message, 'text', None):
            txt = message.text.strip()
            if txt.lower() == 'skip':
                bot.reply_to(message, '✅ Finished without attaching file.')
                user_states.pop(message.from_user.id, None)
                try:
                    markup = get_category_markup(category)
                    bot.send_message(message.chat.id, f"📦 <b>{CATEGORY_NAMES.get(category, 'Category')}</b> updated.", parse_mode="HTML", reply_markup=markup)
                except Exception:
                    pass
                return
            details = {"type": "text", "text": txt}

        if not details:
            bot.reply_to(message, 'No supported content detected. Send a document/photo/video or type skip.')
            return

        try:
            data = load_products(); items = data.get(category, [])
            for it in items:
                if it.get('id') == item_id:
                    it['delivery_type'] = f"tg_{details.get('type') if details.get('type') != 'text' else 'text'}"
                    it['delivery_content'] = details
                    break
            data[category] = items
            save_products(data); save_products_to_file_and_reload(data)
            bot.reply_to(message, '📎 Content attached and item updated.')
        except Exception as e:
            bot.reply_to(message, f'Failed to attach content: {e}')
        finally:
            user_states.pop(message.from_user.id, None)
            try:
                markup = get_category_markup(category)
                bot.send_message(message.chat.id, f"📦 <b>{CATEGORY_NAMES.get(category, 'Category')}</b> updated.", parse_mode="HTML", reply_markup=markup)
            except Exception:
                pass

    # =============================
    # ===== Delete / Clear Items ===
    # =============================
    @bot.callback_query_handler(func=lambda call: call.data.startswith("delete_item_"))
    def delete_item(call):
        try:
            # Parse: delete_item_{category}_{item_id}
            # Remove prefix and split from the right to get item_id
            rest = call.data.replace("delete_item_", "", 1)
            # Split from right to separate item_id from category (which may have underscores)
            parts = rest.rsplit('_', 1)
            if len(parts) != 2:
                raise ValueError("Invalid format")
            category = parts[0]
            item_id = int(parts[1])
        except Exception:
            bot.answer_callback_query(call.id, "Bad format", show_alert=True)
            return
        # Permission check
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor(); c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if not c.fetchone():
                    bot.answer_callback_query(call.id, "❌ Not authorized", show_alert=True)
                    return
        try:
            data = load_products()
            items = data.get(category, [])
            before = len(items)
            items = [it for it in items if it.get('id') != item_id]
            data[category] = items
            if len(items) == before:
                bot.answer_callback_query(call.id, "Not found", show_alert=True)
                return
            save_products(data)
            save_products_to_file_and_reload(data)
            bot.answer_callback_query(call.id, "Deleted", show_alert=False)
            # Refresh menu
            refresh_markup = get_category_markup(category)
            try:
                bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=refresh_markup)
            except Exception:
                pass
        except Exception as e:
            bot.answer_callback_query(call.id, f"Err: {e}", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("clear_cat_"))
    def clear_category(call):
        # Parse: clear_cat_{category}
        category = call.data.replace("clear_cat_", "", 1)
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor(); c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if not c.fetchone():
                    bot.answer_callback_query(call.id, "❌ Not authorized", show_alert=True)
                    return
        try:
            data = load_products(); items = data.get(category, [])
            if not items:
                bot.answer_callback_query(call.id, "Already empty", show_alert=True)
                return
            data[category] = []
            save_products(data)
            save_products_to_file_and_reload(data)
            bot.answer_callback_query(call.id, "Cleared", show_alert=False)
            markup = get_category_markup(category)
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception as e:
            bot.answer_callback_query(call.id, f"Err: {e}", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_cat_menu_"))
    def admin_cat_menu_callback(call):
        """
        Generic handler for category management menus.
        
        This function is triggered when the admin selects a category to manage products, 
        users, or other resources. It shows the current items in the category and provides
        options to add new items (via wizard or JSON), clear the category, or delete items.
        """
        try:
            category = call.data.replace("admin_cat_menu_", "")  # Extract category from callback data
            products = load_products()
            items = products.get(category, [])
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {str(e)}", show_alert=True)
            return

        text = f"📦 <b>{CATEGORY_NAMES.get(category, 'Category')} Management</b>\n\n"
        markup = get_category_markup(category)

        # Show current items in the category
        if items:
            text += "🛠️ <b>Current Items:</b>\n"
            for item in items[:10]:  # Show up to 10 items
                item_name = item.get("name", "Unnamed Item")
                item_price = item.get("price", "N/A")
                text += f"• {item_name} - ${item_price}\n"
            if len(items) > 10:
                text += "<i>...and more items</i>\n"
        else:
            text += "No items found in this category.\n"

        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # ======================================
    # ====== USER-FACING MENU HANDLERS ======
    # ======================================

    @bot.callback_query_handler(func=lambda call: call.data == "personal_area")
    def personal_area_callback(call):
        user_id = call.from_user.id
        bot.send_chat_action(user_id, 'typing')
        
        # Fetch the user's details from the database.
        user_details = get_user_details(user_id)
        
        # Handle cases where the user might not be in the database yet.
        if not user_details:
            bot.answer_callback_query(call.id, "Could not retrieve your details. Please /start the bot again to register.", show_alert=True)
            return
            
        # Generate the user's unique referral link.
        try:
            bot_username = bot.get_me().username
            referral_link = f"https://t.me/{bot_username}?start={user_details['referral_code']}"
        except Exception as e:
            print(f"Error getting bot username: {e}")
            referral_link = "Could not generate referral link at this moment."
        
        # Get additional stats
        import datetime
        join_date = user_details.get('created_at', 'Unknown')
        if join_date != 'Unknown':
            try:
                join_date = datetime.datetime.fromisoformat(join_date).strftime("%B %d, %Y")
            except:
                pass
        
        # Determine user level based on spending
        balance = user_details['balance']
        if balance >= 1000:
            user_level = "💎 Diamond"
            level_color = "🔷"
        elif balance >= 500:
            user_level = "🥇 Gold"
            level_color = "🟡"
        elif balance >= 100:
            user_level = "🥈 Silver"
            level_color = "⚪"
        else:
            user_level = "🥉 Bronze"
            level_color = "🟤"

        # Construct the enhanced message for the user.
        text = f"""👤 <b>Personal Dashboard</b>

{level_color} <b>Status:</b> {user_level}
👋 <b>Welcome,</b> {user_details['username']}!

💰 <b>Account Balance:</b> <code>${user_details['balance']:.2f}</code>
🆔 <b>User ID:</b> <code>{user_details['user_id']}</code>
📅 <b>Member Since:</b> {join_date}
👥 <b>Referrals:</b> {user_details['referral_count']} friends

🔗 <b>Your Referral Link:</b>
<code>{referral_link}</code>

<i>💡 Share your link and earn rewards for each new user!</i>
"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        # Account actions
        markup.add(
            types.InlineKeyboardButton("💰 Add Funds", callback_data="add_funds"),
            types.InlineKeyboardButton("� My Statistics", callback_data="user_stats")
        )
        
        markup.add(
            types.InlineKeyboardButton("💳 Transaction History", callback_data="balance_history"),
            types.InlineKeyboardButton("📦 My Orders", callback_data="my_orders")
        )
        
        markup.add(
            types.InlineKeyboardButton("🎯 Referral Program", callback_data="referral_info"),
            types.InlineKeyboardButton("⚙️ Account Settings", callback_data="account_settings")
        )
        
        # Back
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # Alias: Open Personal Area when user taps "My Profile" button
    @bot.callback_query_handler(func=lambda call: call.data == "my_profile")
    def my_profile_alias(call):
        return personal_area_callback(call)

    @bot.callback_query_handler(func=lambda call: call.data == "balance_history")
    def balance_history_callback(call):
        """Show last 10 balance-related transactions (deposits + wallet purchases)."""
        user_id = call.from_user.id
        bot.send_chat_action(user_id, 'typing')
        
        # Show balance history
        text = "💳 <b>Balance History</b>\n\n"
        text += "Feature coming soon! Your transaction history will appear here.\n\n"
        text += "Current balance information is available in your Personal Area."
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Personal Area", callback_data="personal_area"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "add_funds")
    def add_funds_callback(call):
        """Handle add funds request."""
        amounts = [10, 20, 50, 100, 200, 500]
        text = "💰 <b>Add Funds</b>\n\nSelect an amount to deposit:"
        
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = [types.InlineKeyboardButton(f"${amt}", callback_data=f"deposit_{amt}") for amt in amounts]
        for i in range(0, len(buttons), 3):
            markup.row(*buttons[i:i+3])
        markup.add(types.InlineKeyboardButton("💳 Custom Amount", callback_data="deposit_custom"))
        markup.add(types.InlineKeyboardButton("ℹ️ Payment Details", callback_data="payment_info"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Personal Area", callback_data="personal_area"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "payment_info")
    def payment_info_callback(call):
        """Shows detailed payment information for all supported cryptocurrencies."""
        from config import CRYPTO_ADDRESSES
        
        # Format all crypto addresses nicely
        crypto_list = []
        crypto_list.append("💰 <b>BTC (Bitcoin):</b>")
        crypto_list.append(f"<code>{CRYPTO_ADDRESSES['BTC']}</code>")
        crypto_list.append("")
        crypto_list.append("💰 <b>BNB (BEP-20):</b>")
        crypto_list.append(f"<code>{CRYPTO_ADDRESSES['BNB']}</code>")
        crypto_list.append("")
        crypto_list.append("💰 <b>LTC (Litecoin):</b>")
        crypto_list.append(f"<code>{CRYPTO_ADDRESSES['LTC']}</code>")
        crypto_list.append("")
        crypto_list.append("💰 <b>TON Coin:</b>")
        crypto_list.append(f"<code>{CRYPTO_ADDRESSES['TON']}</code>")
        crypto_list.append("")
        crypto_list.append("💰 <b>USDT (TRC-20):</b>")
        crypto_list.append(f"<code>{CRYPTO_ADDRESSES['USDT_TRC20']}</code>")
        crypto_list.append("")
        crypto_list.append("💰 <b>USDT (ERC-20):</b>")
        crypto_list.append(f"<code>{CRYPTO_ADDRESSES['USDT_ERC20']}</code>")
        
        crypto_info = "\n".join(crypto_list)
        
        text = (
            "🪙 <b>Cryptocurrency Payment Information</b>\n\n"
            "💳 <b>Accepted Cryptocurrencies:</b>\n\n"
            f"{crypto_info}\n\n"
            "⚠️ <b>IMPORTANT INSTRUCTIONS:</b>\n"
            "1️⃣ Choose your preferred cryptocurrency\n"
            "2️⃣ Send exact amount to the corresponding address\n"
            "3️⃣ Include your Payment ID in the transaction memo\n"
            "4️⃣ Upload a screenshot of your transaction\n"
            "5️⃣ Wait for verification (usually 1-24 hours)\n\n"
            "🚫 <b>WARNING:</b>\n"
            "• Double-check network type (BEP-20, TRC-20, ERC-20)\n"
            "• Sending wrong network = LOSS OF FUNDS\n"
            "• Minimum deposit: $5 USD equivalent\n\n"
            "💡 <b>Need Help?</b> Contact support after making payment."
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Add Funds", callback_data="add_funds"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("deposit_"))
    def handle_deposit_callback(call):
        """Handles preset deposit amounts."""
        try:
            if call.data == "deposit_custom":
                user_states[call.from_user.id] = "awaiting_custom_deposit"
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("⬅️ Cancel", callback_data="add_funds"))
                bot.edit_message_text(
                    "💳 <b>Custom Deposit Amount</b>\n\n"
                    "Please enter the amount in USD you wish to deposit.\n"
                    "<i>Minimum: $5 USD | Maximum: $10,000 USD</i>",
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                return

            amount = int(call.data.split('_')[1])
            
            # Use the existing payment flow for deposits
            item_name = f"Wallet Deposit"
            item_details = {"deposit_amount": amount, "type": "wallet_deposit"}
            back_callback = "add_funds"
            
            from payment_handler import show_payment_options
            show_payment_options(bot, call, item_name, amount, item_details, back_callback)

        except Exception as e:
            print(f"Error handling deposit callback: {e}")
            bot.answer_callback_query(call.id, "An error occurred. Please try again.", show_alert=True)

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_custom_deposit")
    def handle_custom_deposit_amount(message):
        """Processes custom deposit amounts."""
        try:
            amount = float(message.text.strip())
            if amount < 5:
                bot.reply_to(message, "❌ Minimum deposit amount is $5 USD.")
                return
            if amount > 10000:
                bot.reply_to(message, "❌ Maximum deposit amount is $10,000 USD.")
                return
            
            del user_states[message.from_user.id]
            
            # Use the existing payment flow for custom deposits
            item_name = f"Wallet Deposit"
            item_details = {"deposit_amount": amount, "type": "wallet_deposit"}
            back_callback = "add_funds"
            
            from payment_handler import show_payment_options
            sent_message = bot.send_message(message.chat.id, "🔄 Generating payment details...")
            call_mock = types.CallbackQuery(id=None, from_user=message.from_user, data=None, chat_instance=None, message=sent_message, json_string=None)
            show_payment_options(bot, call_mock, item_name, amount, item_details, back_callback)

        except ValueError:
            bot.reply_to(message, "❌ Invalid amount. Please enter a valid number (e.g., 50 or 125.50).")
        except Exception as e:
            print(f"Error handling custom deposit: {e}")
            bot.reply_to(message, "❌ An error occurred. Please try again.")

    # The 'giftcards_menu' callback is now handled in main.py as 'Coming Soon'.

    @bot.callback_query_handler(func=lambda call: call.data == "rdp_menu")
    def rdp_menu(call):
        if handle_unavailable_section(bot, call, "rdp"):
            return
        create_dynamic_product_menu(call, "rdp")
    
    @bot.callback_query_handler(func=lambda call: call.data == "method_bins_menu")
    def method_bins_menu(call):
        if handle_unavailable_section(bot, call, "bins_methods"):
            return
        create_dynamic_product_menu(call, "method_bins")

    @bot.callback_query_handler(func=lambda call: call.data == "other_menu")
    def other_menu(call):
        create_dynamic_product_menu(call, "other")

    @bot.callback_query_handler(func=lambda call: call.data == "cc_menu")
    def cc_menu(call):
        if handle_unavailable_section(bot, call, "cc_shop"):
            return
        
        text = (
            "🛍️ <b>Credit Card Shop</b>\n\n"
            "Choose your preferred option:\n\n"
            "🎛️ <b>Custom CC:</b> Browse available credit cards with full details\n"
            "   • Country flag, card type, level, bank info\n"
            "   • Multiple cards in stock\n"
            "   • Instant delivery after payment\n\n"
            "🔍 <b>Search by BIN:</b> Find cards from your specific BIN\n"
            "   • Enter your BIN (6-8 digits)\n"
            "   • View all available cards matching your BIN\n"
            "   • Full BIN information lookup\n"
            "   • Direct purchase from search results\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <b>𝗜𝗠𝗣𝗢𝗥𝗧𝗔𝗡𝗧 𝗡𝗢𝗧𝗜𝗖𝗘</b> ⚠️\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>𝗪𝗘 𝗢𝗡𝗟𝗬 𝗚𝗜𝗩𝗘 𝗙𝗥𝗘𝗦𝗛 𝗖𝗛𝗔𝗥𝗚𝗘𝗗 𝗖𝗖, 𝗧𝗛𝗘𝗥𝗘 𝗜𝗦 𝗡𝗢 𝗚𝗨𝗔𝗥𝗔𝗡𝗧𝗘𝗘 𝗢𝗙 𝗜𝗧 𝗧𝗢 𝗘𝗜𝗧𝗛𝗘𝗥 𝗪𝗢𝗥𝗞 𝗢𝗥 𝗡𝗢𝗧!! 𝗜𝗧 𝗗𝗘𝗣𝗘𝗡𝗗𝗦 𝗢𝗡 𝗬𝗢𝗨𝗥 𝗦𝗞𝗜𝗟𝗟𝗦 𝗧𝗢 𝗨𝗦𝗘 𝗜𝗧 𝗣𝗥𝗢𝗣𝗘𝗥𝗟𝗬.</b>\n\n"
            "📌 <b>𝗡𝗢𝗧𝗘:</b>\n"
            "• <b>𝗗𝗢 𝗡𝗢𝗧 𝗖𝗛𝗘𝗖𝗞 𝗧𝗛𝗘 𝗖𝗛𝗔𝗥𝗚𝗘𝗗 𝗖𝗖 𝗔𝗚𝗔𝗜𝗡 𝗜𝗡 𝗖𝗛𝗘𝗖𝗞𝗘𝗥𝗦.</b>\n"
            "  [𝗜𝗧 𝗞𝗜𝗟𝗟𝗦 𝗧𝗛𝗘 𝗖𝗖 𝗔𝗡𝗗 𝗜𝗧 𝗕𝗘𝗖𝗢𝗠𝗘𝗦 𝗨𝗦𝗘𝗟𝗘𝗦𝗦]\n\n"
            "• <b>𝗜𝗡 𝗖𝗔𝗦𝗘 𝗢𝗙 𝗗𝗘𝗔𝗗 𝗖𝗖, 𝗪𝗜𝗧𝗛 𝗩𝗔𝗟𝗜𝗗 𝗥𝗘𝗔𝗦𝗢𝗡𝗦, 𝗪𝗘'𝗟𝗟 𝗢𝗡𝗟𝗬 𝗔𝗡𝗗 𝗢𝗡𝗟𝗬 𝗥𝗘𝗣𝗟𝗔𝗖𝗘 𝗬𝗢𝗨𝗥 𝗖𝗖, 𝗧𝗛𝗘𝗥𝗘 𝗜𝗦 𝗡𝗢 𝗥𝗘𝗙𝗨𝗡𝗗𝗦.</b>"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🎛️ Browse All Cards", callback_data="custom_cc_menu"), 
            types.InlineKeyboardButton("🔍 Search by BIN", callback_data="enter_bin_menu")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "custom_cc_menu")
    def custom_cc_menu(call):
        """Show browse or configure options for Custom CCs"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🔎 Browse Available Cards", callback_data="browse_custom_ccs"))
        markup.add(types.InlineKeyboardButton("🎛️ Configure Custom CC", callback_data="start_custom_cc"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to CC Shop", callback_data="cc_menu"))
        bot.edit_message_text("🎛️ <b>Custom CC</b>\n\nChoose to browse existing cards or configure a custom card to your specs.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "browse_custom_ccs")
    def browse_custom_ccs(call):
        create_dynamic_product_menu(call, "custom_ccs")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("custom_cc_menu_page_"))
    def custom_cc_menu_page(call):
        """Handle pagination for custom CC menu"""
        create_dynamic_product_menu(call, "custom_ccs")

    @bot.callback_query_handler(func=lambda call: call.data == "enter_bin_menu")
    def enter_bin_menu(call):
        """Shows BIN entry interface to search available cards"""
        user_states[call.from_user.id] = "awaiting_bin_input"
        
        text = (
            "🏦 <b>Search CC by BIN</b>\n\n"
            "Enter a 6-8 digit BIN number to search available credit cards:\n\n"
            "🔍 <b>We'll show you:</b>\n"
            "• All available cards matching your BIN\n"
            "• Card details (country, type, level, bank)\n"
            "• Pricing and instant purchase options\n\n"
            "📝 <b>Enter your BIN number:</b>"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Cancel", callback_data="cc_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "start_custom_cc")
    def start_custom_cc_generation(call):
        """Multi-step selector: Country -> Card Type -> Level -> Results/Request"""
        # Load products and get all countries with flags
        products = get_products_from_cache("custom_ccs") or []
        
        # Create a dict of country -> flag and country codes
        country_data = {}
        for p in products:
            if p.get("country"):
                country = p.get("country")
                flag = p.get("country_flag", "")
                # Create short code from country name
                if country not in country_data:
                    # Generate 3-letter code
                    words = country.split()
                    if len(words) > 1:
                        code = ''.join(w[0].upper() for w in words[:3])
                    else:
                        code = country[:3].upper()
                    country_data[country] = {"flag": flag, "code": code}
        
        countries = sorted(country_data.keys())

        if not countries:
            bot.answer_callback_query(call.id, "No countries available at the moment.", show_alert=True)
            return

        text = "🌍 <b>Step 1/3 — Select Country</b>\n\nChoose a country from the list below:"
        markup = types.InlineKeyboardMarkup(row_width=3)
        
        # Display all countries with codes and flags in grid (3 per row)
        row = []
        for country in countries:
            safe_key = country.replace(' ', '_')
            flag = country_data[country]["flag"]
            code = country_data[country]["code"]
            display_text = f"{code} {flag}" if flag else code
            row.append(types.InlineKeyboardButton(display_text, callback_data=f"cc_country_{safe_key}"))
            
            # Add row when we have 3 buttons
            if len(row) == 3:
                markup.add(*row)
                row = []
        
        # Add remaining buttons
        if row:
            markup.add(*row)
        
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="custom_cc_menu"))

        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_bin_input")
    def handle_bin_input(message):
        """Handles BIN input from user and searches for matching cards"""
        try:
            bin_number = message.text.strip()
            
            # Validate BIN format
            if not bin_number.isdigit() or len(bin_number) < 6 or len(bin_number) > 8:
                bot.reply_to(message, "❌ Invalid BIN format. Please enter a 6-8 digit BIN number.")
                return
            
            # Clear user state
            del user_states[message.from_user.id]
            
            # Search for cards with matching BIN in custom_ccs
            products = get_products_from_cache("custom_ccs") or []
            matching_cards = [p for p in products if p.get('bin', '').startswith(bin_number)]
            
            if not matching_cards:
                # No cards found, show BIN info and option to request
                from helpers import lookup_bin_info
                bin_info = lookup_bin_info(bin_number)
                
                text = (
                    f"🔍 <b>BIN Search Results</b>\n\n"
                    f"🔢 <b>BIN:</b> <code>{bin_number}</code>\n\n"
                    f"❌ <b>No cards available with this BIN</b>\n\n"
                    f"<b>📊 BIN Information:</b>\n"
                    f"🌍 <b>Country:</b> {bin_info['country']} {bin_info['country_flag']}\n"
                    f"💳 <b>Card Type:</b> {bin_info['brand']}\n"
                    f"⭐ <b>Level:</b> {bin_info['level']}\n"
                    f"🏦 <b>Bank:</b> {bin_info['bank']}\n"
                    f"📊 <b>Type:</b> {bin_info['type']}\n\n"
                    f"💡 <b>What to do:</b>\n"
                    f"• Check back later for new stock\n"
                    f"• Browse other available cards\n"
                    f"• Contact support for special requests"
                )
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔎 Browse All Cards", callback_data="browse_custom_ccs"))
                markup.add(types.InlineKeyboardButton("🔄 Try Another BIN", callback_data="enter_bin_menu"))
                markup.add(types.InlineKeyboardButton("⬅️ Back to CC Shop", callback_data="cc_menu"))
                
                bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")
            else:
                # Cards found, display them
                from helpers import lookup_bin_info
                bin_info = lookup_bin_info(bin_number)
                
                text = (
                    f"🔍 <b>BIN Search Results</b>\n\n"
                    f"🔢 <b>BIN:</b> <code>{bin_number}</code>\n"
                    f"✅ <b>Found {len(matching_cards)} card(s)</b>\n\n"
                    f"<b>📊 BIN Information:</b>\n"
                    f"🌍 <b>Country:</b> {bin_info['country']} {bin_info['country_flag']}\n"
                    f"💳 <b>Card Type:</b> {bin_info['brand']}\n"
                    f"⭐ <b>Level:</b> {bin_info['level']}\n"
                    f"🏦 <b>Bank:</b> {bin_info['bank']}\n"
                    f"📊 <b>Type:</b> {bin_info['type']}\n\n"
                    f"📦 <b>Available Cards:</b>"
                )
                
                markup = types.InlineKeyboardMarkup(row_width=1)
                
                # Display matching cards (limit to 20)
                for idx, card in enumerate(matching_cards[:20]):
                    card_id = card.get('id', idx)
                    card_bin = card.get('bin', 'N/A')
                    price = card.get('price', 0)
                    country = card.get('country', 'Unknown')
                    country_flag = card.get('country_flag', '')
                    card_type = card.get('card_type', 'Unknown')
                    level = card.get('level', 'Unknown')
                    
                    # Create button text
                    button_text = f"💳 {card_bin[:6]}...{card_bin[-4:] if len(card_bin) > 10 else ''} {country_flag} {card_type} {level} - ${price}"
                    
                    # Find original index in full products list for callback
                    original_idx = next((i for i, p in enumerate(products) if p.get('id') == card_id), None)
                    if original_idx is not None:
                        markup.add(types.InlineKeyboardButton(button_text, callback_data=f"buy_idx_custom_ccs_{original_idx}"))
                
                markup.add(types.InlineKeyboardButton("🔄 Try Another BIN", callback_data="enter_bin_menu"))
                markup.add(types.InlineKeyboardButton("⬅️ Back to CC Shop", callback_data="cc_menu"))
                
                bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error handling BIN input: {e}")
            bot.reply_to(message, "❌ An error occurred. Please try again.")

    @bot.callback_query_handler(func=lambda call: call.data == "giftcards_menu")
    def giftcards_menu(call):
        if handle_unavailable_section(bot, call, "gift_cards"):
            return
        create_dynamic_product_menu(call, "gift_cards")

    @bot.callback_query_handler(func=lambda call: call.data == "hacks_menu")
    def hacks_menu(call):
        if handle_unavailable_section(bot, call, "hacks"):
            return
        create_dynamic_product_menu(call, "hacks")

    @bot.callback_query_handler(func=lambda call: call.data == "dumps_menu")
    def dumps_menu(call):
        if handle_unavailable_section(bot, call, "dumps"):
            return
        
        # Load products
        bot.send_chat_action(call.message.chat.id, 'typing')
        products = get_products_from_cache("dumps")
        
        if not products:
            bot.answer_callback_query(call.id, "There are no products in the Dumps category at the moment.", show_alert=True)
            return
        
        # Create text with instructions
        text = (
            "💾 <b>Dumps</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📋 <b>𝗦𝗧𝗘𝗣𝗦 𝗧𝗢 𝗗𝗨𝗠𝗣𝗜𝗡𝗚</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>𝟭. 𝗗𝗢𝗪𝗡𝗟𝗢𝗔𝗗 𝗔𝗡𝗗 𝗘𝗫𝗧𝗥𝗔𝗖𝗧 𝗫𝗗𝗨𝗠𝗣 𝗧𝗢𝗢𝗟</b>\n\n"
            "<b>𝟮. 𝗥𝗨𝗡 .𝗘𝗫𝗘 𝗙𝗜𝗟𝗘 𝗙𝗥𝗢𝗠 𝗧𝗛𝗘 𝗙𝗢𝗟𝗗𝗘𝗥 𝗘𝗫𝗧𝗥𝗔𝗖𝗧𝗘𝗗</b>\n\n"
            "<b>𝟯. 𝗬𝗢𝗨'𝗟𝗟 𝗦𝗘𝗘 𝗗𝗨𝗠𝗣𝗜𝗡𝗚 𝗧𝗢𝗢𝗟 𝗜𝗡𝗧𝗘𝗥𝗙𝗔𝗖𝗘</b>\n\n"
            "<b>𝟰. 𝗙𝗜𝗟𝗟 𝗧𝗔𝗥𝗚𝗘𝗧 𝗪𝗘𝗕𝗦𝗜𝗧𝗘, 𝗗𝗢𝗥𝗞𝗦 𝗟𝗜𝗦𝗧 𝗔𝗡𝗗 𝗛𝗜𝗧 𝗥𝗨𝗡</b>\n\n"
            "<b>𝟱. 𝗬𝗢𝗨'𝗟𝗟 𝗦𝗘𝗘 𝗡𝗨𝗠𝗕𝗘𝗥 𝗢𝗙 𝗕𝗔𝗖𝗞𝗟𝗜𝗡𝗞𝗦 𝗙𝗢𝗨𝗡𝗗, 𝗔𝗡𝗗 𝗜𝗡𝗝𝗘𝗖𝗧𝗜𝗕𝗟𝗘 𝗟𝗜𝗡𝗞𝗦.</b>\n\n"
            "<b>𝟲. 𝗜𝗡 𝗧𝗛𝗘 𝗜𝗡𝗝𝗘𝗖𝗧𝗜𝗕𝗟𝗘 𝗟𝗜𝗡𝗞𝗦, 𝗨𝗦𝗘 𝗠𝗬 𝗙𝗜𝗟𝗘𝗙𝗘𝗧𝗖𝗛𝗘𝗥.𝗣𝗬 𝗧𝗢𝗢𝗟 𝗔𝗡𝗗 𝗜𝗧'𝗟𝗟 𝗖𝗔𝗧𝗖𝗛 𝗔𝗡𝗗 𝗙𝗘𝗧𝗖𝗛 𝗘𝗩𝗘𝗥𝗬 .𝗧𝗫𝗧, .𝗖𝗦𝗩, .𝗝𝗦𝗢𝗡, .𝗛𝗧𝗠𝗟..... 𝗘𝗧𝗖. 𝗙𝗜𝗟𝗘𝗦.</b>\n\n"
            "<b>𝟳. 𝗧𝗛𝗘𝗡 𝗦𝗘𝗔𝗥𝗖𝗛 𝗧𝗛𝗥𝗢𝗨𝗚𝗛 𝗙𝗜𝗟𝗘𝗦 𝗠𝗔𝗡𝗨𝗔𝗟𝗟𝗬 𝗢𝗥 𝗨𝗦𝗘 𝗔𝗡𝗢𝗧𝗛𝗘𝗥 𝗧𝗢𝗢𝗟 𝗧𝗢 𝗦𝗘𝗔𝗥𝗖𝗛 𝗙𝗢𝗥 𝗖𝗖 𝗙𝗢𝗥𝗠𝗔𝗧 𝗜𝗡 𝗜𝗧</b>\n\n"
            "<b>𝟴. 𝗜𝗙 𝗪𝗘 𝗚𝗢𝗧 𝗔𝗡 𝗛𝗜𝗧, 𝗜𝗧 𝗜𝗦 𝗔 𝗖𝗖 𝗗𝗔𝗧𝗔𝗕𝗔𝗦𝗘, 𝗔𝗡𝗗 𝗪𝗘 𝗙𝗢𝗨𝗡𝗗 𝗗𝗨𝗠𝗣𝗦</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Select a product below:\n\n"
        )
        
        # Create markup with products
        markup = types.InlineKeyboardMarkup(row_width=1)
        for index, item in enumerate(products):
            item_name = item.get("name")
            price = item.get("price")
            callback_data = f"buy_idx_dumps_{index}"
            markup.add(types.InlineKeyboardButton(f"🛒 {item_name} - ${price}", callback_data=callback_data))
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "dumping_toolkit_menu")
    def dumping_toolkit_menu(call):
        if handle_unavailable_section(bot, call, "dumping_toolkit"):
            return
        create_dynamic_product_menu(call, "dumping_toolkit")

    @bot.callback_query_handler(func=lambda call: call.data == "courses_menu")
    def courses_menu(call):
        if handle_unavailable_section(bot, call, "courses"):
            return
        create_dynamic_product_menu(call, "courses")


    # --- Admin: Add dump/upload flow ---
    @bot.callback_query_handler(func=lambda call: call.data == "admin_add_dump")
    def admin_add_dump(call):
        # Only owner or global admins should add dumps; reuse admin check used elsewhere
        user_id = call.from_user.id
        is_global_admin = False
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor(); c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
                is_global_admin = c.fetchone() is not None
        except Exception:
            is_global_admin = False
        if user_id != ADMIN_ID and not is_global_admin:
            bot.answer_callback_query(call.id, "❌ Only owner/global admin", show_alert=True)
            return
        # Ask for how admin wants to add: document/forward/text
    # --- Custom CC multi-step handlers ---
    @bot.callback_query_handler(func=lambda call: call.data.startswith("cc_letter_") or call.data == "cc_country_ALL")
    def cc_letter_or_all_handler(call):
        """Show countries for chosen initial or all countries."""
        try:
            # Load products and countries with flags
            products = get_products_from_cache("custom_ccs") or []
            
            # Create a dict of country -> flag
            country_flags = {}
            for p in products:
                if p.get("country") and p.get("country_flag"):
                    country_flags[p.get("country")] = p.get("country_flag")
            
            if call.data == "cc_country_ALL":
                countries = sorted({p.get("country") for p in products if p.get("country")})
            else:
                letter = call.data.split('_')[-1]
                countries = sorted({p.get("country") for p in products if p.get("country") and p.get("country").upper().startswith(letter)})

            if not countries:
                bot.answer_callback_query(call.id, "No countries found for that selection.", show_alert=True)
                return

            markup = types.InlineKeyboardMarkup(row_width=1)
            for c in countries:
                safe_key = c.replace(' ', '_')
                flag = country_flags.get(c, "")
                display_text = f"{flag} {c}" if flag else c
                markup.add(types.InlineKeyboardButton(display_text, callback_data=f"cc_country_{safe_key}"))
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="start_custom_cc"))

            bot.edit_message_text("🌍 <b>Select Country</b>\n\nChoose a country:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            print(f"Error in cc_letter_or_all_handler: {e}")
            bot.answer_callback_query(call.id, "An error occurred.", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("cc_country_"))
    def cc_country_selected(call):
        try:
            country = call.data.replace("cc_country_", "").replace('_', ' ')
            # Save selection in a short-lived session keyed by user id
            sid = str(call.from_user.id)
            if not hasattr(bot, '_cc_user_choice'):
                bot._cc_user_choice = {}
            bot._cc_user_choice[sid] = {"country": country}

            # Next: ask for card type
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("VISA", callback_data=f"cc_type_VISA"), types.InlineKeyboardButton("MASTERCARD", callback_data=f"cc_type_MASTERCARD"))
            markup.add(types.InlineKeyboardButton("AMEX", callback_data=f"cc_type_AMEX"), types.InlineKeyboardButton("ALL TYPES", callback_data=f"cc_type_ALL"))
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="start_custom_cc"))

            bot.edit_message_text(f"💳 <b>Step 2/3 — Card Type</b>\n\nSelected country: <b>{country}</b>\n\nChoose card brand:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            print(f"Error in cc_country_selected: {e}")
            bot.answer_callback_query(call.id, "An error occurred.", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("cc_type_"))
    def cc_type_selected(call):
        try:
            typ = call.data.replace('cc_type_', '')
            sid = str(call.from_user.id)
            if not hasattr(bot, '_cc_user_choice') or sid not in bot._cc_user_choice:
                bot.answer_callback_query(call.id, "Session expired. Please start again.", show_alert=True)
                return
            bot._cc_user_choice[sid]['type'] = None if typ == 'ALL' else typ

            # Next: ask for level
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("CLASSIC", callback_data=f"cc_level_CLASSIC"), types.InlineKeyboardButton("GOLD", callback_data=f"cc_level_GOLD"))
            markup.add(types.InlineKeyboardButton("PLATINUM", callback_data=f"cc_level_PLATINUM"), types.InlineKeyboardButton("ALL LEVELS", callback_data=f"cc_level_ALL"))
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="start_custom_cc"))

            sel_country = bot._cc_user_choice[sid].get('country')
            bot.edit_message_text(f"⭐ <b>Step 3/3 — Card Level</b>\n\nCountry: <b>{sel_country}</b>\nBrand: <b>{typ}</b>\n\nChoose card level:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            print(f"Error in cc_type_selected: {e}")
            bot.answer_callback_query(call.id, "An error occurred.", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("cc_level_"))
    def cc_level_selected(call):
        try:
            level = call.data.replace('cc_level_', '')
            sid = str(call.from_user.id)
            if not hasattr(bot, '_cc_user_choice') or sid not in bot._cc_user_choice:
                bot.answer_callback_query(call.id, "Session expired. Please start again.", show_alert=True)
                return
            bot._cc_user_choice[sid]['level'] = None if level == 'ALL' else level

            # Filter products
            sel = bot._cc_user_choice[sid]
            products = get_products_from_cache('custom_ccs') or []
            def matches(p):
                if sel.get('country') and sel['country'] != 'ALL' and p.get('country') != sel['country']:
                    return False
                if sel.get('type') and p.get('card_type') and sel['type'] != p.get('card_type'):
                    return False
                if sel.get('level') and p.get('level') and sel['level'] != p.get('level'):
                    return False
                return True

            results = [ (i,p) for i,p in enumerate(products) if matches(p) ]
            if results:
                text = f"🔎 <b>Found {len(results)} matching cards</b>\n\nSelect a card to buy:\n"
                markup = types.InlineKeyboardMarkup(row_width=1)
                for idx, prod in results:
                    flag = prod.get('country_flag', '')
                    name = prod.get('name', 'Card')
                    price = prod.get('price', 0)
                    card_type = prod.get('card_type', '')
                    level = prod.get('level', '')
                    
                    # Build button with flag, name, type, level
                    button_parts = [flag, name] if flag else [name]
                    if card_type:
                        button_parts.append(f"({card_type})")
                    button_text = f"{' '.join(button_parts)} — ${price}"
                    
                    markup.add(types.InlineKeyboardButton(button_text, callback_data=f"buy_idx_custom_ccs_{idx}"))
                markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="start_custom_cc"))
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
                return

            # No results: offer request options
            markup = types.InlineKeyboardMarkup(row_width=1)
            req_payload = f"{sel.get('country','ANY')}|{sel.get('type','ANY')}|{sel.get('level','ANY')}"
            markup.add(types.InlineKeyboardButton("✉️ Send Request to Admin (No Advance)", callback_data=f"cc_request_{req_payload}_NORMAL"))
            # Urgent: pay small advance ($10)
            markup.add(types.InlineKeyboardButton("⚡ Urgent — Pay Advance $10", callback_data=f"buy_dyn_customcc_10~{sel.get('country','None')}~{sel.get('type','None')}~{sel.get('level','None')}~REQUEST"))
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="start_custom_cc"))
            bot.edit_message_text("❗ <b>No matching cards found</b>\n\nYou can send a request to admin or pay a small advance for an urgent request.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

        except Exception as e:
            print(f"Error in cc_level_selected: {e}")
            bot.answer_callback_query(call.id, "An error occurred.", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("cc_request_"))
    def cc_request_handler(call):
        try:
            # cc_request_COUNTRY|TYPE|LEVEL_NORMAL
            payload = call.data.replace('cc_request_', '')
            parts = payload.rsplit('_', 1)
            specs = parts[0]
            mode = parts[1] if len(parts) > 1 else 'NORMAL'
            country, typ, level = specs.split('|')

            # Save request to disk and memory
            req_id = str(uuid.uuid4()).split('-')[0]
            request_obj = {
                'id': req_id,
                'user_id': call.from_user.id,
                'country': country,
                'type': typ,
                'level': level,
                'mode': mode,
                'created_at': datetime.utcnow().isoformat()
            }
            # persist
            try:
                with open('cc_requests.json', 'r', encoding='utf-8') as f:
                    all_reqs = json.load(f)
            except Exception:
                all_reqs = []
            all_reqs.append(request_obj)
            try:
                with open('cc_requests.json', 'w', encoding='utf-8') as f:
                    json.dump(all_reqs, f, indent=2)
            except Exception as e:
                print(f"Could not persist cc request: {e}")

            # Notify admin
            from helpers import notify_admin
            admin_text = (
                f"📥 <b>New Custom CC Request</b>\n\n"
                f"User: <code>{call.from_user.id}</code> ({call.from_user.first_name})\n"
                f"Country: {country}\nType: {typ}\nLevel: {level}\n"
                f"Mode: {mode}\nRequest ID: <code>{req_id}</code>\n"
            )
            admin_markup = types.InlineKeyboardMarkup(row_width=2)
            admin_markup.add(types.InlineKeyboardButton("✅ Mark as Added", callback_data=f"admin_cc_request_added_{req_id}"))
            admin_markup.add(types.InlineKeyboardButton("❌ Reject", callback_data=f"admin_cc_request_reject_{req_id}"))
            admin_markup.add(types.InlineKeyboardButton("💬 Chat with User", callback_data=f"admin_chat_user_{call.from_user.id}"))
            notify_admin(bot, admin_text, markup=admin_markup)

            bot.answer_callback_query(call.id, "Request sent to admin.", show_alert=True)
            bot.edit_message_text("✅ Your request has been sent to the admin. You will be notified when it's added.", call.message.chat.id, call.message.message_id, parse_mode="HTML")
        except Exception as e:
            print(f"Error in cc_request_handler: {e}")
            bot.answer_callback_query(call.id, "An error occurred.", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_cc_request_added_") or call.data.startswith("admin_cc_request_reject_"))
    def admin_cc_request_action(call):
        # Only owner/admin may act
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "You are not authorized.", show_alert=True)
            return
        try:
            if call.data.startswith('admin_cc_request_added_'):
                req_id = call.data.replace('admin_cc_request_added_', '')
                # load requests
                try:
                    with open('cc_requests.json', 'r', encoding='utf-8') as f:
                        all_reqs = json.load(f)
                except Exception:
                    all_reqs = []
                req = next((r for r in all_reqs if r['id'] == req_id), None)
                if not req:
                    bot.answer_callback_query(call.id, 'Request not found.', show_alert=True)
                    return
                # Notify user
                try:
                    bot.send_message(req['user_id'], f"✅ Your requested custom card ({req['country']}|{req['type']}|{req['level']}) has been added by admin. You can now browse the CC Shop and purchase it.")
                except Exception:
                    pass
                # remove request
                all_reqs = [r for r in all_reqs if r['id'] != req_id]
                try:
                    with open('cc_requests.json', 'w', encoding='utf-8') as f:
                        json.dump(all_reqs, f, indent=2)
                except Exception:
                    pass
                bot.answer_callback_query(call.id, 'Marked as added and user notified.')
                bot.edit_message_text('✅ Request marked as added.', call.message.chat.id, call.message.message_id)

            elif call.data.startswith('admin_cc_request_reject_'):
                req_id = call.data.replace('admin_cc_request_reject_', '')
                # load requests
                try:
                    with open('cc_requests.json', 'r', encoding='utf-8') as f:
                        all_reqs = json.load(f)
                except Exception:
                    all_reqs = []
                req = next((r for r in all_reqs if r['id'] == req_id), None)
                if not req:
                    bot.answer_callback_query(call.id, 'Request not found.', show_alert=True)
                    return
                try:
                    bot.send_message(req['user_id'], f"❌ Your requested custom card ({req['country']}|{req['type']}|{req['level']}) was rejected by admin.")
                except Exception:
                    pass
                all_reqs = [r for r in all_reqs if r['id'] != req_id]
                try:
                    with open('cc_requests.json', 'w', encoding='utf-8') as f:
                        json.dump(all_reqs, f, indent=2)
                except Exception:
                    pass
                bot.answer_callback_query(call.id, 'Request rejected and user notified.')
                bot.edit_message_text('❌ Request rejected.', call.message.chat.id, call.message.message_id)
        except Exception as e:
            print(f"Error in admin_cc_request_action: {e}")
            bot.answer_callback_query(call.id, 'An error occurred.', show_alert=True)
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📎 Upload Document/Forward", callback_data="admin_add_dump_mode_doc"))
        markup.add(types.InlineKeyboardButton("🔗 Add via URL/Text", callback_data="admin_add_dump_mode_text"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"))
        bot.edit_message_text("➕ <b>Add Dump</b>\n\nChoose how you want to add the dump (document/forward or paste a link/text).", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_add_dump_mode_doc")
    def admin_add_dump_doc_mode(call):
        user_id = call.from_user.id
        is_global_admin = False
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor(); c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
                is_global_admin = c.fetchone() is not None
        except Exception:
            is_global_admin = False
        if user_id != ADMIN_ID and not is_global_admin:
            bot.answer_callback_query(call.id, "❌ Only owner/global admin", show_alert=True)
            return
        # Set state to await a document or forwarded message
        user_states[user_id] = "awaiting_new_dump_doc"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Cancel", callback_data="admin_panel"))
        bot.edit_message_text("Send a document or forward the message that contains the dump (file or link). The bot will store the file_id or the forwarded message link.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_add_dump_mode_text")
    def admin_add_dump_text_mode(call):
        user_id = call.from_user.id
        is_global_admin = False
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor(); c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
                is_global_admin = c.fetchone() is not None
        except Exception:
            is_global_admin = False
        if user_id != ADMIN_ID and not is_global_admin:
            bot.answer_callback_query(call.id, "❌ Only owner/global admin", show_alert=True)
            return
        user_states[user_id] = "awaiting_new_dump_text"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Cancel", callback_data="admin_panel"))
        bot.edit_message_text("Paste the link or dump text now. You can also include an optional short name and price in the format: name | price_usd | url_or_text\nExample: 'MegaDump | 10 | https://...'", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "awaiting_new_dump_doc", content_types=["document", "text", "photo", "video", "animation"])
    def handle_new_dump_doc(message):
        user_id = message.from_user.id
        # Verify permission again
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor(); c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
                is_global_admin = c.fetchone() is not None
        except Exception:
            is_global_admin = False
        if user_id != ADMIN_ID and not is_global_admin:
            bot.reply_to(message, "❌ Only owner/global admin can add dumps.")
            if user_id in user_states: del user_states[user_id]
            return
        # Extract a reference for the dump: file_id if present, else forwarded message info or text
        dump_entry = {
            "id": None,
            "name": None,
            "price": 0,
            "details": None
        }
        try:
            if message.document:
                # Store file_id reference
                dump_entry['details'] = {"type": "document", "file_id": message.document.file_id, "file_name": message.document.file_name}
            elif message.photo:
                dump_entry['details'] = {"type": "photo", "file_id": message.photo[-1].file_id}
            elif message.animation:
                dump_entry['details'] = {"type": "animation", "file_id": message.animation.file_id}
            elif message.video:
                dump_entry['details'] = {"type": "video", "file_id": message.video.file_id}
            elif message.forward_from or message.forward_from_chat:
                # Store forward reference to reconstruct later
                dump_entry['details'] = {"type": "forward", "forward_from_chat": getattr(message, 'forward_from_chat', None) and getattr(message.forward_from_chat, 'id', None), "forward_message_id": getattr(message, 'forward_from_message_id', None)}
            else:
                # Might be plain text sent instead of document
                if message.text:
                    dump_entry['details'] = {"type": "text", "text": message.text}
                else:
                    dump_entry['details'] = {"type": "unknown", "raw": str(message)}

            # Load existing products data and append
            data = load_products()
            if 'dumps' not in data:
                data['dumps'] = []
            # Assign an id
            existing_ids = [p.get('id') for p in data.get('dumps', []) if isinstance(p, dict) and p.get('id') is not None]
            next_id = (max(existing_ids) + 1) if existing_ids else 1
            dump_entry['id'] = next_id
            dump_entry['name'] = message.document.file_name if message.document and message.document.file_name else f"Dump #{next_id}"
            dump_entry['price'] = 0
            data['dumps'].append(dump_entry)
            save_products(data)
            # Notify and reload via callback passed to register_other_handlers
            try:
                save_products_to_file_and_reload(data)
            except Exception:
                pass
            bot.reply_to(message, f"✅ Dump added as <b>{dump_entry['name']}</b> (id: {next_id}). Set price later from admin panel.", parse_mode="HTML")
        except Exception as e:
            bot.reply_to(message, f"Error adding dump: {e}")
        finally:
            if user_id in user_states: del user_states[user_id]

    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "awaiting_new_dump_text")
    def handle_new_dump_text(message):
        user_id = message.from_user.id
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor(); c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
                is_global_admin = c.fetchone() is not None
        except Exception:
            is_global_admin = False
        if user_id != ADMIN_ID and not is_global_admin:
            bot.reply_to(message, "❌ Only owner/global admin can add dumps.")
            if user_id in user_states: del user_states[user_id]
            return
        text = message.text or ""
        # Parse optional 'name | price | url' format
        parts = [p.strip() for p in text.split("|")]
        name = parts[0] if parts else f"Dump"
        price = 0
        details = {"type": "text", "text": text}
        if len(parts) >= 2:
            try:
                price = float(parts[1])
            except Exception:
                price = 0
        if len(parts) >= 3:
            details = {"type": "text", "text": parts[2]}

        try:
            data = load_products()
            if 'dumps' not in data:
                data['dumps'] = []
            existing_ids = [p.get('id') for p in data.get('dumps', []) if isinstance(p, dict) and p.get('id') is not None]
            next_id = (max(existing_ids) + 1) if existing_ids else 1
            entry = {"id": next_id, "name": name, "price": price, "details": details}
            data['dumps'].append(entry)
            save_products(data)
            try:
                save_products_to_file_and_reload(data)
            except Exception:
                pass
            bot.reply_to(message, f"✅ Dump added: <b>{name}</b> (id: {next_id})", parse_mode="HTML")
        except Exception as e:
            bot.reply_to(message, f"Error adding dump: {e}")
        finally:
            if user_id in user_states: del user_states[user_id]

    @bot.callback_query_handler(func=lambda call: call.data == "support")
    def support_callback(call):
        if handle_unavailable_section(bot, call, "support"):
            return
        """Displays Support menu with AI answers and in-bot live chat (no admin IDs exposed)."""
        text = (
            "🤖 **AI Support Assistant**\n\n"
            "How can I help you today? Choose a topic or start a live chat with support."
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("💳 Payment Issues", callback_data="support_topic_payment"),
            types.InlineKeyboardButton("📦 Order Problem", callback_data="support_topic_order"),
            types.InlineKeyboardButton("💰 Adding Funds", callback_data="support_topic_funds"),
            types.InlineKeyboardButton("🤔 Other", callback_data="support_topic_other")
        )
        markup.add(types.InlineKeyboardButton("🗣️ Start Live Chat", callback_data="support_start_chat"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        # Set AI query state for free text
        user_states[call.from_user.id] = "awaiting_support_query"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("support_topic_"))
    def handle_support_topic(call):
        """Handles predefined support topic buttons."""
        topic = call.data.replace("support_topic_", "")
        # We can just reuse the message handler by passing it a mock message
        mock_message = call.message
        mock_message.text = topic # Set the text to the topic name
        handle_support_query(mock_message)

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_support_query")
    def handle_support_query(message):
        """The core AI logic to answer user support questions."""
        query = message.text.lower()
        user_id = message.from_user.id
        
        # Clear the state
        if user_id in user_states:
            del user_states[user_id]

        # --- AI Knowledge Base ---
        response = ""
        if any(word in query for word in ["payment", "crypto", "paid", "approve"]):
            response = (
                "**Regarding Payments:**\n\n"
                "All crypto payments are processed manually. After you send the funds, you must click the 'I Have Paid' button. "
                "An admin will then be notified to verify your transaction.\n\n"
                f"Please ensure you are sending to the correct address: `{bot.crypto_address}`\n\n"
                "If your payment has been pending for a long time, please use the 'Contact Admins' option."
            )
        elif any(word in query for word in ["order", "item", "receive", "not working"]):
            response = (
                "**Regarding Orders:**\n\n"
                "Once your payment is approved, your item will be delivered automatically. You can check the status of all your orders in your 'Personal Area' (coming soon).\n\n"
                "If you believe there is an issue with an item you received, please use the 'Contact Admins' option and provide your **Order ID**."
            )
        elif any(word in query for word in ["funds", "balance", "wallet", "deposit"]):
            response = (
                "**Regarding Your Wallet:**\n\n"
                "You can add funds to your internal wallet via the 'Personal Area' -> 'Add Funds' button. "
                "This allows for instant purchases from the shop without waiting for payment confirmation.\n\n"
                "All fund deposits are processed with the same manual crypto approval system."
            )
        else:
            # If the AI can't answer, provide the escalation option
            response = "I'm sorry, I couldn't find a direct answer for your question. Please see below to contact a human admin."

        # --- Send the response ---
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🗣️ Contact Human Admins", callback_data="contact_admins"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        
        bot.send_message(user_id, response, reply_markup=markup, parse_mode="Markdown")

    # --- Live Support Chat (no admin ID exposure) ---
    @bot.callback_query_handler(func=lambda call: call.data == "support_start_chat")
    def support_start_chat(call):
        user_id = call.from_user.id
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            row = c.execute("SELECT session_id, status FROM support_sessions WHERE user_id = ? AND status IN ('open','assigned') ORDER BY session_id DESC LIMIT 1", (user_id,)).fetchone()
            if row:
                session_id, status = row
            else:
                c.execute("INSERT INTO support_sessions (user_id, status) VALUES (?, 'open')", (user_id,))
                conn.commit()
                session_id = c.lastrowid
        user_states[user_id] = f"support_chat_user_{session_id}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔚 End Chat", callback_data=f"support_end_{session_id}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        bot.edit_message_text(
            "💬 **Live Chat Started**\n\nA support admin will join shortly. Please type your message.",
            call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown"
        )

    @bot.message_handler(func=lambda m: isinstance(user_states.get(m.from_user.id, ''), str) and user_states.get(m.from_user.id, '').startswith("support_chat_user_"))
    def handle_user_support_chat(message):
        user_id = message.from_user.id
        state = user_states.get(user_id, '')
        try:
            session_id = int(state.split('_')[-1])
        except Exception:
            return
        # Notify all global admins about new/unassigned message
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            sess = c.execute("SELECT admin_id, status FROM support_sessions WHERE session_id = ?", (session_id,)).fetchone()
            if not sess:
                return
            admin_id, status = sess
            if not admin_id:
                # Broadcast to admins to take the chat
                admin_ids = [ADMIN_ID]
                try:
                    c2 = conn.cursor(); c2.execute("SELECT user_id FROM admins"); admin_ids += [r[0] for r in c2.fetchall()]
                except Exception:
                    pass
                text = f"🆕 New support chat from user <code>{user_id}</code> (session #{session_id}). Tap to join."
                join_markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("👋 Join Chat", callback_data=f"support_admin_join_{session_id}"))
                for aid in set(admin_ids):
                    try:
                        bot.send_message(aid, text, parse_mode="HTML", reply_markup=join_markup)
                    except Exception:
                        pass
            else:
                # Forward to assigned admin
                try:
                    bot.copy_message(admin_id, from_chat_id=message.chat.id, message_id=message.message_id)
                except Exception:
                    pass

    @bot.callback_query_handler(func=lambda call: call.data.startswith("support_admin_join_"))
    def support_admin_join(call):
        # Owner or global admins only
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor(); c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Not authorized", show_alert=True)
                    return
        try:
            session_id = int(call.data.split('_')[-1])
        except Exception:
            return
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            sess = c.execute("SELECT user_id, admin_id, status FROM support_sessions WHERE session_id = ?", (session_id,)).fetchone()
            if not sess:
                bot.answer_callback_query(call.id, "Session not found", show_alert=True)
                return
            user_id, current_admin, status = sess
            if current_admin and current_admin != call.from_user.id:
                bot.answer_callback_query(call.id, "Already assigned", show_alert=True)
                return
            c.execute("UPDATE support_sessions SET admin_id = ?, status = 'assigned', updated_at = CURRENT_TIMESTAMP WHERE session_id = ?", (call.from_user.id, session_id))
            conn.commit()
        # Notify admin and user
        bot.answer_callback_query(call.id, f"Joined chat #{session_id}")
        try:
            bot.send_message(call.from_user.id, f"✅ You joined support chat #{session_id}. Reply here to talk to the user. Send /end to close.")
            bot.send_message(user_id, "🟢 A support admin joined the chat. You can continue messaging here.")
        except Exception:
            pass
        # Put admin into chat state
        user_states[call.from_user.id] = f"support_chat_admin_{session_id}"

    @bot.message_handler(func=lambda m: isinstance(user_states.get(m.from_user.id, ''), str) and user_states.get(m.from_user.id, '').startswith("support_chat_admin_"))
    def handle_admin_support_chat(message):
        admin_id = message.from_user.id
        try:
            session_id = int(user_states[admin_id].split('_')[-1])
        except Exception:
            return
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            sess = c.execute("SELECT user_id, status FROM support_sessions WHERE session_id = ?", (session_id,)).fetchone()
            if not sess:
                return
            user_id, status = sess
        # Forward admin message to user
        try:
            bot.copy_message(user_id, from_chat_id=message.chat.id, message_id=message.message_id)
        except Exception:
            pass

    @bot.callback_query_handler(func=lambda call: call.data.startswith("support_end_"))
    def support_end_chat(call):
        try:
            session_id = int(call.data.split('_')[-1])
        except Exception:
            return
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("UPDATE support_sessions SET status = 'closed', ended_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?", (session_id,))
            conn.commit()
        # Clear states for both sides
        for uid, st in list(user_states.items()):
            if isinstance(st, str) and st.endswith(f"_{session_id}") and st.startswith("support_chat_"):
                user_states.pop(uid, None)
        # Acknowledge
        bot.answer_callback_query(call.id, "Chat ended")
        try:
            bot.edit_message_text("Chat ended.", call.message.chat.id, call.message.message_id)
        except Exception:
            pass

    @bot.callback_query_handler(func=lambda call: call.data == "rules")
    def rules_callback(call):
        text = (
            "📜 **RULES OF BUYING CARD [ CC ]**\n\n"
            "To ensure a fair and secure experience for everyone, please adhere to the following rules:\n\n"
            "💎 **Agreement:** Buying cards in our service means you automatically agree with all the stated rules.\n"
            "💎 **Validation:** When issuing the material, we provide a screenshot that the product is valid and has been checked at the time of sale.\n"
            "💎 **Usage Guarantee:** We cannot guarantee the success of using the card, as its accessibility depends on the service you are using it on. The responsibility for its use is yours.\n"
            "💎 **Responsibility:** We are not responsible for your actions with the card after purchase.\n"
            "💎 **No Training:** We do not provide advice or training on how to cash out or use the material. Remember, we sell the material itself, not training on how to realize its value.\n"
            "💎 **Validity at Sale:** From our side, we guarantee that the CC will be live and valid at the time it is delivered to you."
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    # =============================
    # ====== ADMIN PANEL LOGIC ======
    # =============================
        
    @bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
    def admin_panel_callback(call):
        user_id = call.from_user.id
        is_owner = user_id == ADMIN_ID
        is_global_admin = False
        section_admin_sections = []
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            is_global_admin = cursor.fetchone() is not None or is_owner
            cursor.execute("SELECT section FROM section_admins WHERE user_id = ?", (user_id,))
            section_admin_sections = [row[0] for row in cursor.fetchall()]
        
        if not (is_global_admin or section_admin_sections):
            bot.answer_callback_query(call.id, "❌ Access Denied! Only global or section admins can access this panel.", show_alert=True)
            return

        # Modern Admin Panel Design
        text = (
            "⚙️ <b>Admin Control Panel</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👋 Welcome, <b>{call.from_user.first_name}</b>!\n"
            f"🎭 Role: {'👑 Owner' if is_owner else '🛡️ Global Admin' if is_global_admin else '🔧 Section Admin'}\n\n"
        )
        
        if section_admin_sections and not is_global_admin:
            text += f"📋 Your sections: <b>{', '.join(section_admin_sections)}</b>\n\n"
        
        text += "Select a management category:"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        if is_global_admin:
            # 🏪 STORE MANAGEMENT
            markup.add(
                types.InlineKeyboardButton("📦 Products", callback_data="admin_products_menu"),
                types.InlineKeyboardButton("📊 Orders", callback_data="admin_orders_menu")
            )
            
            # 👥 USER MANAGEMENT
            markup.add(
                types.InlineKeyboardButton("👥 Users", callback_data="admin_users_menu"),
                types.InlineKeyboardButton("🔎 Lookup", callback_data="admin_lookup_menu")
            )
            
            # 💰 PAYMENTS & SUPPORT
            markup.add(
                types.InlineKeyboardButton("📱 Payments", callback_data="admin_payments_menu"),
                types.InlineKeyboardButton("🎯 Support", callback_data="admin_support_dashboard")
            )
            
            # 🎁 REWARDS & ENGAGEMENT
            markup.add(
                types.InlineKeyboardButton("🏆 Referrals", callback_data="admin_referrals_menu"),
                types.InlineKeyboardButton("🔑 Pro Keys", callback_data="admin_keys_menu")
            )
            
            # 📊 ANALYTICS & TOOLS
            markup.add(
                types.InlineKeyboardButton("📈 Analytics", callback_data="admin_analytics_menu"),
                types.InlineKeyboardButton("🎁 Giveaway", callback_data="admin_giveaway_menu")
            )
            
            # 🔍 SCRAPER
            markup.add(
                types.InlineKeyboardButton("🔍 Scraper", callback_data="scraper_menu"),
                types.InlineKeyboardButton("🔐 Scraper Admins", callback_data="admin_scraper_management")
            )
            
            # 👑 OWNER EXCLUSIVE
            if is_owner:
                markup.add(
                    types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
                    types.InlineKeyboardButton("🖼️ Media", callback_data="admin_media_menu")
                )
                markup.add(
                    types.InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings_menu")
                )
        # Section-specific admin buttons
        for section in section_admin_sections:
            markup.add(types.InlineKeyboardButton(
                f"📦 {section.title()} Orders", 
                callback_data=f"admin_orders_{section}"
            ))
            # Also add a direct manage-products shortcut for section admins
            markup.add(types.InlineKeyboardButton(
                f"🛠️ Manage {section.title()}",
                callback_data=f"admin_cat_menu_{section}"
            ))
        
        # Navigation
        markup.add(types.InlineKeyboardButton("🏠 Back to Main Menu", callback_data="main_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_section_management")
    def admin_section_management_callback(call):
        """Section Admin Management Menu for Global Admins"""
        user_id = call.from_user.id
        is_owner = user_id == ADMIN_ID
        is_global_admin = False
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            is_global_admin = cursor.fetchone() is not None
        
        if not (is_owner or is_global_admin):
            bot.answer_callback_query(call.id, "❌ Only owner and global admins can manage section admins", show_alert=True)
            return
        
        text = (
            "╔═══════════════════════╗\n"
            "║  ⚡ 𝗦𝗘𝗖𝗧𝗜𝗢𝗡 𝗔𝗗𝗠𝗜𝗡𝗦  ║\n"
            "╚═══════════════════════╝\n\n"
            "⚡ <b>Section Admin Management</b>\n\n"
            "Section admins have control over specific product categories.\n"
            "They can manage orders, products, and users for their assigned sections.\n\n"
            "<b>Manage section administrators:</b>"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Add Section Admin", callback_data="owner_add_section_admin"),
            types.InlineKeyboardButton("❌ Remove Section Admin", callback_data="owner_remove_section_admin")
        )
        markup.add(
            types.InlineKeyboardButton("📋 View All Section Admins", callback_data="owner_list_section_admins")
        )
        markup.add(
            types.InlineKeyboardButton("ℹ️ Section Info", callback_data="admin_info_section")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"))
        
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="HTML")

    # Scraper management removed - will be recreated
    
    @bot.callback_query_handler(func=lambda call: call.data == "admin_scraper_management")
    def admin_scraper_management_callback(call):
        """Scraper Admin Management Menu"""
        user_id = call.from_user.id
        is_owner = user_id == ADMIN_ID
        is_global_admin = False
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            is_global_admin = cursor.fetchone() is not None
        
        if not (is_owner or is_global_admin):
            bot.answer_callback_query(call.id, "❌ Only owner and global admins can manage scraper admins", show_alert=True)
            return
        
        # Get scraper admins
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, added_at FROM scraper_admins ORDER BY added_at DESC")
                scraper_admins = cursor.fetchall()
        except Exception:
            scraper_admins = []
        
        text = "🔐 <b>Scraper Admin Management</b>\n\n"
        
        if scraper_admins:
            text += f"<b>Total Scraper Admins:</b> {len(scraper_admins)}\n\n"
            for user_id_val, added_at in scraper_admins[:10]:
                text += f"• <code>{user_id_val}</code>\n"
                text += f"  Added: {added_at[:10] if added_at else 'N/A'}\n\n"
            
            if len(scraper_admins) > 10:
                text += f"... and {len(scraper_admins) - 10} more\n"
        else:
            text += "No scraper admins configured yet.\n\n"
            text += "💡 Add scraper admins to allow them to:\n"
            text += "• Configure scraper settings\n"
            text += "• Add/remove monitored groups\n"
            text += "• View scraper statistics\n"
            text += "• Control scraper operations\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➕ Add Scraper Admin", callback_data="scraper_add_admin"))
        if scraper_admins:
            markup.add(types.InlineKeyboardButton("➖ Remove Scraper Admin", callback_data="scraper_remove_admin"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")
        
        text = (
            "╔═══════════════════════╗\n"
            "║  🔍 𝗦𝗖𝗥𝗔𝗣𝗘𝗥 𝗔𝗗𝗠𝗜𝗡𝗦  ║\n"
            "╚═══════════════════════╝\n\n"
            "🔐 <b>Scraper Admin Management</b>\n\n"
            "Scraper admins have full control over the scraper system.\n"
            "They can start/stop scraper, manage groups, and configure settings.\n\n"
            "<b>Manage scraper administrators:</b>"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Add Scraper Admin", callback_data="admin_add_scraper_admin"),
            types.InlineKeyboardButton("❌ Remove Scraper Admin", callback_data="admin_remove_scraper_admin")
        )
        markup.add(
            types.InlineKeyboardButton("📋 View All Scraper Admins", callback_data="admin_list_scraper_admins")
        )
        markup.add(
            types.InlineKeyboardButton("👥 Manage User Access", callback_data="admin_scraper_user_access")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"))
        
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_add_scraper_admin")
    def admin_add_scraper_admin_callback(call):
        """Add scraper admin"""
        user_id = call.from_user.id
        is_owner = user_id == ADMIN_ID
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            is_global_admin = cursor.fetchone() is not None
        
        if not (is_owner or is_global_admin):
            bot.answer_callback_query(call.id, "❌ Access denied", show_alert=True)
            return
        
        user_states[user_id] = "awaiting_scraper_admin_add"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="admin_scraper_management"))
        
        bot.edit_message_text(
            "➕ <b>Add Scraper Admin</b>\n\n"
            "Forward a message from the user or send their user ID:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )

    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "awaiting_scraper_admin_add")
    def handle_scraper_admin_add(message):
        user_id = message.from_user.id
        if user_id not in user_states:
            return
        
        del user_states[user_id]
        
        target_id = None
        if message.forward_from:
            target_id = message.forward_from.id
        elif message.text and message.text.isdigit():
            target_id = int(message.text)
        
        if not target_id:
            bot.reply_to(message, "❌ Invalid user ID. Please try again.")
            return
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO scraper_admins (user_id, added_by) VALUES (?, ?)", (target_id, user_id))
                conn.commit()
                bot.reply_to(message, f"✅ User {target_id} added as scraper admin!")
            except sqlite3.IntegrityError:
                bot.reply_to(message, "❌ User is already a scraper admin.")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_remove_scraper_admin")
    def admin_remove_scraper_admin_callback(call):
        """Remove scraper admin"""
        user_id = call.from_user.id
        is_owner = user_id == ADMIN_ID
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            is_global_admin = cursor.fetchone() is not None
        
        if not (is_owner or is_global_admin):
            bot.answer_callback_query(call.id, "❌ Access denied", show_alert=True)
            return
        
        user_states[user_id] = "awaiting_scraper_admin_remove"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="admin_scraper_management"))
        
        bot.edit_message_text(
            "❌ <b>Remove Scraper Admin</b>\n\n"
            "Send the user ID to remove:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )

    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "awaiting_scraper_admin_remove")
    def handle_scraper_admin_remove(message):
        user_id = message.from_user.id
        if user_id not in user_states:
            return
        
        del user_states[user_id]
        
        if not message.text or not message.text.isdigit():
            bot.reply_to(message, "❌ Invalid user ID.")
            return
        
        target_id = int(message.text)
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM scraper_admins WHERE user_id = ?", (target_id,))
            if cursor.rowcount > 0:
                conn.commit()
                bot.reply_to(message, f"✅ User {target_id} removed from scraper admins.")
            else:
                bot.reply_to(message, "❌ User was not a scraper admin.")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_list_scraper_admins")
    def admin_list_scraper_admins_callback(call):
        """List all scraper admins"""
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, added_at FROM scraper_admins ORDER BY added_at DESC")
            admins = cursor.fetchall()
        
        text = "📋 <b>Scraper Admins</b>\n\n"
        if not admins:
            text += "No scraper admins found."
        else:
            for admin_id, added_at in admins:
                text += f"👤 <code>{admin_id}</code> - {added_at}\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_scraper_management"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_scraper_user_access")
    def admin_scraper_user_access_callback(call):
        """Manage user scraper access"""
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM user_scraper_access")
            total_users = cursor.fetchone()[0]
        
        text = (
            "👥 <b>Scraper User Access</b>\n\n"
            f"Total users with access: <b>{total_users}</b>\n\n"
            "Users can purchase scraper access for $10 (lifetime).\n"
            "Admins have free access automatically."
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Grant Access", callback_data="admin_grant_scraper_access"),
            types.InlineKeyboardButton("❌ Revoke Access", callback_data="admin_revoke_scraper_access")
        )
        markup.add(
            types.InlineKeyboardButton("📋 View All Users", callback_data="admin_list_scraper_users")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_scraper_management"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_grant_scraper_access")
    def admin_grant_scraper_access_callback(call):
        """Grant scraper access to user"""
        user_states[call.from_user.id] = "awaiting_grant_scraper_access"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="admin_scraper_user_access"))
        
        bot.edit_message_text(
            "➕ <b>Grant Scraper Access</b>\n\n"
            "Send the user ID to grant access:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )

    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "awaiting_grant_scraper_access")
    def handle_grant_scraper_access(message):
        user_id = message.from_user.id
        if user_id not in user_states:
            return
        
        del user_states[user_id]
        
        if not message.text or not message.text.isdigit():
            bot.reply_to(message, "❌ Invalid user ID.")
            return
        
        target_id = int(message.text)
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO user_scraper_access (user_id, expiry_date, price_paid) VALUES (?, NULL, 0.0)",
                (target_id,)
            )
            conn.commit()
        
        bot.reply_to(message, f"✅ Scraper access granted to user {target_id}!")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_revoke_scraper_access")
    def admin_revoke_scraper_access_callback(call):
        """Revoke scraper access from user"""
        user_states[call.from_user.id] = "awaiting_revoke_scraper_access"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="admin_scraper_user_access"))
        
        bot.edit_message_text(
            "❌ <b>Revoke Scraper Access</b>\n\n"
            "Send the user ID to revoke access:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )

    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "awaiting_revoke_scraper_access")
    def handle_revoke_scraper_access(message):
        user_id = message.from_user.id
        if user_id not in user_states:
            return
        
        del user_states[user_id]
        
        if not message.text or not message.text.isdigit():
            bot.reply_to(message, "❌ Invalid user ID.")
            return
        
        target_id = int(message.text)
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_scraper_access WHERE user_id = ?", (target_id,))
            if cursor.rowcount > 0:
                conn.commit()
                bot.reply_to(message, f"✅ Scraper access revoked from user {target_id}.")
            else:
                bot.reply_to(message, "❌ User doesn't have scraper access.")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_list_scraper_users")
    def admin_list_scraper_users_callback(call):
        """List all users with scraper access"""
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, purchased_at, price_paid FROM user_scraper_access ORDER BY purchased_at DESC LIMIT 20")
            users = cursor.fetchall()
        
        text = "📋 <b>Users with Scraper Access</b>\n\n"
        if not users:
            text += "No users with access found."
        else:
            for uid, purchased, price in users:
                text += f"👤 <code>{uid}</code>\n"
                text += f"💰 Paid: ${price:.2f}\n"
                text += f"📅 {purchased}\n━━━━━━\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_scraper_user_access"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_giveaway_menu")
    def admin_giveaway_menu_callback(call):
        """Displays the giveaway management menu."""
        text = "🎁 <b>Giveaway Management</b>\n\nSelect an option:"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🏆 Pick Winner", callback_data="admin_pick_winner"),
            types.InlineKeyboardButton("🎪 New Contest", callback_data="admin_new_contest"),
            types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel")
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_pick_winner")
    def admin_pick_winner_callback(call):
        """Picks a random winner from all registered users."""
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username FROM users ORDER BY RANDOM() LIMIT 1")
            winner = cursor.fetchone()
        
        if winner:
            winner_id, winner_name = winner
            text = f"🏆 <b>Winner!</b>\n\nCongratulations to <b>{winner_name}</b> (ID: <code>{winner_id}</code>)!"
        else:
            text = "No users found to pick a winner from."

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Giveaway", callback_data="admin_giveaway_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_new_contest")
    def admin_new_contest_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Access Denied! Only the owner can start a new contest.", show_alert=True)
            return
        
        user_states[call.from_user.id] = "awaiting_contest_message"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Cancel", callback_data="admin_giveaway_menu"))
        bot.edit_message_text("🎪 <b>New Contest</b>\n\nPlease send the announcement message for the new contest. This will be broadcast to all users.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_contest_message")
    def handle_contest_message(message):
        if message.from_user.id != ADMIN_ID:
            return

        del user_states[message.from_user.id]
        
        bot.send_message(message.chat.id, "⏳ Announcing the new contest to all users...")

        def _broadcast_contest():
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users WHERE COALESCE(is_active, 1) = 1")
                users = cursor.fetchall()

            sent_count = 0
            failed_count = 0
            for user in users:
                user_id = user[0]
                try:
                    bot.send_message(user_id, f"🎉 <b>New Contest!</b> 🎉\n\n{message.text}", parse_mode="HTML")
                    sent_count += 1
                except Exception as e:
                    print(f"Failed to send contest announcement to {user_id}: {e}")
                    failed_count += 1
                time.sleep(0.1)

            bot.send_message(message.chat.id, f"✅ Contest announced!\n\nSent: {sent_count}\nFailed: {failed_count}")

        threading.Thread(target=_broadcast_contest).start()

    @bot.callback_query_handler(func=lambda call: call.data == "admin_users_menu")
    def admin_users_menu_callback(call):
        """Displays the user management menu."""
        text = "👥 <b>User Management</b>\n\nSelect an option:"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📋 All Users", callback_data="admin_all_users"),
            types.InlineKeyboardButton("💰 Top Balances", callback_data="admin_top_balances"),
            types.InlineKeyboardButton("🏆 Top Referrers", callback_data="admin_top_referrers"),
            types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel")
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_all_users")
    def admin_all_users_callback(call):
        """Displays a list of all registered users."""
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, balance_usd, join_date FROM users ORDER BY join_date DESC LIMIT 20")
            users = cursor.fetchall()
        
        text = "📋 <b>All Users (Recent 20)</b>\n\n"
        if not users:
            text += "No users found."
        else:
            for user in users:
                text += f"<b>ID:</b> <code>{user[0]}</code>\n"
                text += f"<b>Name:</b> {user[1] or 'N/A'}\n"
                text += f"<b>Balance:</b> ${user[2] if user[2] is not None else 0:.2f}\n"
                text += f"<b>Joined:</b> {user[3]}\n"
                text += "━━━━━━━━━━━━\n"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Users", callback_data="admin_users_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_products_menu")
    def admin_products_menu_callback(call):
        """Displays the product management menu."""
        text = "📦 <b>Product Management</b>\n\nSelect a category to manage:"
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        # Dynamically create buttons from CATEGORY_NAMES
        buttons = [
            types.InlineKeyboardButton(name, callback_data=f"admin_cat_menu_{key}")
            for key, name in CATEGORY_NAMES.items()
        ]
        
        # Arrange buttons in rows of 2
        for i in range(0, len(buttons), 2):
            if i + 1 < len(buttons):
                markup.row(buttons[i], buttons[i+1])
            else:
                markup.row(buttons[i])

        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        safe_edit_message(bot, call.message.chat.id, call.message.message_id, text, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_orders_menu")
    def admin_orders_menu_callback(call):
        """Displays the order management menu."""
        text = "📊 <b>Order Management</b>\n\nSelect an option:"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📋 Recent Orders", callback_data="admin_recent_orders"),
            types.InlineKeyboardButton("⏳ Pending Orders", callback_data="admin_pending_orders"),
            types.InlineKeyboardButton("🔍 Search Orders", callback_data="admin_search_orders"),
            types.InlineKeyboardButton("📈 Sales Report", callback_data="admin_sales_report"),
            types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel")
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_recent_orders")
    def admin_recent_orders_callback(call):
        """Displays the 10 most recent orders."""
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT order_id, user_id, item_name, price_usd, payment_status, creation_date FROM orders ORDER BY creation_date DESC LIMIT 10")
            orders = cursor.fetchall()
        
        text = "📋 <b>Recent Orders</b>\n\n"
        if not orders:
            text += "No orders found."
        else:
            for order in orders:
                text += f"<b>ID:</b> <code>{order[0]}</code>\n"
                text += f"<b>User:</b> <code>{order[1]}</code>\n"
                text += f"<b>Item:</b> {order[2]}\n"
                text += f"<b>Price:</b> ${order[3]}\n"
                text += f"<b>Status:</b> {order[4]}\n"
                text += f"<b>Date:</b> {order[5]}\n"
                text += "━━━━━━━━━━━━\n"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Orders", callback_data="admin_orders_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_pending_orders")
    def admin_pending_orders_callback(call):
        """Displays orders with pending statuses (updated to new status constants)."""
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT order_id, user_id, item_name, price_usd, payment_status, creation_date FROM orders WHERE payment_status IN ('PENDING_PAYMENT','PENDING_APPROVAL') ORDER BY creation_date DESC LIMIT 10")
            orders = cursor.fetchall()
        
        text = "⏳ <b>Pending Orders</b>\n\n"
        if not orders:
            text += "No pending orders found."
        else:
            for order in orders:
                text += f"<b>ID:</b> <code>{order[0]}</code>\n"
                text += f"<b>User:</b> <code>{order[1]}</code>\n"
                text += f"<b>Item:</b> {order[2]}\n"
                text += f"<b>Price:</b> ${order[3]}\n"
                text += f"<b>Status:</b> {order[4]}\n"
                text += f"<b>Date:</b> {order[5]}\n"
                text += "━━━━━━━━━━━━\n"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Orders", callback_data="admin_orders_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    def create_coming_soon_handler(callback_data, back_button_cb):
        """Factory to create a 'Coming Soon' handler."""
        @bot.callback_query_handler(func=lambda call: call.data == callback_data)
        def coming_soon_handler(call):
            text = "🚧 <b>Coming Soon!</b>\n\nThis feature is currently under development."
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=back_button_cb))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
        return coming_soon_handler

    # NOTE: Support Center dashboard handler removed here to allow the canonical implementation
    # in perfect_support.py to be the single source of truth. This avoids duplicate registration
    # conflicts for callback data 'admin_support_dashboard'.

    # Real implementations replacing earlier placeholders

    def _is_global_or_owner(uid: int):
        if uid == ADMIN_ID:
            return True
        with sqlite3.connect(DB_NAME) as _c:
            cur = _c.cursor(); cur.execute("SELECT 1 FROM admins WHERE user_id = ?", (uid,))
            return cur.fetchone() is not None

    # ----- Lookup -----
    @bot.callback_query_handler(func=lambda call: call.data == "admin_lookup_menu")
    def admin_lookup_menu(call):
        if not _is_global_or_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Not authorized", show_alert=True)
            return
        user_states[call.from_user.id] = "awaiting_lookup_query"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"))
        bot.edit_message_text("🔎 <b>User Lookup</b>\n\nSend a <code>user_id</code> or @username to view details.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "awaiting_lookup_query")
    def handle_lookup_query(message):
        if not _is_global_or_owner(message.from_user.id):
            return
        query = message.text.strip()
        del user_states[message.from_user.id]
        target_id = None
        username = None
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            if query.startswith('@'):
                username = query[1:]
                c.execute("SELECT user_id, username, balance_usd, referral_count, join_date, cc_credits, is_pro FROM users WHERE username = ?", (username,))
            else:
                try:
                    target_id = int(query)
                except Exception:
                    bot.reply_to(message, "❌ Invalid input. Send numeric ID or @username.")
                    return
                c.execute("SELECT user_id, username, balance_usd, referral_count, join_date, cc_credits, is_pro FROM users WHERE user_id = ?", (target_id,))
            row = c.fetchone()
            if not row:
                bot.reply_to(message, "No user found.")
                return
            uid, uname, bal, refs, join_date, credits, is_pro = row
            c.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (uid,))
            order_count = c.fetchone()[0]
        text = (
            "👤 <b>User Profile</b>\n\n"
            f"<b>ID:</b> <code>{uid}</code>\n"
            f"<b>Username:</b> {uname or '-'}\n"
            f"<b>Balance:</b> ${bal:.2f}\n"
            f"<b>Referrals:</b> {refs}\n"
            f"<b>Orders:</b> {order_count}\n"
            f"<b>CC Credits:</b> {credits}{' (∞ PRO)' if is_pro else ''}\n"
            f"<b>Joined:</b> {join_date}\n"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)

    # ----- Broadcast -----
    @bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
    def admin_broadcast(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only", show_alert=True)
            return
        user_states[call.from_user.id] = "awaiting_broadcast_message"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Cancel", callback_data="admin_panel"))
        bot.edit_message_text("📢 <b>Broadcast Message</b>\n\nSend the message text (Markdown/HTML allowed).", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "awaiting_broadcast_message")
    def handle_broadcast_message(message):
        if message.from_user.id != ADMIN_ID:
            return
        content = message.text
        user_states[message.from_user.id] = f"broadcast_confirm::{content}"
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Send", callback_data="broadcast_send"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")
        )
        bot.send_message(message.chat.id, "Preview:\n\n" + content, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data in ["broadcast_send", "broadcast_cancel"])
    def broadcast_decision(call):
        state = user_states.get(call.from_user.id, '')
        if not state.startswith("broadcast_confirm::"):
            bot.answer_callback_query(call.id, "Expired", show_alert=True)
            return
        content = state.replace("broadcast_confirm::", "")
        if call.data == "broadcast_cancel":
            user_states.pop(call.from_user.id, None)
            bot.edit_message_text("Broadcast canceled.", call.message.chat.id, call.message.message_id)
            return
        # send
        bot.edit_message_text("🚀 Starting broadcast...", call.message.chat.id, call.message.message_id)
        user_states.pop(call.from_user.id, None)
        def _do_broadcast(msg_id, chat_id):
            sent = 0; failed = 0
            try:
                with sqlite3.connect(DB_NAME) as conn:
                    cur = conn.cursor(); cur.execute("SELECT user_id FROM users WHERE COALESCE(is_active,1)=1")
                    targets = [r[0] for r in cur.fetchall()]
            except Exception as e:
                bot.send_message(chat_id, f"DB error: {e}")
                return
            for idx, uid in enumerate(targets, start=1):
                try:
                    bot.send_message(uid, content, parse_mode="HTML")
                    sent += 1
                except Exception:
                    failed += 1
                if idx % 50 == 0:
                    try:
                        bot.edit_message_text(f"📢 Broadcasting... Sent: {sent} | Failed: {failed}", chat_id, msg_id)
                    except Exception:
                        pass
                time.sleep(0.03)
            try:
                bot.edit_message_text(f"✅ Broadcast finished. Sent: {sent} | Failed: {failed}", chat_id, msg_id)
            except Exception:
                bot.send_message(chat_id, f"✅ Broadcast finished. Sent: {sent} | Failed: {failed}")
        threading.Thread(target=_do_broadcast, args=(call.message.message_id, call.message.chat.id), daemon=True).start()

    # ----- Top balances & referrers -----
    @bot.callback_query_handler(func=lambda call: call.data == "admin_top_balances")
    def admin_top_balances(call):
        if not _is_global_or_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Not authorized", show_alert=True)
            return
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor(); c.execute("SELECT user_id, username, balance_usd FROM users ORDER BY balance_usd DESC LIMIT 10")
            rows = c.fetchall()
        text = "💰 <b>Top Balances</b>\n\n" + ("No users." if not rows else "")
        for i, r in enumerate(rows, start=1):
            text += f"{i}. <code>{r[0]}</code> {r[1] or ''} - ${r[2]:.2f}\n"
        markup = types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_users_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_top_referrers")
    def admin_top_referrers(call):
        if not _is_global_or_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Not authorized", show_alert=True)
            return
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor(); c.execute("SELECT user_id, username, referral_count FROM users ORDER BY referral_count DESC LIMIT 10")
            rows = c.fetchall()
        text = "🏆 <b>Top Referrers</b>\n\n" + ("No users." if not rows else "")
        for i, r in enumerate(rows, start=1):
            text += f"{i}. <code>{r[0]}</code> {r[1] or ''} - {r[2]} refs\n"
        markup = types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_users_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # ----- Referrals summary -----
    @bot.callback_query_handler(func=lambda call: call.data == "admin_referrals_menu")
    def admin_referrals_menu(call):
        if not _is_global_or_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Not authorized", show_alert=True)
            return
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor();
            c.execute("SELECT COUNT(*) FROM users")
            total_users = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM users WHERE referral_count > 0")
            ref_users = c.fetchone()[0]
            c.execute("SELECT SUM(referral_count) FROM users")
            total_refs = c.fetchone()[0] or 0
            c.execute("SELECT user_id, username, referral_count FROM users ORDER BY referral_count DESC LIMIT 5")
            top5 = c.fetchall()
        adoption = (ref_users / total_users * 100) if total_users else 0
        text = (
            "🔗 <b>Referrals Overview</b>\n\n"
            f"<b>Total Users:</b> {total_users}\n"
            f"<b>Total Referrals:</b> {total_refs}\n"
            f"<b>Users With >=1 Referral:</b> {ref_users} ({adoption:.1f}%)\n\n"
            "<b>Top 5:</b>\n"
        )
        for r in top5:
            text += f"• <code>{r[0]}</code> {r[1] or ''} - {r[2]}\n"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🏆 Full Top Referrers", callback_data="admin_top_referrers"),
            types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # ----- Keys menu integration -----
    @bot.callback_query_handler(func=lambda call: call.data == "admin_keys_menu")
    def admin_keys_menu(call):
        if not _is_global_or_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Not authorized", show_alert=True)
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🔑 Manage Pro Keys", callback_data="manage_pro_keys"),
            types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")
        )
        bot.edit_message_text("🔑 <b>Pro Keys</b>\n\nManage or generate keys.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # ----- Media manager -----
    @bot.callback_query_handler(func=lambda call: call.data == "admin_media_menu")
    def admin_media_menu(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only", show_alert=True)
            return
        counts = get_media_pool_counts()
        text = "🖼️ <b>Media Pools</b>\n\n" + "\n".join([f"<b>{k}:</b> {v}" for k, v in counts.items()])
        markup = types.InlineKeyboardMarkup(row_width=2)
        for kind in counts.keys():
            markup.add(types.InlineKeyboardButton(f"🗑️ {kind}", callback_data=f"media_clear_kind_{kind}"))
        # Add button to allow owner to add new media to pools
        markup.add(types.InlineKeyboardButton("➕ Add", callback_data="media_add"))
        markup.add(types.InlineKeyboardButton("🧹 Clear All", callback_data="media_clear_all"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("media_clear_kind_") or call.data == "media_clear_all")
    def media_clear_actions(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only", show_alert=True)
            return
        if call.data == "media_clear_all":
            clear_media_pool()
        else:
            kind = call.data.replace("media_clear_kind_", "")
            clear_media_pool(kind)
        bot.answer_callback_query(call.id, "Cleared")
        admin_media_menu(call)

    # ----- Media add flow -----
    @bot.callback_query_handler(func=lambda call: call.data == "media_add")
    def media_add_menu(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only", show_alert=True)
            return
        # Present choices of pools to add to
        kinds = ["welcome", "success", "reject", "pending", "any"]
        markup = types.InlineKeyboardMarkup(row_width=2)
        for k in kinds:
            markup.add(types.InlineKeyboardButton(k.title(), callback_data=f"media_add_kind_{k}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_media_menu"))
        bot.edit_message_text("➕ <b>Add GIF to Pool</b>\n\nChoose a pool, then send an animated GIF to add.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("media_add_kind_"))
    def media_add_kind(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only", show_alert=True)
            return
        kind = call.data.replace("media_add_kind_", "")
        # Set awaiting state so the next animation message will be treated as the GIF to add
        user_states[call.from_user.id] = f"awaiting_add_gif_{kind}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Cancel", callback_data="admin_media_menu"))
        bot.edit_message_text(f"Send an animated GIF now to add to the '<b>{kind}</b>' pool. It will be saved when you send it.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id, "").startswith("awaiting_add_gif_"), content_types=["animation"])
    def handle_admin_add_gif(message):
        state = user_states.get(message.from_user.id, "")
        if not state:
            return
        kind = state.replace("awaiting_add_gif_", "")
        if not message.animation:
            bot.reply_to(message, "Please send an animated GIF to add.")
            return
        file_id = message.animation.file_id
        try:
            added = add_gif_to_pool(file_id, kind)
            # Get updated counts
            counts = get_media_pool_counts()
            bot.reply_to(message, f"✅ Added GIF to '<b>{kind}</b>' pool. Total now: {counts.get(kind, 0)}", parse_mode="HTML")
        except Exception as e:
            bot.reply_to(message, f"Error adding GIF: {e}")
        finally:
            # Clear state
            if message.from_user.id in user_states:
                del user_states[message.from_user.id]

    # Status manager and related handlers removed

    # ----- Manage Admins (list & remove) -----
    @bot.callback_query_handler(func=lambda call: call.data == "admin_manage_admins")
    def admin_manage_admins(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only", show_alert=True)
            return
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor(); c.execute("SELECT user_id, added_at FROM admins ORDER BY added_at DESC")
            rows = c.fetchall()
        text = "🧩 <b>Global Admins</b>\n\n" + ("None" if not rows else "")
        markup = types.InlineKeyboardMarkup(row_width=2)
        for uid, added_at in rows:
            if uid == ADMIN_ID:
                continue
            markup.add(types.InlineKeyboardButton(f"❌ {uid}", callback_data=f"remove_admin_{uid}"))
            text += f"<code>{uid}</code> (added { (added_at or '')[:10] })\n"
        markup.add(types.InlineKeyboardButton("👑 Owner Panel", callback_data="owner_panel"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("remove_admin_"))
    def remove_admin_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only", show_alert=True)
            return
        try:
            target_id = int(call.data.replace("remove_admin_", ""))
            if target_id == ADMIN_ID:
                bot.answer_callback_query(call.id, "Cannot remove owner", show_alert=True)
                return
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor(); c.execute("DELETE FROM admins WHERE user_id = ?", (target_id,)); conn.commit()
            bot.answer_callback_query(call.id, "Removed")
            admin_manage_admins(call)
        except Exception as e:
            bot.answer_callback_query(call.id, f"Err: {e}", show_alert=True)

    # ----- Giveaway menu -----
    # (Moved above)

    # ----- Analytics (sales/users/products) -----
    @bot.callback_query_handler(func=lambda call: call.data == "analytics_sales")
    def analytics_sales(call):
        if not _is_global_or_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Not authorized", show_alert=True)
            return
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor();
            c.execute("SELECT COUNT(*), COALESCE(SUM(price_usd),0) FROM orders")
            total_orders, total_rev = c.fetchone()
            c.execute("SELECT DATE(creation_date), COALESCE(SUM(price_usd),0) FROM orders WHERE creation_date >= DATE('now','-7 day') GROUP BY DATE(creation_date) ORDER BY DATE(creation_date)")
            last7 = c.fetchall()
            c.execute("SELECT item_name, COUNT(*) c FROM orders GROUP BY item_name ORDER BY c DESC LIMIT 5")
            top_items = c.fetchall()
        text = "📊 <b>Sales Analytics</b>\n\n"
        text += f"<b>Total Orders:</b> {total_orders}\n<b>Total Revenue:</b> ${total_rev:.2f}\n\n"
        text += "<b>Last 7 Days:</b>\n" + ("None\n" if not last7 else "\n".join([f"{d}: ${amt:.2f}" for d, amt in last7]) + "\n")
        text += "\n<b>Top Items:</b>\n" + ("None" if not top_items else "\n".join([f"{nm} ({cnt})" for nm, cnt in top_items]))
        markup = types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_analytics_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "analytics_users")
    def analytics_users(call):
        if not _is_global_or_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Not authorized", show_alert=True)
            return
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor();
            c.execute("SELECT COUNT(*) FROM users")
            total_users = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM users WHERE join_date >= DATE('now','-7 day')")
            new_week = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM users WHERE COALESCE(is_active,1)=1")
            active = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM users WHERE referral_count > 0")
            ref_used = c.fetchone()[0]
        text = (
            "👥 <b>User Analytics</b>\n\n"
            f"<b>Total Users:</b> {total_users}\n"
            f"<b>New (7d):</b> {new_week}\n"
            f"<b>Active:</b> {active}\n"
            f"<b>Referral Adoption:</b> { (ref_used/total_users*100) if total_users else 0:.1f}%\n"
        )
        markup = types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_analytics_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "analytics_products")
    def analytics_products(call):
        if not _is_global_or_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Not authorized", show_alert=True)
            return
        # Load products JSON directly
        try:
            from config import PRODUCTS_FILE
            with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
                pdata = json.load(f)
        except Exception:
            pdata = {}
        counts = {k: len(v) if isinstance(v, list) else 0 for k, v in pdata.items()}
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:8]
        text = "🛒 <b>Product Analytics</b>\n\n" + ("No data" if not counts else "\n".join([f"{k}: {v}" for k, v in sorted_counts]))
        markup = types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_analytics_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # ----- Personal Area (user panel) -----
    # (Defined above at line 1347)

    # ═══════════════════════════════════════════════
    # 🆕 NEW ENHANCED FEATURES
    # ═══════════════════════════════════════════════
    
    @bot.callback_query_handler(func=lambda call: call.data == "user_stats")
    def user_stats_callback(call):
        """Show user statistics and achievements."""
        user_id = call.from_user.id
        bot.send_chat_action(user_id, 'typing')
        
        try:
            from database import get_user_details
            user_details = get_user_details(user_id)
            
            if not user_details:
                bot.answer_callback_query(call.id, "❌ User data not found", show_alert=True)
                return
            
            # Calculate user activity stats
            import datetime
            current_date = datetime.datetime.now()
            join_date = user_details.get('created_at', current_date.isoformat())
            
            try:
                join_datetime = datetime.datetime.fromisoformat(join_date)
                days_active = (current_date - join_datetime).days
            except:
                days_active = 0
            
            # Create stats message
            text = f"""📊 <b>Your Statistics</b>

👤 <b>Account Information</b>
• User ID: <code>{user_details['user_id']}</code>
• Username: {user_details['username']}
• Days Active: {days_active} days
• Account Status: ✅ Active

💰 <b>Financial Stats</b>
• Current Balance: <code>${user_details['balance']:.2f}</code>
• Total Spent: <code>$0.00</code> (Coming Soon)
• Orders Completed: 0 (Coming Soon)

👥 <b>Referral Stats</b>
• Total Referrals: {user_details['referral_count']}
• Earnings from Referrals: <code>$0.00</code> (Coming Soon)
• Active Referrals: 0 (Coming Soon)
"""
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="user_panel"))
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error loading stats: {str(e)[:50]}", show_alert=True)

    # ----- Keys menu integration -----
    @bot.callback_query_handler(func=lambda call: call.data == "admin_keys_menu")
    def admin_keys_menu(call):
        if not _is_global_or_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Not authorized", show_alert=True)
            return
        
        try:
            import json
            orders = json.load(open("scraper_orders.json", 'r')) if os.path.exists("scraper_orders.json") else []
            
            pending = [o for o in orders if o.get('status') in ['pending', 'claimed']]
            
            if not pending:
                text = "📦 <b>Pending Orders</b>\n\n❌ No pending orders"
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="admin_scraper_pending"))
                markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_scraper_menu"))
            else:
                text = f"📦 <b>Pending Orders ({len(pending)})</b>\n\n"
                
                for order in pending[:10]:  # Show first 10
                    status_icon = "⏳" if order['status'] == 'pending' else "💰"
                    text += (
                        f"{status_icon} <b>Order #{order['order_id'][-8:]}</b>\n"
                        f"User: {order['username']} (ID: <code>{order['user_id']}</code>)\n"
                        f"Plan: {order['plan_name']} - ${order['price']}\n"
                        f"Status: {order['status'].title()}\n"
                        f"Created: {order['created_at'][:10]}\n"
                        "━━━━━━━━━━━━\n"
                    )
                
                if len(pending) > 10:
                    text += f"\n<i>Showing 10 of {len(pending)} orders</i>"
                
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("🔄 Refresh", callback_data="admin_scraper_pending")
                )
                markup.add(
                    types.InlineKeyboardButton("⬅️ Back", callback_data="admin_scraper_menu")
                )
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {str(e)[:50]}", show_alert=True)

    # ----- Keys menu integration -----
    @bot.callback_query_handler(func=lambda call: call.data == "admin_keys_menu")
    def admin_keys_menu(call):
        if not _is_global_or_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Not authorized", show_alert=True)
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🔑 Manage Pro Keys", callback_data="manage_pro_keys"),
            types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")
        )
        bot.edit_message_text("🔑 <b>Pro Keys</b>\n\nManage or generate keys.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # Status manager and related handlers removed

    # ----- Analytics (sales/users/products) -----
    @bot.callback_query_handler(func=lambda call: call.data == "analytics_sales")
    def analytics_sales(call):
        if not _is_global_or_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Not authorized", show_alert=True)
            return
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor();
            c.execute("SELECT COUNT(*), COALESCE(SUM(price_usd),0) FROM orders")
            total_orders, total_rev = c.fetchone()
            c.execute("SELECT DATE(creation_date), COALESCE(SUM(price_usd),0) FROM orders WHERE creation_date >= DATE('now','-7 day') GROUP BY DATE(creation_date) ORDER BY DATE(creation_date)")
            last7 = c.fetchall()
            c.execute("SELECT item_name, COUNT(*) c FROM orders GROUP BY item_name ORDER BY c DESC LIMIT 5")
            top_items = c.fetchall()
        text = "📊 <b>Sales Analytics</b>\n\n"
        text += f"<b>Total Orders:</b> {total_orders}\n<b>Total Revenue:</b> ${total_rev:.2f}\n\n"
        text += "<b>Last 7 Days:</b>\n" + ("None\n" if not last7 else "\n".join([f"{d}: ${amt:.2f}" for d, amt in last7]) + "\n")
        text += "\n<b>Top Items:</b>\n" + ("None" if not top_items else "\n".join([f"{nm} ({cnt})" for nm, cnt in top_items]))
        markup = types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_analytics_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "analytics_users")
    def analytics_users(call):
        if not _is_global_or_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Not authorized", show_alert=True)
            return
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor();
            c.execute("SELECT COUNT(*) FROM users")
            total_users = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM users WHERE join_date >= DATE('now','-7 day')")
            new_week = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM users WHERE COALESCE(is_active,1)=1")
            active = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM users WHERE referral_count > 0")
            ref_used = c.fetchone()[0]
        text = (
            "👥 <b>User Analytics</b>\n\n"
            f"<b>Total Users:</b> {total_users}\n"
            f"<b>New (7d):</b> {new_week}\n"
            f"<b>Active:</b> {active}\n"
            f"<b>Referral Adoption:</b> { (ref_used/total_users*100) if total_users else 0:.1f}%\n"
        )
        markup = types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_analytics_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "analytics_products")
    def analytics_products(call):
        if not _is_global_or_owner(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Not authorized", show_alert=True)
            return
        # Load products JSON directly
        try:
            from config import PRODUCTS_FILE
            with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
                pdata = json.load(f)
        except Exception:
            pdata = {}
        counts = {k: len(v) if isinstance(v, list) else 0 for k, v in pdata.items()}
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:8]
        text = "🛒 <b>Product Analytics</b>\n\n" + ("No data" if not counts else "\n".join([f"{k}: {v}" for k, v in sorted_counts]))
        markup = types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_analytics_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # (admin_user_chat remains placeholder for future full implementation)

    @bot.callback_query_handler(func=lambda call: call.data == "admin_payments_menu")
    def admin_payments_menu_callback(call):
        """Displays the payments management menu."""
        text = "📱 <b>Payments Management</b>\n\nSelect an option:"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("⏳ Pending Payments", callback_data="admin_pending_payments"),
            types.InlineKeyboardButton("✅ Approved Payments", callback_data="admin_approved_payments"),
            types.InlineKeyboardButton("❌ Rejected Payments", callback_data="admin_rejected_payments"),
            types.InlineKeyboardButton("🧹 Reject ALL Pending (⚠️)", callback_data="admin_reject_all_pending_confirm"),
            types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel")
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_reject_all_pending_confirm")
    def admin_reject_all_pending_confirm(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only", show_alert=True); return
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor(); c.execute("SELECT COUNT(*) FROM orders WHERE payment_status IN ('PENDING_PAYMENT','PENDING_APPROVAL')")
            pending_count = c.fetchone()[0]
        text = (
            "🧹 <b>Reject ALL Pending Payments</b>\n\n"
            f"This will mark <b>{pending_count}</b> pending orders as <code>REJECTED</code>.\n"
            "Use only for mass clean-up (spam / expired payments).\n\n"
            "Are you absolutely sure?"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Yes, Reject All", callback_data="admin_reject_all_pending_execute"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="admin_payments_menu")
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_reject_all_pending_execute")
    def admin_reject_all_pending_execute(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only", show_alert=True); return
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("UPDATE orders SET payment_status='REJECTED' WHERE payment_status IN ('PENDING_PAYMENT','PENDING_APPROVAL')")
                affected = c.rowcount
                conn.commit()
            bot.answer_callback_query(call.id, f"Rejected {affected} orders")
            # Return to payments menu
            admin_payments_menu_callback(call)
        except Exception as e:
            bot.answer_callback_query(call.id, f"Err: {e}", show_alert=True)

    # admin_user_chat deliberately left as placeholder (not yet implemented chat routing UI)
    # (Removed obsolete 'Coming Soon' payment handlers; real implementations below.)

    @bot.callback_query_handler(func=lambda call: call.data == "admin_pending_payments")
    def admin_pending_payments_callback(call):
        """Displays payments awaiting confirmation or approval."""
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT order_id, user_id, item_name, price_usd, payment_status, creation_date FROM orders WHERE payment_status IN ('PENDING_PAYMENT','PENDING_APPROVAL') ORDER BY creation_date DESC LIMIT 20")
            orders = cursor.fetchall()
        
        text = "⏳ <b>Pending Payments</b>\n\n"
        if not orders:
            text += "No pending payments found."
        else:
            for order in orders:
                text += f"<b>ID:</b> <code>{order[0]}</code>\n"
                text += f"<b>User:</b> <code>{order[1]}</code>\n"
                text += f"<b>Item:</b> {order[2]}\n"
                text += f"<b>Price:</b> ${order[3]}\n"
                text += f"<b>Status:</b> {order[4]}\n"
                text += f"<b>Date:</b> {order[5]}\n"
                text += "━━━━━━━━━━━━\n"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Payments", callback_data="admin_payments_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_approved_payments")
    def admin_approved_payments_callback(call):
        """Displays orders that have been completed (delivered or deposited)."""
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT order_id, user_id, item_name, price_usd, payment_status, creation_date FROM orders WHERE payment_status = 'COMPLETED' ORDER BY creation_date DESC LIMIT 20")
            orders = cursor.fetchall()
        
        text = "✅ <b>Approved Payments</b>\n\n"
        if not orders:
            text += "No approved payments found."
        else:
            for order in orders:
                text += f"<b>ID:</b> <code>{order[0]}</code>\n"
                text += f"<b>User:</b> <code>{order[1]}</code>\n"
                text += f"<b>Item:</b> {order[2]}\n"
                text += f"<b>Price:</b> ${order[3]}\n"
                text += f"<b>Status:</b> {order[4]}\n"
                text += f"<b>Date:</b> {order[5]}\n"
                text += "━━━━━━━━━━━━\n"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Payments", callback_data="admin_payments_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_rejected_payments")
    def admin_rejected_payments_callback(call):
        """Displays orders with rejected status."""
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT order_id, user_id, item_name, price_usd, payment_status, creation_date FROM orders WHERE payment_status = 'REJECTED' ORDER BY creation_date DESC LIMIT 20")
            orders = cursor.fetchall()
        
        text = "❌ <b>Rejected Payments</b>\n\n"
        if not orders:
            text += "No rejected payments found."
        else:
            for order in orders:
                text += f"<b>ID:</b> <code>{order[0]}</code>\n"
                text += f"<b>User:</b> <code>{order[1]}</code>\n"
                text += f"<b>Item:</b> {order[2]}\n"
                text += f"<b>Price:</b> ${order[3]}\n"
                text += f"<b>Status:</b> {order[4]}\n"
                text += f"<b>Date:</b> {order[5]}\n"
                text += "━━━━━━━━━━━━\n"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Payments", callback_data="admin_payments_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # ---- Settings Menu (owner only) ----
    @bot.callback_query_handler(func=lambda call: call.data == "admin_settings_menu")
    def admin_settings_menu(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only", show_alert=True); return
        text = (
            "⚙️ <b>Settings</b>\n\n"
            "Quick shortcuts to management tools:\n"
            "• Media Manager (GIF pools)\n"
            "• Manage Admins & Pro Keys\n\n"
            "Planned additions: pricing rules, auto-expiry, audit exports."
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🖼️ Media Manager", callback_data="admin_media_menu"),
            types.InlineKeyboardButton("🔑 Pro Keys", callback_data="admin_keys_menu"),
            types.InlineKeyboardButton("🧩 Manage Admins", callback_data="admin_manage_admins")
        )
        # Log utilities (view & clear) owner-only
        markup.add(
            types.InlineKeyboardButton("📄 View Log Tail", callback_data="admin_view_log"),
            types.InlineKeyboardButton("🧹 Clear Logs", callback_data="admin_clear_logs_confirm")
        )
        # Maintenance submenu
        markup.add(types.InlineKeyboardButton("🛠️ Maintenance", callback_data="admin_maintenance_menu"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # --- Maintenance Menu ---
    @bot.callback_query_handler(func=lambda call: call.data == "admin_maintenance_menu")
    def admin_maintenance_menu(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only", show_alert=True); return
        text = (
            "🛠️ <b>Maintenance Utilities</b>\n\n"
            "Danger zone actions for testing / reset.\n"
            "<b>Actions:</b>\n"
            "• Wipe only pending payments (PENDING_*)\n"
            "• Reset ALL wallet balances to 0\n"
            "• Delete ALL orders (irreversible)\n"
            "• Full payment reset (orders + enhanced tables)\n"
            "• Clear logs (existing option)\n\n"
            "<i>Use carefully. These cannot be undone.</i>"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🧹 Wipe Pending Payments", callback_data="maint_wipe_pending_confirm"),
            types.InlineKeyboardButton("💣 Delete ALL Orders", callback_data="maint_delete_orders_confirm"),
            types.InlineKeyboardButton("💼 Reset ALL Balances", callback_data="maint_reset_balances_confirm"),
            types.InlineKeyboardButton("♻️ Full Payment Reset", callback_data="maint_full_payment_reset_confirm"),
            types.InlineKeyboardButton("🧹 Clear Logs", callback_data="admin_clear_logs_confirm"),
            types.InlineKeyboardButton("⬅️ Back to Settings", callback_data="admin_settings_menu")
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    def _confirm_action(call, action_key, description):
        text = f"⚠️ <b>Confirm Action</b>\n\n{description}\n\nAre you sure?"
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Yes", callback_data=f"maint_exec_{action_key}"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="admin_maintenance_menu")
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.endswith("_confirm") and call.data.startswith("maint_"))
    def maint_confirm_router(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only", show_alert=True); return
        mapping = {
            "maint_wipe_pending_confirm": ("wipe_pending", "This will delete all orders in statuses PENDING_PAYMENT / PENDING_APPROVAL."),
            "maint_delete_orders_confirm": ("delete_orders", "This will DELETE every row in orders table."),
            "maint_reset_balances_confirm": ("reset_balances", "This will set every user's wallet balance to 0.0."),
            "maint_full_payment_reset_confirm": ("full_payment_reset", "This will delete orders + enhanced payment tracking tables + payment communications.")
        }
        key = call.data
        if key in mapping:
            action_key, desc = mapping[key]
            _confirm_action(call, action_key, desc)
        else:
            bot.answer_callback_query(call.id, "Unknown action", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("maint_exec_"))
    def maint_execute(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only", show_alert=True); return
        action = call.data.replace("maint_exec_", "")
        result_msg = ""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                if action == "wipe_pending":
                    c.execute("DELETE FROM orders WHERE payment_status IN ('PENDING_PAYMENT','PENDING_APPROVAL')")
                    affected = c.rowcount; conn.commit()
                    result_msg = f"Deleted {affected} pending orders."
                elif action == "delete_orders":
                    c.execute("DELETE FROM orders"); affected = c.rowcount; conn.commit()
                    result_msg = f"Deleted ALL orders ({affected})."
                elif action == "reset_balances":
                    c.execute("UPDATE users SET balance_usd = 0.0"); affected = c.rowcount; conn.commit()
                    result_msg = f"Reset balances for {affected} users."
                elif action == "full_payment_reset":
                    c.execute("DELETE FROM payment_communications")
                    c.execute("DELETE FROM enhanced_payments")
                    c.execute("DELETE FROM orders")
                    conn.commit()
                    result_msg = "Cleared orders + enhanced payment tracking tables."
                else:
                    bot.answer_callback_query(call.id, "Unknown exec", show_alert=True); return
        except Exception as e:
            result_msg = f"Error: {e}"
        # Show result and return to maintenance menu
        try:
            bot.answer_callback_query(call.id, result_msg[:190], show_alert=True)
        except Exception:
            pass
        try:
            admin_maintenance_menu(call)
        except Exception:
            bot.send_message(call.message.chat.id, result_msg)

    # --- Enhanced Payment Support Handlers ---
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_chat_user_"))
    def admin_chat_user(call):
        """Admin chat with user functionality"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Admin access only", show_alert=True)
            return
        
        user_id = int(call.data.replace("admin_chat_user_", ""))
        
        try:
            # Get user info
            user_info = bot.get_chat(user_id)
            user_name = f"{user_info.first_name or 'Unknown'} {user_info.last_name or ''}".strip()
            username = f"@{user_info.username}" if user_info.username else "No username"
        except:
            user_name = "Unknown User"
            username = "No username"
        
        text = (
            f"💬 <b>Admin Chat with User</b>\n\n"
            f"👤 <b>User:</b> {user_name} ({username})\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code>\n\n"
            f"Choose an action to communicate with this user:"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📤 Send Message", callback_data=f"admin_send_msg_{user_id}"),
            types.InlineKeyboardButton("📋 View User Orders", callback_data=f"admin_user_orders_{user_id}"),
            types.InlineKeyboardButton("💰 View User Balance", callback_data=f"admin_user_balance_{user_id}"),
            types.InlineKeyboardButton("🔔 Send Notification", callback_data=f"admin_notify_user_{user_id}"),
            types.InlineKeyboardButton("⬅️ Back", callback_data="admin_payments_menu")
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_payment_menu_"))
    def admin_payment_menu(call):
        """Admin payment management menu for specific payment"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Admin access only", show_alert=True)
            return
        
        payment_id = call.data.replace("admin_payment_menu_", "")
        
        # Get payment details from database
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                
                # Check both enhanced_payments and orders tables
                enhanced_data = cursor.execute('''
                    SELECT ep.user_id, ep.status, ep.created_at, o.item_name, o.price_usd
                    FROM enhanced_payments ep
                    LEFT JOIN orders o ON ep.payment_id = o.order_id
                    WHERE ep.payment_id = ?
                ''', (payment_id,)).fetchone()
                
                if not enhanced_data:
                    # Try regular orders table
                    order_data = cursor.execute('''
                        SELECT user_id, payment_status, creation_date, item_name, price_usd
                        FROM orders WHERE order_id = ?
                    ''', (payment_id,)).fetchone()
                    
                    if order_data:
                        user_id, status, created_at, item_name, price = order_data
                    else:
                        bot.answer_callback_query(call.id, "Payment not found", show_alert=True)
                        return
                else:
                    user_id, status, created_at, item_name, price = enhanced_data
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {str(e)}", show_alert=True)
            return
        
        # Get user info
        try:
            user_info = bot.get_chat(user_id)
            user_name = f"{user_info.first_name or 'Unknown'} {user_info.last_name or ''}".strip()
            username = f"@{user_info.username}" if user_info.username else "No username"
        except:
            user_name = "Unknown User"
            username = "No username"
        
        text = (
            f"💳 <b>Payment Management</b>\n\n"
            f"📄 <b>Payment ID:</b> <code>{payment_id}</code>\n"
            f"👤 <b>User:</b> {user_name} ({username})\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
            f"🛍️ <b>Item:</b> {item_name or 'Unknown'}\n"
            f"💰 <b>Amount:</b> ${price or 'Unknown'}\n"
            f"📅 <b>Created:</b> {created_at or 'Unknown'}\n"
            f"🔄 <b>Status:</b> {status or 'Unknown'}\n\n"
            f"Choose an action for this payment:"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        if status in ['pending_review', 'screenshot_uploaded', 'PENDING_APPROVAL']:
            markup.add(
                types.InlineKeyboardButton("✅ Approve", callback_data=f"quick_approve_{payment_id}"),
                types.InlineKeyboardButton("❌ Reject", callback_data=f"enhanced_quick_reject_{payment_id}")
            )
            markup.add(
                types.InlineKeyboardButton("💬 Approve + Message", callback_data=f"approve_with_remarks_{payment_id}"),
                types.InlineKeyboardButton("📝 Reject + Reason", callback_data=f"reject_with_remarks_{payment_id}")
            )
        
        markup.add(
            types.InlineKeyboardButton("🔍 View Details", callback_data=f"view_payment_details_{payment_id}"),
            types.InlineKeyboardButton("💬 Chat with User", callback_data=f"admin_chat_user_{user_id}")
        )
        markup.add(
            types.InlineKeyboardButton("⬅️ Back to Payments", callback_data="admin_payments_menu")
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")
    
    # Helper handlers for admin chat functionality
    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_send_msg_"))
    def admin_send_message_prompt(call):
        """Prompt admin to send message to user"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Admin access only", show_alert=True)
            return

        user_id = int(call.data.replace("admin_send_msg_", ""))
        user_states[call.from_user.id] = f"admin_sending_msg_{user_id}"
        bot.answer_callback_query(call.id)
        prompt = (
            f"✉️ <b>Send Message to User</b>\n\n"
            f"Enter the message you want to send to <code>{user_id}</code>.\n\n"
            f"<i>Type your message and send. Use /cancel to abort.</i>"
        )
        bot.send_message(call.message.chat.id, prompt, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id, '').startswith('admin_sending_msg_'))
    def handle_admin_send_message(message):
        """Handle admin's message to user"""
        state = user_states.get(message.from_user.id, '')
        if not state:
            return
        user_id = int(state.replace('admin_sending_msg_', ''))
        if message.text and message.text.strip().lower() == '/cancel':
            del user_states[message.from_user.id]
            bot.reply_to(message, "❌ Message sending cancelled.")
            return
        try:
            bot.send_message(user_id, f"📩 <b>Message from Admin</b>\n\n{message.text}", parse_mode="HTML")
            bot.reply_to(message, f"✅ Message sent to user <code>{user_id}</code>.", parse_mode="HTML")
        except Exception as e:
            bot.reply_to(message, f"❌ Failed to send message: {e}")
        del user_states[message.from_user.id]
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_user_orders_"))
    def admin_view_user_orders(call):
        """View user's order history"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Admin access only", show_alert=True)
            return
        
        user_id = int(call.data.replace("admin_user_orders_", ""))
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            orders = cursor.execute('''
                SELECT order_id, item_name, price_usd, payment_status, creation_date
                FROM orders WHERE user_id = ?
                ORDER BY creation_date DESC LIMIT 10
            ''', (user_id,)).fetchall()
        
        if not orders:
            text = f"📋 <b>User Orders</b>\n\n🆔 User ID: <code>{user_id}</code>\n\n❌ No orders found."
        else:
            text = f"📋 <b>User Orders</b>\n\n🆔 User ID: <code>{user_id}</code>\n\n"
            for order in orders[:5]:  # Show first 5
                order_id, item_name, price, status, date = order
                text += f"📄 <code>{order_id}</code>\n🛍️ {item_name}\n💰 ${price} • {status}\n📅 {date}\n\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=f"admin_chat_user_{user_id}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_user_balance_"))
    def admin_view_user_balance(call):
        """View user's balance"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Admin access only", show_alert=True)
            return
        
        user_id = int(call.data.replace("admin_user_balance_", ""))
        
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            balance = cursor.execute('SELECT balance_usd FROM users WHERE user_id = ?', (user_id,)).fetchone()
        
        balance_amount = balance[0] if balance else 0.0
        
        text = (
            f"💰 <b>User Balance</b>\n\n"
            f"🆔 User ID: <code>{user_id}</code>\n"
            f"💵 Balance: <b>${balance_amount:.2f} USD</b>\n\n"
            f"Options:"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Add Funds", callback_data=f"admin_add_funds_{user_id}"),
            types.InlineKeyboardButton("➖ Remove Funds", callback_data=f"admin_remove_funds_{user_id}")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=f"admin_chat_user_{user_id}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_notify_user_"))
    def admin_notify_user(call):
        """Send notification to user"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Admin access only", show_alert=True)
            return
        
        user_id = call.data.replace("admin_notify_user_", "")
        bot.answer_callback_query(call.id, "Notification feature coming soon!", show_alert=True)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_add_funds_") or call.data.startswith("admin_remove_funds_"))
    def admin_balance_modification(call):
        """Handle balance modification requests"""
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Admin access only", show_alert=True)
            return
        
        bot.answer_callback_query(call.id, "Balance modification coming soon!", show_alert=True)

    # --- Log viewing (tail) ---
    @bot.callback_query_handler(func=lambda call: call.data == "admin_view_log")
    def admin_view_log(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only", show_alert=True); return
        log_path = "bot.log"
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()[-40:]
            content = ''.join(lines).strip()
            if not content:
                content = "(log file empty)"
            # Escape HTML special chars for safe display
            import html
            safe_content = html.escape(content)
            text = f"📄 <b>bot.log (last {len(lines)} lines)</b>\n\n<pre>{safe_content}</pre>"
        except FileNotFoundError:
            text = "📄 <b>bot.log</b> not found."
        except Exception as e:
            text = f"⚠️ Failed to read log: {e}"
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🔄 Refresh", callback_data="admin_view_log"),
            types.InlineKeyboardButton("🧹 Clear", callback_data="admin_clear_logs_confirm")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_settings_menu"))
        # If content length exceeds Telegram max (~4096) trim center
        if len(text) > 3900:
            # Keep head and tail around 1500 each
            head = safe_content[:1500]
            tail = safe_content[-1500:]
            trimmed = head + "\n...<trimmed>...\n" + tail
            text = f"📄 <b>bot.log (trimmed)</b>\n\n<pre>{trimmed}</pre>"
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
        except Exception:
            try:
                bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
            except Exception:
                pass

    # --- Clear logs confirmation ---
    @bot.callback_query_handler(func=lambda call: call.data == "admin_clear_logs_confirm")
    def admin_clear_logs_confirm(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only", show_alert=True); return
        text = (
            "🧹 <b>Clear Logs</b>\n\n"
            "This will truncate the <code>bot.log</code> file.\n"
            "Are you sure you want to proceed?"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Yes, Clear", callback_data="admin_clear_logs"),
            types.InlineKeyboardButton("❌ Cancel", callback_data="admin_settings_menu")
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="HTML")

    # --- Perform log clearing ---
    @bot.callback_query_handler(func=lambda call: call.data == "admin_clear_logs")
    def admin_clear_logs(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only", show_alert=True); return
        log_path = "bot.log"
        try:
            open(log_path, 'w').close()
            bot.answer_callback_query(call.id, "Logs cleared")
        except Exception as e:
            bot.answer_callback_query(call.id, f"Err: {e}", show_alert=True)
        # Return to settings menu
        try:
            admin_settings_menu(call)
        except Exception:
            pass

    # ═══════════════════════════════════════════════
    # 🆕 NEW ENHANCED FEATURES
    # ═══════════════════════════════════════════════
    
    @bot.callback_query_handler(func=lambda call: call.data == "user_stats")
    def user_stats_callback(call):
        """Show user statistics and achievements."""
        user_id = call.from_user.id
        bot.send_chat_action(user_id, 'typing')
        
        try:
            from database import get_user_details
            user_details = get_user_details(user_id)
            
            if not user_details:
                bot.answer_callback_query(call.id, "❌ User data not found", show_alert=True)
                return
            
            # Calculate user activity stats
            import datetime
            current_date = datetime.datetime.now()
            join_date = user_details.get('created_at', current_date.isoformat())
            
            try:
                join_datetime = datetime.datetime.fromisoformat(join_date)
                days_active = (current_date - join_datetime).days
            except:
                days_active = 0
            
            # Create stats message
            text = f"""📊 <b>Your Statistics</b>

👤 <b>Account Information</b>
• User ID: <code>{user_details['user_id']}</code>
• Username: {user_details['username']}
• Days Active: {days_active} days
• Account Status: ✅ Active

💰 <b>Financial Stats</b>
• Current Balance: <code>${user_details['balance']:.2f}</code>
• Total Spent: <code>$0.00</code> (Coming Soon)
• Orders Completed: 0 (Coming Soon)

👥 <b>Referral Stats</b>
• Total Referrals: {user_details['referral_count']}
• Earnings from Referrals: <code>$0.00</code> (Coming Soon)
• Active Referrals: 0 (Coming Soon)

🏆 <b>Achievements</b>
{"🥉 New Member" if days_active < 7 else "🥈 Regular User" if days_active < 30 else "🥇 Veteran User"}
"""
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Refresh Stats", callback_data="user_stats"))
            markup.add(types.InlineKeyboardButton("⬅️ Back to Profile", callback_data="personal_area"))
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                 reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error loading stats: {str(e)[:50]}", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data == "referral_info")
    def referral_info_callback(call):
        """Show detailed referral program information."""
        text = """🎯 <b>Referral Program</b>

💰 <b>How it works:</b>
1️⃣ Share your unique referral link
2️⃣ Friends join using your link
3️⃣ You earn rewards for each referral!

🎁 <b>Rewards Structure:</b>
• 1-10 referrals: 5% bonus on all purchases
• 11-25 referrals: 10% bonus + $5 credit
• 26-50 referrals: 15% bonus + $15 credit
• 50+ referrals: 20% bonus + $50 credit

📈 <b>Additional Benefits:</b>
• Priority customer support
• Early access to new products
• Exclusive discount codes
• Monthly bonus payments

💡 <b>Pro Tips:</b>
• Share on social media for maximum reach
• Help your referrals with their first purchase
• Active referrals earn you more rewards!

<i>Start sharing your link and watch your rewards grow! 🚀</i>"""
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔗 Copy My Link", callback_data="copy_referral_link"))
        markup.add(types.InlineKeyboardButton("📊 My Referrals", callback_data="user_stats"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Profile", callback_data="personal_area"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "account_settings")
    def account_settings_callback(call):
        """Show account settings menu."""
        text = """⚙️ <b>Account Settings</b>

Manage your account preferences and settings below:

🔔 <b>Notifications</b>
• Order updates: ✅ Enabled
• Promotional messages: ✅ Enabled
• Security alerts: ✅ Enabled

🛡️ <b>Security</b>
• Two-factor authentication: ❌ Disabled
• Login notifications: ✅ Enabled

📱 <b>Preferences</b>
• Language: English 🇺🇸
• Timezone: Auto-detect
• Currency: USD ($)

<i>More settings coming soon!</i>"""
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🔔 Notifications", callback_data="settings_notifications"),
            types.InlineKeyboardButton("🛡️ Security", callback_data="settings_security")
        )
        markup.add(
            types.InlineKeyboardButton("📱 Preferences", callback_data="settings_preferences"),
            types.InlineKeyboardButton("🆘 Help", callback_data="support")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Profile", callback_data="personal_area"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "copy_referral_link")
    def copy_referral_link_callback(call):
        """Show referral link for easy copying.""" 
        user_id = call.from_user.id
        try:
            from database import get_user_details
            user_details = get_user_details(user_id)
            
            if user_details:
                bot_username = bot.get_me().username
                referral_link = f"https://t.me/{bot_username}?start={user_details['referral_code']}"
                
                bot.answer_callback_query(
                    call.id, 
                    f"📋 Link copied!\n{referral_link}", 
                    show_alert=True
                )
            else:
                bot.answer_callback_query(call.id, "❌ Could not get referral link", show_alert=True)
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)[:50]}", show_alert=True)

