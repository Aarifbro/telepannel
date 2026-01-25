"""
Bulk Upload Handler for Admin Panel
Allows admins to upload multiple products at once by pasting lists
"""

from telebot import types
import re
import json

def parse_cc_line(line):
    """
    Parse a single CC line in various formats:
    - CC|MM|YY|CVV
    - CC MM YY CVV
    - CC|MM|YYYY|CVV
    - CC:MM:YY:CVV
    - CC/MM/YY/CVV
    Returns dict with cc, mm, yy, cvv or None if invalid
    """
    line = line.strip()
    if not line:
        return None
    
    # Try different separators
    separators = ['|', ' ', ':', '/', ',']
    for sep in separators:
        if sep in line:
            parts = [p.strip() for p in line.split(sep) if p.strip()]
            if len(parts) >= 4:
                cc, mm, yy, cvv = parts[0], parts[1], parts[2], parts[3]
                
                # Validate CC (13-19 digits)
                if not cc.isdigit() or len(cc) < 13 or len(cc) > 19:
                    continue
                
                # Validate MM (01-12)
                if not mm.isdigit() or len(mm) != 2 or int(mm) < 1 or int(mm) > 12:
                    continue
                
                # Validate YY (convert YYYY to YY if needed)
                if yy.isdigit():
                    if len(yy) == 4:
                        yy = yy[2:]  # Convert 2025 to 25
                    if len(yy) != 2:
                        continue
                else:
                    continue
                
                # Validate CVV (3-4 digits)
                if not cvv.isdigit() or len(cvv) < 3 or len(cvv) > 4:
                    continue
                
                return {
                    'cc': cc,
                    'mm': mm,
                    'yy': yy,
                    'cvv': cvv,
                    'bin': cc[:6]
                }
    
    return None


def get_bin_info(bin_number):
    """Get BIN information from a BIN number"""
    import requests
    
    try:
        # Try binlist.net API first
        response = requests.get(f"https://lookup.binlist.net/{bin_number[:6]}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            
            brand = data.get("scheme", "VISA").upper()
            card_type = data.get("type", "CREDIT").upper()
            level = data.get("brand", "CLASSIC").upper()
            bank = data.get("bank", {}).get("name", "Unknown Bank")
            country_info = data.get("country", {})
            country = country_info.get("name", "United States")
            country_code = country_info.get("alpha2", "US")
            
            # Get country flag emoji
            flag = ""
            if country_code:
                flag = "".join(chr(127397 + ord(c)) for c in country_code.upper())
            
            return {
                "brand": brand,
                "card_type": card_type,
                "level": level,
                "bank": bank,
                "country": country,
                "country_flag": flag,
                "country_code": country_code
            }
    except Exception as e:
        print(f"BIN lookup failed: {e}")
    
    # Fallback
    return {
        "brand": "VISA",
        "card_type": "CREDIT",
        "level": "CLASSIC",
        "bank": "Unknown Bank",
        "country": "United States",
        "country_flag": "🇺🇸",
        "country_code": "US"
    }


def register_bulk_upload_handlers(bot, user_states, get_products_from_cache, save_products_to_file_and_reload):
    """Register bulk upload handlers for admin panel"""
    
    from config import ADMIN_ID, DB_NAME
    import sqlite3
    
    # Add bulk upload button to admin products menu
    @bot.callback_query_handler(func=lambda call: call.data == "bulk_upload_cc")
    def bulk_upload_cc_prompt(call):
        """Show bulk upload instructions"""
        user_id = call.from_user.id
        
        # Check if user is authorized (owner or admin)
        if user_id != ADMIN_ID:
            is_admin = False
            try:
                with sqlite3.connect(DB_NAME) as conn:
                    c = conn.cursor()
                    c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
                    is_admin = c.fetchone() is not None
            except:
                pass
            
            if not is_admin:
                bot.answer_callback_query(call.id, "❌ Not authorized", show_alert=True)
                return
        
        user_states[user_id] = "awaiting_bulk_cc_upload"
        
        text = (
            "📦 <b>Bulk CC Upload</b>\n\n"
            "Paste your CC list below. Supported formats:\n\n"
            "✅ <code>CC|MM|YY|CVV</code>\n"
            "✅ <code>CC MM YY CVV</code>\n"
            "✅ <code>CC:MM:YY:CVV</code>\n"
            "✅ <code>CC/MM/YY/CVV</code>\n"
            "✅ <code>CC,MM,YY,CVV</code>\n\n"
            "📝 <b>Example:</b>\n"
            "<code>4532015112830366|12|25|123\n"
            "5425233430109903|01|26|456\n"
            "4916338506082832|11|27|789</code>\n\n"
            "⚡ <b>Features:</b>\n"
            "• Auto BIN lookup for each card\n"
            "• Country flag, brand, bank info\n"
            "• Duplicate detection\n"
            "• Bulk pricing (set once for all)\n\n"
            "📤 <b>Send your CC list now:</b>\n"
            "<i>(One CC per line, any format)</i>"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="admin_cat_menu_custom_ccs"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode="HTML")
    
    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "awaiting_bulk_cc_upload")
    def process_bulk_cc_upload(message):
        """Process bulk CC upload"""
        user_id = message.from_user.id
        
        # Send processing message
        processing_msg = bot.send_message(
            message.chat.id,
            "⏳ <b>Processing your CC list...</b>\n\n"
            "Please wait while we parse and validate the cards.",
            parse_mode="HTML"
        )
        
        lines = message.text.strip().split('\n')
        parsed_cards = []
        failed_lines = []
        
        # Parse each line
        for line_num, line in enumerate(lines, 1):
            parsed = parse_cc_line(line)
            if parsed:
                parsed_cards.append(parsed)
            else:
                if line.strip():  # Only count non-empty lines as failed
                    failed_lines.append((line_num, line[:50]))  # First 50 chars
        
        if not parsed_cards:
            bot.edit_message_text(
                "❌ <b>No valid cards found!</b>\n\n"
                f"Failed to parse {len(failed_lines)} lines.\n\n"
                "Please check the format and try again.",
                processing_msg.chat.id,
                processing_msg.message_id,
                parse_mode="HTML"
            )
            del user_states[user_id]
            return
        
        # Store parsed cards temporarily and ask for price
        user_states[user_id] = f"bulk_cc_set_price::{json.dumps(parsed_cards)}"
        
        status_text = (
            f"✅ <b>Parsed {len(parsed_cards)} cards successfully!</b>\n\n"
        )
        
        if failed_lines:
            status_text += f"⚠️ <b>Failed:</b> {len(failed_lines)} lines\n\n"
        
        status_text += (
            f"💳 <b>Sample cards:</b>\n"
        )
        
        for i, card in enumerate(parsed_cards[:3], 1):
            status_text += f"{i}. <code>{card['cc'][:4]}****{card['cc'][-4:]}</code> {card['mm']}/{card['yy']} BIN:{card['bin']}\n"
        
        if len(parsed_cards) > 3:
            status_text += f"... and {len(parsed_cards) - 3} more\n"
        
        status_text += (
            "\n💲 <b>Now send the price per card (USD):</b>\n"
            "<i>Example: 5 or 12.50</i>"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="admin_cat_menu_custom_ccs"))
        
        bot.edit_message_text(status_text, processing_msg.chat.id, processing_msg.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id, '').startswith("bulk_cc_set_price::"))
    def bulk_cc_set_price(message):
        """Set price for bulk uploaded CCs"""
        user_id = message.from_user.id
        
        try:
            price = float(message.text.strip())
            if price <= 0:
                raise ValueError
        except ValueError:
            bot.reply_to(message, "❌ Invalid price. Please send a positive number (e.g., 5 or 12.50)")
            return
        
        # Get stored cards
        state_parts = user_states[user_id].split("::", 1)
        parsed_cards = json.loads(state_parts[1])
        
        # Processing message
        processing_msg = bot.send_message(
            message.chat.id,
            "⏳ <b>Adding cards to database...</b>\n\n"
            f"💰 Price per card: ${price}\n"
            f"📦 Total cards: {len(parsed_cards)}\n\n"
            "Please wait...",
            parse_mode="HTML"
        )
        
        # Load existing products
        products_data = get_products_from_cache()
        custom_ccs = products_data.get("custom_ccs", [])
        
        # Get next ID
        next_id = (max([item.get('id', 0) for item in custom_ccs]) + 1) if custom_ccs else 1
        
        # Add each card with BIN lookup
        added_count = 0
        skipped_count = 0
        
        for card in parsed_cards:
            # Check for duplicates (same CC number)
            if any(item.get('cc') == card['cc'] for item in custom_ccs):
                skipped_count += 1
                continue
            
            # Get BIN info
            bin_info = get_bin_info(card['bin'])
            
            # Create product entry
            new_item = {
                "id": next_id,
                "name": f"{bin_info['country_flag']} {bin_info['brand']} {card['bin']}",
                "price": price,
                "cc": card['cc'],
                "mm": card['mm'],
                "yy": card['yy'],
                "cvv": card['cvv'],
                "bin": card['bin'],
                "country": bin_info['country'],
                "country_flag": bin_info['country_flag'],
                "country_code": bin_info['country_code'],
                "card_type": bin_info['card_type'],
                "brand": bin_info['brand'],
                "level": bin_info['level'],
                "bank": bin_info['bank'],
                "description": f"{bin_info['brand']} {bin_info['card_type']} - {bin_info['bank']} - {bin_info['country']}"
            }
            
            custom_ccs.append(new_item)
            next_id += 1
            added_count += 1
        
        # Save to database
        products_data["custom_ccs"] = custom_ccs
        save_products_to_file_and_reload(products_data)
        
        # Clear state
        del user_states[user_id]
        
        # Success message
        result_text = (
            "✅ <b>Bulk Upload Complete!</b>\n\n"
            f"📦 <b>Added:</b> {added_count} cards\n"
            f"💰 <b>Price:</b> ${price} per card\n"
        )
        
        if skipped_count > 0:
            result_text += f"⚠️ <b>Skipped:</b> {skipped_count} duplicates\n"
        
        result_text += (
            f"\n💵 <b>Total Value:</b> ${added_count * price}\n\n"
            "✨ Cards are now available in the CC Shop!"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("➕ Upload More", callback_data="bulk_upload_cc"),
            types.InlineKeyboardButton("📋 View CCs", callback_data="admin_cat_menu_custom_ccs")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Back to Admin", callback_data="owner_panel"))
        
        bot.edit_message_text(result_text, processing_msg.chat.id, processing_msg.message_id,
                            reply_markup=markup, parse_mode="HTML")
    
    print("✅ Bulk upload handlers registered")
