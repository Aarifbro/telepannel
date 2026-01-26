"""
Referral System Module
Allows users to invite friends and earn rewards
"""

import sqlite3
import json
from datetime import datetime
from telebot import types
from config import DB_NAME, ADMIN_IDS
from database import update_user_credits, get_user_credits

# Referral Configuration
REFERRAL_REWARD = 50  # Credits for referrer when someone uses their code
REFEREE_BONUS = 25    # Bonus credits for new user who uses a referral code
REFERRAL_MILESTONES = {
    5: 100,    # 5 referrals = 100 bonus credits
    10: 250,   # 10 referrals = 250 bonus credits
    25: 750,   # 25 referrals = 750 bonus credits
    50: 2000,  # 50 referrals = 2000 bonus credits
    100: 5000  # 100 referrals = 5000 bonus credits
}


def init_referral_db():
    """Initialize referral database tables"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Create referrals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referee_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reward_claimed BOOLEAN DEFAULT 0,
                UNIQUE(referee_id)
            )
        ''')
        
        # Create referral codes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS referral_codes (
                user_id INTEGER PRIMARY KEY,
                referral_code TEXT UNIQUE NOT NULL,
                total_referrals INTEGER DEFAULT 0,
                total_earnings INTEGER DEFAULT 0,
                last_milestone INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Referral database initialized")
    except Exception as e:
        print(f"❌ Error initializing referral DB: {e}")


def generate_referral_code(user_id):
    """Generate or retrieve existing referral code for user"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Check if user already has a code
        cursor.execute("SELECT referral_code FROM referral_codes WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if result:
            conn.close()
            return result[0]
        
        # Generate new code: REF + user_id in base36
        code = f"REF{user_id:08X}"
        
        cursor.execute(
            "INSERT INTO referral_codes (user_id, referral_code) VALUES (?, ?)",
            (user_id, code)
        )
        conn.commit()
        conn.close()
        
        return code
    except Exception as e:
        print(f"Error generating referral code: {e}")
        return None


def use_referral_code(referee_id, referral_code):
    """
    Process when a new user uses a referral code
    Returns (success, message)
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Check if referee already used a code
        cursor.execute("SELECT id FROM referrals WHERE referee_id = ?", (referee_id,))
        if cursor.fetchone():
            conn.close()
            return False, "❌ You have already used a referral code!"
        
        # Find referrer by code
        cursor.execute("SELECT user_id FROM referral_codes WHERE referral_code = ?", (referral_code,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return False, "❌ Invalid referral code!"
        
        referrer_id = result[0]
        
        # Can't refer yourself
        if referrer_id == referee_id:
            conn.close()
            return False, "❌ You cannot use your own referral code!"
        
        # Create referral record
        cursor.execute(
            "INSERT INTO referrals (referrer_id, referee_id, reward_claimed) VALUES (?, ?, 1)",
            (referrer_id, referee_id)
        )
        
        # Update referrer stats
        cursor.execute(
            "UPDATE referral_codes SET total_referrals = total_referrals + 1, total_earnings = total_earnings + ? WHERE user_id = ?",
            (REFERRAL_REWARD, referrer_id)
        )
        
        # Award credits
        update_user_credits(referrer_id, REFERRAL_REWARD)  # Reward for referrer
        update_user_credits(referee_id, REFEREE_BONUS)     # Bonus for new user
        
        # Check for milestone rewards
        cursor.execute("SELECT total_referrals, last_milestone FROM referral_codes WHERE user_id = ?", (referrer_id,))
        total_refs, last_milestone = cursor.fetchone()
        
        milestone_bonus = 0
        for milestone, bonus in sorted(REFERRAL_MILESTONES.items()):
            if total_refs >= milestone and last_milestone < milestone:
                milestone_bonus += bonus
                cursor.execute(
                    "UPDATE referral_codes SET last_milestone = ?, total_earnings = total_earnings + ? WHERE user_id = ?",
                    (milestone, bonus, referrer_id)
                )
        
        if milestone_bonus > 0:
            update_user_credits(referrer_id, milestone_bonus)
        
        conn.commit()
        conn.close()
        
        return True, f"✅ Referral code applied!\n\n💰 You received <b>{REFEREE_BONUS} credits</b> as a welcome bonus!"
        
    except Exception as e:
        print(f"Error using referral code: {e}")
        return False, f"❌ An error occurred: {str(e)}"


def get_referral_stats(user_id):
    """Get referral statistics for a user"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Get user's referral data
        cursor.execute(
            "SELECT referral_code, total_referrals, total_earnings, last_milestone FROM referral_codes WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            # Create code if doesn't exist
            code = generate_referral_code(user_id)
            conn.close()
            return {
                'code': code,
                'total_referrals': 0,
                'total_earnings': 0,
                'last_milestone': 0,
                'recent_referrals': []
            }
        
        code, total_refs, earnings, last_milestone = result
        
        # Get recent referrals
        cursor.execute(
            "SELECT referee_id, created_at FROM referrals WHERE referrer_id = ? ORDER BY created_at DESC LIMIT 10",
            (user_id,)
        )
        recent = cursor.fetchall()
        
        conn.close()
        
        return {
            'code': code,
            'total_referrals': total_refs,
            'total_earnings': earnings,
            'last_milestone': last_milestone,
            'recent_referrals': recent
        }
    except Exception as e:
        print(f"Error getting referral stats: {e}")
        return None


def register_referral_handlers(bot):
    """Register all referral-related handlers"""
    
    # Initialize DB on registration
    init_referral_db()
    
    @bot.callback_query_handler(func=lambda call: call.data == "referral_menu")
    def referral_menu(call):
        """Show referral menu"""
        user_id = call.from_user.id
        stats = get_referral_stats(user_id)
        
        if not stats:
            bot.answer_callback_query(call.id, "❌ Error loading referral data", show_alert=True)
            return
        
        # Calculate next milestone
        next_milestone = None
        next_reward = 0
        for milestone, reward in sorted(REFERRAL_MILESTONES.items()):
            if stats['total_referrals'] < milestone:
                next_milestone = milestone
                next_reward = reward
                break
        
        text = f"""🎁 <b>Referral Program</b>

👥 <b>Your Stats:</b>
• Referrals: <code>{stats['total_referrals']}</code>
• Total Earned: <code>{stats['total_earnings']} credits</code>

🎯 <b>Your Referral Code:</b>
<code>{stats['code']}</code>

💰 <b>Rewards:</b>
• You earn: <b>{REFERRAL_REWARD} credits</b> per referral
• They get: <b>{REFEREE_BONUS} credits</b> bonus

🏆 <b>Milestone Bonuses:</b>"""
        
        for milestone, bonus in sorted(REFERRAL_MILESTONES.items()):
            status = "✅" if stats['total_referrals'] >= milestone else "🔒"
            text += f"\n{status} {milestone} referrals = <b>{bonus} credits</b>"
        
        if next_milestone:
            remaining = next_milestone - stats['total_referrals']
            text += f"\n\n📊 <b>Next Milestone:</b> {remaining} more referrals for <b>{next_reward} credits</b>!"
        
        text += f"\n\n📤 <b>Share your code with friends to start earning!</b>"
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📋 Copy Referral Code", callback_data=f"copy_ref_{stats['code']}"),
            types.InlineKeyboardButton("📊 View Recent Referrals", callback_data="recent_referrals"),
            types.InlineKeyboardButton("ℹ️ How It Works", callback_data="referral_info"),
            types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")
        )
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("copy_ref_"))
    def copy_referral_code(call):
        """Copy referral code to clipboard"""
        code = call.data.replace("copy_ref_", "")
        
        # Show code in a copyable format
        bot.answer_callback_query(
            call.id,
            f"✅ Code: {code}\nShare this with your friends!",
            show_alert=True
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "recent_referrals")
    def show_recent_referrals(call):
        """Show recent referrals list"""
        user_id = call.from_user.id
        stats = get_referral_stats(user_id)
        
        if not stats or not stats['recent_referrals']:
            bot.answer_callback_query(call.id, "You don't have any referrals yet!", show_alert=True)
            return
        
        text = f"👥 <b>Recent Referrals</b>\n\n"
        
        for idx, (referee_id, created_at) in enumerate(stats['recent_referrals'], 1):
            # Format date
            date_str = created_at[:10] if created_at else "Unknown"
            text += f"{idx}. User <code>{referee_id}</code> • {date_str}\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="referral_menu"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "referral_info")
    def referral_info(call):
        """Show how referral system works"""
        text = f"""ℹ️ <b>How Referral System Works</b>

<b>1. Get Your Code</b>
Your unique referral code is displayed in the Referral Menu.

<b>2. Share With Friends</b>
Share your code with friends. They can use it during signup or in their profile.

<b>3. Earn Rewards</b>
• When someone uses your code, you get <b>{REFERRAL_REWARD} credits</b>
• They receive <b>{REFEREE_BONUS} credits</b> as a welcome bonus

<b>4. Unlock Milestones</b>
Reach referral milestones to earn huge bonuses:
"""
        
        for milestone, bonus in sorted(REFERRAL_MILESTONES.items()):
            text += f"• {milestone} referrals = <b>{bonus} credits</b>\n"
        
        text += "\n💡 <b>Pro Tip:</b> The more you refer, the more you earn!"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="referral_menu"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "use_referral_code")
    def prompt_referral_code(call):
        """Prompt user to enter referral code"""
        msg = bot.send_message(
            call.message.chat.id,
            "🎁 <b>Enter Referral Code</b>\n\nPlease enter the referral code you received from a friend:",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, process_referral_code)
    
    def process_referral_code(message):
        """Process the entered referral code"""
        code = message.text.strip().upper()
        success, msg = use_referral_code(message.from_user.id, code)
        
        if success:
            # Show success with credits earned
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("💰 View Balance", callback_data="profile"))
            bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, msg, parse_mode="HTML")
    
    # Admin command to view top referrers
    @bot.message_handler(commands=['top_referrers'])
    def top_referrers(message):
        """Show top referrers (admin only)"""
        if message.from_user.id not in ADMIN_IDS:
            return
        
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT user_id, total_referrals, total_earnings 
                FROM referral_codes 
                WHERE total_referrals > 0 
                ORDER BY total_referrals DESC 
                LIMIT 10
            """)
            
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                bot.reply_to(message, "No referrals yet!")
                return
            
            text = "🏆 <b>Top 10 Referrers</b>\n\n"
            
            for idx, (user_id, refs, earnings) in enumerate(results, 1):
                emoji = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
                text += f"{emoji} User <code>{user_id}</code>\n"
                text += f"   • Referrals: <b>{refs}</b> | Earned: <b>{earnings} credits</b>\n\n"
            
            bot.reply_to(message, text, parse_mode="HTML")
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {str(e)}")

    print("✅ Referral system handlers registered")
