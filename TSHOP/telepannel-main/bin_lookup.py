# BIN Lookup Module
# Features: Lookup BIN information from APIs

import logging
import aiohttp
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

class BINLookup:
    def __init__(self):
        self.api_url = "https://lookup.binlist.net/{}"
    
    async def lookup_bin(self, bin_number):
        """Lookup BIN information from API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.api_url.format(bin_number),
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'success': True,
                            'scheme': data.get('scheme', 'UNKNOWN').upper(),
                            'type': data.get('type', 'UNKNOWN').upper(),
                            'brand': data.get('brand', 'UNKNOWN').upper(),
                            'bank': data.get('bank', {}).get('name', 'UNKNOWN'),
                            'country': data.get('country', {}).get('name', 'UNKNOWN'),
                            'country_code': data.get('country', {}).get('alpha2', 'XX'),
                            'prepaid': data.get('prepaid', False),
                        }
                    else:
                        return {'success': False, 'error': 'BIN not found'}
        except Exception as e:
            logger.error(f"BIN lookup error: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_country_flag(self, country_code):
        """Convert country code to flag emoji"""
        if len(country_code) != 2:
            return "🏳️"
        
        # Convert to regional indicator symbols
        code_points = [ord(char) + 127397 for char in country_code.upper()]
        return ''.join(chr(cp) for cp in code_points)

async def cmd_bin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """BIN lookup command"""
    user = update.effective_user
    msg = update.message
    
    if not msg.text or len(msg.text.split()) < 2:
        await msg.reply_text(
            "🔍 <b>BIN Lookup</b>\n\n"
            "Usage: /bin <bin_number>\n\n"
            "Examples:\n"
            "• /bin 451629\n"
            "• /bin 453201\n"
            "• /bin 556677\n\n"
            "Provides card information from BIN",
            parse_mode='HTML'
        )
        return
    
    bin_number = msg.text.split()[1].strip()
    
    # Validate BIN
    if not bin_number.isdigit():
        await msg.reply_text("❌ BIN must contain only digits")
        return
    
    if len(bin_number) < 6 or len(bin_number) > 8:
        await msg.reply_text("❌ BIN should be 6-8 digits")
        return
    
    status_msg = await msg.reply_text("⏳ Looking up BIN...")
    
    lookup = BINLookup()
    result = await lookup.lookup_bin(bin_number)
    
    if not result.get('success'):
        await status_msg.edit_text(
            f"❌ <b>Lookup Failed</b>\n\n"
            f"BIN: <code>{bin_number}</code>\n"
            f"Error: {result.get('error', 'Unknown error')}",
            parse_mode='HTML'
        )
        return
    
    # Format response
    flag = lookup.get_country_flag(result['country_code'])
    
    response = f"🔍 <b>BIN Information</b>\n\n"
    response += f"BIN: <code>{bin_number}</code>\n"
    response += f"━━━━━━━━━━━━━━━━\n\n"
    response += f"🏦 Bank: <b>{result['bank']}</b>\n"
    response += f"💳 Brand: <b>{result['brand']}</b>\n"
    response += f"📇 Scheme: <b>{result['scheme']}</b>\n"
    response += f"📊 Type: <b>{result['type']}</b>\n"
    response += f"{flag} Country: <b>{result['country']}</b>\n"
    response += f"🔖 Prepaid: <b>{'Yes' if result.get('prepaid') else 'No'}</b>\n\n"
    response += f"⏰ {datetime.now().strftime('%H:%M:%S')}"
    
    await status_msg.edit_text(response, parse_mode='HTML')

def register_bin_lookup_handlers(application):
    """Register BIN lookup command handlers"""
    from telegram.ext import CommandHandler
    
    application.add_handler(CommandHandler("bin", cmd_bin))
    
    logger.info("✅ BIN Lookup handlers registered")
