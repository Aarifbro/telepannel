"""
Lucky Wheel / Spin System
Daily spin feature where users can win random prizes
"""

import sqlite3
import random
from datetime import datetime, timedelta
from telebot import types
from config import DB_NAME, ADMIN_IDS
from database import update_user_credits, generate_pro_key


# Prize Configuration (weight determines probability)
PRIZES = [
    {"name": "5 Credits", "type": "credits", "value": 5, "weight": 30, "emoji": "🪙"},
    {"name": "10 Credits", "type": "credits", "value": 10, "weight": 25, "emoji": "💰"},
    {"name": "25 Credits", "type": "credits", "value": 25, "weight": 15, "emoji": "💵"},
    {"name": "50 Credits", "type": "credits", "value": 50, "weight": 10, "emoji": "💸"},
    {"name": "100 Credits", "type": "credits", "value": 100, "weight": 8, "emoji": "💎"},
    {"name": "250 Credits", "type": "credits", "value": 250, "weight": 5, "emoji": "💰✨"},
    {"name": "500 Credits", "type": "credits", "value": 500, "weight": 2, "emoji": "🏆"},
    {"name": "Pro Key", "type": "pro_key", "value": 1, "weight": 3, "emoji": "🔑"},
    {"name": "Better Luck", "type": "nothing", "value": 0, "weight": 2, "emoji": "😅"},
]

# Spin costs and limits
FREE_SPINS_PER_DAY = 3
PAID_SPIN_COST = 20  # Credits per additional spin


def init_lucky_wheel_db():
    """Initialize lucky wheel database"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lucky_wheel (
                user_id INTEGER PRIMARY KEY,
                last_spin_date DATE,
                free_spins_used INTEGER DEFAULT 0,
                paid_spins_used INTEGER DEFAULT 0,
                total_spins INTEGER DEFAULT 0,
                total_won_credits INTEGER DEFAULT 0,
                total_spent_credits INTEGER DEFAULT 0,
                biggest_win INTEGER DEFAULT 0,
                pro_keys_won INTEGER DEFAULT 0,
                spin_history TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Lucky wheel database initialized")
    except Exception as e:
        print(f"❌ Error initializing lucky wheel DB: {e}")


def get_user_spin_data(user_id):
    """Get user's spin data"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT last_spin_date, free_spins_used, paid_spins_used, total_spins, total_won_credits, total_spent_credits, biggest_win, pro_keys_won FROM lucky_wheel WHERE user_id = ?",
            (user_id,)
        )
        
        result = cursor.fetchone()
        
        if not result:
            # Create new record
            cursor.execute("INSERT INTO lucky_wheel (user_id) VALUES (?)", (user_id,))
            conn.commit()
            conn.close()
            return {
                'last_spin_date': None,
                'free_spins_used': 0,
                'paid_spins_used': 0,
                'total_spins': 0,
                'total_won_credits': 0,
                'total_spent_credits': 0,
                'biggest_win': 0,
                'pro_keys_won': 0
            }
        
        conn.close()
        
        return {
            'last_spin_date': result[0],
            'free_spins_used': result[1],
            'paid_spins_used': result[2],
            'total_spins': result[3],
            'total_won_credits': result[4],
            'total_spent_credits': result[5],
            'biggest_win': result[6],
            'pro_keys_won': result[7]
        }
    except Exception as e:
        print(f"Error getting spin data: {e}")
        return None


def get_available_spins(user_id):
    """
    Check available spins for user
    Returns (free_spins_remaining, can_buy_spin)
    """
    data = get_user_spin_data(user_id)
    if not data:
        return 0, False
    
    today = datetime.now().date()
    last_spin = data['last_spin_date']
    
    # Reset daily spins if new day
    if not last_spin or datetime.strptime(last_spin, '%Y-%m-%d').date() < today:
        return FREE_SPINS_PER_DAY, True
    
    free_remaining = max(0, FREE_SPINS_PER_DAY - data['free_spins_used'])
    return free_remaining, True


def spin_wheel(user_id, is_paid=False):
    """
    Spin the wheel and get a prize
    Returns (success, prize_dict, message)
    """
    try:
        from database import get_user_credits
        
        free_spins, can_buy = get_available_spins(user_id)
        
        # Check if user has spins available
        if not is_paid and free_spins <= 0:
            return False, None, f"❌ No free spins left! Buy a spin for {PAID_SPIN_COST} credits."
        
        # Check if user can afford paid spin
        if is_paid:
            user_credits = get_user_credits(user_id)
            if user_credits < PAID_SPIN_COST:
                return False, None, f"❌ Insufficient credits! You need {PAID_SPIN_COST} credits."
            
            # Deduct cost
            update_user_credits(user_id, -PAID_SPIN_COST)
        
        # Select prize based on weights
        prizes_list = []
        weights_list = []
        
        for prize in PRIZES:
            prizes_list.append(prize)
            weights_list.append(prize['weight'])
        
        selected_prize = random.choices(prizes_list, weights=weights_list, k=1)[0]
        
        # Process prize
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        data = get_user_spin_data(user_id)
        today = datetime.now().date().isoformat()
        
        # Reset counters if new day
        if not data['last_spin_date'] or datetime.strptime(data['last_spin_date'], '%Y-%m-%d').date() < datetime.now().date():
            free_used = 0
            paid_used = 0
        else:
            free_used = data['free_spins_used']
            paid_used = data['paid_spins_used']
        
        # Update spin counters
        if is_paid:
            paid_used += 1
            spent = data['total_spent_credits'] + PAID_SPIN_COST
        else:
            free_used += 1
            spent = data['total_spent_credits']
        
        # Award prize
        won_credits = 0
        pro_keys_won = data['pro_keys_won']
        
        if selected_prize['type'] == 'credits':
            won_credits = selected_prize['value']
            update_user_credits(user_id, won_credits)
        elif selected_prize['type'] == 'pro_key':
            # Generate a pro key
            key = generate_pro_key(credits=1000, max_uses=1)
            pro_keys_won += 1
        
        # Update stats
        total_won = data['total_won_credits'] + won_credits
        biggest_win = max(data['biggest_win'], won_credits)
        total_spins = data['total_spins'] + 1
        
        cursor.execute('''
            UPDATE lucky_wheel
            SET last_spin_date = ?,
                free_spins_used = ?,
                paid_spins_used = ?,
                total_spins = ?,
                total_won_credits = ?,
                total_spent_credits = ?,
                biggest_win = ?,
                pro_keys_won = ?
            WHERE user_id = ?
        ''', (today, free_used, paid_used, total_spins, total_won, spent, biggest_win, pro_keys_won, user_id))
        
        conn.commit()
        conn.close()
        
        return True, selected_prize, "✅ Spin complete!"
        
    except Exception as e:
        print(f"Error spinning wheel: {e}")
        return False, None, f"❌ Error: {str(e)}"


def register_lucky_wheel_handlers(bot):
    """Register lucky wheel handlers"""
    
    # Initialize DB
    init_lucky_wheel_db()
    
    @bot.callback_query_handler(func=lambda call: call.data == "lucky_wheel")
    def lucky_wheel_menu(call):
        """Show lucky wheel menu"""
        user_id = call.from_user.id
        data = get_user_spin_data(user_id)
        
        if not data:
            bot.answer_callback_query(call.id, "❌ Error loading wheel data", show_alert=True)
            return
        
        free_spins, can_buy = get_available_spins(user_id)
        
        # Calculate profit/loss
        profit = data['total_won_credits'] - data['total_spent_credits']
        profit_emoji = "📈" if profit >= 0 else "📉"
        
        text = f"""🎡 <b>Lucky Wheel</b>

Spin the wheel to win amazing prizes!

🎯 <b>Your Stats:</b>
• Free Spins Left: <code>{free_spins}/{FREE_SPINS_PER_DAY}</code>
• Total Spins: <code>{data['total_spins']}</code>
• Total Won: <code>{data['total_won_credits']}</code> credits
• Biggest Win: <code>{data['biggest_win']}</code> credits
• Pro Keys Won: <code>{data['pro_keys_won']}</code> 🔑
{profit_emoji} Profit: <code>{profit:+d}</code> credits

💰 <b>Additional Spin Cost:</b> {PAID_SPIN_COST} credits

🎁 <b>Possible Prizes:</b>
"""
        
        # Show prizes sorted by value
        sorted_prizes = sorted([p for p in PRIZES if p['type'] != 'nothing'], 
                              key=lambda x: x['value'], reverse=True)
        
        for prize in sorted_prizes[:5]:  # Show top 5 prizes
            text += f"{prize['emoji']} {prize['name']}\n"
        
        text += "😅 Better Luck Next Time\n"
        text += "\n✨ <i>Spin now for a chance to win!</i>"
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        if free_spins > 0:
            markup.add(types.InlineKeyboardButton(
                f"🎡 Spin (Free - {free_spins} left)", 
                callback_data="spin_free"
            ))
        
        markup.add(
            types.InlineKeyboardButton(
                f"💰 Buy Spin ({PAID_SPIN_COST} credits)", 
                callback_data="spin_paid"
            ),
            types.InlineKeyboardButton("🏆 Prize List", callback_data="wheel_prizes"),
            types.InlineKeyboardButton("📊 Statistics", callback_data="wheel_stats"),
            types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")
        )
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
    
    @bot.callback_query_handler(func=lambda call: call.data in ["spin_free", "spin_paid"])
    def spin_handler(call):
        """Handle wheel spin"""
        user_id = call.from_user.id
        is_paid = call.data == "spin_paid"
        
        # Show spinning animation
        try:
            bot.edit_message_text(
                "🎡 <b>Spinning...</b>\n\n🌀 🌀 🌀",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML"
            )
        except:
            pass
        
        # Process spin
        success, prize, message = spin_wheel(user_id, is_paid)
        
        if not success:
            bot.answer_callback_query(call.id, message, show_alert=True)
            # Refresh menu
            lucky_wheel_menu(call)
            return
        
        # Show result
        if prize['type'] == 'nothing':
            result_text = f"""🎡 <b>Lucky Wheel Result</b>

{prize['emoji']} <b>{prize['name']}</b>

Don't give up! Try again for better prizes!
"""
        elif prize['type'] == 'credits':
            result_text = f"""🎡 <b>Lucky Wheel Result</b>

🎉 <b>WINNER!</b>

{prize['emoji']} You won <b>{prize['value']} credits</b>!

💰 Credits added to your balance.
"""
        elif prize['type'] == 'pro_key':
            result_text = f"""🎡 <b>Lucky Wheel Result</b>

🎊 <b>JACKPOT!</b>

{prize['emoji']} You won a <b>Pro Key</b>!

🔑 Check /keys to view your prize!
This key gives you 1000 credits!
"""
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🎡 Spin Again", callback_data="lucky_wheel"),
            types.InlineKeyboardButton("⬅️ Main Menu", callback_data="main_menu")
        )
        
        # Try to send with animation
        try:
            from helpers import send_random_animation
            animation_type = "success" if prize['type'] != 'nothing' else "reject"
            send_random_animation(
                bot,
                call.message.chat.id,
                animation_type,
                caption=result_text,
                reply_markup=markup,
                parse_mode="HTML"
            )
            # Delete old message
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
        except:
            # Fallback
            bot.edit_message_text(
                result_text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="HTML"
            )
    
    @bot.callback_query_handler(func=lambda call: call.data == "wheel_prizes")
    def show_prizes(call):
        """Show all possible prizes"""
        text = """🎁 <b>Prize List</b>

All possible prizes you can win from the Lucky Wheel:

"""
        
        # Group prizes by type
        credits_prizes = [p for p in PRIZES if p['type'] == 'credits']
        special_prizes = [p for p in PRIZES if p['type'] != 'credits' and p['type'] != 'nothing']
        
        text += "<b>💰 Credit Prizes:</b>\n"
        for prize in sorted(credits_prizes, key=lambda x: x['value'], reverse=True):
            rarity = "Common" if prize['weight'] > 20 else "Rare" if prize['weight'] > 10 else "Epic" if prize['weight'] > 5 else "Legendary"
            text += f"{prize['emoji']} <b>{prize['name']}</b> - {rarity}\n"
        
        text += "\n<b>🎁 Special Prizes:</b>\n"
        for prize in special_prizes:
            text += f"{prize['emoji']} <b>{prize['name']}</b> - Ultra Rare\n   Worth 1000 credits!\n"
        
        text += "\n😅 <b>Better Luck Next Time</b> - Common\n"
        
        text += f"\n💡 <b>Tips:</b>\n• You get {FREE_SPINS_PER_DAY} free spins daily\n• Additional spins cost {PAID_SPIN_COST} credits\n• Higher value prizes are rarer!"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="lucky_wheel"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "wheel_stats")
    def show_wheel_stats(call):
        """Show detailed statistics"""
        user_id = call.from_user.id
        data = get_user_spin_data(user_id)
        
        if not data:
            bot.answer_callback_query(call.id, "❌ Error loading stats", show_alert=True)
            return
        
        # Calculate stats
        profit = data['total_won_credits'] - data['total_spent_credits']
        profit_emoji = "📈" if profit >= 0 else "📉"
        
        avg_win = data['total_won_credits'] // data['total_spins'] if data['total_spins'] > 0 else 0
        
        text = f"""📊 <b>Your Lucky Wheel Statistics</b>

<b>🎯 Spin Stats:</b>
• Total Spins: <code>{data['total_spins']}</code>
• Paid Spins: <code>{data['paid_spins_used']}</code>

<b>💰 Winnings:</b>
• Total Won: <code>{data['total_won_credits']}</code> credits
• Total Spent: <code>{data['total_spent_credits']}</code> credits
{profit_emoji} Net Profit: <code>{profit:+d}</code> credits
• Average Win: <code>{avg_win}</code> credits/spin

<b>🏆 Records:</b>
• Biggest Win: <code>{data['biggest_win']}</code> credits
• Pro Keys Won: <code>{data['pro_keys_won']}</code> 🔑

<b>📅 Today:</b>
• Free Spins: <code>{data['free_spins_used']}/{FREE_SPINS_PER_DAY}</code> used

Keep spinning to improve your stats!
"""
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="lucky_wheel"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
    
    # Admin command to view wheel stats
    @bot.message_handler(commands=['wheel_stats'])
    def admin_wheel_stats(message):
        """Show overall wheel statistics (admin only)"""
        if message.from_user.id not in ADMIN_IDS:
            return
        
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            # Overall stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_users,
                    SUM(total_spins) as total_spins,
                    SUM(total_won_credits) as total_won,
                    SUM(total_spent_credits) as total_spent,
                    SUM(pro_keys_won) as total_keys,
                    MAX(biggest_win) as biggest_win
                FROM lucky_wheel
            """)
            
            stats = cursor.fetchone()
            
            # Top winners
            cursor.execute("""
                SELECT user_id, total_won_credits, total_spins, biggest_win
                FROM lucky_wheel
                ORDER BY total_won_credits DESC
                LIMIT 5
            """)
            
            top_winners = cursor.fetchall()
            conn.close()
            
            total_users, total_spins, total_won, total_spent, total_keys, biggest = stats
            profit = (total_won or 0) - (total_spent or 0)
            
            text = f"""🎡 <b>Lucky Wheel Statistics</b>

<b>📊 Overall Stats:</b>
• Active Users: {total_users or 0}
• Total Spins: {total_spins or 0}
• Total Won: {total_won or 0} credits
• Total Spent: {total_spent or 0} credits
• House Profit: {-profit:+d} credits
• Pro Keys Won: {total_keys or 0}
• Biggest Win: {biggest or 0} credits

<b>🏆 Top 5 Winners:</b>
"""
            
            for idx, (uid, won, spins, big) in enumerate(top_winners, 1):
                text += f"{idx}. User {uid}: {won} credits ({spins} spins)\n"
            
            bot.reply_to(message, text, parse_mode="HTML")
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {str(e)}")

    print("✅ Lucky wheel handlers registered")
