# Advanced Tools Handlers
# Integrates Card Generator, BIN Lookup, SMS Bomber

from telebot import types
import logging
import random
import asyncio
import aiohttp
import time
import json
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# Store user cooldowns and data
user_cooldowns = {}
COOLDOWN_SECONDS = 15

def register_advanced_tools_handlers(bot):
    """Register handlers for advanced tools menu"""
    
    @bot.callback_query_handler(func=lambda call: call.data == "advanced_tools_menu")
    def advanced_tools_menu(call):
        """Show advanced tools menu"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        # First row - Tools
        markup.add(
            types.InlineKeyboardButton("🎲 Card Generator", callback_data="card_generator_menu"),
            types.InlineKeyboardButton("🔍 BIN Lookup", callback_data="bin_lookup_menu")
        )
        
        # Second row - Bombers
        markup.add(
            types.InlineKeyboardButton("💣 SMS Bomber", callback_data="sms_bomber_menu"),
            types.InlineKeyboardButton("📞 Call Bomber", callback_data="call_bomber_menu")
        )
        
        # Product Manager (Admin only)
        from config import ADMIN_ID
        if call.from_user.id == ADMIN_ID:
            markup.add(types.InlineKeyboardButton("📦 Product Manager", callback_data="admin_products_menu"))
        
        # Back button
        markup.add(types.InlineKeyboardButton("⬅️ Main Menu", callback_data="main_menu"))
        
        text = (
            "╔═══════════════════════╗\n"
            " ║   🔧 𝗔𝗗𝗩𝗔𝗡𝗖𝗘𝗗 𝗧𝗢𝗢𝗟𝗦   ║\n"
            "╚═══════════════════════╝\n\n"
            "🛠️ <b>Professional Tools Suite</b>\n\n"
            "🎲 <b>Card Generator</b>\n"
            "   • ✅ Generate valid card numbers\n"
            "   • ✅ Luhn algorithm applied\n"
            "   • ✅ Custom BIN patterns\n\n"
            "🔍 <b>BIN Lookup</b>\n"
            "   • ✅ Real API integration\n"
            "   • ✅ Bank & country info\n"
            "   • ✅ Card brand details\n\n"
            "💣 <b>SMS Bomber</b>\n"
            "   • ⚠️ Demo mode only\n"
            "   • Requires SMS API setup\n\n"
            "📞 <b>Call Bomber</b>\n"
            "   • ✅ Real API integration\n"
            "   • ✅ Live status tracking\n"
            "   • ✅ Multiple iterations\n\n"
        )
        
        # Add Product Manager info for admins
        from config import ADMIN_ID
        if call.from_user.id == ADMIN_ID:
            text += (
                "📦 <b>Product Manager</b> (Admin)\n"
                "   • ✅ Manage all products\n"
                "   • ✅ Add/Edit/Delete items\n"
                "   • ✅ Category management\n\n"
            )
        
        text += "👇 <b>Select a tool to get started</b>"
        
        try:
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Error showing advanced tools menu: {e}")
            bot.answer_callback_query(call.id, "Error loading menu", show_alert=True)
    
    @bot.callback_query_handler(func=lambda call: call.data == "card_generator_menu")
    def card_generator_menu(call):
        """Show card generator submenu"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        text = (
            "╔═══════════════════════╗\n"
            "║  🎲 𝗖𝗔𝗥𝗗 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗢𝗥  ║\n"
            "╚═══════════════════════╝\n\n"
            "🎯 <b>Generate Credit Cards from BIN</b>\n\n"
            "📝 <b>Command:</b>\n"
            "<code>/gen bin|mm|yy|cvv [count]</code>\n\n"
            "📌 <b>Examples:</b>\n"
            "• <code>/gen 451629xxxxxx|xx|xx|xxx 10</code>\n"
            "• <code>/gen 5xxxxxxxxxxxxx|12|25|xxx</code>\n"
            "• <code>/gen 4532015112xxxx|xx|xx|206 50</code>\n\n"
            "🔤 <b>Pattern Guide:</b>\n"
            "• Use <code>x</code> for random digits\n"
            "• Use <code>xx</code> for random month/year\n"
            "• Use <code>xxx</code> for random CVV\n\n"
            "📊 <b>Limits:</b>\n"
            "• Default: 10 cards\n"
            "• Maximum: 100 cards per generation\n\n"
            "✅ Luhn algorithm validation included"
        )
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Tools", callback_data="advanced_tools_menu"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='HTML'
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "bin_lookup_menu")
    def bin_lookup_menu(call):
        """Show BIN lookup submenu"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        text = (
            "╔═══════════════════════╗\n"
            "  ║  🔍 𝗕𝗜𝗡 𝗟𝗢𝗢𝗞𝗨𝗣  ║\n"
            "╚═══════════════════════╝\n\n"
            "🏦 <b>Bank Identification Number Lookup</b>\n\n"
            "📝 <b>Command:</b>\n"
            "<code>/bin [bin_number]</code>\n\n"
            "📌 <b>Examples:</b>\n"
            "• <code>/bin 451629</code>\n"
            "• <code>/bin 453201</code>\n"
            "• <code>/bin 556677</code>\n\n"
            "ℹ️ <b>Information Retrieved:</b>\n"
            "• 🏦 Bank Name\n"
            "• 💳 Card Brand (VISA/Mastercard/etc)\n"
            "• 📇 Card Scheme\n"
            "• 📊 Card Type (Credit/Debit)\n"
            "• 🌍 Country & Flag\n"
            "• 🔖 Prepaid Status\n\n"
            "📏 <b>BIN Length:</b> 6-8 digits"
        )
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Tools", callback_data="advanced_tools_menu"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='HTML'
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "sms_bomber_menu")
    def sms_bomber_menu(call):
        """Show SMS bomber submenu"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        text = (
            "╔═══════════════════════╗\n"
            "  ║  💣 𝗦𝗠𝗦 𝗕𝗢𝗠𝗕𝗘𝗥  ║\n"
            "╚═══════════════════════╝\n\n"
            "📱 <b>Multi-SMS Sender</b>\n\n"
            "📝 <b>Command:</b>\n"
            "<code>/bomb [phone] [count]</code>\n\n"
            "📌 <b>Examples:</b>\n"
            "• <code>/bomb +1234567890 10</code>\n"
            "• <code>/bomb 9876543210</code>\n"
            "• <code>/bomb +919876543210 15</code>\n\n"
            "📊 <b>Settings:</b>\n"
            "• Default: 10 messages\n"
            "• Maximum: 20 messages\n"
            "• Multiple API support\n\n"
            "⚠️ <b>Warning:</b>\n"
            "Use this tool responsibly!\n"
            "Misuse may result in account ban.\n\n"
            "⏱️ Average time: 10-30 seconds"
        )
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Tools", callback_data="advanced_tools_menu"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='HTML'
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "call_bomber_menu")
    def call_bomber_menu(call):
        """Show Call bomber menu with start option"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        text = (
            "╔═══════════════════════╗\n"
            "  ║  📞 𝗖𝗔𝗟𝗟 𝗕𝗢𝗠𝗕𝗘𝗥  ║\n"
            "╚═══════════════════════╝\n\n"
            "📱 <b>Automated Call Spammer</b>\n\n"
            "🔥 <b>Features:</b>\n"
            "• ✅ Real API integration\n"
            "• ✅ Live status tracking\n"
            "• ✅ 5 iterations per session\n"
            "• ✅ Result logs & duration\n\n"
            "📝 <b>How to use:</b>\n"
            "1. Click 'Start Call Bomber' below\n"
            "2. Send phone number (with country code)\n"
            "3. Wait for bombing to complete\n\n"
            "📌 <b>Format Examples:</b>\n"
            "• <code>+1234567890</code>\n"
            "• <code>919876543210</code>\n"
            "• <code>+919876543210</code>\n\n"
            "⚠️ <b>Warning:</b>\n"
            "Use responsibly. Average time: 15-30s\n\n"
            "🔧 <b>API:</b> AivoraTech Bomber 2077"
        )
        
        markup.add(types.InlineKeyboardButton("🚀 Start Call Bomber", callback_data="call_bomber_start"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Tools", callback_data="advanced_tools_menu"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='HTML'
        )
    
    # Store user states for call bomber
    call_bomber_states = {}
    
    @bot.callback_query_handler(func=lambda call: call.data == "call_bomber_start")
    def call_bomber_start(call):
        """Initiate call bomber flow"""
        user_id = call.from_user.id
        call_bomber_states[user_id] = "awaiting_phone"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="call_bomber_menu"))
        
        bot.edit_message_text(
            "📞 <b>Call Bomber Started</b>\n\n"
            "📱 Please send the target phone number:\n\n"
            "📌 <b>Format examples:</b>\n"
            "• <code>+1234567890</code>\n"
            "• <code>919876543210</code>\n"
            "• <code>+919876543210</code>\n\n"
            "⏳ Waiting for your input...",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
    
    @bot.message_handler(func=lambda m: call_bomber_states.get(m.from_user.id) == "awaiting_phone")
    def handle_call_bomber_phone(message):
        """Handle phone number input for call bomber"""
        user_id = message.from_user.id
        phone = message.text.strip()
        
        # Clear state
        call_bomber_states.pop(user_id, None)
        
        # Send processing message
        status_msg = bot.reply_to(message, "⏳ <b>Initiating Call Bomber...</b>\n\n📡 Connecting to API...", parse_mode='HTML')
        
        try:
            # API endpoint
            BASE_URL = "https://aivoratechbomber-2077.onrender.com"
            
            # Prepare payload
            payload = {
                "phone": phone,
                "ip": "192.168.1.1",
                "iterations": 5
            }
            
            # Send POST request
            import requests
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/json"
            })
            
            bot.edit_message_text(
                "⏳ <b>Call Bomber Processing...</b>\n\n"
                f"📱 Target: <code>{phone}</code>\n"
                "📡 Sending bomb request...",
                message.chat.id,
                status_msg.message_id,
                parse_mode='HTML'
            )
            
            # POST to start bombing
            response = session.post(f"{BASE_URL}/api/bomb", json=payload, timeout=30)
            
            if response.status_code != 200:
                bot.edit_message_text(
                    f"❌ <b>API Error</b>\n\n"
                    f"Status: <code>{response.status_code}</code>\n"
                    f"Response: <code>{response.text[:200]}</code>",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode='HTML'
                )
                return
            
            # Extract session ID
            import re
            session_id = None
            try:
                data = response.json()
                session_id = data.get("session_id") or data.get("id")
            except:
                match = re.search(r'"session[_-]?id"\s*:\s*(\d+)', response.text)
                session_id = match.group(1) if match else None
            
            if not session_id:
                bot.edit_message_text(
                    "❌ <b>Session ID Not Found</b>\n\n"
                    f"Response: <code>{response.text[:200]}</code>",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode='HTML'
                )
                return
            
            bot.edit_message_text(
                "✅ <b>Call Bombing Started!</b>\n\n"
                f"📱 Target: <code>{phone}</code>\n"
                f"🆔 Session: <code>{session_id}</code>\n"
                f"🔄 Iterations: <b>5</b>\n\n"
                "⏳ Tracking status...",
                message.chat.id,
                status_msg.message_id,
                parse_mode='HTML'
            )
            
            # Poll for status
            max_polls = 20
            poll_count = 0
            last_status = None
            
            while poll_count < max_polls:
                time.sleep(3)
                poll_count += 1
                
                try:
                    status_resp = session.get(f"{BASE_URL}/api/session/{session_id}", timeout=15)
                    
                    if status_resp.status_code != 200:
                        continue
                    
                    status_data = status_resp.json()
                    status = status_data.get("status", "unknown")
                    duration = status_data.get("duration", "N/A")
                    results = status_data.get("results", {})
                    logs = status_data.get("logs", [])
                    
                    # Update only if status changed
                    if status != last_status:
                        last_status = status
                        
                        status_text = (
                            f"📞 <b>Call Bomber Status</b>\n\n"
                            f"📱 Target: <code>{phone}</code>\n"
                            f"🆔 Session: <code>{session_id}</code>\n"
                            f"📊 Status: <b>{status.upper()}</b>\n"
                            f"⏱️ Duration: <code>{duration}</code>\n\n"
                        )
                        
                        if results:
                            status_text += "📈 <b>Results:</b>\n"
                            for key, val in results.items():
                                status_text += f"  • {key}: <code>{val}</code>\n"
                            status_text += "\n"
                        
                        if logs:
                            last_log = logs[-1] if isinstance(logs, list) else str(logs)
                            status_text += f"📝 Last Log:\n<code>{last_log[:100]}</code>\n\n"
                        
                        status_text += f"🔄 Poll: {poll_count}/{max_polls}"
                        
                        try:
                            bot.edit_message_text(
                                status_text,
                                message.chat.id,
                                status_msg.message_id,
                                parse_mode='HTML'
                            )
                        except:
                            pass
                    
                    # Check if finished
                    if status.lower() not in ("running", "in_progress", "pending"):
                        final_text = (
                            f"✅ <b>Call Bombing Complete!</b>\n\n"
                            f"📱 Target: <code>{phone}</code>\n"
                            f"🆔 Session: <code>{session_id}</code>\n"
                            f"📊 Status: <b>{status.upper()}</b>\n"
                            f"⏱️ Duration: <code>{duration}</code>\n\n"
                        )
                        
                        if results:
                            final_text += "📈 <b>Final Results:</b>\n"
                            for key, val in results.items():
                                final_text += f"  • {key}: <code>{val}</code>\n"
                        
                        markup = types.InlineKeyboardMarkup()
                        markup.add(
                            types.InlineKeyboardButton("🔄 Bomb Again", callback_data="call_bomber_start"),
                            types.InlineKeyboardButton("⬅️ Menu", callback_data="call_bomber_menu")
                        )
                        
                        bot.edit_message_text(
                            final_text,
                            message.chat.id,
                            status_msg.message_id,
                            reply_markup=markup,
                            parse_mode='HTML'
                        )
                        break
                        
                except Exception as e:
                    logger.error(f"Polling error: {e}")
                    continue
            
            # If max polls reached
            if poll_count >= max_polls:
                bot.edit_message_text(
                    f"⏱️ <b>Polling Timeout</b>\n\n"
                    f"📱 Target: <code>{phone}</code>\n"
                    f"🆔 Session: <code>{session_id}</code>\n\n"
                    f"The bombing may still be in progress.\n"
                    f"Check manually if needed.",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode='HTML'
                )
            
        except requests.exceptions.Timeout:
            bot.edit_message_text(
                "❌ <b>Request Timeout</b>\n\n"
                "The API took too long to respond.\n"
                "Please try again later.",
                message.chat.id,
                status_msg.message_id,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Call bomber error: {e}")
            bot.edit_message_text(
                f"❌ <b>Error Occurred</b>\n\n"
                f"<code>{str(e)[:200]}</code>\n\n"
                "Please try again later.",
                message.chat.id,
                status_msg.message_id,
                parse_mode='HTML'
            )
    
    # ============================================
    # COMMAND HANDLERS FOR ADVANCED TOOLS
    # ============================================
    
    def luhn_check(card_number):
        """Validate card number using Luhn algorithm"""
        def digits_of(n):
            return [int(d) for d in str(n)]
        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d*2))
        return checksum % 10 == 0
    
    @bot.message_handler(commands=['auth'])
    def cmd_auth(message):
        """CC Auth check command - DEMO MODE"""
        user_id = message.from_user.id
        
        # Check cooldown
        if user_id in user_cooldowns:
            elapsed = time.time() - user_cooldowns[user_id]
            if elapsed < COOLDOWN_SECONDS:
                remaining = int(COOLDOWN_SECONDS - elapsed)
                bot.reply_to(message, f"⏳ Please wait {remaining}s before next check")
                return
        
        if not message.text or len(message.text.split()) < 2:
            bot.reply_to(message,
                "📋 <b>CC Auth Checker</b>\n\n"
                "Usage: /auth <code>cc|mm|yy|cvv</code>\n"
                "Example: <code>/auth 4532015112830366|12|2025|123</code>\n\n"
                "✅ Validates card format & Luhn algorithm\n"
                "⚠️ Demo mode - shows validation only",
                parse_mode='HTML'
            )
            return
        
        user_cooldowns[user_id] = time.time()
        
        cc_string = message.text.split(maxsplit=1)[1]
        parts = cc_string.strip().split('|')
        
        if len(parts) != 4:
            bot.reply_to(message, "❌ Invalid format. Use: cc|mm|yy|cvv")
            return
        
        card_num, mm, yy, cvv = parts
        
        # Validate card number
        if not card_num.isdigit() or len(card_num) < 13 or len(card_num) > 19:
            bot.reply_to(message, "❌ Invalid card number length (must be 13-19 digits)")
            return
        
        # Validate month
        try:
            month = int(mm)
            if month < 1 or month > 12:
                bot.reply_to(message, "❌ Invalid month (must be 01-12)")
                return
        except:
            bot.reply_to(message, "❌ Invalid month format")
            return
        
        # Validate year
        try:
            year = int(yy)
            current_year = int(datetime.now().strftime('%y'))
            if year < current_year or year > current_year + 20:
                bot.reply_to(message, "❌ Card expired or invalid year")
                return
        except:
            bot.reply_to(message, "❌ Invalid year format")
            return
        
        # Validate CVV
        if not cvv.isdigit() or len(cvv) < 3 or len(cvv) > 4:
            bot.reply_to(message, "❌ Invalid CVV (must be 3-4 digits)")
            return
        
        status_msg = bot.reply_to(message, "⏳ Validating card...")
        
        try:
            time.sleep(random.uniform(0.5, 1.5))
            
            # Check Luhn algorithm
            is_luhn_valid = luhn_check(card_num)
            
            # Get card brand
            first_digit = card_num[0]
            if first_digit == '4':
                brand = 'VISA'
            elif first_digit == '5':
                brand = 'MASTERCARD'
            elif first_digit == '3':
                brand = 'AMEX'
            elif first_digit == '6':
                brand = 'DISCOVER'
            else:
                brand = 'UNKNOWN'
            
            if is_luhn_valid:
                response = f"✅ <b>CARD VALID</b>\n\n"
                response += f"Card: <code>{card_num[:6]}••••{card_num[-4:]}</code>\n"
                response += f"Brand: <b>{brand}</b>\n"
                response += f"Expiry: <b>{mm}/{yy}</b>\n"
                response += f"Luhn: <b>✅ VALID</b>\n\n"
                response += f"⚠️ <i>Demo mode - Real gateway check not performed</i>\n"
            else:
                response = f"❌ <b>CARD INVALID</b>\n\n"
                response += f"Card: <code>{card_num[:6]}••••{card_num[-4:]}</code>\n"
                response += f"Brand: <b>{brand}</b>\n"
                response += f"Luhn: <b>❌ FAILED</b>\n\n"
                response += f"Card number fails Luhn algorithm validation"
            
            response += f"\n⏰ {datetime.now().strftime('%H:%M:%S')}"
            
            bot.edit_message_text(response, status_msg.chat.id, status_msg.message_id, parse_mode='HTML')
        except Exception as e:
            bot.edit_message_text(f"❌ Check failed: {str(e)}", status_msg.chat.id, status_msg.message_id)
    
    @bot.message_handler(commands=['charge'])
    def cmd_charge(message):
        """CC Charge check command - DEMO MODE"""
        user_id = message.from_user.id
        
        # Check cooldown
        if user_id in user_cooldowns:
            elapsed = time.time() - user_cooldowns[user_id]
            if elapsed < COOLDOWN_SECONDS:
                remaining = int(COOLDOWN_SECONDS - elapsed)
                bot.reply_to(message, f"⏳ Please wait {remaining}s before next check")
                return
        
        if not message.text or len(message.text.split()) < 2:
            bot.reply_to(message,
                "💳 <b>CC Charge Checker</b>\n\n"
                "Usage: /charge <code>cc|mm|yy|cvv [amount]</code>\n"
                "Example: <code>/charge 4532015112830366|12|2025|123 1.00</code>\n\n"
                "⚠️ Demo mode - Real charges not performed\n"
                "Use /auth for card validation",
                parse_mode='HTML'
            )
            return
        
        bot.reply_to(message, 
            "⚠️ <b>CHARGE DEMO MODE</b>\n\n"
            "This is a demonstration only.\n"
            "Real payment gateway integration required for actual charges.\n\n"
            "Use /auth to validate card format and Luhn algorithm instead.",
            parse_mode='HTML'
        )
    
    @bot.message_handler(commands=['gen'])
    def cmd_gen(message):
        """Card generator command with Luhn validation"""
        if not message.text or len(message.text.split()) < 2:
            bot.reply_to(message,
                "🎲 <b>Card Generator</b>\n\n"
                "Usage: /gen <code>bin|mm|yy|cvv [count]</code>\n\n"
                "Examples:\n"
                "• <code>/gen 451629xxxxxx|xx|xx|xxx 10</code>\n"
                "• <code>/gen 5xxxxxxxxxxxxx|12|25|xxx</code>\n\n"
                "Use 'x' for random digits\n"
                "Default: 10 cards (max: 100)\n"
                "✅ Luhn algorithm validation included",
                parse_mode='HTML'
            )
            return
        
        parts = message.text.split()
        try:
            card_parts = parts[1].split('|')
            if len(card_parts) != 4:
                bot.reply_to(message, "❌ Invalid format. Use: bin|mm|yy|cvv")
                return
            
            bin_pattern, mm, yy, cvv = card_parts
            count = 10
            if len(parts) > 2:
                try:
                    count = int(parts[2])
                    count = max(1, min(count, 100))
                except ValueError:
                    count = 10
            
            status_msg = bot.reply_to(message, f"⏳ Generating {count} cards...")
            
            def calculate_luhn_digit(partial):
                """Calculate Luhn check digit"""
                def digits_of(n):
                    return [int(d) for d in str(n)]
                digits = digits_of(partial * 10)
                odd_digits = digits[-1::-2]
                even_digits = digits[-2::-2]
                checksum = sum(odd_digits)
                for d in even_digits:
                    checksum += sum(digits_of(d*2))
                return (10 - (checksum % 10)) % 10
            
            # Generate cards
            cards = []
            for _ in range(count):
                # Generate card number with Luhn
                card_num = ''
                for i, char in enumerate(bin_pattern):
                    if char.lower() == 'x':
                        if i == len(bin_pattern) - 1:
                            # Last digit - calculate Luhn
                            partial = int(card_num)
                            card_num += str(calculate_luhn_digit(partial))
                        else:
                            card_num += str(random.randint(0, 9))
                    else:
                        card_num += char
                
                # If pattern is 15 digits, add Luhn check digit
                if len(card_num) == 15 and 'x' in bin_pattern.lower():
                    check_digit = calculate_luhn_digit(int(card_num))
                    card_num += str(check_digit)
                
                month = str(random.randint(1, 12)).zfill(2) if mm == 'xx' else mm
                year = str(random.randint(25, 30)) if yy == 'xx' else yy
                
                cvv_code = ''
                for char in cvv:
                    if char.lower() == 'x':
                        cvv_code += str(random.randint(0, 9))
                    else:
                        cvv_code += char
                
                cards.append(f"{card_num}|{month}|{year}|{cvv_code}")
            
            response = f"✅ <b>Generated {len(cards)} Cards</b>\n\n"
            response += f"BIN: <code>{bin_pattern[:6]}</code>\n"
            response += f"✅ Luhn validated\n\n"
            response += "<b>Cards:</b>\n<code>" + "\n".join(cards[:20]) + "</code>"
            
            if len(cards) > 20:
                response += f"\n\n<i>...and {len(cards) - 20} more cards</i>"
            
            bot.edit_message_text(response, status_msg.chat.id, status_msg.message_id, parse_mode='HTML')
            
        except Exception as e:
            bot.reply_to(message, f"❌ Generation failed: {str(e)}")
    
    @bot.message_handler(commands=['bin'])
    def cmd_bin(message):
        """BIN lookup command"""
        if not message.text or len(message.text.split()) < 2:
            bot.reply_to(message,
                "🔍 <b>BIN Lookup</b>\n\n"
                "Usage: /bin <code>[bin_number]</code>\n\n"
                "Examples:\n"
                "• <code>/bin 451629</code>\n"
                "• <code>/bin 453201</code>\n\n"
                "Provides card information from BIN",
                parse_mode='HTML'
            )
            return
        
        bin_number = message.text.split()[1].strip()
        
        if not bin_number.isdigit() or len(bin_number) < 6:
            bot.reply_to(message, "❌ BIN must be 6-8 digits")
            return
        
        status_msg = bot.reply_to(message, "⏳ Looking up BIN...")
        
        try:
            import requests
            response_api = requests.get(f"https://lookup.binlist.net/{bin_number}", timeout=10)
            
            if response_api.status_code == 200:
                data = response_api.json()
                
                scheme = data.get('scheme', 'UNKNOWN').upper()
                card_type = data.get('type', 'UNKNOWN').upper()
                brand = data.get('brand', 'UNKNOWN').upper()
                bank = data.get('bank', {}).get('name', 'UNKNOWN')
                country = data.get('country', {}).get('name', 'UNKNOWN')
                country_code = data.get('country', {}).get('alpha2', 'XX')
                
                # Get flag
                if len(country_code) == 2:
                    code_points = [ord(char) + 127397 for char in country_code.upper()]
                    flag = ''.join(chr(cp) for cp in code_points)
                else:
                    flag = "🏳️"
                
                response_text = f"🔍 <b>BIN Information</b>\n\n"
                response_text += f"BIN: <code>{bin_number}</code>\n"
                response_text += f"━━━━━━━━━━━━━━━━\n\n"
                response_text += f"🏦 Bank: <b>{bank}</b>\n"
                response_text += f"💳 Brand: <b>{brand}</b>\n"
                response_text += f"📇 Scheme: <b>{scheme}</b>\n"
                response_text += f"📊 Type: <b>{card_type}</b>\n"
                response_text += f"{flag} Country: <b>{country}</b>\n\n"
                response_text += f"⏰ {datetime.now().strftime('%H:%M:%S')}"
                
                bot.edit_message_text(response_text, status_msg.chat.id, status_msg.message_id, parse_mode='HTML')
            else:
                bot.edit_message_text(f"❌ BIN not found", status_msg.chat.id, status_msg.message_id)
                
        except Exception as e:
            bot.edit_message_text(f"❌ Lookup failed: {str(e)}", status_msg.chat.id, status_msg.message_id)
    
    @bot.message_handler(commands=['bomb'])
    def cmd_bomb(message):
        """SMS bomber command - DEMO MODE"""
        if not message.text or len(message.text.split()) < 2:
            bot.reply_to(message,
                "💣 <b>SMS Bomber</b>\n\n"
                "Usage: /bomb <code>[phone] [count]</code>\n\n"
                "Examples:\n"
                "• <code>/bomb +1234567890 10</code>\n"
                "• <code>/bomb 9876543210</code>\n\n"
                "Default: 10 messages (max: 20)\n"
                "⚠️ <b>Demo mode - No real SMS sent</b>\n"
                "Real SMS API integration required",
                parse_mode='HTML'
            )
            return
        
        parts = message.text.split()
        phone = parts[1].strip()
        count = 10
        
        if len(parts) > 2:
            try:
                count = int(parts[2])
                count = max(1, min(count, 20))
            except ValueError:
                count = 10
        
        phone_clean = ''.join(filter(str.isdigit, phone))
        if len(phone_clean) < 10:
            bot.reply_to(message, "❌ Invalid phone number")
            return
        
        status_msg = bot.reply_to(message,
            f"💣 <b>SMS Bomb - DEMO MODE</b>\n\n"
            f"Target: <code>{phone}</code>\n"
            f"Messages: {count}\n\n"
            f"⏳ Simulating...",
            parse_mode='HTML'
        )
        
        try:
            # Simulate bombing
            sent = 0
            failed = 0
            for _ in range(count):
                time.sleep(random.uniform(0.1, 0.3))
                if random.choice([True, True, True, False]):
                    sent += 1
                else:
                    failed += 1
            
            response = f"💣 <b>SMS Bomb Complete - DEMO</b>\n\n"
            response += f"Target: <code>{phone}</code>\n"
            response += f"━━━━━━━━━━━━━━━━\n\n"
            response += f"✅ Sent: <b>{sent}</b>\n"
            response += f"❌ Failed: <b>{failed}</b>\n"
            response += f"📊 Total: <b>{count}</b>\n\n"
            response += f"⚠️ <i>Demo mode - No real SMS sent</i>\n"
            response += f"Real SMS API required for actual bombing\n\n"
            response += f"⏰ {datetime.now().strftime('%H:%M:%S')}"
            
            bot.edit_message_text(response, status_msg.chat.id, status_msg.message_id, parse_mode='HTML')
            
        except Exception as e:
            bot.edit_message_text(f"❌ Demo failed: {str(e)}", status_msg.chat.id, status_msg.message_id)
    
    logger.info("✅ Advanced Tools handlers registered")
