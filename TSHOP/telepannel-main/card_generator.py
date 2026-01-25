# Card Generator Module
# Features: Generate credit cards from BIN patterns

import random
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

class CardGenerator:
    def __init__(self):
        pass
    
    def luhn_checksum(self, card_number):
        """Calculate Luhn checksum"""
        def digits_of(n):
            return [int(d) for d in str(n)]
        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d*2))
        return checksum % 10
    
    def is_luhn_valid(self, card_number):
        """Check if card number is Luhn valid"""
        return self.luhn_checksum(card_number) == 0
    
    def calculate_luhn(self, partial):
        """Calculate Luhn check digit for partial card number"""
        check_digit = self.luhn_checksum(int(partial) * 10)
        return (10 - check_digit) % 10
    
    def generate_card(self, bin_pattern, mm='xx', yy='xx', cvv='xxx'):
        """Generate a single card from pattern"""
        # Replace x's with random digits
        card_num = ''
        for char in bin_pattern:
            if char.lower() == 'x':
                card_num += str(random.randint(0, 9))
            else:
                card_num += char
        
        # If 15 digits, calculate last Luhn digit
        if len(card_num) == 15:
            check_digit = self.calculate_luhn(card_num)
            card_num += str(check_digit)
        
        # Generate month
        if mm == 'xx':
            month = str(random.randint(1, 12)).zfill(2)
        else:
            month = mm
        
        # Generate year
        if yy == 'xx':
            year = str(random.randint(25, 30))
        else:
            year = yy
        
        # Generate CVV
        if cvv == 'xxx':
            cvv_code = str(random.randint(100, 999))
        else:
            cvv_code = ''
            for char in cvv:
                if char.lower() == 'x':
                    cvv_code += str(random.randint(0, 9))
                else:
                    cvv_code += char
        
        return f"{card_num}|{month}|{year}|{cvv_code}"
    
    def generate_multiple(self, bin_pattern, mm, yy, cvv, count):
        """Generate multiple cards"""
        cards = []
        for _ in range(count):
            card = self.generate_card(bin_pattern, mm, yy, cvv)
            cards.append(card)
        return cards

async def cmd_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate credit cards from BIN pattern"""
    user = update.effective_user
    msg = update.message
    
    if not msg.text or len(msg.text.split()) < 2:
        await msg.reply_text(
            "🎲 <b>Card Generator</b>\n\n"
            "Usage: /gen <bin_pattern>|<mm>|<yy>|<cvv> [count]\n\n"
            "Examples:\n"
            "• /gen 451629xxxxxx|xx|xx|xxx 10\n"
            "• /gen 5xxxxxxxxxxxxx|12|25|xxx\n"
            "• /gen 4532015112xxxx|xx|xx|206 50\n\n"
            "Use 'x' for random digits\n"
            "Default count: 10 (max: 100)",
            parse_mode='HTML'
        )
        return
    
    generator = CardGenerator()
    
    parts = msg.text.split()
    try:
        # Parse format: bin|mm|yy|cvv
        card_parts = parts[1].split('|')
        if len(card_parts) != 4:
            await msg.reply_text("❌ Invalid format. Use: <bin>|<mm>|<yy>|<cvv>")
            return
        
        bin_pattern, mm, yy, cvv = card_parts
        
        # Get count
        count = 10
        if len(parts) > 2:
            try:
                count = int(parts[2])
                if count < 1:
                    count = 1
                elif count > 100:
                    count = 100
            except ValueError:
                count = 10
        
        # Validate BIN pattern
        if len(bin_pattern) < 6:
            await msg.reply_text("❌ BIN must be at least 6 digits")
            return
        
        status_msg = await msg.reply_text(f"⏳ Generating {count} cards...")
        
        # Generate cards
        cards = generator.generate_multiple(bin_pattern, mm, yy, cvv, count)
        
        # Format response
        response = f"✅ <b>Generated {len(cards)} Cards</b>\n\n"
        response += f"BIN: <code>{bin_pattern[:6]}</code>\n"
        response += f"Pattern: <code>{bin_pattern}</code>\n\n"
        response += "<b>Cards:</b>\n"
        response += "<code>" + "\n".join(cards[:20]) + "</code>"
        
        if len(cards) > 20:
            response += f"\n\n<i>...and {len(cards) - 20} more cards</i>"
        
        await status_msg.edit_text(response, parse_mode='HTML')
        
        # Send as file if more than 20
        if len(cards) > 20:
            from io import BytesIO
            file_content = "\n".join(cards)
            file_obj = BytesIO(file_content.encode('utf-8'))
            file_obj.name = f"cards_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            await msg.reply_document(
                document=file_obj,
                caption=f"📄 All {len(cards)} generated cards",
                filename=file_obj.name
            )
        
    except Exception as e:
        logger.error(f"Card generation error: {e}")
        await msg.reply_text(f"❌ Generation failed: {str(e)}")

def register_card_generator_handlers(application):
    """Register card generator command handlers"""
    from telegram.ext import CommandHandler
    
    application.add_handler(CommandHandler("gen", cmd_gen))
    
    logger.info("✅ Card Generator handlers registered")
