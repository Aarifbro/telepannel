"""
Menu handlers for the Telegram shop bot
This file contains all callback handlers for main menu sections
"""

from telebot import types
import sqlite3
from config import DB_NAME, ADMIN_ID
from helpers import send_random_animation, safe_edit_message


def register_menu_handlers(bot):
    """Register all menu callback handlers"""
    
    # ============================================================
    # TOOLS MENU - Complete toolkit with all required tools
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "tools_menu")
    def tools_menu_handler(call):
        """
        Main Tools menu with:
        - Hitter
        - CC Checker
        - Scraper
        - CC Generator
        - CC Cleaner
        - Proxy Checker
        - Fake Address Generator
        - Website SS
        - SMS Bomber
        """
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("🎯 Hitter", callback_data="hitter_menu"),
            types.InlineKeyboardButton("💳 CC Checker", callback_data="cc_checker_main_menu")
        )
        
        markup.add(
            types.InlineKeyboardButton("🔍 Scraper", callback_data="user_scraper_menu"),
            types.InlineKeyboardButton("🎲 CC Generator", callback_data="tool_cc_gen")
        )
        
        markup.add(
            types.InlineKeyboardButton("🧹 CC Cleaner", callback_data="tool_cc_cleaner"),
            types.InlineKeyboardButton("🌐 Proxy Checker", callback_data="tool_proxy_checker")
        )
        
        markup.add(
            types.InlineKeyboardButton("🏠 Fake Address", callback_data="tool_fake_address"),
            types.InlineKeyboardButton("📸 Website SS", callback_data="tool_screenshot")
        )
        
        markup.add(
            types.InlineKeyboardButton("📱 SMS Bomber", callback_data="sms_bomber_menu")
        )
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        
        text = (
            "🛠️ <b>Tools Menu</b>\n\n"
            "Select a tool from the options below:\n\n"
            "🎯 <b>Hitter</b> - Test cards on live sites\n"
            "💳 <b>CC Checker</b> - Validate card status\n"
            "🔍 <b>Scraper</b> - Extract data from sites\n"
            "🎲 <b>CC Generator</b> - Generate valid CC numbers\n"
            "🧹 <b>CC Cleaner</b> - Format and clean card lists\n"
            "🌐 <b>Proxy Checker</b> - Test proxy availability\n"
            "🏠 <b>Fake Address</b> - Generate realistic addresses\n"
            "📸 <b>Website SS</b> - Capture website screenshots\n"
            "📱 <b>SMS Bomber</b> - SMS flooding tool"
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode="HTML")

    # ============================================================
    # HACKS MENU - RAT, Panel, BGMI Attack
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "hacks_menu")
    def hacks_menu_handler(call):
        """
        Hacks menu with:
        - RAT (Remote Access Trojan)
        - Panel
        - BGMI Attack
        """
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("🐀 RAT", callback_data="rat_menu"),
            types.InlineKeyboardButton("📊 Panel", callback_data="panel_menu")
        )
        
        markup.add(
            types.InlineKeyboardButton("🎮 BGMI Attack", callback_data="bgmi_attack_menu")
        )
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        
        text = (
            "🔥 <b>Hacks Menu</b>\n\n"
            "Advanced hacking tools and utilities:\n\n"
            "🐀 <b>RAT</b> - Remote Access Tool\n"
            "📊 <b>Panel</b> - Control panel access\n"
            "🎮 <b>BGMI Attack</b> - Game server stress testing\n\n"
            "⚠️ <i>Use responsibly and legally</i>"
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode="HTML")

    # ============================================================
    # SETTINGS MENU - Personal settings and account management
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "settings_menu")
    def settings_menu_handler(call):
        """
        Settings menu with:
        - My Profile
        - My Orders
        - My Claims
        - Enter Key Code
        - Support
        """
        user_id = call.from_user.id
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("👤 My Profile", callback_data="personal_area"),
            types.InlineKeyboardButton("📦 My Orders", callback_data="my_orders")
        )
        
        markup.add(
            types.InlineKeyboardButton("🎁 My Claims", callback_data="my_temp_claims"),
            types.InlineKeyboardButton("🔑 Enter Key Code", callback_data="enter_key_code")
        )
        
        markup.add(
            types.InlineKeyboardButton("💬 Support", callback_data="support")
        )
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        
        text = (
            "⚙️ <b>Settings</b>\n\n"
            "Manage your account and settings:\n\n"
            "👤 <b>My Profile</b> - View and edit your profile\n"
            "📦 <b>My Orders</b> - Check your purchase history\n"
            "🎁 <b>My Claims</b> - View your claimed items\n"
            "🔑 <b>Enter Key Code</b> - Redeem access keys\n"
            "💬 <b>Support</b> - Contact support team"
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode="HTML")

    # ============================================================
    # CC GENERATOR MENU
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "cc_generator_menu")
    def cc_generator_menu_handler(call):
        """CC Generator tool interface"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        markup.add(
            types.InlineKeyboardButton("🎲 Generate Random CC", callback_data="gen_random_cc"),
            types.InlineKeyboardButton("🔢 Generate from BIN", callback_data="gen_from_bin")
        )
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Tools", callback_data="tools_menu"))
        
        text = (
            "🎲 <b>CC Generator</b>\n\n"
            "Generate valid credit card numbers for testing:\n\n"
            "• Random generation with Luhn algorithm\n"
            "• Generate from specific BIN\n"
            "• Includes CVV and expiry date\n\n"
            "⚠️ <i>For testing purposes only</i>"
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode="HTML")

    # ============================================================
    # CC CLEANER MENU
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "cc_cleaner_menu")
    def cc_cleaner_menu_handler(call):
        """CC Cleaner tool interface"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        markup.add(
            types.InlineKeyboardButton("📝 Send CC List", callback_data="cc_cleaner_send")
        )
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Tools", callback_data="tools_menu"))
        
        text = (
            "🧹 <b>CC Cleaner</b>\n\n"
            "Clean and format your credit card lists:\n\n"
            "• Remove duplicates\n"
            "• Fix formatting\n"
            "• Validate card numbers\n"
            "• Export clean list\n\n"
            "📤 Send your CC list to clean it"
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode="HTML")

    # ============================================================
    # PROXY CHECKER MENU
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "proxy_checker_menu")
    def proxy_checker_menu_handler(call):
        """Proxy Checker tool interface"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        markup.add(
            types.InlineKeyboardButton("✅ Check My Proxies", callback_data="check_my_proxies"),
            types.InlineKeyboardButton("📤 Upload Proxy List", callback_data="upload_proxy_list")
        )
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Tools", callback_data="tools_menu"))
        
        text = (
            "🌐 <b>Proxy Checker</b>\n\n"
            "Test proxy availability and speed:\n\n"
            "• Check proxy status\n"
            "• Measure response time\n"
            "• Filter working proxies\n"
            "• Support multiple formats\n\n"
            "Format: <code>host:port:user:pass</code>"
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode="HTML")

    # ============================================================
    # WEBSITE SCREENSHOT MENU
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "website_ss_menu")
    def website_ss_menu_handler(call):
        """Website Screenshot tool interface"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        markup.add(
            types.InlineKeyboardButton("📸 Take Screenshot", callback_data="website_ss_take")
        )
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Tools", callback_data="tools_menu"))
        
        text = (
            "📸 <b>Website Screenshot</b>\n\n"
            "Capture screenshots of any website:\n\n"
            "• Full page screenshot\n"
            "• Multiple resolutions\n"
            "• Fast processing\n\n"
            "Send website URL to capture"
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode="HTML")

    # ============================================================
    # PANEL MENU
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "panel_menu")
    def panel_menu_handler(call):
        """Panel access interface"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        markup.add(
            types.InlineKeyboardButton("🔐 Request Access", callback_data="panel_request"),
            types.InlineKeyboardButton("📊 View Panels", callback_data="panel_view")
        )
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Hacks", callback_data="hacks_menu"))
        
        text = (
            "📊 <b>Panel Access</b>\n\n"
            "Manage control panel access:\n\n"
            "• Admin panels\n"
            "• cPanel access\n"
            "• Database panels\n\n"
            "⚠️ <i>Authorized use only</i>"
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode="HTML")

    # ============================================================
    # SMS BOMBER MENU
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "sms_bomber_menu")
    def sms_bomber_menu_handler(call):
        """SMS Bomber tool interface"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        markup.add(
            types.InlineKeyboardButton("📱 Start SMS Bomber", callback_data="sms_bomber_start")
        )
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Tools", callback_data="tools_menu"))
        
        text = (
            "📱 <b>SMS Bomber</b>\n\n"
            "SMS flooding tool:\n\n"
            "• Send multiple SMS\n"
            "• Configurable count\n"
            "• Multi-API support\n\n"
            "⚠️ <i>Use responsibly - for testing only</i>\n\n"
            "Send phone number to start:\n"
            "Format: <code>+1234567890</code>"
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode="HTML")

    # ============================================================
    # MAIN MENU CALLBACK
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "main_menu")
    def main_menu_callback(call):
        """Return to main menu"""
        from helpers import send_main_menu
        menu_text = (
            "╔═══════════════════════╗\n"
            " ║  💎 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗦𝗛𝗢𝗣  ║\n"
            "╚═══════════════════════╝\n\n"
            "✨ <i>All-in-one • Fast • Secure</i>\n\n"
            "🛍️ <b>CC</b> • 💎 <b>BINs</b> • 📦 <b>Methods</b>\n"
            "⚡ <b>Instant delivery</b> • 🎯 <b>Smart search</b>\n\n"
            "👇 <b>Select a category below</b>"
        )
        send_main_menu(bot, call.message.chat.id, menu_text, call.message.message_id)

    print("✅ Menu handlers registered successfully")


def register_simple_menu_placeholders(bot):
    """Register placeholder handlers for menus that don't have full implementation yet"""
    
    @bot.callback_query_handler(func=lambda call: call.data == "enter_key_code")
    def enter_key_code_handler(call):
        """Enter key code placeholder"""
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Settings", callback_data="settings_menu"))
        
        text = (
            "🔑 <b>Enter Key Code</b>\n\n"
            "Send your access key code to redeem.\n\n"
            "Keys can provide:\n"
            "• Premium access\n"
            "• Credit bonuses\n"
            "• Special features\n\n"
            "Type your key code:"
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data == "rat_menu")
    def rat_menu_handler(call):
        """RAT (Remote Access Tool) menu"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        markup.add(
            types.InlineKeyboardButton("📥 Download RAT", callback_data="rat_download"),
            types.InlineKeyboardButton("📖 RAT Tutorial", callback_data="rat_tutorial")
        )
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Hacks", callback_data="hacks_menu"))
        
        text = (
            "🐀 <b>RAT - Remote Access Tool</b>\n\n"
            "Remote administration and monitoring:\n\n"
            "• Remote desktop access\n"
            "• File management\n"
            "• Screen capture\n"
            "• Keylogger\n"
            "• Camera/Mic access\n\n"
            "⚠️ <i>For authorized testing only!\i>\n"
            "📚 Educational purposes"
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data == "panel_request")
    def panel_request_handler(call):
        """Panel access request"""
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="panel_menu"))
        
        text = (
            "🔐 <b>Request Panel Access</b>\n\n"
            "To request access, provide:\n"
            "• Target panel URL\n"
            "• Purpose\n"
            "• Authorization proof\n\n"
            "Contact admin for access."
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data == "panel_view")
    def panel_view_handler(call):
        """View available panels"""
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="panel_menu"))
        
        text = (
            "📊 <b>Available Panels</b>\n\n"
            "No panels available at the moment.\n\n"
            "Check back later or contact admin."
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data == "rat_download")
    def rat_download_handler(call):
        """RAT download"""
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="rat_menu"))
        
        text = (
            "📥 <b>Download RAT</b>\n\n"
            "Contact admin to get access to RAT tools.\n\n"
            "Requirements:\n"
            "• Verified account\n"
            "• Premium access\n"
            "• Authorization approval"
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data == "rat_tutorial")
    def rat_tutorial_handler(call):
        """RAT tutorial"""
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="rat_menu"))
        
        text = (
            "📖 <b>RAT Tutorial</b>\n\n"
            "<b>Step 1:</b> Download RAT builder\n"
            "<b>Step 2:</b> Configure settings\n"
            "<b>Step 3:</b> Build payload\n"
            "<b>Step 4:</b> Deploy and connect\n\n"
            "⚠️ Legal disclaimer:\n"
            "Only use on systems you own or have permission to test."
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data == "sms_bomber_start")
    def sms_bomber_start_handler(call):
        """SMS Bomber start"""
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="sms_bomber_menu"))
        
        text = (
            "📱 <b>SMS Bomber</b>\n\n"
            "Send the target phone number:\n\n"
            "Format: <code>+1234567890</code>\n\n"
            "⚠️ Use for testing only!"
        )
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode="HTML")

    print("✅ Placeholder menu handlers registered")
