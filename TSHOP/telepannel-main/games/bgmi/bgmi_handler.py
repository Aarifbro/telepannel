# games/bgmi/bgmi_handler.py

import json
import os
import random
from datetime import datetime, timedelta
from telebot import types
from helpers import safe_edit_message

# BGMI accounts storage file
BGMI_DATA_FILE = "bgmi_accounts.json"

# Store claimed accounts with cooldown
bgmi_claims = {}

def load_bgmi_accounts():
    """Load BGMI accounts from JSON file"""
    if os.path.exists(BGMI_DATA_FILE):
        try:
            with open(BGMI_DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"accounts": [], "claimed_history": {}}

def save_bgmi_accounts(data):
    """Save BGMI accounts to JSON file"""
    with open(BGMI_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def can_claim_bgmi(user_id):
    """Check if user can claim a BGMI account (24-hour cooldown)"""
    if user_id not in bgmi_claims:
        return True, None
    
    last_claim = bgmi_claims[user_id]
    time_passed = datetime.now() - last_claim
    cooldown = timedelta(hours=24)
    
    if time_passed >= cooldown:
        return True, None
    
    remaining = cooldown - time_passed
    hours = int(remaining.total_seconds() // 3600)
    minutes = int((remaining.total_seconds() % 3600) // 60)
    return False, f"{hours}h {minutes}m"

def register_bgmi_handlers(bot):
    """Register all BGMI-related callback handlers"""
    
    @bot.callback_query_handler(func=lambda call: call.data == "bgmi_menu")
    def bgmi_menu(call):
        """Show BGMI main menu"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        text = (
            "🎮 <b>BGMI Account Giveaway</b>\n\n"
            "🎁 Get free BGMI accounts!\n"
            "⏱️ One claim per 24 hours\n"
            "📊 Random account selection\n\n"
            "🔥 <b>Account Types Available:</b>\n"
            "• Level 1-10 accounts\n"
            "• Level 11-30 accounts\n"
            "• Level 31-50 accounts\n"
            "• Level 51+ premium accounts\n\n"
            "💎 Each account may have:\n"
            "✅ UC (Unknown Cash)\n"
            "✅ Skins & Outfits\n"
            "✅ Weapons & Items\n"
            "✅ Battle Pass Points\n\n"
            "Click below to claim your account!"
        )
        
        markup.add(
            types.InlineKeyboardButton(
                "🎁 Claim Account",
                callback_data="bgmi_claim"
            )
        )
        
        markup.add(
            types.InlineKeyboardButton(
                "📊 My Claims",
                callback_data="bgmi_history"
            )
        )
        
        markup.add(
            types.InlineKeyboardButton(
                "⬅️ Back to Games",
                callback_data="games_menu"
            )
        )
        
        safe_edit_message(
            bot,
            call,
            text,
            reply_markup=markup,
            parse_mode="HTML"
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "bgmi_claim")
    def bgmi_claim(call):
        """Handle BGMI account claim"""
        user_id = call.from_user.id
        
        # Check cooldown
        can_claim, remaining = can_claim_bgmi(user_id)
        
        if not can_claim:
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "⬅️ Back",
                    callback_data="bgmi_menu"
                )
            )
            
            text = (
                "⏰ <b>Cooldown Active</b>\n\n"
                f"You can claim another account in:\n"
                f"🕐 <b>{remaining}</b>\n\n"
                "Come back later!"
            )
            
            safe_edit_message(
                bot,
                call,
                text,
                reply_markup=markup,
                parse_mode="HTML"
            )
            return
        
        # Load accounts
        data = load_bgmi_accounts()
        accounts = data.get("accounts", [])
        
        if not accounts:
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "⬅️ Back",
                    callback_data="bgmi_menu"
                )
            )
            
            text = (
                "😔 <b>No Accounts Available</b>\n\n"
                "All BGMI accounts have been claimed.\n"
                "Check back later for new accounts!"
            )
            
            safe_edit_message(
                bot,
                call,
                text,
                reply_markup=markup,
                parse_mode="HTML"
            )
            return
        
        # Give random account
        account = random.choice(accounts)
        accounts.remove(account)
        
        # Update cooldown
        bgmi_claims[user_id] = datetime.now()
        
        # Save to history
        if "claimed_history" not in data:
            data["claimed_history"] = {}
        
        if str(user_id) not in data["claimed_history"]:
            data["claimed_history"][str(user_id)] = []
        
        claim_record = {
            "account": account,
            "timestamp": datetime.now().isoformat()
        }
        data["claimed_history"][str(user_id)].append(claim_record)
        
        # Save updated data
        data["accounts"] = accounts
        save_bgmi_accounts(data)
        
        # Send account details
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(
                "🎮 Claim Another (24h)",
                callback_data="bgmi_claim"
            )
        )
        markup.add(
            types.InlineKeyboardButton(
                "⬅️ Back to Menu",
                callback_data="bgmi_menu"
            )
        )
        
        username = account.get("username", "N/A")
        password = account.get("password", "N/A")
        level = account.get("level", "N/A")
        uc = account.get("uc", 0)
        skins = account.get("skins", 0)
        
        text = (
            "🎉 <b>Account Claimed Successfully!</b>\n\n"
            "📋 <b>Account Details:</b>\n"
            f"👤 Username: <code>{username}</code>\n"
            f"🔐 Password: <code>{password}</code>\n"
            f"⭐ Level: <b>{level}</b>\n"
            f"💰 UC: <b>{uc}</b>\n"
            f"👕 Skins: <b>{skins}</b>\n\n"
            "⚠️ <b>Important:</b>\n"
            "• Change password immediately\n"
            "• Link to your email/phone\n"
            "• Save these details securely\n\n"
            "🎮 Enjoy your BGMI account!"
        )
        
        safe_edit_message(
            bot,
            call,
            text,
            reply_markup=markup,
            parse_mode="HTML"
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "bgmi_history")
    def bgmi_history(call):
        """Show user's claim history"""
        user_id = call.from_user.id
        
        data = load_bgmi_accounts()
        history = data.get("claimed_history", {}).get(str(user_id), [])
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "⬅️ Back",
                callback_data="bgmi_menu"
            )
        )
        
        if not history:
            text = (
                "📊 <b>Your Claims History</b>\n\n"
                "You haven't claimed any BGMI accounts yet.\n\n"
                "Go back and claim your first account!"
            )
        else:
            text = f"📊 <b>Your Claims History</b>\n\n"
            text += f"Total Claims: <b>{len(history)}</b>\n\n"
            
            for i, claim in enumerate(reversed(history[-5:]), 1):  # Show last 5
                account = claim.get("account", {})
                timestamp = claim.get("timestamp", "")
                username = account.get("username", "N/A")
                level = account.get("level", "N/A")
                
                try:
                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    time_str = "Unknown"
                
                text += (
                    f"<b>{i}.</b> {username} (Lvl {level})\n"
                    f"   🕐 {time_str}\n\n"
                )
        
        safe_edit_message(
            bot,
            call,
            text,
            reply_markup=markup,
            parse_mode="HTML"
        )
