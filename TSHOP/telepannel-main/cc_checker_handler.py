# CC Checker Handler for Main Bot
# Integrates cc_checker.py gateway functionality with telebot

from telebot import types
import logging
import asyncio
import aiohttp
import time
from datetime import datetime

logger = logging.getLogger(__name__)

# === GATEWAY API CONFIG (from cc_checker.py) ===
GATEWAY_BASE_URL = "https://payment-gateway-api.onrender.com"

# Stripe APIs
STRIPE_AUTH_API = f"{GATEWAY_BASE_URL}/api/stripe/auth"
STRIPE_CHARGE_1_API = f"{GATEWAY_BASE_URL}/api/stripe/charge/1"
STRIPE_CHARGE_3_API = f"{GATEWAY_BASE_URL}/api/stripe/charge/3"

# Shopify APIs
SHOPIFY_CHARGE_098_API = f"{GATEWAY_BASE_URL}/api/shopify/charge/0.98"
SHOPIFY_CHARGE_1_API = f"{GATEWAY_BASE_URL}/api/shopify/charge/1"
SHOPIFY_CHARGE_10_API = f"{GATEWAY_BASE_URL}/api/shopify/charge/10"

# Other Gateways
PAYPAL_CHARGE_1_API = f"{GATEWAY_BASE_URL}/api/paypal/charge/1"
PAYPAL_CHARGE_9_API = f"{GATEWAY_BASE_URL}/api/paypal/charge/9"
AUTHNET_API = f"{GATEWAY_BASE_URL}/api/authnet/charge/1"
ADYEN_API = f"{GATEWAY_BASE_URL}/api/adyen/charge/1"
RAZORPAY_API = f"{GATEWAY_BASE_URL}/api/razorpay/charge/1"
OCEAN_API = f"{GATEWAY_BASE_URL}/api/ocean/charge/4"

# API Key
GATEWAY_API_KEY = "ccchkr_bot_2024_dec"

# Store user cooldowns
user_cooldowns = {}
COOLDOWN_SECONDS = 15

def register_cc_checker_handlers(bot, user_states):
    """Register CC Checker handlers for the main bot"""
    
    # ===== COMMAND HANDLERS FOR DIRECT CC CHECKING =====
    @bot.message_handler(commands=["auth"])
    def cmd_auth(message):
        """Quick auth check via command"""
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: <code>/auth CC|MM|YY|CVV</code>", parse_mode='HTML')
            return
        user_states[message.from_user.id] = "cc_stripe_auth"
        handle_cc_check(message, parts[1])
    
    @bot.message_handler(commands=["charge"])
    def cmd_charge(message):
        """Quick charge check via command"""
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: <code>/charge CC|MM|YY|CVV</code>", parse_mode='HTML')
            return
        user_states[message.from_user.id] = "cc_stripe_charge"
        handle_cc_check(message, parts[1])
    
    @bot.message_handler(commands=["shopify098"])
    def cmd_shopify098(message):
        """Shopify $0.98 check via command"""
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: <code>/shopify098 CC|MM|YY|CVV</code>", parse_mode='HTML')
            return
        user_states[message.from_user.id] = "cc_shopify_098"
        handle_cc_check(message, parts[1])
    
    @bot.message_handler(commands=["shopify1"])
    def cmd_shopify1(message):
        """Shopify $1 check via command"""
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: <code>/shopify1 CC|MM|YY|CVV</code>", parse_mode='HTML')
            return
        user_states[message.from_user.id] = "cc_shopify_1"
        handle_cc_check(message, parts[1])
    
    @bot.message_handler(commands=["paypal1"])
    def cmd_paypal1(message):
        """PayPal $1 check via command"""
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: <code>/paypal1 CC|MM|YY|CVV</code>", parse_mode='HTML')
            return
        user_states[message.from_user.id] = "cc_paypal_1"
        handle_cc_check(message, parts[1])
    
    @bot.message_handler(commands=["paypal9"])
    def cmd_paypal9(message):
        """PayPal $9 check via command"""
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: <code>/paypal9 CC|MM|YY|CVV</code>", parse_mode='HTML')
            return
        user_states[message.from_user.id] = "cc_paypal_9"
        handle_cc_check(message, parts[1])
    
    @bot.message_handler(commands=["authnet"])
    def cmd_authnet(message):
        """AuthNet check via command"""
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: <code>/authnet CC|MM|YY|CVV</code>", parse_mode='HTML')
            return
        user_states[message.from_user.id] = "cc_authnet"
        handle_cc_check(message, parts[1])
    
    @bot.message_handler(commands=["adyen"])
    def cmd_adyen(message):
        """Adyen check via command"""
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: <code>/adyen CC|MM|YY|CVV</code>", parse_mode='HTML')
            return
        user_states[message.from_user.id] = "cc_adyen"
        handle_cc_check(message, parts[1])
    
    @bot.message_handler(commands=["razorpay"])
    def cmd_razorpay(message):
        """Razorpay check via command"""
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: <code>/razorpay CC|MM|YY|CVV</code>", parse_mode='HTML')
            return
        user_states[message.from_user.id] = "cc_razorpay"
        handle_cc_check(message, parts[1])
    
    @bot.message_handler(commands=["ocean"])
    def cmd_ocean(message):
        """Ocean check via command"""
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: <code>/ocean CC|MM|YY|CVV</code>", parse_mode='HTML')
            return
        user_states[message.from_user.id] = "cc_ocean"
        handle_cc_check(message, parts[1])
    
    @bot.callback_query_handler(func=lambda call: call.data == "cc_checker_main_menu")
    def cc_checker_main_menu(call):
        """Show CC Checker main menu"""
        
        # Clear any stuck state when returning to main menu
        user_id = call.from_user.id
        if user_id in user_states:
            del user_states[user_id]
            print(f"🔄 Cleared CC checker state for user {user_id}")
            
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        markup.add(
            types.InlineKeyboardButton("📋 Stripe Auth", callback_data="cc_stripe_auth"),
            types.InlineKeyboardButton("💰 Stripe Charge", callback_data="cc_stripe_charge")
        )
        
        markup.add(
            types.InlineKeyboardButton("🛒 Shopify $0.98", callback_data="cc_shopify_098"),
            types.InlineKeyboardButton("🛍️ Shopify $1", callback_data="cc_shopify_1")
        )
        
        markup.add(
            types.InlineKeyboardButton("💳 PayPal $1", callback_data="cc_paypal_1"),
            types.InlineKeyboardButton("💵 PayPal $9", callback_data="cc_paypal_9")
        )
        
        markup.add(
            types.InlineKeyboardButton("🏦 AuthNet $1", callback_data="cc_authnet"),
            types.InlineKeyboardButton("💎 Adyen $1", callback_data="cc_adyen")
        )
        
        markup.add(
            types.InlineKeyboardButton("💰 Razorpay ₹1", callback_data="cc_razorpay"),
            types.InlineKeyboardButton("🌊 Ocean $4", callback_data="cc_ocean")
        )
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"))
        
        text = (
            "╔═══════════════════════╗\n"
            "  ║   💳 𝗖𝗖 𝗖𝗛𝗘𝗖𝗞𝗘𝗥   ║\n"
            "╚═══════════════════════╗\n\n"
            "🔐 <b>Premium Gateway Access</b>\n\n"
            "Select a gateway to check your cards:\n\n"
            "• <b>Stripe Auth</b> - No charge validation\n"
            "• <b>Stripe Charge</b> - $1-$3 charge test\n"
            "• <b>Shopify</b> - Multiple amount options\n"
            "• <b>PayPal</b> - $1 or $9 charge\n"
            "• <b>Other Gateways</b> - AuthNet, Adyen, etc.\n\n"
            "⚠️ <b>Note:</b> 15-second cooldown between checks\n"
            "💡 <b>Format:</b> CardNumber|Month|Year|CVV"
        )
        
        msg = bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='HTML'
        )
    
    # Gateway selection handlers
    @bot.callback_query_handler(func=lambda call: call.data == "cc_stripe_auth")
    def cc_stripe_auth_start(call):
        user_id = call.from_user.id
        user_states[user_id] = "cc_stripe_auth"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cc_checker_main_menu"))
        
        bot.edit_message_text(
            "📋 <b>Stripe Auth Check</b>\n\n"
            "Send your card details:\n"
            "<code>CardNumber|Month|Year|CVV</code>\n\n"
            "📌 <b>Example:</b>\n"
            "<code>4532015112830366|12|2025|123</code>\n\n"
            "✅ <b>Gateway:</b> Stripe Auth (No Charge)\n"
            "⏳ <b>Cooldown:</b> 15 seconds",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='HTML'
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "cc_stripe_charge")
    def cc_stripe_charge_start(call):
        user_id = call.from_user.id
        user_states[user_id] = "cc_stripe_charge"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cc_checker_main_menu"))
        
        bot.edit_message_text(
            "💰 <b>Stripe Charge Check</b>\n\n"
            "Send your card details with amount:\n"
            "<code>CardNumber|Month|Year|CVV [Amount]</code>\n\n"
            "📌 <b>Examples:</b>\n"
            "<code>4532015112830366|12|2025|123</code> ($1.00)\n"
            "<code>4532015112830366|12|2025|123 3</code> ($3.00)\n\n"
            "✅ <b>Gateway:</b> Stripe Charge\n"
            "⏳ <b>Cooldown:</b> 15 seconds",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='HTML'
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "cc_shopify_098")
    def cc_shopify_098_start(call):
        user_id = call.from_user.id
        user_states[user_id] = "cc_shopify_098"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cc_checker_main_menu"))
        
        bot.edit_message_text(
            "🛒 <b>Shopify $0.98 Check</b>\n\n"
            "Send your card details:\n"
            "<code>CardNumber|Month|Year|CVV</code>\n\n"
            "📌 <b>Example:</b>\n"
            "<code>4532015112830366|12|2025|123</code>\n\n"
            "✅ <b>Gateway:</b> Shopify\n"
            "💵 <b>Charge:</b> $0.98\n"
            "⏳ <b>Cooldown:</b> 15 seconds",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='HTML'
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "cc_shopify_1")
    def cc_shopify_1_start(call):
        user_id = call.from_user.id
        user_states[user_id] = "cc_shopify_1"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cc_checker_main_menu"))
        
        bot.edit_message_text(
            "🛍️ <b>Shopify $1 Check</b>\n\n"
            "Send your card details:\n"
            "<code>CardNumber|Month|Year|CVV</code>\n\n"
            "📌 <b>Example:</b>\n"
            "<code>4532015112830366|12|2025|123</code>\n\n"
            "✅ <b>Gateway:</b> Shopify\n"
            "💵 <b>Charge:</b> $1.00\n"
            "⏳ <b>Cooldown:</b> 15 seconds",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='HTML'
        )
    
    @bot.callback_query_handler(func=lambda call: call.data in ["cc_paypal_1", "cc_paypal_9", "cc_authnet", "cc_adyen", "cc_razorpay", "cc_ocean"])
    def cc_other_gateways_start(call):
        gateway_info = {
            "cc_paypal_1": ("💳 PayPal $1", "$1.00", "PayPal"),
            "cc_paypal_9": ("💵 PayPal $9", "$9.00", "PayPal"),
            "cc_authnet": ("🏦 AuthNet $1", "$1.00", "Authorize.Net"),
            "cc_adyen": ("💎 Adyen $1", "$1.00", "Adyen"),
            "cc_razorpay": ("💰 Razorpay ₹1", "₹1", "Razorpay"),
            "cc_ocean": ("🌊 Ocean $4", "$4.00", "Ocean Payments")
        }
        
        user_id = call.from_user.id
        user_states[user_id] = call.data
        
        title, charge, gateway = gateway_info[call.data]
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cc_checker_main_menu"))
        
        bot.edit_message_text(
            f"{title} <b>Check</b>\n\n"
            f"Send your card details:\n"
            f"<code>CardNumber|Month|Year|CVV</code>\n\n"
            f"📌 <b>Example:</b>\n"
            f"<code>4532015112830366|12|2025|123</code>\n\n"
            f"✅ <b>Gateway:</b> {gateway}\n"
            f"💵 <b>Charge:</b> {charge}\n"
            f"⏳ <b>Cooldown:</b> 15 seconds",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='HTML'
        )
    
    # Helper functions
    def parse_cc_format(cc_string):
        """Parse CC format: 1234567890123456|12|2025|123"""
        try:
            parts = cc_string.strip().split('|')
            if len(parts) != 4:
                return None
            
            return {
                'number': parts[0],
                'month': parts[1],
                'year': parts[2],
                'cvv': parts[3]
            }
        except Exception:
            return None
    
    def check_cooldown(user_id):
        """Check if user is on cooldown"""
        if user_id in user_cooldowns:
            elapsed = time.time() - user_cooldowns[user_id]
            if elapsed < COOLDOWN_SECONDS:
                remaining = int(COOLDOWN_SECONDS - elapsed)
                return False, remaining
        user_cooldowns[user_id] = time.time()
        return True, 0
    
    async def check_gateway_api(gateway_type, card, mm, yy, cvv, amount=1.0):
        """Universal gateway checker"""
        try:
            # Select API based on gateway type
            api_map = {
                "cc_stripe_auth": STRIPE_AUTH_API,
                "cc_stripe_charge": STRIPE_CHARGE_1_API if amount < 3 else STRIPE_CHARGE_3_API,
                "cc_shopify_098": SHOPIFY_CHARGE_098_API,
                "cc_shopify_1": SHOPIFY_CHARGE_1_API,
                "cc_paypal_1": PAYPAL_CHARGE_1_API,
                "cc_paypal_9": PAYPAL_CHARGE_9_API,
                "cc_authnet": AUTHNET_API,
                "cc_adyen": ADYEN_API,
                "cc_razorpay": RAZORPAY_API,
                "cc_ocean": OCEAN_API
            }
            
            api_url = api_map.get(gateway_type, STRIPE_AUTH_API)
            
            payload = {
                "card": card,
                "month": mm,
                "year": yy,
                "cvv": cvv
            }
            
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": GATEWAY_API_KEY
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    api_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        return {
                            'status': data.get('status', 'DECLINED'),
                            'message': data.get('message', ''),
                            'response': data.get('response', ''),
                            'bin_info': data.get('bin_info', {}),
                            'timestamp': datetime.now().isoformat()
                        }
                    else:
                        return {
                            'status': 'API_ERROR',
                            'message': f'Gateway returned status {response.status}',
                            'timestamp': datetime.now().isoformat()
                        }
                        
        except asyncio.TimeoutError:
            return {
                'status': 'TIMEOUT',
                'message': 'Request timed out',
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Gateway API error: {e}")
            return {
                'status': 'ERROR',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    # Message handler for card input
    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id, "").startswith("cc_"), content_types=['text'])
    def handle_cc_check(message, cc_string_override=None):
        """Handle card check for any gateway"""
        user_id = message.from_user.id
        gateway_type = user_states.get(user_id, "")
        
        if not gateway_type:
            return
        
        # Get CC string from override or message text
        if cc_string_override:
            cc_string = cc_string_override.strip()
        else:
            # Allow cancellation with /cancel or /start
            if message.text.strip().lower() in ['/cancel', '/start']:
                user_states.pop(user_id, None)
                bot.reply_to(message, "🔄 CC check cancelled. Use /start to begin again.")
                return
            
            # Parse input
            parts = message.text.strip().split()
            cc_string = parts[0]
        
        # Check cooldown
        can_proceed, remaining = check_cooldown(user_id)
        if not can_proceed:
            bot.reply_to(message, f"⏳ Please wait {remaining}s before next check. Use /cancel to exit.")
            return
        
        amount = 1.0  # Default amount
        if gateway_type == "cc_stripe_charge" and not cc_string_override:
            parts = message.text.strip().split()
            amount = float(parts[1]) if len(parts) > 1 else 1.0
        
        cc_data = parse_cc_format(cc_string)
        
        if not cc_data:
            bot.reply_to(message, "❌ Invalid format. Use: <code>1234567890123456|12|2025|123</code>\n\n💡 Or use /cancel to exit", parse_mode='HTML')
            return
        
        # Gateway name for display
        gateway_names = {
            "cc_stripe_auth": "Stripe Auth",
            "cc_stripe_charge": "Stripe Charge",
            "cc_shopify_098": "Shopify $0.98",
            "cc_shopify_1": "Shopify $1",
            "cc_paypal_1": "PayPal $1",
            "cc_paypal_9": "PayPal $9",
            "cc_authnet": "AuthNet",
            "cc_adyen": "Adyen",
            "cc_razorpay": "Razorpay",
            "cc_ocean": "Ocean Payments"
        }
        
        gateway_name = gateway_names.get(gateway_type, "Gateway")
        status_msg = bot.reply_to(message, f"⏳ Checking via {gateway_name}...")
        
        try:
            # Run async check
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(check_gateway_api(
                gateway_type,
                cc_data['number'],
                cc_data['month'],
                cc_data['year'],
                cc_data['cvv'],
                amount
            ))
            loop.close()
            
            # Determine status
            status = result.get('status', 'DECLINED')
            if status in ['APPROVED', 'CHARGED', 'CVV_MATCH', 'LIVE']:
                response = "✅ <b>APPROVED</b>\n\n"
                emoji = "✅"
            else:
                response = "❌ <b>DECLINED</b>\n\n"
                emoji = "❌"
            
            response += f"Card: <code>{cc_data['number'][:6]}••••{cc_data['number'][-4:]}</code>\n"
            response += f"Expiry: <code>{cc_data['month']}/{cc_data['year']}</code>\n"
            response += f"Gateway: <b>{gateway_name}</b>\n"
            response += f"Status: <b>{status}</b>\n"
            
            # Add bin info if available
            bin_info = result.get('bin_info', {})
            if bin_info:
                brand = bin_info.get('brand', 'N/A')
                bank = bin_info.get('bank', 'N/A')
                country = bin_info.get('country', 'N/A')
                response += f"\n🏦 Bank: <code>{bank}</code>\n"
                response += f"💳 Brand: <code>{brand}</code>\n"
                response += f"🌍 Country: <code>{country}</code>\n"
            
            # Add message if available
            msg = result.get('message', '')
            if msg:
                response += f"\n💬 Response: <i>{msg}</i>\n"
            
            response += f"\n⏰ Time: {datetime.now().strftime('%H:%M:%S')}\n"
            response += f"{emoji} Check completed"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("🔄 Check Another", callback_data=gateway_type),
                types.InlineKeyboardButton("⬅️ Menu", callback_data="cc_checker_main_menu")
            )
            
            bot.edit_message_text(response, message.chat.id, status_msg.message_id, reply_markup=markup, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"CC check error: {e}")
            bot.edit_message_text(f"❌ Check failed: {str(e)}", message.chat.id, status_msg.message_id)
        finally:
            user_states.pop(user_id, None)
