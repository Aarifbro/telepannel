"""
Daily Rewards & Streak System
Encourages daily user engagement with increasing rewards
"""

import sqlite3
from datetime import datetime, timedelta
from telebot import types
from config import DB_NAME, ADMIN_IDS
from database import update_user_credits


# Daily Reward Configuration
DAILY_REWARDS = {
    1: {"credits": 10, "emoji": "⭐"},
    2: {"credits": 15, "emoji": "🌟"},
    3: {"credits": 20, "emoji": "✨"},
    4: {"credits": 25, "emoji": "💫"},
    5: {"credits": 30, "emoji": "🎯"},
    6: {"credits": 40, "emoji": "🔥"},
    7: {"credits": 100, "emoji": "💎"},  # Weekly bonus
}

# Streak milestones with bonus rewards
STREAK_MILESTONES = {
    7: 150,    # 1 week streak
    14: 300,   # 2 weeks streak
    30: 1000,  # 1 month streak
    60: 2500,  # 2 months streak
    90: 5000,  # 3 months streak
}


def init_daily_rewards_db():
    """Initialize daily rewards database table"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_rewards (
                user_id INTEGER PRIMARY KEY,
                current_streak INTEGER DEFAULT 0,
                longest_streak INTEGER DEFAULT 0,
                last_claim_date DATE,
                total_claims INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                streak_milestones_claimed TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Daily rewards database initialized")
    except Exception as e:
        print(f"❌ Error initializing daily rewards DB: {e}")


def get_user_streak_data(user_id):
    """Get user's streak and reward data"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT current_streak, longest_streak, last_claim_date, total_claims, total_earned, streak_milestones_claimed FROM daily_rewards WHERE user_id = ?",
            (user_id,)
        )
        
        result = cursor.fetchone()
        
        if not result:
            # Create new record
            cursor.execute(
                "INSERT INTO daily_rewards (user_id) VALUES (?)",
                (user_id,)
            )
            conn.commit()
            conn.close()
            return {
                'current_streak': 0,
                'longest_streak': 0,
                'last_claim_date': None,
                'total_claims': 0,
                'total_earned': 0,
                'milestones_claimed': []
            }
        
        conn.close()
        
        import json
        return {
            'current_streak': result[0],
            'longest_streak': result[1],
            'last_claim_date': result[2],
            'total_claims': result[3],
            'total_earned': result[4],
            'milestones_claimed': json.loads(result[5])
        }
    except Exception as e:
        print(f"Error getting streak data: {e}")
        return None


def can_claim_daily_reward(user_id):
    """
    Check if user can claim daily reward
    Returns (can_claim, next_claim_time, streak_broken)
    """
    data = get_user_streak_data(user_id)
    if not data:
        return False, None, False
    
    if not data['last_claim_date']:
        return True, None, False
    
    today = datetime.now().date()
    last_claim = datetime.strptime(data['last_claim_date'], '%Y-%m-%d').date()
    
    # Already claimed today
    if last_claim == today:
        next_claim = datetime.combine(today + timedelta(days=1), datetime.min.time())
        return False, next_claim, False
    
    # Check if streak is broken (missed yesterday)
    yesterday = today - timedelta(days=1)
    streak_broken = last_claim < yesterday
    
    return True, None, streak_broken


def claim_daily_reward(user_id):
    """
    Process daily reward claim
    Returns (success, reward_amount, streak_day, milestone_bonus, message)
    """
    try:
        can_claim, next_claim, streak_broken = can_claim_daily_reward(user_id)
        
        if not can_claim:
            if next_claim:
                time_left = next_claim - datetime.now()
                hours = int(time_left.total_seconds() // 3600)
                minutes = int((time_left.total_seconds() % 3600) // 60)
                return False, 0, 0, 0, f"⏰ You can claim your next reward in {hours}h {minutes}m"
            return False, 0, 0, 0, "❌ Error checking claim status"
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        data = get_user_streak_data(user_id)
        
        # Update streak
        if streak_broken:
            new_streak = 1
        else:
            new_streak = data['current_streak'] + 1
        
        # Get reward for current day
        day_in_cycle = ((new_streak - 1) % 7) + 1
        reward_info = DAILY_REWARDS[day_in_cycle]
        reward_amount = reward_info['credits']
        
        # Check for streak milestones
        milestone_bonus = 0
        import json
        milestones_claimed = data['milestones_claimed']
        
        for milestone, bonus in STREAK_MILESTONES.items():
            if new_streak >= milestone and milestone not in milestones_claimed:
                milestone_bonus += bonus
                milestones_claimed.append(milestone)
        
        # Update database
        today = datetime.now().date().isoformat()
        new_longest = max(new_streak, data['longest_streak'])
        new_total_claims = data['total_claims'] + 1
        new_total_earned = data['total_earned'] + reward_amount + milestone_bonus
        
        cursor.execute('''
            UPDATE daily_rewards 
            SET current_streak = ?, 
                longest_streak = ?, 
                last_claim_date = ?, 
                total_claims = ?,
                total_earned = ?,
                streak_milestones_claimed = ?
            WHERE user_id = ?
        ''', (new_streak, new_longest, today, new_total_claims, new_total_earned, json.dumps(milestones_claimed), user_id))
        
        conn.commit()
        conn.close()
        
        # Award credits
        total_reward = reward_amount + milestone_bonus
        update_user_credits(user_id, total_reward)
        
        return True, reward_amount, new_streak, milestone_bonus, "✅ Daily reward claimed!"
        
    except Exception as e:
        print(f"Error claiming daily reward: {e}")
        return False, 0, 0, 0, f"❌ Error: {str(e)}"


def register_daily_rewards_handlers(bot):
    """Register all daily rewards handlers"""
    
    # Initialize DB
    init_daily_rewards_db()
    
    @bot.callback_query_handler(func=lambda call: call.data == "daily_rewards")
    def daily_rewards_menu(call):
        """Show daily rewards menu"""
        user_id = call.from_user.id
        data = get_user_streak_data(user_id)
        
        if not data:
            bot.answer_callback_query(call.id, "❌ Error loading reward data", show_alert=True)
            return
        
        can_claim, next_claim, streak_broken = can_claim_daily_reward(user_id)
        
        # Calculate current day in cycle
        current_day = ((data['current_streak'] - 1) % 7) + 1 if data['current_streak'] > 0 else 1
        
        text = f"""🎁 <b>Daily Rewards</b>

🔥 <b>Current Streak:</b> <code>{data['current_streak']}</code> days
🏆 <b>Longest Streak:</b> <code>{data['longest_streak']}</code> days
📊 <b>Total Claims:</b> <code>{data['total_claims']}</code>
💰 <b>Total Earned:</b> <code>{data['total_earned']}</code> credits

"""
        
        if streak_broken and data['current_streak'] > 0:
            text += "⚠️ <b>Streak broken!</b> Claim today to start a new streak.\n\n"
        
        # Show 7-day reward calendar
        text += "<b>📅 Weekly Rewards Calendar:</b>\n\n"
        
        for day in range(1, 8):
            reward = DAILY_REWARDS[day]
            
            if day < current_day and not can_claim:
                status = "✅"  # Already claimed this cycle
            elif day == current_day and can_claim:
                status = "🎯"  # Can claim now
            elif day == current_day and not can_claim:
                status = "⏳"  # Already claimed today
            else:
                status = "🔒"  # Future days
            
            text += f"{status} Day {day}: <b>{reward['credits']} credits</b> {reward['emoji']}\n"
        
        # Show next milestone
        next_milestone = None
        next_bonus = 0
        for milestone, bonus in sorted(STREAK_MILESTONES.items()):
            if milestone not in data['milestones_claimed']:
                next_milestone = milestone
                next_bonus = bonus
                break
        
        if next_milestone:
            remaining = next_milestone - data['current_streak']
            if remaining > 0:
                text += f"\n🎯 <b>Next Milestone:</b> {remaining} more days for <b>{next_bonus} bonus credits!</b>"
        
        if not can_claim and next_claim:
            time_left = next_claim - datetime.now()
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            text += f"\n\n⏰ Next reward in: <b>{hours}h {minutes}m</b>"
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        if can_claim:
            markup.add(types.InlineKeyboardButton("🎁 Claim Daily Reward", callback_data="claim_daily"))
        
        markup.add(
            types.InlineKeyboardButton("🏆 Streak Milestones", callback_data="streak_milestones"),
            types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")
        )
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "claim_daily")
    def claim_daily(call):
        """Process daily reward claim"""
        user_id = call.from_user.id
        
        success, reward, streak, milestone_bonus, message = claim_daily_reward(user_id)
        
        if not success:
            bot.answer_callback_query(call.id, message, show_alert=True)
            return
        
        # Get reward emoji for the day
        day_in_cycle = ((streak - 1) % 7) + 1
        emoji = DAILY_REWARDS[day_in_cycle]['emoji']
        
        # Create success message
        text = f"""✅ <b>Daily Reward Claimed!</b>

{emoji} <b>Day {streak} Reward</b>
💰 Earned: <b>{reward} credits</b>
"""
        
        if milestone_bonus > 0:
            text += f"\n🎉 <b>MILESTONE BONUS!</b>\n💎 Extra: <b>{milestone_bonus} credits</b>\n"
        
        text += f"\n🔥 Current Streak: <b>{streak} days</b>"
        text += f"\n💰 Total Earned: <b>{reward + milestone_bonus} credits</b>"
        
        text += "\n\n✨ Come back tomorrow to keep your streak!"
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📊 View Rewards", callback_data="daily_rewards"),
            types.InlineKeyboardButton("⬅️ Main Menu", callback_data="main_menu")
        )
        
        # Try to send animation for success
        try:
            from helpers import send_random_animation
            send_random_animation(
                bot,
                call.message.chat.id,
                "success",
                caption=text,
                reply_markup=markup,
                parse_mode="HTML"
            )
            # Delete the old message
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
        except:
            # Fallback to edit
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="HTML"
            )
    
    @bot.callback_query_handler(func=lambda call: call.data == "streak_milestones")
    def show_streak_milestones(call):
        """Show streak milestone information"""
        user_id = call.from_user.id
        data = get_user_streak_data(user_id)
        
        text = f"""🏆 <b>Streak Milestones</b>

Keep your daily streak going to unlock massive bonuses!

<b>Your Progress:</b>
🔥 Current Streak: <code>{data['current_streak']}</code> days
🏆 Longest Streak: <code>{data['longest_streak']}</code> days

<b>Milestone Rewards:</b>
"""
        
        for milestone, bonus in sorted(STREAK_MILESTONES.items()):
            if milestone in data['milestones_claimed']:
                status = "✅ Claimed"
            elif data['current_streak'] >= milestone:
                status = "🎁 Ready to claim!"
            else:
                remaining = milestone - data['current_streak']
                status = f"🔒 {remaining} days remaining"
            
            text += f"\n• <b>{milestone} days</b> = {bonus} credits - {status}"
        
        text += "\n\n💡 <b>Tip:</b> Don't break your streak! Log in every day to claim rewards."
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="daily_rewards"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
    
    # Admin command to view top streaks
    @bot.message_handler(commands=['top_streaks'])
    def top_streaks(message):
        """Show users with longest streaks (admin only)"""
        if message.from_user.id not in ADMIN_IDS:
            return
        
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT user_id, current_streak, longest_streak, total_earned
                FROM daily_rewards
                WHERE current_streak > 0
                ORDER BY current_streak DESC
                LIMIT 10
            """)
            
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                bot.reply_to(message, "No active streaks yet!")
                return
            
            text = "🔥 <b>Top 10 Current Streaks</b>\n\n"
            
            for idx, (user_id, current, longest, earned) in enumerate(results, 1):
                emoji = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
                text += f"{emoji} User <code>{user_id}</code>\n"
                text += f"   🔥 {current} days | 🏆 Best: {longest} | 💰 {earned} credits\n\n"
            
            bot.reply_to(message, text, parse_mode="HTML")
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {str(e)}")

    print("✅ Daily rewards system handlers registered")
