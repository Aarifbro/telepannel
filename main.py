# --- Gift Card Status Storage ---
import json

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


from payment_handler import register_payment_handlers, show_payment_options
import telebot
import time
import requests
from telebot import types

# Import functions from handler files
from config import API_TOKEN, API_TOKEN_2, ADMIN_ID
from database import init_db, add_user
from helpers import check_force_join, notify_admin
from cc_handler import register_cc_handlers
from bin_handler import register_bin_handlers
from payment_handler import register_payment_handlers
from other_handlers import register_other_handlers


# Initialize the main bot
bot = telebot.TeleBot(API_TOKEN)

# Initialize the mirror bot
mirror_bot = telebot.TeleBot(API_TOKEN_2)

# Register all handlers for the mirror bot (reuse the same handlers)
def register_all_handlers(bot_instance):
    register_cc_handlers(bot_instance, user_states)
    register_bin_handlers(bot_instance)
    register_payment_handlers(bot_instance)
    register_other_handlers(bot_instance, user_states)

# Dictionary to track user states (e.g., awaiting input for admin panel)
user_states = {}

# =================================================================
# ======================== START & MAIN MENU ========================
# =================================================================

# ======================== MAIN MENU & MANAGE ORDERS PANEL ========================
import sqlite3
from config import DB_NAME, ADMIN_ID

def send_main_menu(chat_id, text, message_id=None):
    """Sends the main menu with dynamic admin/owner panel buttons."""
    bot.send_chat_action(chat_id, 'typing')
    markup = types.InlineKeyboardMarkup(row_width=2)
    # Standard menu buttons with new emojis and Personal Area
    markup.add(
        types.InlineKeyboardButton("� Personal Area", callback_data="personal_area"),
        types.InlineKeyboardButton("💳 Cards", callback_data="cc_menu"),
        types.InlineKeyboardButton("�️ BINs", callback_data="bin_menu"),
        types.InlineKeyboardButton("🎁 Gift Cards", callback_data="giftcards_menu"),
        types.InlineKeyboardButton("💾 Dumps", callback_data="dumps_menu"),
        types.InlineKeyboardButton("�️‍♂️ Hacks", callback_data="hacks_menu"),
        types.InlineKeyboardButton("🖥️ RDP", callback_data="rdp_menu"),
        types.InlineKeyboardButton("📚 Methods", callback_data="method_menu"),
        types.InlineKeyboardButton("✨ Other", callback_data="other_menu"),
        types.InlineKeyboardButton("🆘 Help", callback_data="support")
    )
    # Determine roles
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

    # Owner: add Status Manage button
    if is_owner:
        markup.add(types.InlineKeyboardButton("🛠️ Status Manage", callback_data="status_manage"))
        markup.add(
            types.InlineKeyboardButton("👑 Owner Panel", callback_data="owner_panel"),
            types.InlineKeyboardButton("📦 Manage Orders", callback_data="manage_orders_panel")
        )
    elif is_global_admin:
        markup.add(types.InlineKeyboardButton("🔐 Admin Panel", callback_data="admin_panel"))
        markup.add(types.InlineKeyboardButton("📦 Manage Orders", callback_data="manage_orders_panel"))
    elif is_section_admin:
        markup.add(types.InlineKeyboardButton("📦 Manage Orders", callback_data="manage_orders_panel"))

    # Always send or edit the menu message
    try:
        if message_id:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        pass

# Dedicated Manage Orders panel for admins/section-admins
@bot.callback_query_handler(func=lambda call: call.data == "manage_orders_panel")
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
        bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    # Define all main product sections for order management
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
        # Owner/global admin can manage all sections
        for section_key, section_label in all_sections:
            markup.add(types.InlineKeyboardButton(f"Manage {section_label} Orders", callback_data=f"admin_orders_{section_key}"))
    else:
        # Section admin: only show their assigned sections (and only if the section is valid)
        for section in section_admin_sections:
            label = next((lbl for key, lbl in all_sections if key == section), None)
            if label:
                markup.add(types.InlineKeyboardButton(f"Manage {label} Orders", callback_data=f"admin_orders_{section}"))
    markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
    bot.edit_message_text("<b>📦 Manage Orders Panel</b>\n\nSelect which orders to manage:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
# Buy Hacks main menu
@bot.callback_query_handler(func=lambda call: call.data == "hacks_menu")
def hacks_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("🎣 Premium Phishing Kits", callback_data="phishing_kits_menu"))
    markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
    bot.edit_message_text("<b>🛡️ Buy Hacks</b>\n\nSelect a category:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

# Premium Phishing Kits submenu
from database import load_products
@bot.callback_query_handler(func=lambda call: call.data == "phishing_kits_menu")
def phishing_kits_menu(call):
    products = load_products().get("phishing_kits", [])
    markup = types.InlineKeyboardMarkup(row_width=1)
    if not products:
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="hacks_menu"))
        bot.edit_message_text("<b>🎣 Premium Phishing Kits</b>\n\nNo kits available at the moment.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
        return
    for idx, item in enumerate(products):
        name = item.get("name", "Unnamed Kit")
        price = item.get("price", "?")
        markup.add(types.InlineKeyboardButton(f"🛒 {name} - ${price}", callback_data=f"phishing_kit_detail_{idx}"))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="hacks_menu"))
    bot.edit_message_text("<b>🎣 Premium Phishing Kits</b>\n\nSelect a kit to view details:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

# Show phishing kit details and buy button
@bot.callback_query_handler(func=lambda call: call.data.startswith("phishing_kit_detail_"))
def phishing_kit_detail(call):
    idx = int(call.data.split("_")[-1])
    products = load_products().get("phishing_kits", [])
    if idx >= len(products):
        bot.answer_callback_query(call.id, "Invalid selection.", show_alert=True)
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
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

# Buy phishing kit (route to payment)
from payment_handler import show_payment_options

# --- Payment Option: Add Screenshot Upload and Confirmation ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_phishing_kit_"))
def buy_phishing_kit(call):
    idx = int(call.data.split("_")[-1])
    products = load_products().get("phishing_kits", [])
    if idx >= len(products):
        bot.answer_callback_query(call.id, "Invalid selection.", show_alert=True)
        return
    item = products[idx]
    price = item.get("price", 0)
    name = item.get("name", "Unnamed Kit")
    # Show payment options with screenshot upload
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("➡️ Proceed to Payment", callback_data=f"proceed_payment_{idx}"))
    markup.add(types.InlineKeyboardButton("📸 Send Payment Screenshot", callback_data=f"send_ss_{idx}"))
    markup.add(types.InlineKeyboardButton("⬅️ Back to Kits", callback_data="phishing_kits_menu"))
    bot.edit_message_text(f"<b>{name}</b>\n\n<b>Price:</b> ${price}\n\nChoose a payment option:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

# Handler for Proceed to Payment (original flow)
@bot.callback_query_handler(func=lambda call: call.data.startswith("proceed_payment_"))
def proceed_payment(call):
    idx = int(call.data.split("_")[-1])
    products = load_products().get("phishing_kits", [])
    if idx >= len(products):
        bot.answer_callback_query(call.id, "Invalid selection.", show_alert=True)
        return
    item = products[idx]
    price = item.get("price", 0)
    name = item.get("name", "Unnamed Kit")
    show_payment_options(bot, call, name, price, item, "phishing_kits_menu")

# Handler for Send Payment Screenshot
@bot.callback_query_handler(func=lambda call: call.data.startswith("send_ss_"))
def send_payment_screenshot_prompt(call):
    idx = int(call.data.split("_")[-1])
    products = load_products().get("phishing_kits", [])
    if idx >= len(products):
        bot.answer_callback_query(call.id, "Invalid selection.", show_alert=True)
        return
    user_states[call.from_user.id] = f"awaiting_ss_{idx}"
    bot.send_message(call.from_user.id, "📸 Please upload your payment screenshot now.")

# Handler to receive screenshot and confirm payment
@bot.message_handler(content_types=['photo'])
def receive_payment_screenshot(message):
    state = user_states.get(message.from_user.id, "")
    if state.startswith("awaiting_ss_"):
        idx = int(state.split("_")[-1])
        products = load_products().get("phishing_kits", [])
        if idx >= len(products):
            bot.send_message(message.chat.id, "Invalid product selection.")
            return
        # Save screenshot file_id for admin review (not implemented)
        file_id = message.photo[-1].file_id
        # Ask user to confirm payment after sending screenshot
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Confirm Payment", callback_data=f"confirm_ss_{idx}_{file_id}"))
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="main_menu"))
        bot.send_message(message.chat.id, "Screenshot received! Now confirm your payment:", reply_markup=markup)
        del user_states[message.from_user.id]

# Handler for Confirm Payment after screenshot
@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_ss_"))
def confirm_payment_screenshot(call):
    parts = call.data.split("_")
    idx = int(parts[2])
    file_id = parts[3]
    products = load_products().get("phishing_kits", [])
    if idx >= len(products):
        bot.answer_callback_query(call.id, "Invalid selection.", show_alert=True)
        return
    # Notify owner/admin with screenshot file_id (not implemented)
    bot.send_message(ADMIN_ID, f"User {call.from_user.id} submitted a payment screenshot for {products[idx].get('name','?')}.", reply_markup=None)
    bot.send_photo(ADMIN_ID, file_id, caption=f"Payment screenshot from user {call.from_user.id} for {products[idx].get('name','?')}")
    bot.answer_callback_query(call.id, "Payment confirmation sent! Await admin approval.", show_alert=True)

@bot.message_handler(commands=["start"])
def start_command(message):
    """Handles the /start command, including referrals."""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    parts = message.text.split()
    referrer_code = parts[1] if len(parts) > 1 else None

    add_user(user_id, username, referrer_code)

    intro_text = "✨🛍️ <b>𝓦𝓮𝓵𝓬𝓸𝓶𝓮 𝓽𝓸 𝓟𝓻𝓮𝓶𝓲𝓾𝓶 𝓢𝓱𝓸𝓹 𝓑𝓸𝓽!</b> 🛍️✨\n\n<em>Your one-stop shop for digital goods, deals, and more!</em>\n\n👇 <b>𝑺𝒆𝒍𝒆𝒄𝒕 𝒂 𝒄𝒂𝒕𝒆𝒈𝒐𝒓𝒚 𝒃𝒆𝒍𝒐𝒘 𝒕𝒐 𝒈𝒆𝒕 𝒔𝒕𝒂𝒓𝒕𝒆𝒅</b> 👇"

    if not check_force_join(bot, user_id):
        from config import FORCE_CHANNEL_LINKS
        markup = types.InlineKeyboardMarkup()
        # Add a join button for each channel/group
        for link in FORCE_CHANNEL_LINKS:
            markup.add(types.InlineKeyboardButton("🔗 Join Channel/Group", url=link))
        markup.add(types.InlineKeyboardButton("✅ I Have Joined", callback_data="check_join"))
        force_join_text = f"{intro_text}\n\n⚠️ To get full access, you must first join all our partner channels/groups."
        bot.send_message(user_id, force_join_text, reply_markup=markup, parse_mode="HTML")
    else:
        send_main_menu(user_id, intro_text,)

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def joined_callback(call):
    """Handles the 'I Have Joined' button."""
    if check_force_join(bot, call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        send_main_menu(call.message.chat.id, "<b>✅ Thank you for joining! You can now use the bot.</b>")
    else:
        bot.answer_callback_query(call.id, "❌ You haven't joined the channel yet.", show_alert=True)



# Section status panel for each section (example: Gift Cards)
def get_section_status_label(section_key):
    status_key = get_section_status(section_key)
    return next((label for key, label in SECTION_STATUS_OPTIONS if key == status_key), "🟡 Coming Soon")

@bot.callback_query_handler(func=lambda call: call.data == "giftcards_menu")
def giftcards_status_panel(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
    status_label = get_section_status_label("gift_cards")
    bot.edit_message_text(f"🎁 Gift Cards\n\n<b>Status:</b> {status_label}", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

# --- Status Manage (Owner only, all sections) ---
@bot.callback_query_handler(func=lambda call: call.data == "status_manage")
def status_manage_panel(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Only the owner can access this.", show_alert=True)
        return
    markup = types.InlineKeyboardMarkup()
    for section_key, section_label in SECTION_KEYS:
        status_label = get_section_status_label(section_key)
        markup.add(types.InlineKeyboardButton(f"{section_label}: {status_label}", callback_data=f"set_status_{section_key}"))
    markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
    bot.edit_message_text("<b>Status Manage</b>\n\nSelect a section to update its status:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

# Owner selects section to set status
@bot.callback_query_handler(func=lambda call: call.data.startswith("set_status_"))
def set_section_status_panel(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Only the owner can access this.", show_alert=True)
        return
    section_key = call.data.replace("set_status_", "")
    markup = types.InlineKeyboardMarkup()
    for status_key, status_label in SECTION_STATUS_OPTIONS:
        markup.add(types.InlineKeyboardButton(status_label, callback_data=f"set_section_status_{section_key}_{status_key}"))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="status_manage"))
    current_status = get_section_status(section_key)
    current_label = next((label for k, label in SECTION_STATUS_OPTIONS if k == current_status), "🟡 Coming Soon")
    section_label = next((lbl for k, lbl in SECTION_KEYS if k == section_key), section_key)
    bot.edit_message_text(f"<b>Status Manage</b>\n\nSection: {section_label}\nCurrent status: {current_label}\n\nChoose a new status:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

# Owner sets status for section
@bot.callback_query_handler(func=lambda call: call.data.startswith("set_section_status_"))
def set_section_status_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Only the owner can access this.", show_alert=True)
        return
    parts = call.data.replace("set_section_status_", "").split("_")
    section_key = parts[0]
    status_key = parts[1]
    set_section_status(section_key, status_key)
    bot.answer_callback_query(call.id, "Section status updated!", show_alert=True)
    status_manage_panel(call)


# Dumps: Show real data
from database import load_products
@bot.callback_query_handler(func=lambda call: call.data == "dumps_menu")
def dumps_menu(call):
    products = load_products().get("dumps", [])
    markup = types.InlineKeyboardMarkup(row_width=1)
    if not products:
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        bot.edit_message_text("<b>💾 Dumps</b>\n\n<i>No dumps available at the moment.</i>", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
        return
    for idx, item in enumerate(products):
        name = item.get("name", "Unnamed Dump")
        price = item.get("price", "?")
        markup.add(types.InlineKeyboardButton(f"🛒 {name} - ${price}", callback_data=f"dumps_detail_{idx}"))
    markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
    text = "<b>💾 Dumps</b>\n\nSelect a dump from the list below.\n\nAll dumps are checked and quality guaranteed."
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

# Show dump details professionally
# Show dump details professionally
@bot.callback_query_handler(func=lambda call: call.data.startswith("dumps_detail_"))
def dumps_detail(call):
    idx = int(call.data.split("_")[-1])
    products = load_products().get("dumps", [])
    if idx >= len(products):
        bot.answer_callback_query(call.id, "Invalid selection.", show_alert=True)
        return
    item = products[idx]
    name = item.get("name", "Unnamed Dump")
    price = item.get("price", "?")
    desc = item.get("description", "No description.")
    text = f"<b>{name}</b>\n\n<b>Price:</b> ${price}\n<b>Description:</b> {desc}\n\nTo purchase, click the button below."
    markup = types.InlineKeyboardMarkup()
    # Use a dedicated callback for dumps purchase to avoid long callback data
    markup.add(types.InlineKeyboardButton("💸 Buy Now", callback_data=f"buy_dump_{idx}"))
    markup.add(types.InlineKeyboardButton("⬅️ Back to Dumps List", callback_data="dumps_menu"))
    markup.add(types.InlineKeyboardButton("⬅️ Main Menu", callback_data="main_menu"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

# Place this handler after bot is defined
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_dump_"))
def buy_dump_callback(call):
    idx = int(call.data.split("_")[-1])
    products = load_products().get("dumps", [])
    if idx >= len(products):
        bot.answer_callback_query(call.id, "Invalid selection.", show_alert=True)
        return
    item = products[idx]
    price = item.get("price", 0)
    name = item.get("name", "Unnamed Dump")
    show_payment_options(bot, call, name, price, item, "dumps_menu")

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def main_menu_callback(call):
    """Callback to return to the main menu."""
    send_main_menu(call.message.chat.id, "✅ Welcome back! Please choose an option:", call.message.message_id)

# =================================================================
# ========================== BOT RUN ================================
# =================================================================

if __name__ == '__main__':
    print("🤖 Main bot is starting...")
    init_db()
    register_all_handlers(bot)
    print("✅ Main bot handlers registered.")
    try:
        bot_username = bot.get_me().username
        startup_markup = types.InlineKeyboardMarkup()
        startup_markup.add(types.InlineKeyboardButton("▶️ Start Bot", url=f"https://t.me/{bot_username}?start=admin"))
        notify_admin(bot, "✅ **Main Bot is Online!**", markup=startup_markup)
    except Exception as e:
        print(f"Could not send startup notification with button: {e}")
        notify_admin(bot, "✅ **Main Bot is Online!** (Could not create button)")

    # Start mirror bot in a separate thread
    import threading
    def run_mirror():
        print("🤖 Mirror bot is starting...")
        register_all_handlers(mirror_bot)
        print("✅ Mirror bot handlers registered.")
        mirror_bot.infinity_polling(skip_pending=True, timeout=90)

    threading.Thread(target=run_mirror, daemon=True).start()

    while True:
        try:
            print("▶️ Starting polling for main bot...")
            bot.infinity_polling(skip_pending=True, timeout=90)
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError, telebot.apihelper.ApiTelegramException) as e:
            print(f"🔴 Network error: {e}. Retrying in 15 seconds...")

