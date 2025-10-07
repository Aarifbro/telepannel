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
    "cc_shop": "🛍️ CC Shop",
    "custom_ccs": "🎛️ Custom CC",
    "ready_ccs": "💳 Ready CC",
    # Unified bundle category replacing legacy bins/methods variations
    "method_bins": "💎 BIN+Method Bundle",
    "gift_cards": "🎁 Gift Cards",
    "hacks": "🔧 Hacks",
    "dumps": "💾 Dumps",
    "rdp": "🖥️ RDPs",
    "other": "📦 Other Items"
}

# Categories where media/link-based items are NOT allowed via admin add; only JSON text is accepted
RESTRICTED_MEDIA_CATEGORIES = {"custom_ccs", "ready_ccs", "gift_cards"}

def register_other_handlers(bot, user_states, get_products_from_cache, save_products_to_file_and_reload):
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
                "ready_ccs": "cc_ready_menu",
                "gift_cards": "giftcards_menu",
                "dumps": "dumps_menu",
                "hacks": "hacks_menu",
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
        
        # Owner-exclusive admin management
        markup.add(
            types.InlineKeyboardButton("➕ Add Global Admin", callback_data="owner_add_admin"),
            types.InlineKeyboardButton("➖ Remove Global Admin", callback_data="owner_remove_admin")
        )
        markup.add(
            types.InlineKeyboardButton("👥 List Global Admins", callback_data="owner_list_admins"),
            types.InlineKeyboardButton("� User Chat", callback_data="owner_user_chat")
        )
        
        # Section admin management
        markup.add(
            types.InlineKeyboardButton("➕ Add Section Admin", callback_data="owner_add_section_admin"),
            types.InlineKeyboardButton("➖ Remove Section Admin", callback_data="owner_remove_section_admin")
        )
        markup.add(
            types.InlineKeyboardButton("👥 List Section Admins", callback_data="owner_list_section_admins"),
            types.InlineKeyboardButton("🎛️ Button Status Manager", callback_data="status_manager")
        )
        
        # Quick access to admin tools & stats
        markup.add(
            types.InlineKeyboardButton("⚙️ Admin Tools", callback_data="admin_panel"),
            types.InlineKeyboardButton("📊 Bot Stats", callback_data="owner_bot_stats")
        )
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
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
                if category in ['custom_ccs', 'ready_ccs']:
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
        if category in ["custom_ccs", "ready_ccs"]:
            markup.add(types.InlineKeyboardButton("⬅️ Back to CC Shop", callback_data="admin_cc_shop_menu"))
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
        if call.from_user.id != ADMIN_ID:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor(); c.execute("SELECT 1 FROM admins WHERE user_id = ?", (call.from_user.id,))
                if not c.fetchone():
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
            else:
                bot.send_message(message.chat.id, f"✅ Added <b>{name}</b> (ID {next_id}) to <code>{CATEGORY_NAMES.get(category, category)}</code>.", parse_mode="HTML")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Failed to save item: {e}")
        finally:
            if not user_states.get(message.from_user.id, '').startswith('wizard_file_method_bins::'):
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

    # =============================
    # ===== Delete / Clear Items ===
    # =============================
    @bot.callback_query_handler(func=lambda call: call.data.startswith("delete_item_"))
    def delete_item(call):
        try:
            _, category, item_id = call.data.split('_', 2)
            item_id = int(item_id)
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
        category = call.data.replace("clear_cat_", "")
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
        """Shows custom CC products from the product management system"""
        create_dynamic_product_menu(call, "custom_ccs")

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
            # Only show User Chat for non-owners (owners have it in Owner Panel)
            if not is_owner:
                markup.add(
                    types.InlineKeyboardButton("💬 User Chat", callback_data="admin_user_chat"),
                    types.InlineKeyboardButton("📱 Payments", callback_data="admin_payments_menu")
                )
            else:
                markup.add(types.InlineKeyboardButton("📱 Payments", callback_data="admin_payments_menu"))
            
            # 💬 SUPPORT SYSTEM 💬
            markup.add(
                types.InlineKeyboardButton("🎯 Support Center", callback_data="admin_support_dashboard")
            )
            
            # 🎁 REWARDS & KEYS 🎁
            markup.add(
                types.InlineKeyboardButton("🏆 Referrals", callback_data="admin_referrals_menu"),
                types.InlineKeyboardButton("🔑 Pro Keys", callback_data="admin_keys_menu")
            )
            markup.add(
                types.InlineKeyboardButton("🎁 Giveaway", callback_data="admin_giveaway_menu"),
                types.InlineKeyboardButton("📈 Analytics", callback_data="admin_analytics_menu")
            )
            
            if is_owner:
                # 👑 OWNER EXCLUSIVE 👑 (non-duplicates only)
                markup.add(
                    types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
                    types.InlineKeyboardButton("🖼️ Media", callback_data="admin_media_menu")
                )
                # Settings only (Admins & Status Manager are in Owner Panel)
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
            cursor.execute("SELECT user_id, username, balance, registration_date FROM users ORDER BY registration_date DESC LIMIT 20")
            users = cursor.fetchall()
        
        text = "📋 <b>All Users (Recent 20)</b>\n\n"
        if not users:
            text += "No users found."
        else:
            for user in users:
                text += f"<b>ID:</b> <code>{user[0]}</code>\n"
                text += f"<b>Name:</b> {user[1]}\n"
                text += f"<b>Balance:</b> ${user[2]:.2f}\n"
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
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

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
        # Refresh
        counts = get_media_pool_counts()
        text = "🖼️ <b>Media Pools</b>\n\n" + "\n".join([f"<b>{k}:</b> {v}" for k, v in counts.items()])
        markup = types.InlineKeyboardMarkup(row_width=2)
        for kind in counts.keys():
            markup.add(types.InlineKeyboardButton(f"🗑️ {kind}", callback_data=f"media_clear_kind_{kind}"))
        markup.add(types.InlineKeyboardButton("🧹 Clear All", callback_data="media_clear_all"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"))
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
        except Exception:
            pass

    # ----- Status manager redirect -----
    @bot.callback_query_handler(func=lambda call: call.data == "status_manager")
    def status_manager(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only", show_alert=True)
            return
        # Import DB-backed helpers lazily to avoid circular import
        from admin_meta_db import list_all_statuses, set_section_status
        # Determine ordered list relative to SECTION_STATUS_OPTIONS duplication (mirror constant from main)
        status_order = ["coming_soon", "error", "maintenance", "available"]
        existing = {k: v for k, v in list_all_statuses()}
        # Define canonical section keys & pretty names
        sections = [
            ("gift_cards", "Gift Cards"),
            ("dumps", "Dumps"),
            ("hacks", "Hacks"),
            ("cc", "Credit Cards"),
            ("bins", "BINs"),
            ("rdp", "RDP"),
            ("methods", "Methods"),
            ("other", "Other"),
        ]
        text = "🛠️ <b>Section Status Manager</b>\n\nTap a button to cycle a section through: Coming Soon → Error → Maintenance → Available.\n"
        markup = types.InlineKeyboardMarkup(row_width=1)
        for key, label in sections:
            cur = existing.get(key, "coming_soon")
            emoji = {
                "coming_soon": "🟡",
                "error": "🔴",
                "maintenance": "🛠️",
                "available": "🟢"
            }.get(cur, "🟡")
            # Each button cycles the status
            markup.add(types.InlineKeyboardButton(f"{emoji} {label}: {cur}", callback_data=f"cycle_status_{key}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("cycle_status_"))
    def cycle_status(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Owner only", show_alert=True)
            return
        from admin_meta_db import list_all_statuses, set_section_status
        key = call.data.replace("cycle_status_", "")
        order = ["coming_soon", "error", "maintenance", "available"]
        existing = {k: v for k, v in list_all_statuses()}
        cur = existing.get(key, "coming_soon")
        try:
            nxt = order[(order.index(cur) + 1) % len(order)]
        except Exception:
            nxt = "coming_soon"
        set_section_status(key, nxt)
        bot.answer_callback_query(call.id, f"{key} → {nxt}")
        # Re-render manager
        try:
            status_manager(call)
        except Exception:
            pass

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
            "• Status Manager (toggle section availability)\n"
            "• Media Manager (GIF pools)\n"
            "• Manage Admins & Pro Keys\n\n"
            "Planned additions: pricing rules, auto-expiry, audit exports."
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🎛️ Status Manager", callback_data="status_manager"),
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
        
        user_id = call.data.replace("admin_send_msg_", "")
        bot.answer_callback_query(call.id, "This feature is coming soon!", show_alert=True)
    
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