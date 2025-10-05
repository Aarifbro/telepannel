import threading
import time
from telebot import types
import sqlite3
import json
import random
from config import DB_NAME, ADMIN_ID
from database import get_user_details, load_products, save_products, get_user_balance, update_user_balance
from helpers import add_gif_to_pool, get_media_pool_counts, clear_media_pool, send_random_animation
from status_handler import handle_unavailable_section

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
    "bins": "BINs",
    "ready_ccs": "Ready CCs",
    "gift_cards": "Gift Cards",
    "rdp": "RDPs",
    "methods": "Methods",
    "method_bins": "BINs + Methods",
    "other": "Other Items",
    "dumps": "Dumps",
    "hacks": "Hacks",
    "phishing_kits": "Phishing Kits"
}

# Categories where media/link-based items are NOT allowed via admin add; only JSON text is accepted
RESTRICTED_MEDIA_CATEGORIES = {"bins", "ready_ccs", "gift_cards"}

def register_other_handlers(bot, user_states, get_products_from_cache, save_products_to_file_and_reload):
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
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("💬 User Chat", callback_data="owner_user_chat"),
            types.InlineKeyboardButton("➕ Add Global Admin", callback_data="owner_add_admin"),
            types.InlineKeyboardButton("➖ Remove Global Admin", callback_data="owner_remove_admin"),
            types.InlineKeyboardButton("👥 List Global Admins", callback_data="owner_list_admins"),
            types.InlineKeyboardButton("➕ Add Section Admin", callback_data="owner_add_section_admin"),
            types.InlineKeyboardButton("➖ Remove Section Admin", callback_data="owner_remove_section_admin"),
            types.InlineKeyboardButton("👥 List Section Admins", callback_data="owner_list_section_admins"),
            types.InlineKeyboardButton("🎛️ Button Status Manager", callback_data="status_manager"),
            types.InlineKeyboardButton(" Bot Stats", callback_data="owner_bot_stats"),
            types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")
        )
        bot.edit_message_text("👑 <b>Owner Panel</b>\n\nManage global and section-based admins. Section admins can only manage their assigned section (e.g., Hacks).", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # Section Admin Management
    @bot.callback_query_handler(func=lambda call: call.data == "owner_add_section_admin")
    def owner_add_section_admin_prompt(call):
        user_states[call.from_user.id] = "awaiting_new_section_admin_id"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_panel"))
        bot.edit_message_text("Send the <b>User ID</b> and <b>Section</b> (e.g., hacks) to assign, separated by a space.\nExample: <code>123456789 hacks</code>", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_new_section_admin_id")
    def owner_add_section_admin(message):
        try:
            parts = message.text.strip().split()
            user_id = int(parts[0])
            section = parts[1].lower()
        except Exception:
            bot.send_message(message.chat.id, "❌ Invalid format. Please send: <code>UserID section</code>", parse_mode="HTML")
            return
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM section_admins WHERE user_id = ? AND section = ?", (user_id, section))
            if cursor.fetchone():
                bot.send_message(message.chat.id, f"User is already an admin for section <b>{section}</b>.", parse_mode="HTML")
                return
            cursor.execute("INSERT INTO section_admins (user_id, section, added_by) VALUES (?, ?, ?)", (user_id, section, message.from_user.id))
            conn.commit()
        bot.send_message(message.chat.id, f"✅ User <code>{user_id}</code> added as admin for section <b>{section}</b>.", parse_mode="HTML")
        del user_states[message.from_user.id]

    @bot.callback_query_handler(func=lambda call: call.data == "owner_remove_section_admin")
    def owner_remove_section_admin_prompt(call):
        user_states[call.from_user.id] = "awaiting_remove_section_admin_id"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_panel"))
        bot.edit_message_text("Send the <b>User ID</b> and <b>Section</b> to remove, separated by a space.\nExample: <code>123456789 hacks</code>", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_remove_section_admin_id")
    def owner_remove_section_admin(message):
        try:
            parts = message.text.strip().split()
            user_id = int(parts[0])
            section = parts[1].lower()
        except Exception:
            bot.send_message(message.chat.id, "❌ Invalid format. Please send: <code>UserID section</code>", parse_mode="HTML")
            return
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM section_admins WHERE user_id = ? AND section = ?", (user_id, section))
            conn.commit()
        bot.send_message(message.chat.id, f"✅ User <code>{user_id}</code> removed from section <b>{section}</b> admins.", parse_mode="HTML")
        del user_states[message.from_user.id]

    @bot.callback_query_handler(func=lambda call: call.data == "owner_list_section_admins")
    def owner_list_section_admins(call):
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, section, added_at FROM section_admins ORDER BY added_at DESC")
            admins = cursor.fetchall()
        text = "<b>Section Admins:</b>\n"
        if not admins:
            text += "No section admins found."
        else:
            for a in admins:
                text += f"<b>ID:</b> <code>{a[0]}</code> | <b>Section:</b> {a[1]} | <b>Added:</b> {a[2]}\n"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Owner Panel", callback_data="owner_panel"))
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
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="owner_panel"))
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
        # Loop through the products using enumerate to get both the index and the item data.
        for index, item in enumerate(products):
            item_name = item.get("name")
            price = item.get("price")
            # The callback data is lightweight, containing only the category and the item's index.
            callback_data = f"buy_idx_{category_key}_{index}"
            markup.add(types.InlineKeyboardButton(f"🛒 {item_name} - ${price}", callback_data=callback_data))
        
        # Add a consistent "Back" button to every product menu for easy navigation.
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        text = f"🎁 **{title}**\n\nPlease select a product to purchase from the list below."
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

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
        
        # Construct the detailed message for the user.
        text = f"""👤 **Personal Area**

This is your personal dashboard where you can find your information, balance, and track your referrals.

**Name:** `{user_details['username']}`
**User ID:** `{user_details['user_id']}`
**Balance:** `${user_details['balance']:.2f}`
**Total Referrals:** `{user_details['referral_count']}`

**Your Referral Link:**
`{referral_link}`

Share this unique link with your friends. Every time someone starts the bot using your link, your referral count will increase. Special bonuses may be available for top referrers in the future!
"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        # Wallet actions
        markup.add(
            types.InlineKeyboardButton("💰 Add Funds", callback_data="add_funds"),
            types.InlineKeyboardButton("💳 Balance History", callback_data="balance_history")
        )
        # Back
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    # Alias: Open Personal Area when user taps "My Profile" button
    @bot.callback_query_handler(func=lambda call: call.data == "my_profile")
    def my_profile_alias(call):
        return personal_area_callback(call)

    @bot.callback_query_handler(func=lambda call: call.data == "balance_history")
    def balance_history_callback(call):
        """Show last 10 balance-related transactions (deposits + wallet purchases)."""
        user_id = call.from_user.id
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT order_id, item_name, price_usd, payment_method, payment_status, creation_date
                FROM orders
                WHERE user_id = ? AND (item_name = 'Wallet Deposit' OR payment_method = 'WALLET')
                ORDER BY creation_date DESC
                LIMIT 10
                """,
                (user_id,)
            )
            rows = cursor.fetchall()
        text = "<b>💳 Balance History</b>\n\n"
        if not rows:
            text += "No balance activity yet."
        else:
            text += "<code>Type | Amount | Status | Date | Order</code>\n" + ("-"*42) + "\n"
            for oid, name, amount, method, status, created in rows:
                if name == 'Wallet Deposit':
                    typ = 'Deposit'
                    amt = f"+${int(amount) if amount else 0}"
                else:
                    typ = 'Purchase'
                    amt = f"-${int(amount) if amount else 0}"
                date_short = created[:10] if created else "-"
                text += f"<code>{typ}</code> | <code>{amt}</code> | <code>{status}</code> | <code>{date_short}</code> | <code>{oid}</code>\n"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Profile", callback_data="personal_area"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "add_funds")
    def add_funds_callback(call):
        """Bitcoin-only payment interface for wallet deposits."""
        text = (
            "🪙 <b>Add Funds to Your Wallet - Bitcoin Only</b>\n\n"
            "💰 <b>Payment Method:</b> Bitcoin (BTC) Only\n"
            "⚡ <b>Network:</b> Bitcoin Mainnet\n"
            "🔒 <b>Security:</b> All payments verified manually\n"
            "📱 <b>Process:</b> Send BTC → Upload Screenshot → Manual Approval\n\n"
            "<b>Quick Amounts:</b>"
        )
        markup = types.InlineKeyboardMarkup(row_width=3)
        amounts = [10, 25, 50, 100, 200, 500]
        buttons = [types.InlineKeyboardButton(f"${amt}", callback_data=f"deposit_{amt}") for amt in amounts]
        for i in range(0, len(buttons), 3):
            markup.row(*buttons[i:i+3])
        markup.add(types.InlineKeyboardButton("💳 Custom Amount", callback_data="deposit_custom"))
        markup.add(types.InlineKeyboardButton("ℹ️ Payment Details", callback_data="payment_info"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Personal Area", callback_data="personal_area"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "payment_info")
    def payment_info_callback(call):
        """Shows detailed payment information for Bitcoin transactions."""
        from config import CRYPTO_ADDRESS
        text = (
            "🪙 <b>Bitcoin Payment Information</b>\n\n"
            "💳 <b>Accepted Cryptocurrency:</b> Bitcoin (BTC) Only\n"
            "🌐 <b>Network:</b> Bitcoin Mainnet\n"
            "⚡ <b>Confirmations Required:</b> 1+ confirmations\n\n"
            "📍 <b>Deposit Address:</b>\n"
            f"<code>{CRYPTO_ADDRESS}</code>\n\n"
            "⚠️ <b>IMPORTANT INSTRUCTIONS:</b>\n"
            "1️⃣ Only send Bitcoin (BTC) to this address\n"
            "2️⃣ Include your Payment ID in the transaction memo\n"
            "3️⃣ Upload a screenshot of your transaction\n"
            "4️⃣ Wait for manual verification (usually 1-24 hours)\n\n"
            "🚫 <b>DO NOT SEND:</b>\n"
            "• Other cryptocurrencies (ETH, USDT, etc.)\n"
            "• Test network transactions\n"
            "• Amounts less than $5 USD equivalent\n\n"
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
    
    @bot.callback_query_handler(func=lambda call: call.data == "method_menu")
    def method_menu(call):
        create_dynamic_product_menu(call, "methods")
    
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
            "💳 <b>Ready CC:</b> Pre-loaded credit cards\n"
            "🎛️ <b>Custom CC:</b> Generate cards by specifications\n"
            "🏦 <b>Enter Your BIN:</b> Generate CC from your BIN"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("💳 Ready CC", callback_data="ready_cc_menu"),
            types.InlineKeyboardButton("🎛️ Custom CC", callback_data="custom_cc_menu"), 
            types.InlineKeyboardButton("🏦 Enter Your BIN", callback_data="enter_bin_menu")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "ready_cc_menu")
    def ready_cc_menu(call):
        """Shows ready-made credit cards from products.json"""
        create_dynamic_product_menu(call, "ready_ccs")

    @bot.callback_query_handler(func=lambda call: call.data == "custom_cc_menu")
    def custom_cc_menu(call):
        """Shows custom CC generation interface"""
        text = (
            "🎛️ <b>Custom Credit Card Generator</b>\n\n"
            "Generate custom credit cards with your specifications:\n\n"
            "💰 <b>Price:</b> $25 per card\n"
            "🔧 <b>Options:</b> Country, Bank, Type, Level\n"
            "⚡ <b>Generated instantly</b> upon payment"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎯 Start Custom Generation", callback_data="start_custom_cc"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to CC Shop", callback_data="cc_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "enter_bin_menu")
    def enter_bin_menu(call):
        """Shows BIN entry interface"""
        user_states[call.from_user.id] = "awaiting_bin_input"
        
        text = (
            "🏦 <b>Generate CC from Your BIN</b>\n\n"
            "Enter a 6-8 digit BIN number to generate credit cards:\n\n"
            "💰 <b>Price:</b> $40 per card\n"
            "🎯 <b>Generated from your BIN</b>\n"
            "⚡ <b>Instant delivery</b> after payment\n\n"
            "Please enter your BIN number:"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Cancel", callback_data="cc_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "start_custom_cc")
    def start_custom_cc_generation(call):
        """Starts the custom CC generation process"""
        # This should integrate with existing custom CC logic
        # For now, let's create a simple interface
        text = (
            "🎛️ <b>Custom CC Configuration</b>\n\n"
            "Configure your custom credit card:\n\n"
            "🌍 <b>Country:</b> Any available\n"
            "🏦 <b>Bank:</b> Any available\n" 
            "💳 <b>Type:</b> VISA/Mastercard/etc\n"
            "⭐ <b>Level:</b> Classic/Gold/Platinum\n\n"
            "💰 <b>Final Price:</b> $25"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💳 Buy Custom CC - $25", callback_data="buy_dyn_customcc_25~None~None~None~None"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="custom_cc_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_bin_input")
    def handle_bin_input(message):
        """Handles BIN input from user"""
        try:
            bin_number = message.text.strip()
            
            # Validate BIN format
            if not bin_number.isdigit() or len(bin_number) < 6 or len(bin_number) > 8:
                bot.reply_to(message, "❌ Invalid BIN format. Please enter a 6-8 digit BIN number.")
                return
            
            # Clear user state
            del user_states[message.from_user.id]
            
            # Show payment option for BIN-based CC
            text = (
                f"🏦 <b>Generate CC from BIN</b>\n\n"
                f"🔢 <b>BIN:</b> {bin_number}\n"
                f"💰 <b>Price:</b> $40\n"
                f"⚡ <b>Delivery:</b> Instant after payment\n\n"
                f"Proceed with payment?"
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(f"💳 Buy CC from BIN - $40", callback_data=f"buy_dyn_frombin_{bin_number}"))
            markup.add(types.InlineKeyboardButton("⬅️ Back to CC Shop", callback_data="cc_menu"))
            
            bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")
            
        except Exception as e:
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
        create_dynamic_product_menu(call, "dumps")

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
        text = """📜 **RULES OF BUYING CARD [ CC ]**

To ensure a fair and secure experience for everyone, please adhere to the following rules:

💎 **Agreement:** Buying cards in our service means you automatically agree with all the stated rules.
💎 **Validation:** When issuing the material, we provide a screenshot that the product is valid and has been checked at the time of sale.
💎 **Usage Guarantee:** We cannot guarantee the success of using the card, as its accessibility depends on the service you are using it on. The responsibility for its use is yours.
💎 **Responsibility:** We are not responsible for your actions with the card after purchase.
💎 **No Training:** We do not provide advice or training on how to cash out or use the material. Remember, we sell the material itself, not training on how to realize its value.
💎 **Validity at Sale:** From our side, we guarantee that the CC will be live and valid at the time it is delivered to you.
"""
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
            # 🏪 STORE MANAGEMENT 🏪
            markup.add(
                types.InlineKeyboardButton("📦 Products", callback_data="admin_products_menu"),
                types.InlineKeyboardButton("📊 Orders", callback_data="admin_orders_menu")
            )
            
            # 👥 USER MANAGEMENT 👥
            markup.add(
                types.InlineKeyboardButton("👥 Users", callback_data="admin_users_menu"),
                types.InlineKeyboardButton("🔎 Lookup", callback_data="admin_lookup_menu")
            )
            markup.add(
                types.InlineKeyboardButton("💬 User Chat", callback_data="admin_user_chat"),
                types.InlineKeyboardButton("📱 Payments", callback_data="admin_payments_menu")
            )
            
            # 💬 SUPPORT SYSTEM 💬
            markup.add(
                types.InlineKeyboardButton("🎯 Support Center", callback_data="admin_support_dashboard")
            )
            
            # 🎁 REWARDS & KEYS 🎁
            markup.add(
                types.InlineKeyboardButton("🏆 Referrals", callback_data="admin_referrals_menu"),
                types.InlineKeyboardButton("🔑 Pro Keys", callback_data="admin_keys_menu")
            )
            
            # 🎮 SPECIAL FEATURES 🎮
            markup.add(
                types.InlineKeyboardButton("🎁 Giveaway", callback_data="admin_giveaway_menu"),
                types.InlineKeyboardButton("📊 Analytics", callback_data="admin_analytics_menu")
            )
            
            if is_owner:
                # 👑 OWNER EXCLUSIVE 👑
                markup.add(
                    types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast_menu"),
                    types.InlineKeyboardButton("🖼️ Media", callback_data="admin_media_menu")
                )
                markup.add(
                    types.InlineKeyboardButton("🧩 Admins", callback_data="admin_manage_admins"),
                    types.InlineKeyboardButton("🎛️ Status", callback_data="status_manager")
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
        
        # Navigation
        markup.add(types.InlineKeyboardButton("🏠 Back to Main Menu", callback_data="main_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # ===== ADMIN SUB-MENUS =====
    
    @bot.callback_query_handler(func=lambda call: call.data == "admin_products_menu")
    def admin_products_menu(call):
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return
        
        text = (
            "📦 <b>Product Management</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Manage all store products and categories:\n\n"
            "🛍️ <b>Add Products:</b> Add new items to categories\n"
            "📋 <b>View Products:</b> Browse current inventory\n"
            "✏️ <b>Edit Products:</b> Modify existing items\n"
            "🗑️ <b>Delete Products:</b> Remove items from store\n"
            "📊 <b>Category Stats:</b> View category statistics"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Add Product", callback_data="admin_manage_products"),
            types.InlineKeyboardButton("📋 View All", callback_data="admin_view_products")
        )
        markup.add(
            types.InlineKeyboardButton("✏️ Edit Product", callback_data="admin_edit_products"),
            types.InlineKeyboardButton("🗑️ Delete Product", callback_data="admin_delete_products")
        )
        markup.add(
            types.InlineKeyboardButton("📊 Category Stats", callback_data="admin_product_stats"),
            types.InlineKeyboardButton("🔄 Bulk Operations", callback_data="admin_bulk_products")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_orders_menu")
    def admin_orders_menu(call):
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return
        
        text = (
            "📊 <b>Order Management</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Track and manage all customer orders:\n\n"
            "📋 <b>Recent Orders:</b> View latest transactions\n"
            "🔍 <b>Search Orders:</b> Find specific orders\n"
            "📈 <b>Sales Analytics:</b> Revenue & statistics\n"
            "⚠️ <b>Pending Orders:</b> Orders needing attention\n"
            "📅 <b>Order History:</b> Historical data"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📋 Recent Orders", callback_data="admin_orders"),
            types.InlineKeyboardButton("🔍 Search Orders", callback_data="admin_search_orders")
        )
        markup.add(
            types.InlineKeyboardButton("📈 Sales Report", callback_data="admin_sales_report"),
            types.InlineKeyboardButton("⚠️ Pending Orders", callback_data="admin_pending_orders")
        )
        markup.add(
            types.InlineKeyboardButton("📅 Order History", callback_data="admin_order_history"),
            types.InlineKeyboardButton("💳 Payment Issues", callback_data="admin_payment_issues")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_users_menu")
    def admin_users_menu(call):
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return
        
        text = (
            "👥 <b>User Management</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Manage all registered users:\n\n"
            "👤 <b>User List:</b> View all registered users\n"
            "🔍 <b>User Search:</b> Find specific users\n"
            "⚡ <b>User Stats:</b> Activity statistics\n"
            "🚫 <b>User Actions:</b> Ban/unban users\n"
            "💰 <b>Credits:</b> Manage user credits"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("👥 All Users", callback_data="admin_users"),
            types.InlineKeyboardButton("🔍 User Search", callback_data="admin_user_lookup")
        )
        markup.add(
            types.InlineKeyboardButton("⚡ User Stats", callback_data="admin_user_stats"),
            types.InlineKeyboardButton("🚫 Manage Bans", callback_data="admin_user_bans")
        )
        markup.add(
            types.InlineKeyboardButton("💰 Manage Credits", callback_data="admin_user_credits"),
            types.InlineKeyboardButton("📊 Activity Report", callback_data="admin_user_activity")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_keys_menu")
    def admin_keys_menu(call):
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return
        
        text = (
            "🔑 <b>Pro Keys Management</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Manage premium access keys:\n\n"
            "➕ <b>Generate Keys:</b> Create new pro keys\n"
            "📋 <b>View Keys:</b> See all generated keys\n"
            "🗑️ <b>Delete Keys:</b> Remove unused keys\n"
            "📊 <b>Usage Stats:</b> Key usage statistics\n"
            "⏰ <b>Expiry:</b> Set key expiration dates"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Generate Keys", callback_data="generate_pro_keys"),
            types.InlineKeyboardButton("📋 View All Keys", callback_data="manage_pro_keys")
        )
        markup.add(
            types.InlineKeyboardButton("🗑️ Delete Keys", callback_data="delete_pro_keys"),
            types.InlineKeyboardButton("📊 Key Statistics", callback_data="pro_key_stats")
        )
        markup.add(
            types.InlineKeyboardButton("⏰ Set Expiry", callback_data="set_key_expiry"),
            types.InlineKeyboardButton("🔄 Bulk Actions", callback_data="bulk_key_actions")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # Add some missing menu handlers that were referenced
    @bot.callback_query_handler(func=lambda call: call.data == "admin_view_products")
    def admin_view_products(call):
        # Redirect to existing manage products function
        call.data = "admin_manage_products"
        manage_products_callback(call)

    @bot.callback_query_handler(func=lambda call: call.data == "admin_referrals_menu")
    def admin_referrals_menu(call):
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return
        
        text = (
            "🏆 <b>Referral Management</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Manage referral system:\n\n"
            "📊 <b>Top Referrers:</b> See most active referrers\n"
            "🎁 <b>Referral Rewards:</b> Manage reward system\n"
            "📈 <b>Statistics:</b> View referral analytics"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🏆 Top Referrers", callback_data="admin_top_referrers"),
            types.InlineKeyboardButton("📊 Referral Stats", callback_data="admin_referral_stats")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_giveaway_menu")
    def admin_giveaway_menu(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Only owner can access this!", show_alert=True)
            return
        
        text = (
            "🎁 <b>Giveaway Management</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Manage giveaways and contests:\n\n"
            "🎯 <b>Select Winner:</b> Pick a random winner\n"
            "🎪 <b>Create Contest:</b> Start new giveaway\n"
            "📊 <b>History:</b> View past giveaways"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🎯 Select Winner", callback_data="admin_giveaway"),
            types.InlineKeyboardButton("🎪 New Contest", callback_data="admin_new_contest")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_manage_section_admins")
    def admin_manage_section_admins(call):
        # Only owner or global admins can manage section admins
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("➕ Add Section Admin", callback_data="owner_add_section_admin"))
        markup.add(types.InlineKeyboardButton("➖ Remove Section Admin", callback_data="owner_remove_section_admin"))
        markup.add(types.InlineKeyboardButton("👥 List Section Admins", callback_data="owner_list_section_admins"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"))
        bot.edit_message_text("<b>🧩 Manage Section Admins</b>\n\nUse the options below to assign or remove section-specific admins.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # =============================
    # ===== STATUS MANAGER ======
    # =============================

    @bot.callback_query_handler(func=lambda call: call.data == "status_manager")
    def status_manager_callback(call):
        # Allow owner and global admins to access status manager
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return

        # Load or create default section statuses
        try:
            with open('section_status.json', 'r') as f:
                statuses = json.load(f)
        except FileNotFoundError:
            # Create default status configuration
            statuses = {
                "cc_shop": "available",
                "bins_methods": "available", 
                "gift_cards": "coming_soon",
                "hacks": "available",
                "dumps": "available",
                "rdp": "available",
                "support": "available",
                "ai_search": "available"
            }
            with open('section_status.json', 'w') as f:
                json.dump(statuses, f, indent=4)

        text = (
            "🎛️ <b>Button Status Manager</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Toggle the availability status of bot sections:\n\n"
            "🟢 <b>Available</b> - Fully functional\n"
            "🟡 <b>Coming Soon</b> - Shows preview message\n"
            "🔴 <b>Maintenance</b> - Temporarily disabled\n\n"
            "<b>Current Status:</b>"
        )
        
        status_icons = {
            "available": "🟢",
            "coming_soon": "🟡", 
            "maintenance": "🔴"
        }

        markup = types.InlineKeyboardMarkup(row_width=1)
        for section, status in statuses.items():
            icon = status_icons.get(status, "⚪")
            section_name = section.replace('_', ' ').title()
            button_text = f"{icon} {section_name}: {status.replace('_', ' ').title()}"
            markup.add(types.InlineKeyboardButton(button_text, callback_data=f"status_toggle_{section}"))
        
        markup.add(types.InlineKeyboardButton("🔄 Reset All to Available", callback_data="status_reset_all"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        safe_edit_message(bot, call.message.chat.id, call.message.message_id, text, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("status_toggle_"))
    def status_toggle_callback(call):
        # Allow owner and global admins to toggle status
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return

        section = call.data.replace("status_toggle_", "")
        
        try:
            with open('section_status.json', 'r') as f:
                statuses = json.load(f)
        except FileNotFoundError:
            statuses = {}

        current_status = statuses.get(section, "available")
        
        # Cycle through statuses: available -> coming_soon -> maintenance -> available
        if current_status == "available":
            new_status = "coming_soon"
        elif current_status == "coming_soon":
            new_status = "maintenance"
        else:  # maintenance or other
            new_status = "available"
        
        statuses[section] = new_status

        with open('section_status.json', 'w') as f:
            json.dump(statuses, f, indent=4)

        # Show updated status with proper formatting
        status_display = {
            "available": "🟢 Available",
            "coming_soon": "🟡 Coming Soon", 
            "maintenance": "🔴 Maintenance"
        }
        
        bot.answer_callback_query(call.id, f"✅ {section.replace('_', ' ').title()} → {status_display.get(new_status, new_status)}")
        status_manager_callback(call)

    @bot.callback_query_handler(func=lambda call: call.data == "status_reset_all")
    def status_reset_all(call):
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return
        
        # Reset all sections to available
        statuses = {
            "cc_shop": "available",
            "bins_methods": "available", 
            "gift_cards": "available",
            "hacks": "available",
            "dumps": "available",
            "rdp": "available",
            "support": "available",
            "ai_search": "available"
        }
        
        with open('section_status.json', 'w') as f:
            json.dump(statuses, f, indent=4)
            
        bot.answer_callback_query(call.id, "✅ All sections reset to 🟢 Available")
        status_manager_callback(call)

    # ===== ANALYTICS FUNCTIONALITY =====
    
    @bot.callback_query_handler(func=lambda call: call.data == "admin_analytics_menu")
    def admin_analytics_menu(call):
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return
        
        text = (
            "📊 <b>Analytics Dashboard</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "View comprehensive bot analytics:\n\n"
            "📈 <b>User Analytics:</b> User activity & engagement\n"
            "💰 <b>Revenue Analytics:</b> Sales & financial data\n" 
            "📊 <b>Product Analytics:</b> Best selling items\n"
            "⚡ <b>Performance:</b> Bot performance metrics\n"
            "📅 <b>Reports:</b> Weekly/monthly summaries"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("👥 User Analytics", callback_data="analytics_users"),
            types.InlineKeyboardButton("💰 Revenue Analytics", callback_data="analytics_revenue")
        )
        markup.add(
            types.InlineKeyboardButton("📦 Product Analytics", callback_data="analytics_products"),
            types.InlineKeyboardButton("⚡ Performance", callback_data="analytics_performance")
        )
        markup.add(
            types.InlineKeyboardButton("📅 Weekly Report", callback_data="analytics_weekly"),
            types.InlineKeyboardButton("📊 Monthly Report", callback_data="analytics_monthly")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "analytics_users")
    def analytics_users(call):
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return

        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            
            # Total users
            c.execute("SELECT COUNT(*) FROM users")
            total_users = c.fetchone()[0]
            
            # Active users (last 30 days)
            c.execute("SELECT COUNT(*) FROM users WHERE join_date >= datetime('now', '-30 days')")
            new_users_month = c.fetchone()[0]
            
            # Users with orders
            c.execute("SELECT COUNT(DISTINCT user_id) FROM orders")
            paying_users = c.fetchone()[0]
            
            # Top referrer
            c.execute("SELECT username, referral_count FROM users ORDER BY referral_count DESC LIMIT 1")
            top_referrer = c.fetchone()
            
        text = (
            f"👥 <b>User Analytics</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 <b>Total Users:</b> {total_users}\n"
            f"🆕 <b>New Users (30d):</b> {new_users_month}\n"
            f"💳 <b>Paying Users:</b> {paying_users}\n"
            f"🏆 <b>Top Referrer:</b> {top_referrer[0] if top_referrer else 'None'} ({top_referrer[1] if top_referrer else 0} refs)\n\n"
            f"📈 <b>Conversion Rate:</b> {(paying_users/total_users*100):.1f}%\n"
            f"🎯 <b>Growth Rate:</b> {(new_users_month/max(total_users-new_users_month, 1)*100):.1f}%"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Analytics", callback_data="admin_analytics_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "analytics_revenue")
    def analytics_revenue(call):
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return

        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            
            # Total revenue
            c.execute("SELECT COALESCE(SUM(price_usd), 0) FROM orders WHERE payment_status = 'approved'")
            total_revenue = c.fetchone()[0]
            
            # Revenue this month
            c.execute("SELECT COALESCE(SUM(price_usd), 0) FROM orders WHERE payment_status = 'approved' AND creation_date >= datetime('now', 'start of month')")
            month_revenue = c.fetchone()[0]
            
            # Total orders
            c.execute("SELECT COUNT(*) FROM orders")
            total_orders = c.fetchone()[0]
            
            # Successful orders
            c.execute("SELECT COUNT(*) FROM orders WHERE payment_status = 'approved'")
            successful_orders = c.fetchone()[0]
            
        text = (
            f"💰 <b>Revenue Analytics</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💵 <b>Total Revenue:</b> ${total_revenue:.2f}\n"
            f"📅 <b>This Month:</b> ${month_revenue:.2f}\n"
            f"📦 <b>Total Orders:</b> {total_orders}\n"
            f"✅ <b>Successful Orders:</b> {successful_orders}\n\n"
            f"📊 <b>Success Rate:</b> {(successful_orders/max(total_orders,1)*100):.1f}%\n"
            f"💰 <b>Avg Order Value:</b> ${(total_revenue/max(successful_orders,1)):.2f}"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Analytics", callback_data="admin_analytics_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "analytics_products")
    def analytics_products(call):
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return

        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            
            # Top selling products
            c.execute("""
                SELECT item_name, COUNT(*) as sales, SUM(price_usd) as revenue
                FROM orders 
                WHERE payment_status = 'approved' 
                GROUP BY item_name 
                ORDER BY sales DESC 
                LIMIT 5
            """)
            top_products = c.fetchall()
            
        text = (
            f"📦 <b>Product Analytics</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>🏆 Top Selling Products:</b>\n\n"
        )
        
        if top_products:
            for i, (name, sales, revenue) in enumerate(top_products, 1):
                text += f"{i}. <b>{name}</b>\n   📊 Sales: {sales} | 💰 Revenue: ${revenue:.2f}\n\n"
        else:
            text += "No sales data available yet."
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Analytics", callback_data="admin_analytics_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "analytics_performance")
    def analytics_performance(call):
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return

        import os
        import datetime
        
        # Get bot uptime (approximate)
        try:
            stat = os.stat(__file__)
            last_restart = datetime.datetime.fromtimestamp(stat.st_mtime)
            uptime = datetime.datetime.now() - last_restart
            uptime_str = f"{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds%3600)//60}m"
        except:
            uptime_str = "Unknown"

        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            
            # Recent activity (last 24h)
            c.execute("SELECT COUNT(*) FROM orders WHERE creation_date >= datetime('now', '-1 day')")
            daily_orders = c.fetchone()[0]
            
            # Database size
            c.execute("PRAGMA page_count")
            page_count = c.fetchone()[0]
            c.execute("PRAGMA page_size")
            page_size = c.fetchone()[0]
            db_size_mb = (page_count * page_size) / (1024 * 1024)
        
        text = (
            f"⚡ <b>Performance Metrics</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⏰ <b>Bot Uptime:</b> {uptime_str}\n"
            f"📊 <b>Orders (24h):</b> {daily_orders}\n"
            f"💾 <b>Database Size:</b> {db_size_mb:.1f} MB\n"
            f"🔄 <b>Status:</b> ✅ Operational\n\n"
            f"📈 <b>Performance:</b> Normal\n"
            f"🚀 <b>Response Time:</b> <1s"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="analytics_performance"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Analytics", callback_data="admin_analytics_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "analytics_weekly")
    def analytics_weekly_report(call):
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return

        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            
            # Weekly stats
            c.execute("""
                SELECT 
                    DATE(creation_date) as date,
                    COUNT(*) as orders,
                    SUM(CASE WHEN payment_status = 'approved' THEN price_usd ELSE 0 END) as revenue,
                    COUNT(DISTINCT user_id) as unique_users
                FROM orders 
                WHERE creation_date >= datetime('now', '-7 days')
                GROUP BY DATE(creation_date)
                ORDER BY date
            """)
            weekly_data = c.fetchall()
            
        text = (
            f"📅 <b>Weekly Analytics Report</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        
        if weekly_data:
            total_orders = sum(row[1] for row in weekly_data)
            total_revenue = sum(row[2] for row in weekly_data)
            total_users = len(set(row[3] for row in weekly_data))
            
            text += f"📊 <b>Week Summary:</b>\n"
            text += f"📦 Total Orders: {total_orders}\n"
            text += f"💰 Total Revenue: ${total_revenue:.2f}\n" 
            text += f"👥 Active Users: {total_users}\n\n"
            text += f"📈 <b>Daily Breakdown:</b>\n"
            
            for date, orders, revenue, users in weekly_data:
                text += f"📅 {date}: {orders} orders, ${revenue:.2f}, {users} users\n"
        else:
            text += "No data available for the past week."
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Analytics", callback_data="admin_analytics_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "analytics_monthly")
    def analytics_monthly_report(call):
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return

        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            
            # Monthly stats
            c.execute("""
                SELECT 
                    strftime('%Y-%m', creation_date) as month,
                    COUNT(*) as orders,
                    SUM(CASE WHEN payment_status = 'approved' THEN price_usd ELSE 0 END) as revenue,
                    COUNT(DISTINCT user_id) as unique_users
                FROM orders 
                WHERE creation_date >= datetime('now', '-6 months')
                GROUP BY strftime('%Y-%m', creation_date)
                ORDER BY month DESC
            """)
            monthly_data = c.fetchall()
            
        text = (
            f"📊 <b>Monthly Analytics Report</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        
        if monthly_data:
            for month, orders, revenue, users in monthly_data:
                text += f"📅 <b>{month}:</b>\n"
                text += f"   📦 Orders: {orders}\n"
                text += f"   💰 Revenue: ${revenue:.2f}\n"
                text += f"   👥 Users: {users}\n\n"
        else:
            text += "No monthly data available yet."
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Analytics", callback_data="admin_analytics_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # ===== MISSING ADMIN MENU HANDLERS =====
    
    @bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast_menu")
    def admin_broadcast_menu(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Only owner can access this!", show_alert=True)
            return
        
        text = (
            "📢 <b>Broadcast Management</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Send messages to all users:\n\n"
            "📤 <b>Send Broadcast:</b> Send message to all users\n"
            "📊 <b>Broadcast History:</b> View past broadcasts"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📤 Send Broadcast", callback_data="admin_broadcast"),
            types.InlineKeyboardButton("📊 Broadcast History", callback_data="admin_broadcast_history")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_media_menu")
    def admin_media_menu(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Only owner can access this!", show_alert=True)
            return
        
        # Redirect to existing GIF manager
        call.data = "admin_manage_gifs"
        admin_manage_gifs(call)

    @bot.callback_query_handler(func=lambda call: call.data == "admin_manage_admins")
    def admin_manage_admins_menu(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Only owner can access this!", show_alert=True)
            return
        
        text = (
            "🧩 <b>Admin Management</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Manage bot administrators:\n\n"
            "👥 <b>Global Admins:</b> Full access admins\n"
            "🔧 <b>Section Admins:</b> Category-specific admins"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("➕ Add Global Admin", callback_data="owner_add_admin"),
            types.InlineKeyboardButton("➖ Remove Global Admin", callback_data="owner_remove_admin"),
            types.InlineKeyboardButton("👥 List Global Admins", callback_data="owner_list_admins")
        )
        markup.add(
            types.InlineKeyboardButton("🔧 Manage Section Admins", callback_data="admin_manage_section_admins")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_settings_menu")
    def admin_settings_menu(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Only owner can access this!", show_alert=True)
            return
        
        text = (
            "⚙️ <b>Bot Settings</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Configure bot settings:\n\n"
            "🎛️ <b>Button Status:</b> Toggle section availability\n"
            "🖼️ <b>Media Pool:</b> Manage GIFs and animations\n"
            "📊 <b>System Info:</b> View bot system information"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🎛️ Button Status Manager", callback_data="status_manager"),
            types.InlineKeyboardButton("🖼️ Media Pool Manager", callback_data="admin_manage_gifs"),
            types.InlineKeyboardButton("📊 System Info", callback_data="owner_bot_stats")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # ===== USER DASHBOARD FUNCTIONALITY =====
    
    @bot.callback_query_handler(func=lambda call: call.data == "user_dashboard")
    def user_dashboard_callback(call):
        user_id = call.from_user.id
        
        # Import the user stats system
        try:
            from user_stats import get_user_dashboard_data, user_stats
            dashboard_data = get_user_dashboard_data(user_id)
        except ImportError:
            bot.answer_callback_query(call.id, "Dashboard system not available", show_alert=True)
            return
        except Exception as e:
            print(f"Error getting dashboard data: {e}")
            bot.answer_callback_query(call.id, "Error loading dashboard", show_alert=True)
            return
        
        if "error" in dashboard_data:
            bot.answer_callback_query(call.id, dashboard_data["error"], show_alert=True)
            return
        
        user_info = dashboard_data.get("user_info", {})
        stats = dashboard_data.get("statistics", {})
        
        text = (
            f"📊 <b>Your Dashboard</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>Profile:</b> {user_info.get('username', 'Unknown')}\n"
            f"💰 <b>Balance:</b> ${user_info.get('total_spent', 0):.2f}\n"
            f"👥 <b>Referrals:</b> {user_info.get('referrals', 0)}\n"
            f"🏆 <b>Pro Status:</b> {'Yes' if user_info.get('is_pro') else 'No'}\n\n"
            f"📈 <b>Activity Statistics:</b>\n"
            f"🔄 <b>Total Checks:</b> {stats.get('total_checks', 0)}\n"
            f"✅ <b>Successful:</b> {stats.get('successful_checks', 0)}\n"
            f"❌ <b>Failed:</b> {stats.get('failed_checks', 0)}\n"
            f"📊 <b>Success Rate:</b> {stats.get('success_rate', 0)}%\n"
            f"💳 <b>Credits Spent:</b> {stats.get('total_credits_spent', 0)}\n\n"
            f"📅 <b>Last Active:</b> {stats.get('last_active', 'Unknown')[:10]}"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📅 Weekly Report", callback_data="dashboard_weekly"),
            types.InlineKeyboardButton("🏆 Leaderboard", callback_data="dashboard_leaderboard")
        )
        markup.add(
            types.InlineKeyboardButton("📊 Advanced Stats", callback_data="dashboard_advanced"),
            types.InlineKeyboardButton("🔄 Refresh", callback_data="user_dashboard")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        
        safe_edit_message(bot, call.message.chat.id, call.message.message_id, text, reply_markup=markup, parse_mode="HTML")
        bot.answer_callback_query(call.id, "Dashboard refreshed! ✅")

    @bot.callback_query_handler(func=lambda call: call.data == "dashboard_weekly")
    def dashboard_weekly_report(call):
        user_id = call.from_user.id
        
        try:
            from user_stats import get_user_dashboard_data
            dashboard_data = get_user_dashboard_data(user_id)
        except ImportError:
            bot.answer_callback_query(call.id, "Dashboard system not available", show_alert=True)
            return
        
        weekly_stats = dashboard_data.get("weekly_stats", [])
        
        text = (
            f"📅 <b>Weekly Activity Report</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        
        if weekly_stats:
            total_week_checks = sum(day['total_checks'] for day in weekly_stats)
            total_week_successes = sum(day['successes'] for day in weekly_stats)
            avg_success_rate = (total_week_successes / total_week_checks * 100) if total_week_checks > 0 else 0
            
            text += f"📊 <b>Weekly Summary:</b>\n"
            text += f"🔄 <b>Total Checks:</b> {total_week_checks}\n"
            text += f"✅ <b>Successes:</b> {total_week_successes}\n"
            text += f"📈 <b>Success Rate:</b> {avg_success_rate:.1f}%\n\n"
            text += f"📈 <b>Daily Breakdown:</b>\n"
            
            for day_data in weekly_stats[-7:]:  # Last 7 days
                date = day_data['date']
                checks = day_data['total_checks']
                successes = day_data['successes']
                rate = day_data['success_rate']
                text += f"📅 {date}: {checks} checks, {successes} success ({rate}%)\n"
        else:
            text += "No activity data available for this week."
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="user_dashboard"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "dashboard_leaderboard")
    def dashboard_leaderboard(call):
        try:
            from user_stats import user_stats
            leaderboard = user_stats.get_leaderboard(10)
        except ImportError:
            bot.answer_callback_query(call.id, "Leaderboard system not available", show_alert=True)
            return
        except Exception as e:
            print(f"Error getting leaderboard: {e}")
            bot.answer_callback_query(call.id, "Error loading leaderboard", show_alert=True)
            return
        
        text = (
            f"🏆 <b>Top Users Leaderboard</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>🎯 Based on successful checks:</b>\n\n"
        )
        
        user_id = call.from_user.id
        user_rank = None
        
        if leaderboard:
            for entry in leaderboard:
                rank = entry['rank']
                username = entry['username']
                successes = entry['successful_checks']
                success_rate = entry['success_rate']
                referrals = entry['referrals']
                
                if entry['user_id'] == user_id:
                    user_rank = rank
                    text += f"👑 <b>{rank}. {username}</b> - {successes} ✅ ({success_rate}%) | {referrals} refs\n"
                else:
                    text += f"🏅 {rank}. {username} - {successes} ✅ ({success_rate}%) | {referrals} refs\n"
            
            if user_rank:
                text += f"\n🎊 <b>Your Rank:</b> #{user_rank}"
            else:
                text += f"\n💡 <b>Your Rank:</b> Not in top 10 yet"
        else:
            text += "No leaderboard data available yet."
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="dashboard_leaderboard"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="user_dashboard"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "dashboard_advanced")
    def dashboard_advanced_stats(call):
        user_id = call.from_user.id
        
        try:
            from user_stats import get_user_dashboard_data
            dashboard_data = get_user_dashboard_data(user_id)
        except ImportError:
            bot.answer_callback_query(call.id, "Dashboard system not available", show_alert=True)
            return
        
        stats = dashboard_data.get("statistics", {})
        recent_activity = dashboard_data.get("recent_activity", [])
        
        text = (
            f"📊 <b>Advanced Statistics</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📈 <b>Performance Metrics:</b>\n"
            f"🎯 <b>Success Rate:</b> {stats.get('success_rate', 0)}%\n"
            f"📊 <b>Total Checks:</b> {stats.get('total_checks', 0)}\n"
            f"✅ <b>Successful:</b> {stats.get('successful_checks', 0)}\n"
            f"❌ <b>Failed:</b> {stats.get('failed_checks', 0)}\n"
            f"💳 <b>Credits Spent:</b> {stats.get('total_credits_spent', 0)}\n"
            f"💰 <b>Money Spent:</b> ${stats.get('total_money_spent', 0):.2f}\n"
            f"📅 <b>Member Since:</b> {stats.get('join_date', 'Unknown')[:10]}\n"
            f"⚡ <b>Avg Daily Usage:</b> {stats.get('avg_daily_usage', 0):.1f}\n\n"
            f"🕒 <b>Recent Activity:</b>\n"
        )
        
        if recent_activity:
            for activity in recent_activity[:5]:  # Show last 5 activities
                activity_type = activity['activity']
                success = "✅" if activity['success'] else "❌"
                credits = activity['credits']
                timestamp = activity['timestamp'][:10]
                text += f"{success} {activity_type} ({credits} credits) - {timestamp}\n"
        else:
            text += "No recent activity found."
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="user_dashboard"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "owner_bot_stats")
    def owner_bot_stats(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Only the owner can access this panel.", show_alert=True)
            return
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users")
            user_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM users WHERE COALESCE(is_active,1)=1")
            active_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM orders")
            order_count = c.fetchone()[0]
        text = f"<b>📈 Bot Stats</b>\n\n👥 Users: <b>{user_count}</b>\n✅ Active: <b>{active_count}</b>\n📦 Orders: <b>{order_count}</b>"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Owner Panel", callback_data="owner_panel"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # =============================
    # ===== BROADCAST SYSTEM ======
    # =============================

    @bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
    def admin_broadcast_prompt(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
            return
        
        user_states[call.from_user.id] = "awaiting_broadcast_message"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Cancel", callback_data="admin_panel"))
        bot.edit_message_text(
            "<b>📢 Broadcast Mode</b>\n\nPlease send or forward the message you want to broadcast to all users.\n\nIt can be text, an image with a caption, a video, or any other message type.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_broadcast_message", content_types=['text', 'photo', 'video', 'document', 'audio', 'sticker', 'voice'])
    def admin_broadcast_confirm(message):
        # Store the message to be broadcast
        user_states[message.from_user.id] = {
            "broadcast_chat_id": message.chat.id,
            "broadcast_message_id": message.message_id
        }

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(user_id) FROM users")
            user_count = cursor.fetchone()[0]

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Yes, Send Now", callback_data="broadcast_confirm_yes"),
            types.InlineKeyboardButton("❌ No, Cancel", callback_data="broadcast_confirm_no")
        )
        bot.send_message(
            message.chat.id,
            f"Your message is ready to be sent to <b>{user_count}</b> users. Are you sure you want to proceed?",
            reply_markup=markup,
            parse_mode="HTML"
        )

    @bot.callback_query_handler(func=lambda call: call.data == "broadcast_confirm_no")
    def admin_broadcast_cancel(call):
        del user_states[call.from_user.id]
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Broadcast cancelled.")
        admin_panel_callback(call) # Show admin panel again

    def do_broadcast(admin_id, broadcast_chat_id, broadcast_message_id):
        """The actual broadcasting logic, run in a separate thread."""
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE COALESCE(is_active,1)=1")
            all_users = cursor.fetchall()
        
        success_count = 0
        fail_count = 0
        
        bot.send_message(admin_id, f"🚀 Starting broadcast to {len(all_users)} users. This may take a while...")

        for user in all_users:
            user_id = user[0]
            try:
                bot.copy_message(chat_id=user_id, from_chat_id=broadcast_chat_id, message_id=broadcast_message_id)
                success_count += 1
            except Exception as e:
                err = str(e)
                print(f"Broadcast error to user {user_id}: {err}")
                # Deactivate unreachable users to avoid future errors
                if any(x in err for x in [
                    "bot was blocked by the user",
                    "chat not found",
                    "bot can't initiate conversation",
                    "user is deactivated"
                ]):
                    try:
                        with sqlite3.connect(DB_NAME) as conn2:
                            c2 = conn2.cursor()
                            c2.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
                            conn2.commit()
                    except Exception:
                        pass
                fail_count += 1
            time.sleep(0.1) # Sleep for 100ms between messages to avoid hitting API rate limits

        summary_text = f"""🏁 **Broadcast Complete!**

✅ **Successfully sent to:** `{success_count}` users
❌ **Failed to send to:** `{fail_count}` users (likely blocked the bot)
"""
        bot.send_message(admin_id, summary_text, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data == "broadcast_confirm_yes")
    def admin_broadcast_start(call):
        admin_id = call.from_user.id
        state = user_states.get(admin_id)

        if not isinstance(state, dict) or "broadcast_message_id" not in state:
            bot.answer_callback_query(call.id, "Error: Broadcast message not found. Please start over.", show_alert=True)
            return

        broadcast_chat_id = state["broadcast_chat_id"]
        broadcast_message_id = state["broadcast_message_id"]
        
        del user_states[admin_id]
        bot.edit_message_text("Broadcast is starting... You will receive a summary when it's complete.", call.message.chat.id, call.message.message_id)

        # Run the broadcast in a background thread to not block the bot
        broadcast_thread = threading.Thread(target=do_broadcast, args=(admin_id, broadcast_chat_id, broadcast_message_id))
        broadcast_thread.start()

    # =============================
    # ===== REFERRAL GIVEAWAYS =====
    # =============================

    # =============================
    # ===== GIF MANAGEMENT ========
    # =============================

    @bot.callback_query_handler(func=lambda call: call.data == "admin_manage_gifs")
    def admin_manage_gifs(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
            return
        counts = get_media_pool_counts()
        text = ("<b>🖼️ GIF Manager</b>\n\n"
                f"welcome: <b>{counts.get('welcome', 0)}</b>\n"
                f"success: <b>{counts.get('success', 0)}</b>\n"
                f"reject: <b>{counts.get('reject', 0)}</b>\n"
                f"pending: <b>{counts.get('pending', 0)}</b>\n"
                f"any: <b>{counts.get('any', 0)}</b>\n\n"
                "Send a GIF with one of these captions to add: <code>/addgif welcome</code>, <code>/addgif success</code>, <code>/addgif reject</code>, <code>/addgif pending</code>.\n"
                "Or use the buttons below.")
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Add to Welcome", callback_data="gif_add_welcome"),
            types.InlineKeyboardButton("➕ Add to Success", callback_data="gif_add_success"),
            types.InlineKeyboardButton("➕ Add to Reject", callback_data="gif_add_reject"),
            types.InlineKeyboardButton("➕ Add to Pending", callback_data="gif_add_pending"),
        )
        markup.add(
            types.InlineKeyboardButton("📥 Bulk Add Welcome", callback_data="gif_add_bulk_welcome"),
            types.InlineKeyboardButton("📥 Bulk Add Success", callback_data="gif_add_bulk_success"),
            types.InlineKeyboardButton("📥 Bulk Add Reject", callback_data="gif_add_bulk_reject"),
            types.InlineKeyboardButton("📥 Bulk Add Pending", callback_data="gif_add_bulk_pending"),
        )
        markup.add(
            types.InlineKeyboardButton("📊 Refresh Counts", callback_data="admin_manage_gifs"),
            types.InlineKeyboardButton("🧹 Clear All", callback_data="gif_clear_all"),
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # State for expecting a GIF to add
    @bot.callback_query_handler(func=lambda call: call.data.startswith("gif_add_"))
    def admin_gif_add_prompt(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
            return
        parts = call.data.split('_')
        if len(parts) >= 3 and parts[2] == 'bulk':
            kind = parts[-1]
            user_states[call.from_user.id] = f"awaiting_gif_bulk_{kind}"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🛑 Stop Bulk", callback_data="gif_bulk_stop"))
            bot.edit_message_text(
                f"📥 <b>Bulk Add Mode</b> for <b>{kind}</b>\n\nSend GIFs one by one (forward or upload). They will be saved automatically.\nWhen finished, press ‘Stop Bulk’.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="HTML",
            )
        else:
            kind = parts[-1]
            user_states[call.from_user.id] = f"awaiting_gif_{kind}"
            bot.edit_message_text(f"Send an animated GIF now to add to <b>{kind}</b> pool.", call.message.chat.id, call.message.message_id, parse_mode="HTML")

    def _is_waiting_gif_state(uid):
        st = str(user_states.get(uid, ''))
        return st.startswith("awaiting_gif_") or st.startswith("awaiting_gif_bulk_")

    @bot.message_handler(func=lambda m: _is_waiting_gif_state(m.from_user.id), content_types=['animation'])
    def admin_gif_add_receive(message):
        if message.from_user.id != ADMIN_ID:
            return
        state = str(user_states.get(message.from_user.id, ''))
        is_bulk = state.startswith("awaiting_gif_bulk_")
        kind = state.replace("awaiting_gif_bulk_", "").replace("awaiting_gif_", "")
        file_id = message.animation.file_id
        try:
            count = add_gif_to_pool(kind, file_id)
            if is_bulk:
                bot.reply_to(message, f"✅ Added to '{kind}' pool. Total: {count}\n(Bulk mode: keep sending, or press Stop)")
            else:
                bot.reply_to(message, f"✅ Added to '{kind}' pool. Total: {count}")
        except Exception as e:
            bot.reply_to(message, f"❌ Could not add GIF: {e}")
        finally:
            if not is_bulk:
                try:
                    del user_states[message.from_user.id]
                except Exception:
                    pass

    @bot.callback_query_handler(func=lambda call: call.data == "gif_bulk_stop")
    def admin_gif_bulk_stop(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
            return
        try:
            if call.from_user.id in user_states:
                del user_states[call.from_user.id]
        except Exception:
            pass
        bot.answer_callback_query(call.id, "Bulk add stopped.", show_alert=True)
        admin_manage_gifs(call)

    @bot.callback_query_handler(func=lambda call: call.data == "gif_clear_all")
    def admin_gif_clear_all(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
            return
        counts = clear_media_pool("all")
        bot.answer_callback_query(call.id, "🧹 Cleared all GIF pools.", show_alert=True)
        admin_manage_gifs(call)

    def format_user_line(u):
        uid, uname, ref_count, join_date = u
        uname_disp = uname if uname else "-"
        return f"<code>{uid}</code> | {uname_disp} | <b>{ref_count}</b> | <code>{join_date[:10]}</code>"

    @bot.callback_query_handler(func=lambda call: call.data == "admin_top_referrers" or call.data.startswith("admin_top_referrers_page_"))
    def admin_top_referrers(call):
        if call.from_user.id != ADMIN_ID:
            # Allow global admins as well
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return
        import math
        page = 0
        if call.data.startswith("admin_top_referrers_page_"):
            page = int(call.data.split('_')[-1])
        page_size = 10
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users WHERE referral_count > 0")
            count = cursor.fetchone()[0]
            cursor.execute("SELECT user_id, username, referral_count, join_date FROM users WHERE referral_count > 0 ORDER BY referral_count DESC, join_date ASC LIMIT ? OFFSET ?", (page_size, page*page_size))
            rows = cursor.fetchall()
        total_pages = max(1, math.ceil(count / page_size))
        text = f"<b>🏆 Top Referrers (Page {page+1}/{total_pages})</b>\nTotal with >=1 referral: <b>{count}</b>\n\n<b>ID</b> | <b>Username</b> | <b>Refs</b> | <b>Joined</b> | <b>⭐</b>\n" + ("-"*46) + "\n"
        if not rows:
            text += "No users with successful referrals yet."
        else:
            for u in rows:
                text += format_user_line(u) + "\n"
        markup = types.InlineKeyboardMarkup()
        nav = []
        if page > 0:
            nav.append(types.InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_top_referrers_page_{page-1}"))
        if page < total_pages-1:
            nav.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"admin_top_referrers_page_{page+1}"))
        if nav:
            markup.row(*nav)
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_giveaway")
    def admin_giveaway_menu(call):
        # Owner or global admin only
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return
        # Show top 20 with actions to select as winner
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, referral_count, join_date FROM users WHERE referral_count > 0 ORDER BY referral_count DESC, join_date ASC LIMIT 20")
            rows = cursor.fetchall()
        text = "<b>🎁 Giveaway</b>\n\nPick a winner from recent top referrers (last 20 shown).\nEach referral = one ⭐ in weighted random.\n\n<b>ID</b> | <b>User</b> | <b>Refs</b> | <b>Joined</b> | <b>⭐</b>\n" + ("-"*46) + "\n"
        markup = types.InlineKeyboardMarkup(row_width=2)
        if not rows:
            text += "No eligible users (referrals >= 1) yet."
        else:
            for u in rows:
                uid, uname, ref_count, join_date = u
                stars = "⭐" * min(ref_count, 20)
                if ref_count > 20:
                    stars += f" x{ref_count}"
                text += format_user_line(u) + f" | {stars}\n"
                markup.add(types.InlineKeyboardButton(f"Select {u[0]}", callback_data=f"admin_giveaway_select_{u[0]}"))
        markup.add(types.InlineKeyboardButton("🎲 Weighted Random Winner", callback_data="admin_giveaway_weighted"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_giveaway_select_"))
    def admin_giveaway_select(call):
        # Permission check
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return
        try:
            uid = int(call.data.split('_')[-1])
        except Exception:
            bot.answer_callback_query(call.id, "Invalid selection.", show_alert=True)
            return
        # Persist winner to DB and notify
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO giveaway_winners (user_id, selected_by) VALUES (?, ?)", (uid, call.from_user.id))
            conn.commit()
            cursor.execute("SELECT username FROM users WHERE user_id = ?", (uid,))
            row = cursor.fetchone()
            uname = row[0] if row else None
        
        bot.answer_callback_query(call.id, "🎉 Winner recorded!", show_alert=True)
        winner_name = f"@{uname}" if uname else f"User {uid}"
        try:
            bot.send_message(uid, "🎉 Congratulations! You have been selected as a giveaway winner. The team will contact you with your reward.")
        except Exception:
            pass
        bot.edit_message_text(f"🎁 <b>Giveaway Winner Selected:</b> {winner_name} (<code>{uid}</code>)", call.message.chat.id, call.message.message_id, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_giveaway_weighted")
    def admin_giveaway_weighted(call):
        # Permission check
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if c.fetchone() is None:
                    bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
                    return
        # Build weighted population
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, referral_count FROM users WHERE referral_count > 0")
            rows = cursor.fetchall()
        if not rows:
            bot.answer_callback_query(call.id, "No eligible users.", show_alert=True)
            return
        population = [r[0] for r in rows]
        weights = [max(0, r[2]) for r in rows]
        try:
            winner_id = random.choices(population, weights=weights, k=1)[0]
        except Exception as e:
            bot.answer_callback_query(call.id, f"Failed to pick: {e}", show_alert=True)
            return
        # Persist and notify
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO giveaway_winners (user_id, selected_by) VALUES (?, ?)", (winner_id, call.from_user.id))
            conn.commit()
            cursor.execute("SELECT username FROM users WHERE user_id = ?", (winner_id,))
            row = cursor.fetchone()
            uname = row[0] if row else None
        try:
            bot.send_message(winner_id, "🎉 Congratulations! You have been selected as a giveaway winner by weighted random. The team will contact you with your reward.")
        except Exception:
            pass
        winner_name = f"@{uname}" if uname else f"User {winner_id}"
        bot.edit_message_text(f"🎁 <b>Weighted Random Winner:</b> {winner_name} (<code>{winner_id}</code>)", call.message.chat.id, call.message.message_id, parse_mode="HTML")

    # Section-based Manage Orders for section admins
    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_orders_"))
    def admin_section_orders_callback(call):
        user_id = call.from_user.id
        section = call.data.replace("admin_orders_", "")
        # Check if user is section admin for this section
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM section_admins WHERE user_id = ? AND section = ?", (user_id, section))
            if not cursor.fetchone():
                bot.answer_callback_query(call.id, "❌ Access Denied! You are not an admin for this section.", show_alert=True)
                return
            cursor.execute("SELECT order_id, user_id, item_name, price_usd, payment_status, creation_date FROM orders WHERE item_name LIKE ? ORDER BY creation_date DESC LIMIT 20", (f"%{section}%",))
            orders = cursor.fetchall()
        if not orders:
            text = f"📦 **Recent {section.title()} Orders**\n\nThere are no orders for this section yet."
        else:
            text = f"📦 **Last 20 {section.title()} Orders**\n\n<code>Order ID | User ID | Item | Price | Status | Date</code>\n" + "-"*40 + "\n"
            for o in orders:
                text += f"<code>{o[0]}</code> | <code>{o[1]}</code> | <code>{o[2]}</code> | <code>${o[3]}</code> | <code>{o[4]}</code> | <code>{o[5][:10]}</code>\n"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_user_lookup")
    def admin_user_lookup_prompt(call):
        user_states[call.from_user.id] = "awaiting_user_lookup_id"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"))
        bot.edit_message_text("Please send the <b>User ID</b> of the user you want to look up.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_user_lookup_id")
    def admin_user_lookup(message):
        user_id = message.text.strip()
        try:
            user_id_int = int(user_id)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid User ID. Please send a numeric User ID.")
            return
        user = get_user_details(user_id_int)
        if not user:
            bot.send_message(message.chat.id, f"❌ No user found with ID {user_id}.")
            return
        # Fetch purchase/payment history
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT order_id, item_name, price_usd, payment_status, creation_date FROM orders WHERE user_id = ? ORDER BY creation_date DESC", (user_id_int,))
            orders = cursor.fetchall()
        text = f"<b>👤 User Details</b>\n<b>User ID:</b> <code>{user['user_id']}</code>\n<b>Username:</b> {user['username']}\n<b>Referrals:</b> {user['referral_count']}\n\n<b>Purchase/Payment History:</b>\n"
        if not orders:
            text += "No purchases found."
        else:
            for o in orders:
                text += f"\n<b>Order:</b> <code>{o[0]}</code> | <b>Item:</b> {o[1]} | <b>Price:</b> ${o[2]} | <b>Status:</b> {o[3]} | <b>Date:</b> {o[4]}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")
        del user_states[message.from_user.id]

    @bot.callback_query_handler(func=lambda call: call.data == "admin_manage_products")
    def manage_products_callback(call):
        markup = types.InlineKeyboardMarkup(row_width=1)
        # Show consolidated Hacks management (Methods + Phishing Kits)
        markup.add(types.InlineKeyboardButton("🔧 Manage Hacks (Methods, Phishing)", callback_data="admin_manage_hacks"))
        # Show other top-level categories
        for key, name in CATEGORY_NAMES.items():
            if key in {"methods", "phishing_kits"}:
                continue
            markup.add(types.InlineKeyboardButton(f"🔧 Manage {name}", callback_data=f"admin_cat_menu_{key}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        bot.edit_message_text("📦 **Manage Products**\n\nChoose a category to add, remove, or modify items.", call.message.chat.id, call.message.message_id, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data == "admin_manage_hacks")
    def admin_manage_hacks(call):
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🧰 Manage Methods", callback_data="admin_cat_menu_methods"))
        markup.add(types.InlineKeyboardButton("🎣 Manage Phishing Kits", callback_data="admin_cat_menu_phishing_kits"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_manage_products"))
        bot.edit_message_text("<b>🔧 Manage Hacks</b>\n\nPick what to manage:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    def show_cc_add_wizard(call, category):
        """Enhanced CC product addition wizard with proper format"""
        category_name = "Ready Credit Cards" if category == "ready_ccs" else "BIN Numbers"
        
        if category == "ready_ccs":
            text = (
                f"💳 <b>Add {category_name}</b>\n\n"
                f"Choose how you want to add the CC product:\n\n"
                f"🎯 <b>Quick Add:</b> Basic CC with name and price\n"
                f"💎 <b>Full Details:</b> Complete CC with all info\n"
                f"🔢 <b>Bulk Add:</b> Multiple CCs at once"
            )
        else:  # bins
            text = (
                f"🏦 <b>Add {category_name}</b>\n\n"
                f"Choose how you want to add the BIN:\n\n"
                f"🎯 <b>Quick Add:</b> Basic BIN with name and price\n"
                f"💎 <b>Full Details:</b> Complete BIN with bank info\n"
                f"🔢 <b>Bulk Add:</b> Multiple BINs at once"
            )
            
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🎯 Quick Add", callback_data=f"cc_quick_{category}"),
            types.InlineKeyboardButton("💎 Full Details", callback_data=f"cc_full_{category}"),
            types.InlineKeyboardButton("🔢 Bulk Add", callback_data=f"cc_bulk_{category}")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=f"admin_cat_menu_{category}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # CC Quick Add Handlers
    @bot.callback_query_handler(func=lambda call: call.data.startswith("cc_quick_"))
    def cc_quick_add(call):
        category = call.data.split('_')[2]
        user_states[call.from_user.id] = f"cc_quick_name_{category}"
        
        if category == "ready_ccs":
            text = (
                "💳 <b>Quick Add - Ready CC</b>\n\n"
                "Enter the <b>CC name/title</b>:\n\n"
                "<i>Examples:</i>\n"
                "• CC for Netflix\n"
                "• High Balance Visa\n"
                "• Amazon Working CC\n"
                "• PayPal Verified CC"
            )
        else:
            text = (
                "🏦 <b>Quick Add - BIN</b>\n\n"
                "Enter the <b>BIN name/title</b>:\n\n"
                "<i>Examples:</i>\n"
                "• Netflix BIN\n"
                "• USA Chase Bank BIN\n"
                "• UK Visa BIN\n"
                "• Premium MasterCard BIN"
            )
            
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cat_menu_{category}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id, "").startswith("cc_quick_name_"))
    def handle_cc_quick_name(message):
        state = user_states[message.from_user.id]
        category = state.split('_')[3]
        
        cc_name = message.text.strip()
        if len(cc_name) < 3:
            bot.reply_to(message, "❌ Name too short. Please enter at least 3 characters.")
            return
            
        # Store the name and ask for price
        user_states[message.from_user.id] = f"cc_quick_price_{category}_{cc_name}"
        
        text = (
            f"💰 <b>Price for: {cc_name}</b>\n\n"
            f"Enter the price in USD (numbers only):\n\n"
            f"<i>Examples:</i> 25, 50, 100"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cat_menu_{category}"))
        
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id, "").startswith("cc_quick_price_"))
    def handle_cc_quick_price(message):
        state = user_states[message.from_user.id]
        parts = state.split('_', 4)
        category = parts[3]
        cc_name = parts[4]
        
        try:
            price = int(message.text.strip())
            if price <= 0:
                raise ValueError()
        except ValueError:
            bot.reply_to(message, "❌ Invalid price. Please enter a positive number (e.g., 25, 50, 100)")
            return
            
        # Ask for description
        user_states[message.from_user.id] = f"cc_quick_desc_{category}_{cc_name}_{price}"
        
        text = (
            f"📝 <b>Description for: {cc_name}</b>\n\n"
            f"Enter a short description:\n\n"
            f"<i>Examples:</i>\n"
            f"• Working for streaming services\n"
            f"• High balance, verified\n"
            f"• Good for online shopping\n"
            f"• Premium account compatible"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cat_menu_{category}"))
        
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id, "").startswith("cc_quick_desc_"))
    def handle_cc_quick_desc(message):
        state = user_states[message.from_user.id]
        parts = state.split('_', 5)
        category = parts[3]
        cc_name = parts[4]
        price = int(parts[5])
        
        description = message.text.strip()
        
        # Create the product object
        if category == "ready_ccs":
            new_item = {
                "name": cc_name,
                "price": price,
                "description": description,
                "delivery_type": "generate",
                "card_type": "ready_cc",
                "status": "active"
            }
        else:  # bins
            new_item = {
                "name": cc_name,
                "price": price,
                "description": description,
                "bin": "XXXXXXXXXXXX",
                "status": "WORKING",
                "country": "Unknown",
                "info": "Credit Card",
                "bank": "Unknown"
            }
            
        # Add to products
        products = get_products_from_cache()
        if category not in products:
            products[category] = []
        products[category].append(new_item)
        
        # Save products
        save_products_to_file_and_reload(products)
        
        # Clear state
        del user_states[message.from_user.id]
        
        # Confirmation
        text = (
            f"✅ <b>Product Added Successfully!</b>\n\n"
            f"<b>Category:</b> {CATEGORY_NAMES.get(category, category)}\n"
            f"<b>Name:</b> {cc_name}\n"
            f"<b>Price:</b> ${price}\n"
            f"<b>Description:</b> {description}\n\n"
            f"The product is now available in the shop!"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("➕ Add Another", callback_data=f"cc_quick_{category}"),
            types.InlineKeyboardButton("🔧 Manage Category", callback_data=f"admin_cat_menu_{category}"),
            types.InlineKeyboardButton("⬅️ Back to Products", callback_data="admin_products_menu")
        )
        
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

    # CC Full Details Handlers
    @bot.callback_query_handler(func=lambda call: call.data.startswith("cc_full_"))
    def cc_full_add(call):
        category = call.data.split('_')[2]
        user_states[call.from_user.id] = f"cc_full_name_{category}"
        
        if category == "ready_ccs":
            text = (
                "💳 <b>Full Details - Ready CC</b>\n\n"
                "We'll collect detailed information step by step.\n\n"
                "<b>Step 1:</b> Enter the CC name/title:\n\n"
                "<i>Examples:</i>\n"
                "• Premium Netflix CC\n"
                "• High Balance Visa USA\n"
                "• Amazon Prime Working CC\n"
                "• PayPal Verified MasterCard"
            )
        else:
            text = (
                "🏦 <b>Full Details - BIN</b>\n\n"
                "We'll collect detailed information step by step.\n\n"
                "<b>Step 1:</b> Enter the BIN name/title:\n\n"
                "<i>Examples:</i>\n"
                "• Netflix USA BIN\n"
                "• Chase Bank Premium BIN\n"
                "• UK Visa Classic BIN\n"
                "• MasterCard World Elite BIN"
            )
            
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cat_menu_{category}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # CC Bulk Add Handlers
    @bot.callback_query_handler(func=lambda call: call.data.startswith("cc_bulk_"))
    def cc_bulk_add(call):
        category = call.data.split('_')[2]
        user_states[call.from_user.id] = f"cc_bulk_{category}"
        
        if category == "ready_ccs":
            text = (
                "📦 <b>Bulk Add - Ready CCs</b>\n\n"
                "Send CC data in this format (one per line):\n\n"
                "<code>Name|Price|Description</code>\n\n"
                "<b>Examples:</b>\n"
                "<code>Netflix CC|25|Working for streaming\n"
                "Amazon CC|35|High balance verified\n"
                "PayPal CC|45|Premium account ready</code>\n\n"
                "You can send multiple lines at once."
            )
        else:
            text = (
                "📦 <b>Bulk Add - BINs</b>\n\n"
                "Send BIN data in this format (one per line):\n\n"
                "<code>Name|BIN|Price|Country|Bank|Description</code>\n\n"
                "<b>Examples:</b>\n"
                "<code>Netflix BIN|123456|30|USA|Chase|Works for streaming\n"
                "Amazon BIN|654321|40|UK|Barclays|Good for shopping</code>\n\n"
                "You can send multiple lines at once."
            )
            
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cat_menu_{category}"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id, "").startswith("cc_bulk_"))
    def handle_cc_bulk(message):
        state = user_states[message.from_user.id]
        category = state.split('_')[2]
        
        lines = message.text.strip().split('\n')
        products = get_products_from_cache()
        
        if category not in products:
            products[category] = []
            
        added_count = 0
        errors = []
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            try:
                parts = [p.strip() for p in line.split('|')]
                
                if category == "ready_ccs":
                    if len(parts) < 3:
                        errors.append(f"Line {i}: Need Name|Price|Description format")
                        continue
                        
                    name, price_str, description = parts[0], parts[1], parts[2]
                    price = int(price_str)
                    
                    new_item = {
                        "name": name,
                        "price": price,
                        "description": description,
                        "delivery_type": "generate",
                        "card_type": "ready_cc",
                        "status": "active"
                    }
                    
                else:  # bins
                    if len(parts) < 6:
                        errors.append(f"Line {i}: Need Name|BIN|Price|Country|Bank|Description format")
                        continue
                        
                    name, bin_num, price_str, country, bank, description = parts[:6]
                    price = int(price_str)
                    
                    new_item = {
                        "name": name,
                        "price": price,
                        "description": description,
                        "bin": bin_num,
                        "status": "WORKING",
                        "country": country,
                        "info": "Credit Card",
                        "bank": bank
                    }
                    
                products[category].append(new_item)
                added_count += 1
                
            except ValueError:
                errors.append(f"Line {i}: Invalid price format")
            except Exception as e:
                errors.append(f"Line {i}: {str(e)}")
        
        # Save products
        if added_count > 0:
            save_products_to_file_and_reload(products)
        
        # Clear state
        del user_states[message.from_user.id]
        
        # Build response
        text = f"📊 <b>Bulk Import Results</b>\n\n"
        text += f"✅ <b>Successfully added:</b> {added_count} items\n"
        
        if errors:
            text += f"❌ <b>Errors:</b> {len(errors)}\n\n"
            text += "<b>Error details:</b>\n"
            for error in errors[:5]:  # Show first 5 errors
                text += f"• {error}\n"
            if len(errors) > 5:
                text += f"• ... and {len(errors) - 5} more errors\n"
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("➕ Bulk Add More", callback_data=f"cc_bulk_{category}"),
            types.InlineKeyboardButton("🔧 Manage Category", callback_data=f"admin_cat_menu_{category}"),
            types.InlineKeyboardButton("⬅️ Back to Products", callback_data="admin_products_menu")
        )
        
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

    # Full Details Handlers for CCs
    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id, "").startswith("cc_full_name_"))
    def handle_cc_full_name(message):
        state = user_states[message.from_user.id]
        category = state.split('_')[3]
        
        cc_name = message.text.strip()
        if len(cc_name) < 3:
            bot.reply_to(message, "❌ Name too short. Please enter at least 3 characters.")
            return
            
        # Store the name and ask for next field
        user_states[message.from_user.id] = f"cc_full_price_{category}_{cc_name}"
        
        text = (
            f"💰 <b>Step 2: Price</b>\n\n"
            f"<b>Product:</b> {cc_name}\n\n"
            f"Enter the price in USD (numbers only):\n\n"
            f"<i>Examples:</i> 25, 50, 100, 250"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cat_menu_{category}"))
        
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id, "").startswith("cc_full_price_"))
    def handle_cc_full_price(message):
        state = user_states[message.from_user.id]
        parts = state.split('_', 4)
        category = parts[3]
        cc_name = parts[4]
        
        try:
            price = int(message.text.strip())
            if price <= 0:
                raise ValueError()
        except ValueError:
            bot.reply_to(message, "❌ Invalid price. Please enter a positive number (e.g., 25, 50, 100)")
            return
            
        if category == "ready_ccs":
            # For Ready CCs, ask for description
            user_states[message.from_user.id] = f"cc_full_desc_{category}_{cc_name}_{price}"
            
            text = (
                f"📝 <b>Step 3: Description</b>\n\n"
                f"<b>Product:</b> {cc_name}\n"
                f"<b>Price:</b> ${price}\n\n"
                f"Enter a detailed description:\n\n"
                f"<i>Examples:</i>\n"
                f"• High balance CC, works for Netflix, Amazon\n"
                f"• Verified PayPal account compatible\n"
                f"• Premium streaming services ready\n"
                f"• Good for online shopping and subscriptions"
            )
            
        else:  # bins
            # For BINs, ask for BIN number
            user_states[message.from_user.id] = f"cc_full_bin_{category}_{cc_name}_{price}"
            
            text = (
                f"🏦 <b>Step 3: BIN Number</b>\n\n"
                f"<b>Product:</b> {cc_name}\n"
                f"<b>Price:</b> ${price}\n\n"
                f"Enter the BIN number (first 6 digits):\n\n"
                f"<i>Example:</i> 123456, 456789"
            )
            
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cat_menu_{category}"))
        
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id, "").startswith("cc_full_desc_"))
    def handle_cc_full_desc(message):
        state = user_states[message.from_user.id]
        parts = state.split('_', 5)
        category = parts[3]
        cc_name = parts[4]
        price = int(parts[5])
        
        description = message.text.strip()
        
        # Create the Ready CC product
        new_item = {
            "name": cc_name,
            "price": price,
            "description": description,
            "delivery_type": "generate",
            "card_type": "ready_cc",
            "status": "active"
        }
            
        # Add to products
        products = get_products_from_cache()
        if category not in products:
            products[category] = []
        products[category].append(new_item)
        
        # Save products
        save_products_to_file_and_reload(products)
        
        # Clear state
        del user_states[message.from_user.id]
        
        # Confirmation
        text = (
            f"✅ <b>Ready CC Added Successfully!</b>\n\n"
            f"<b>Name:</b> {cc_name}\n"
            f"<b>Price:</b> ${price}\n"
            f"<b>Description:</b> {description}\n\n"
            f"The product is now available in the shop!"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("➕ Add Another CC", callback_data=f"cc_full_{category}"),
            types.InlineKeyboardButton("🔧 Manage Category", callback_data=f"admin_cat_menu_{category}"),
            types.InlineKeyboardButton("⬅️ Back to Products", callback_data="admin_products_menu")
        )
        
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id, "").startswith("cc_full_bin_"))
    def handle_cc_full_bin(message):
        state = user_states[message.from_user.id]
        parts = state.split('_', 5)
        category = parts[3]
        cc_name = parts[4]
        price = int(parts[5])
        
        bin_num = message.text.strip()
        if not bin_num.isdigit() or len(bin_num) != 6:
            bot.reply_to(message, "❌ Invalid BIN format. Please enter exactly 6 digits (e.g., 123456)")
            return
            
        # Ask for country
        user_states[message.from_user.id] = f"cc_full_country_{category}_{cc_name}_{price}_{bin_num}"
        
        text = (
            f"🌍 <b>Step 4: Country</b>\n\n"
            f"<b>Product:</b> {cc_name}\n"
            f"<b>Price:</b> ${price}\n"
            f"<b>BIN:</b> {bin_num}\n\n"
            f"Enter the country:\n\n"
            f"<i>Examples:</i> USA, UK, Canada, Germany, France"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cat_menu_{category}"))
        
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id, "").startswith("cc_full_country_"))
    def handle_cc_full_country(message):
        state = user_states[message.from_user.id]
        parts = state.split('_', 6)
        category = parts[3]
        cc_name = parts[4]
        price = int(parts[5])
        bin_num = parts[6]
        
        country = message.text.strip()
        
        # Ask for bank
        user_states[message.from_user.id] = f"cc_full_bank_{category}_{cc_name}_{price}_{bin_num}_{country}"
        
        text = (
            f"🏦 <b>Step 5: Bank Name</b>\n\n"
            f"<b>Product:</b> {cc_name}\n"
            f"<b>Price:</b> ${price}\n"
            f"<b>BIN:</b> {bin_num}\n"
            f"<b>Country:</b> {country}\n\n"
            f"Enter the bank name:\n\n"
            f"<i>Examples:</i> Chase, Wells Fargo, Bank of America, Barclays"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cat_menu_{category}"))
        
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id, "").startswith("cc_full_bank_"))
    def handle_cc_full_bank(message):
        state = user_states[message.from_user.id]
        parts = state.split('_', 7)
        category = parts[3]
        cc_name = parts[4]
        price = int(parts[5])
        bin_num = parts[6]
        country = parts[7]
        
        bank = message.text.strip()
        
        # Ask for description
        user_states[message.from_user.id] = f"cc_full_bindesc_{category}_{cc_name}_{price}_{bin_num}_{country}_{bank}"
        
        text = (
            f"📝 <b>Step 6: Description</b>\n\n"
            f"<b>Product:</b> {cc_name}\n"
            f"<b>Price:</b> ${price}\n"
            f"<b>BIN:</b> {bin_num}\n"
            f"<b>Country:</b> {country}\n"
            f"<b>Bank:</b> {bank}\n\n"
            f"Enter a description:\n\n"
            f"<i>Examples:</i>\n"
            f"• Works great for Netflix and streaming\n"
            f"• High success rate for online shopping\n"
            f"• Premium BIN with good approval rates"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cat_menu_{category}"))
        
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id, "").startswith("cc_full_bindesc_"))
    def handle_cc_full_bindesc(message):
        state = user_states[message.from_user.id]
        parts = state.split('_', 8)
        category = parts[3]
        cc_name = parts[4]
        price = int(parts[5])
        bin_num = parts[6]
        country = parts[7]
        bank = parts[8]
        
        description = message.text.strip()
        
        # Create the BIN product
        new_item = {
            "name": cc_name,
            "price": price,
            "description": description,
            "bin": bin_num,
            "status": "WORKING",
            "country": country,
            "info": "Credit Card",
            "bank": bank
        }
            
        # Add to products
        products = get_products_from_cache()
        if category not in products:
            products[category] = []
        products[category].append(new_item)
        
        # Save products
        save_products_to_file_and_reload(products)
        
        # Clear state
        del user_states[message.from_user.id]
        
        # Confirmation
        text = (
            f"✅ <b>BIN Added Successfully!</b>\n\n"
            f"<b>Name:</b> {cc_name}\n"
            f"<b>Price:</b> ${price}\n"
            f"<b>BIN:</b> {bin_num}\n"
            f"<b>Country:</b> {country}\n"
            f"<b>Bank:</b> {bank}\n"
            f"<b>Description:</b> {description}\n\n"
            f"The BIN is now available in the shop!"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("➕ Add Another BIN", callback_data=f"cc_full_{category}"),
            types.InlineKeyboardButton("🔧 Manage Category", callback_data=f"admin_cat_menu_{category}"),
            types.InlineKeyboardButton("⬅️ Back to Products", callback_data="admin_products_menu")
        )
        
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_cat_menu_"))
    def category_menu_callback(call):
        category = call.data.replace("admin_cat_menu_", "", 1)
        # Clear any add-item waiting state for this admin when navigating back to category menu
        try:
            st = user_states.get(call.from_user.id)
            if isinstance(st, str) and st.startswith("awaiting_json_"):
                user_states.pop(call.from_user.id, None)
        except Exception:
            pass
        category_name = CATEGORY_NAMES.get(category, "Items")
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Add Item", callback_data=f"admin_add_{category}"),
            types.InlineKeyboardButton("➖ Remove Item", callback_data=f"admin_remove_list_{category}")
        )
        if category in {"methods", "method_bins", "other", "dumps", "rdp", "phishing_kits"}:
            markup.add(types.InlineKeyboardButton("🧭 Add via Wizard", callback_data=f"admin_addwiz_{category}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_manage_products"))
        bot.edit_message_text(f"🔧 **Manage {category_name}**\n\nWhat would you like to do?", call.message.chat.id, call.message.message_id, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_add_"))
    def add_item_callback(call):
        category = call.data.replace("admin_add_", "", 1)
        
        # Special handling for CC categories with enhanced format
        if category in ["ready_ccs", "bins"]:
            show_cc_add_wizard(call, category)
            return
            
        user_states[call.from_user.id] = f"awaiting_json_{category}"
        # Present helper controls: Cancel and Use Last Draft (if exists)
        markup = types.InlineKeyboardMarkup()
        # In-memory last draft store per admin id, per category
        last_key = f"last_draft_{call.from_user.id}_{category}"
        if user_states.get(last_key):
            markup.add(types.InlineKeyboardButton("📝 Use Last Draft", callback_data=f"admin_use_last_{category}"))
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cancel_add_{category}"))
        if category in RESTRICTED_MEDIA_CATEGORIES:
            base = f"Please send the new item details for the **{CATEGORY_NAMES[category]}** category in JSON format (text only).\n\nRequired keys: `name`, `price`, `description`.\n\n"
            if category == "bins":
                example = (
                    "Example BIN (with optional fields):\n"
                    "```json\n"
                    "{\n"
                    '  "name": "Netflix BIN",\n'
                    '  "price": 10,\n'
                    '  "description": "For Netflix, Spotify, etc.",\n'
                    '  "bin": "4567890000000000",\n'
                    '  "status": "WORKING",\n'
                    '  "country": "USA",\n'
                    '  "info": "VISA Credit Traditional",\n'
                    '  "bank": "CHASE BANK"\n'
                    "}\n"
                    "```\n\n"
                )
            elif category == "gift_cards":
                example = (
                    "Example Gift Card item:\n"
                    "```json\n"
                    "{\n"
                    '  "name": "Amazon Gift Card $50",\n'
                    '  "price": 50,\n'
                    '  "description": "$50 Amazon US Gift Card."\n'
                    "}\n"
                    "```\n\n"
                )
            else:  # ready_ccs
                example = (
                    "Example Credit Card (use same fields as BIN):\n"
                    "```json\n"
                    "{\n"
                    '  "name": "Premium CC",\n'
                    '  "price": 35,\n'
                    '  "description": "High balance CC.",\n'
                    '  "bin": "5123450000000000",\n'
                    '  "status": "WORKING",\n'
                    '  "country": "UK",\n'
                    '  "info": "MasterCard Debit",\n'
                    '  "bank": "BARCLAYS BANK PLC"\n'
                    "}\n"
                    "```\n\n"
                )
            text = base + example + "Note: media or link-only submissions are not allowed for this category."
        else:
            text = (
                f"Please send the new item details for the **{CATEGORY_NAMES[category]}** category.\n\n"
                "Options:\n"
                "1) JSON (text) with keys: `name`, `price`, `description`, optional `delivery_type` ('link','file','text','tg_document','tg_photo','tg_video','tg_animation') and `delivery_content`.\n"
                "2) Send ANY file (document/photo/video/animation). Optional caption: `Name | Price | Description`.\n"
                "3) Send a LINK (http/https) or plain TEXT as the content.\n\n"
                "Examples:\n"
                "- Caption + file: `Carding PDF Guide | 75 | Complete guide`\n"
                "- JSON with text delivery:\n"
                "```json\n{\n  \"name\": \"Private Login\",\n  \"price\": 50,\n  \"description\": \"Login for a premium service.\",\n  \"delivery_type\": \"text\",\n  \"delivery_content\": \"<b>Service</b>: Example\n<b>User</b>: u\n<b>Pass</b>: p\"\n}\n```\n"
            )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_cancel_add_"))
    def admin_cancel_add_item(call):
        category = call.data.replace("admin_cancel_add_", "", 1)
        # Clear state
        try:
            user_states.pop(call.from_user.id, None)
        except Exception:
            pass
        # Navigate back to category menu
        call.data = f"admin_cat_menu_{category}"
        category_menu_callback(call)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_use_last_"))
    def admin_use_last_draft(call):
        category = call.data.replace("admin_use_last_", "", 1)
        last_key = f"last_draft_{call.from_user.id}_{category}"
        draft = user_states.get(last_key)
        if not draft:
            bot.answer_callback_query(call.id, "No draft found.")
            return
        # Re-send JSON to allow quick edit and send
        bot.edit_message_text(
            f"Restored last draft for <b>{CATEGORY_NAMES.get(category, category)}</b>:\n\n<code>{json.dumps(draft, indent=2)}</code>\n\nSend updated JSON now, or press Cancel.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cat_menu_{category}"))
        )

    # ===== ADD ITEM WIZARD =====
    def _is_wizard(uid):
        st = user_states.get(uid)
        return isinstance(st, dict) and st.get("flow") == "add_wizard"

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_addwiz_"))
    def add_item_wizard_start(call):
        category = call.data.replace("admin_addwiz_", "", 1)
        if category in RESTRICTED_MEDIA_CATEGORIES:
            bot.answer_callback_query(call.id, "This category only accepts JSON via text (no media/link-only).", show_alert=True)
            return
        user_states[call.from_user.id] = {"flow": "add_wizard", "category": category, "step": "name", "data": {}}
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cat_menu_{category}"))
        bot.edit_message_text(
            f"🧭 <b>Add {CATEGORY_NAMES.get(category, 'Item')} via Wizard</b>\n\nStep 1/5 — Send the <b>Name</b> of the item.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML",
        )

    @bot.message_handler(func=lambda m: _is_wizard(m.from_user.id) and user_states[m.from_user.id].get("step") in ("name","price","quantity","description","bin"), content_types=['text'])
    def add_item_wizard_text_steps(message):
        st = user_states.get(message.from_user.id)
        step = st.get("step")
        data = st.get("data", {})
        category = st.get("category")
        if message.text.strip().lower() in {"/cancel", "cancel"}:
            del user_states[message.from_user.id]
            bot.send_message(message.chat.id, "❌ Wizard cancelled.")
            return
        try:
            if step == "name":
                data["name"] = message.text.strip()
                st["step"] = "price"
                bot.send_message(message.chat.id, "Step 2/5 — Send the <b>Price</b> in USD (number).", parse_mode="HTML")
            elif step == "price":
                price_val = int(message.text.strip())
                if price_val < 0:
                    raise ValueError("Price must be >= 0")
                data["price"] = price_val
                st["step"] = "quantity"
                bot.send_message(message.chat.id, "Step 3/5 — Send the <b>Quantity</b> (0 for unlimited).", parse_mode="HTML")
            elif step == "quantity":
                qty_val = int(message.text.strip())
                if qty_val < 0:
                    raise ValueError("Quantity must be >= 0")
                data["quantity"] = qty_val
                # For method_bins, ask for a BIN before description/content
                if category == "method_bins":
                    st["step"] = "bin"
                    bot.send_message(message.chat.id, "Step 4/6 — Send the <b>BIN</b> (e.g., 456789).", parse_mode="HTML")
                else:
                    st["step"] = "description"
                    bot.send_message(message.chat.id, "Step 4/5 — Send the <b>Description</b> (text).", parse_mode="HTML")
            elif step == "bin":
                # Basic normalization for BIN value
                data["bin"] = message.text.strip().replace(" ", "")
                st["step"] = "description"
                bot.send_message(message.chat.id, "Step 5/6 — Send the <b>Description</b> (text).", parse_mode="HTML")
            elif step == "description":
                data["description"] = message.text.strip()
                st["step"] = "content"
                # Step label depends if category is method_bins
                final_step = "6/6" if category == "method_bins" else "5/5"
                bot.send_message(
                    message.chat.id,
                    f"Step {final_step} — Send the <b>Content</b>:\n- Paste a <b>link</b> (starts with http/https),\n- Or write <b>text</b>,\n- Or send a <b>file/photo/video/animation</b>.",
                    parse_mode="HTML",
                )
        except ValueError as ve:
            bot.send_message(message.chat.id, f"❌ {ve}")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {e}")

    @bot.message_handler(func=lambda m: _is_wizard(m.from_user.id) and user_states[m.from_user.id].get("step") == 'content', content_types=['text','document','photo','video','animation'])
    def add_item_wizard_content(message):
        st = user_states.get(message.from_user.id)
        data = st.get("data", {})
        category = st.get("category")
        try:
            delivery_type = None
            delivery_content = None
            if message.content_type == 'text':
                txt = message.text.strip()
                if txt.lower() in {"/cancel","cancel"}:
                    del user_states[message.from_user.id]
                    bot.send_message(message.chat.id, "❌ Wizard cancelled.")
                    return
                if txt.startswith("http://") or txt.startswith("https://"):
                    delivery_type = 'link'
                    delivery_content = txt
                else:
                    delivery_type = 'text'
                    delivery_content = txt
            elif message.content_type == 'document':
                delivery_type = 'tg_document'
                delivery_content = message.document.file_id
            elif message.content_type == 'photo':
                delivery_type = 'tg_photo'
                delivery_content = message.photo[-1].file_id
            elif message.content_type == 'video':
                delivery_type = 'tg_video'
                delivery_content = message.video.file_id
            elif message.content_type == 'animation':
                delivery_type = 'tg_animation'
                delivery_content = message.animation.file_id
            else:
                raise ValueError("Unsupported content type")

            item = {
                "name": data.get("name", "Unnamed"),
                "price": data.get("price", 0),
                "description": data.get("description", ""),
                "delivery_type": delivery_type,
                "delivery_content": delivery_content,
            }
            # Save BIN for bundle category
            if st.get("category") == "method_bins" and data.get("bin"):
                item["bin"] = data.get("bin")
            if "quantity" in data:
                item["quantity"] = data["quantity"]

            products_data = get_products_from_cache()
            if category not in products_data:
                products_data[category] = []
            products_data[category].append(item)
            save_products_to_file_and_reload(products_data)
            del user_states[message.from_user.id]
            bot.send_message(message.chat.id, f"✅ Added new item to <b>{CATEGORY_NAMES.get(category, category)}</b>.", parse_mode="HTML")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {e}")

    def _parse_key_value_caption(caption: str) -> dict:
        """Parses a multi-line key: value caption into a dictionary."""
        data = {}
        if not caption:
            return data
        for line in caption.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                if key and value:
                    # Try to convert price to a number
                    if key in ['price', 'quantity']:
                        try:
                            data[key] = int(value)
                        except ValueError:
                            data[key] = value # Keep as string if conversion fails
                    else:
                        data[key] = value
        return data

    def _parse_caption_meta(caption: str):
        name, price, desc = None, None, None
        if caption:
            parts = [p.strip() for p in caption.split('|')]
            if len(parts) >= 1:
                name = parts[0] or None
            if len(parts) >= 2:
                try:
                    price = int(parts[1].replace('$','').strip())
                except Exception:
                    price = None
            if len(parts) >= 3:
                desc = parts[2]
        return name, price, desc

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id, "").startswith("awaiting_json_"), content_types=['text','document','photo','video','animation'])
    def handle_add_item_message(message):
        admin_id = message.from_user.id
        state = user_states[admin_id]
        category = state.replace("awaiting_json_", "")
        try:
            products_data = get_products_from_cache()
            item = None

            if category in RESTRICTED_MEDIA_CATEGORIES:
                # Only accept JSON text for restricted categories
                if message.content_type != 'text':
                    raise ValueError("This category only accepts JSON via text (no media or link-only).")
                try:
                    parsed = json.loads(message.text)
                    if not all(k in parsed for k in ["name", "price", "description"]):
                        raise ValueError("Missing required keys: name, price, description.")
                    item = parsed
                except json.JSONDecodeError:
                    raise ValueError("Invalid JSON. Please send a valid JSON object.")
            else:
                if message.content_type == 'text':
                    # Try JSON first; else parse simple caption format
                    try:
                        parsed = json.loads(message.text)
                        if not all(k in parsed for k in ["name", "price", "description"]):
                            raise ValueError("Missing required keys: name, price, description.")
                        item = parsed
                    except json.JSONDecodeError:
                        n, p, d = _parse_caption_meta(message.text)
                        if not (n and p):
                            # Allow plain link/text as content via wizard-like behavior
                            # Interpret as content message when caption pattern missing
                            txt = message.text.strip()
                            if txt.startswith("http://") or txt.startswith("https://"):
                                item = {"name": "Link Item", "price": 0, "description": "", "delivery_type": "link", "delivery_content": txt}
                            else:
                                item = {"name": "Text Item", "price": 0, "description": "", "delivery_type": "text", "delivery_content": txt}
                        else:
                            item = {"name": n, "price": p, "description": d or ""}

                elif message.content_type in ['document','photo','video','animation']:
                    # Use the new key-value parser for captions
                    caption_data = _parse_key_value_caption(message.caption or "")

                    # Extract file_id and map to delivery type
                    if message.document:
                        file_id = message.document.file_id
                        delivery_type = 'tg_document'
                    elif message.photo:
                        file_id = message.photo[-1].file_id
                        delivery_type = 'tg_photo'
                    elif message.video:
                        file_id = message.video.file_id
                        delivery_type = 'tg_video'
                    elif message.animation:
                        file_id = message.animation.file_id
                        delivery_type = 'tg_animation'
                    else:
                        raise ValueError("Unsupported media type")

                    # Start with the data from the caption
                    item = caption_data

                    # Add/overwrite delivery details
                    item['delivery_type'] = delivery_type
                    item['delivery_content'] = file_id

                    # Ensure essential keys have default values if not in caption
                    if 'name' not in item:
                        item['name'] = f"Uploaded {delivery_type.split('_')[1].title()}"
                    if 'price' not in item:
                        item['price'] = 0
                    if 'description' not in item:
                        item['description'] = ""

                else:
                    raise ValueError("Unsupported message type")

            # Save last draft for quick reuse
            try:
                user_states[f"last_draft_{admin_id}_{category}"] = item
            except Exception:
                pass

            # Ensure category key exists
            if category not in products_data:
                products_data[category] = []
            products_data[category].append(item)
            save_products_to_file_and_reload(products_data)
            bot.send_message(message.chat.id, f"✅ Successfully added new item to <b>{CATEGORY_NAMES[category]}</b>.", parse_mode="HTML")
            del user_states[admin_id]
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ An error occurred: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_remove_list_"))
    def remove_item_list_callback(call):
        category = call.data.replace("admin_remove_list_", "")
        items = get_products_from_cache(category)
        
        if not items:
            bot.answer_callback_query(call.id, f"No items to remove in {CATEGORY_NAMES[category]}.", show_alert=True)
            return
            
        markup = types.InlineKeyboardMarkup(row_width=1)
        for index, item in enumerate(items):
            markup.add(types.InlineKeyboardButton(f"🗑️ {item['name']}", callback_data=f"admin_delete_{category}_{index}"))
        
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=f"admin_cat_menu_{category}"))
        bot.edit_message_text(f"➖ **Remove from {CATEGORY_NAMES[category]}**\n\nSelect an item to delete permanently:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_delete_"))
    def delete_item_callback(call):
        try:
            # Pattern: admin_delete_{category}_{index} where category may contain underscores
            prefix = "admin_delete_"
            payload = call.data[len(prefix):]
            category, index_str = payload.rsplit('_', 1)
            index = int(index_str)
            products_data = get_products_from_cache()
            if 0 <= index < len(products_data[category]):
                # Remove the item from the list at the specified index.
                products_data[category].pop(index)
                save_products_to_file_and_reload(products_data)
                bot.answer_callback_query(call.id, "✅ Item successfully removed.")
                # Refresh the list of items to show the change immediately.
                remove_item_list_callback(call)
            else:
                raise IndexError("The selected item index is out of range, it might have been deleted already.")
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {e}", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data == "admin_orders")
    def admin_orders_callback(call):
        if call.from_user.id != ADMIN_ID: return
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, item_name, price_usd, payment_status FROM orders ORDER BY creation_date DESC LIMIT 10")
            orders = cursor.fetchall()
        if not orders:
            text = "📦 **Recent Orders**\n\nThere are no orders in the database yet."
        else:
            text = "📦 **Last 10 Orders**\n\n`User ID | Item Name | Price | Status`\n" + "-"*40 + "\n"
            for user_id, item, price, status in orders:
                text += f"`{user_id}` | `{item}` | `${price}` | `{status}`\n"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data == "admin_users" or call.data.startswith("admin_users_page_"))
    def admin_users_callback(call):
        if call.from_user.id != ADMIN_ID: return
        import math
        page = 0
        if call.data.startswith("admin_users_page_"):
            page = int(call.data.split('_')[-1])
        page_size = 10
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(user_id) FROM users")
            count = cursor.fetchone()[0]
            cursor.execute("SELECT user_id, username, join_date, phone_number, referral_count FROM users ORDER BY join_date DESC LIMIT ? OFFSET ?", (page_size, page*page_size))
            users = cursor.fetchall()
        total_pages = math.ceil(count / page_size)
        text = f"<b>👥 Registered Users (Page {page+1}/{total_pages})</b>\nTotal: <b>{count}</b>\n\n"
        if not users:
            text += "No users found."
        else:
            for u in users:
                text += f"<b>ID:</b> <code>{u[0]}</code> | <b>Name:</b> {u[1]} | <b>Refs:</b> {u[4]} | <b>Reg:</b> {u[2][:10]}\n"
        markup = types.InlineKeyboardMarkup()
        nav_buttons = []
        if page > 0:
            nav_buttons.append(types.InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_users_page_{page-1}"))
        if page < total_pages-1:
            nav_buttons.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"admin_users_page_{page+1}"))
        if nav_buttons:
            markup.row(*nav_buttons)
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

