from telebot import types
import sqlite3
import json
from config import DB_NAME, ADMIN_ID
from database import get_user_details, load_products, save_products

# A dictionary to map internal category keys to their user-friendly, display-ready names.
# This makes it easy to change how categories are presented to the user without changing the code logic.
CATEGORY_NAMES = {
    "bins": "BINs",
    "ready_ccs": "Ready CCs",
    "gift_cards": "Gift Cards",
    "rdp": "RDPs",
    "methods": "Methods",
    "other": "Other Items"
}

def register_other_handlers(bot, user_states):
    # --- Owner Panel ---
    @bot.callback_query_handler(func=lambda call: call.data == "owner_panel")
    def owner_panel_callback(call):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Only the owner can access this panel.", show_alert=True)
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("➕ Add Global Admin", callback_data="owner_add_admin"),
            types.InlineKeyboardButton("➖ Remove Global Admin", callback_data="owner_remove_admin"),
            types.InlineKeyboardButton("👥 List Global Admins", callback_data="owner_list_admins"),
            types.InlineKeyboardButton("➕ Add Section Admin", callback_data="owner_add_section_admin"),
            types.InlineKeyboardButton("➖ Remove Section Admin", callback_data="owner_remove_section_admin"),
            types.InlineKeyboardButton("👥 List Section Admins", callback_data="owner_list_section_admins"),
            types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")
        )
        bot.edit_message_text("👑 <b>Owner Panel</b>\n\nManage global and section-based admins. Section admins can only manage their assigned section (e.g., Hacks).", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    # Section Admin Management
    @bot.callback_query_handler(func=lambda call: call.data == "owner_add_section_admin")
    def owner_add_section_admin_prompt(call):
        user_states[call.from_user.id] = "awaiting_new_section_admin_id"
        bot.edit_message_text("Send the <b>User ID</b> and <b>Section</b> (e.g., hacks) to assign, separated by a space.\nExample: <code>123456789 hacks</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML")

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
        bot.edit_message_text("Send the <b>User ID</b> and <b>Section</b> to remove, separated by a space.\nExample: <code>123456789 hacks</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML")

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

    @bot.callback_query_handler(func=lambda call: call.data == "owner_add_admin")
    def owner_add_admin_prompt(call):
        user_states[call.from_user.id] = "awaiting_new_admin_id"
        bot.edit_message_text("Send the <b>User ID</b> of the user you want to add as admin.", call.message.chat.id, call.message.message_id, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_new_admin_id")
    def owner_add_admin(message):
        try:
            user_id = int(message.text.strip())
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid User ID. Please send a numeric User ID.")
            return
        import sqlite3
        from config import DB_NAME
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            if cursor.fetchone():
                bot.send_message(message.chat.id, "User is already an admin.")
                return
            cursor.execute("INSERT INTO admins (user_id, username, added_by, added_at) VALUES (?, ?, ?, datetime('now'))", (user_id, None, message.from_user.id))
            conn.commit()
        bot.send_message(message.chat.id, f"✅ User <code>{user_id}</code> added as admin.", parse_mode="HTML")
        del user_states[message.from_user.id]

    @bot.callback_query_handler(func=lambda call: call.data == "owner_remove_admin")
    def owner_remove_admin_prompt(call):
        user_states[call.from_user.id] = "awaiting_remove_admin_id"
        bot.edit_message_text("Send the <b>User ID</b> of the admin you want to remove.", call.message.chat.id, call.message.message_id, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_remove_admin_id")
    def owner_remove_admin(message):
        try:
            user_id = int(message.text.strip())
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid User ID. Please send a numeric User ID.")
            return
        import sqlite3
        from config import DB_NAME
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
            conn.commit()
        bot.send_message(message.chat.id, f"✅ User <code>{user_id}</code> removed from admins.", parse_mode="HTML")
        del user_states[message.from_user.id]

    @bot.callback_query_handler(func=lambda call: call.data == "owner_list_admins")
    def owner_list_admins(call):
        import sqlite3
        from config import DB_NAME
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, added_at FROM admins ORDER BY added_at DESC")
            admins = cursor.fetchall()
        text = "<b>Current Admins:</b>\n"
        if not admins:
            text += "No admins found."
        else:
            for a in admins:
                text += f"<b>ID:</b> <code>{a[0]}</code> | <b>Username:</b> {a[1] or '-'} | <b>Added:</b> {a[2]}\n"
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
        products_data = load_products()
        # Get the list of items for the specific category (e.g., "gift_cards").
        products = products_data.get(category_key, [])
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

This is your personal dashboard where you can find your information and track your referrals.

**Name:** `{user_details['username']}`
**User ID:** `{user_details['user_id']}`
**Total Referrals:** `{user_details['referral_count']}`

**Your Referral Link:**
`{referral_link}`

Share this unique link with your friends. Every time someone starts the bot using your link, your referral count will increase. Special bonuses may be available for top referrers in the future!
"""
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    # The 'giftcards_menu' callback is now handled in main.py as 'Coming Soon'.

    @bot.callback_query_handler(func=lambda call: call.data == "rdp_menu")
    def rdp_menu(call):
        create_dynamic_product_menu(call, "rdp")
    
    @bot.callback_query_handler(func=lambda call: call.data == "method_menu")
    def method_menu(call):
        create_dynamic_product_menu(call, "methods")
    
    @bot.callback_query_handler(func=lambda call: call.data == "other_menu")
    def other_menu(call):
        create_dynamic_product_menu(call, "other")

    @bot.callback_query_handler(func=lambda call: call.data == "support")
    def support_callback(call):
        text = "🛠️ **Support**\n\nIf you need any assistance with an order or have a question, please contact the admin directly. To help us resolve your issue quickly, please mention your User ID when you contact us."
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

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
        is_global_admin = False
        section_admin_sections = []
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            is_global_admin = cursor.fetchone() is not None or user_id == ADMIN_ID
            cursor.execute("SELECT section FROM section_admins WHERE user_id = ?", (user_id,))
            section_admin_sections = [row[0] for row in cursor.fetchall()]
        if not (is_global_admin or section_admin_sections):
            bot.answer_callback_query(call.id, "❌ Access Denied! Only global or section admins can access this panel.", show_alert=True)
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        if is_global_admin:
            markup.add(
                types.InlineKeyboardButton("📦 Manage Products", callback_data="admin_manage_products"),
                types.InlineKeyboardButton("📊 Manage Orders", callback_data="admin_orders"),
                types.InlineKeyboardButton("👥 View Users", callback_data="admin_users"),
                types.InlineKeyboardButton("🔎 User Lookup", callback_data="admin_user_lookup")
            )
        for section in section_admin_sections:
            markup.add(types.InlineKeyboardButton(f"� Manage {section.title()} Orders", callback_data=f"admin_orders_{section}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        bot.edit_message_text("🔐 **Admin Panel**\n\nHere you can manage products, view recent orders, see user statistics, and look up user purchase/payment history. Section admins see only their assigned section's orders.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

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
        bot.edit_message_text("Please send the <b>User ID</b> of the user you want to look up.", call.message.chat.id, call.message.message_id, parse_mode="HTML")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_user_lookup_id")
    def admin_user_lookup(message):
        user_id = message.text.strip()
        try:
            user_id_int = int(user_id)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid User ID. Please send a numeric User ID.")
            return
        from database import get_user_details
        user = get_user_details(user_id_int)
        if not user:
            bot.send_message(message.chat.id, f"❌ No user found with ID {user_id}.")
            return
        # Fetch purchase/payment history
        import sqlite3
        from config import DB_NAME
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
        for key, name in CATEGORY_NAMES.items():
            markup.add(types.InlineKeyboardButton(f"🔧 Manage {name}", callback_data=f"admin_cat_menu_{key}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_panel"))
        bot.edit_message_text("📦 **Manage Products**\n\nChoose a category to add, remove, or modify items.", call.message.chat.id, call.message.message_id, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_cat_menu_"))
    def category_menu_callback(call):
        category = call.data.split('_')[3]
        category_name = CATEGORY_NAMES.get(category, "Items")
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Add Item", callback_data=f"admin_add_{category}"),
            types.InlineKeyboardButton("➖ Remove Item", callback_data=f"admin_remove_list_{category}")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_manage_products"))
        bot.edit_message_text(f"🔧 **Manage {category_name}**\n\nWhat would you like to do?", call.message.chat.id, call.message.message_id, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_add_"))
    def add_item_callback(call):
        category = call.data.split('_')[2]
        user_states[call.from_user.id] = f"awaiting_json_{category}"
        text = (
            f"Please send the new item details for the **{CATEGORY_NAMES[category]}** category in JSON format.\n\n"
            "**Required keys:** `name`, `price`, `description`.\n"
            "For **BINs**, you must also include: `bin`, `status`, `country`, `info`, `bank`.\n\n"
            "Example for a Gift Card:\n"
            "```json\n"
            "{\n"
            '  "name": "Netflix Gift Card",\n'
            '  "price": 20,\n'
            '  "description": "$20 Netflix US Gift Card."\n'
            "}\n"
            "```"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    @bot.message_handler(func=lambda message: user_states.get(message.from_user.id, "").startswith("awaiting_json_"))
    def handle_add_item_message(message):
        admin_id = message.from_user.id
        state = user_states[admin_id]
        category = state.split('_')[2]
        try:
            new_item_data = json.loads(message.text)
            # Perform validation to ensure the essential keys are present.
            if not all(key in new_item_data for key in ["name", "price", "description"]):
                raise ValueError("The JSON is missing one of the required keys: name, price, description.")

            # For BINs, auto-fill missing BIN-specific fields with defaults
            if category == "bins":
                for field in ["bin", "status", "country", "info", "bank"]:
                    if field not in new_item_data:
                        new_item_data[field] = "N/A"

            products_data = load_products()
            products_data[category].append(new_item_data)
            save_products(products_data)
            bot.send_message(admin_id, f"✅ Item successfully added to the **{CATEGORY_NAMES[category]}** category!")
        except Exception as e:
            bot.send_message(admin_id, f"❌ An error occurred while adding the item: {e}")
        finally:
            # Clean up the user's state to prevent accidental triggers.
            if admin_id in user_states:
                del user_states[admin_id]

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_remove_list_"))
    def remove_item_list_callback(call):
        category = call.data.split('_')[3]
        products_data = load_products()
        items = products_data.get(category, [])
        if not items:
            bot.answer_callback_query(call.id, "There are no items in this category to remove.", show_alert=True)
            return
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        for index, item in enumerate(items):
            markup.add(types.InlineKeyboardButton(f"🗑️ {item['name']}", callback_data=f"admin_delete_{category}_{index}"))
        
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=f"admin_cat_menu_{category}"))
        bot.edit_message_text(f"➖ **Remove from {CATEGORY_NAMES[category]}**\n\nSelect an item to delete permanently:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_delete_"))
    def delete_item_callback(call):
        try:
            _, _, category, index_str = call.data.split('_')
            index = int(index_str)
            products_data = load_products()
            if 0 <= index < len(products_data[category]):
                # Remove the item from the list at the specified index.
                products_data[category].pop(index)
                save_products(products_data)
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
            cursor.execute("SELECT user_id, username, old_username, join_date, phone_number FROM users ORDER BY join_date DESC LIMIT ? OFFSET ?", (page_size, page*page_size))
            users = cursor.fetchall()
        total_pages = math.ceil(count / page_size)
        text = f"<b>👥 Registered Users (Page {page+1}/{total_pages})</b>\nTotal: <b>{count}</b>\n\n"
        if not users:
            text += "No users found."
        else:
            for u in users:
                text += f"<b>ID:</b> <code>{u[0]}</code> | <b>Name:</b> {u[1]} | <b>Old Name:</b> {u[2] or '-'} | <b>Reg:</b> {u[3][:10]} | <b>Phone:</b> {u[4] or '-'}\n"
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

