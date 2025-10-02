import requests
import telebot
import re

# --- Your Bot Token and NEW API URL ---
BOT_TOKEN = '8294313536:AAEbstNMHutpUDxUwaxvwJleW4wAxiLAoio'
# IMPORTANT: Replace this with your actual Render API URL If You Do Not Have Make I will Explain In Vedeo 
API_BASE_URL = "https://your-service-name.onrender.com/check" 
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "<b>Welcome! I am a Stripe Auth Bot.\n\nUse the command <code>/st CC|MM|YY|CVV</code> to check a card. Bot By @diwazz </b>", parse_mode='HTML')

@bot.message_handler(commands=['st'])
def handle_st_command(message):
    try:
        command_text = message.text.split(' ', 1)[1]
    except IndexError:
        bot.reply_to(message, "<b>Please provide card details.\nFormat:</b> <code>/st CC|MM|YY|CVV</code>", parse_mode='HTML')
        return

    match = re.match(r'(\d{16})\|(\d{2})\|(\d{2,4})\|(\d{3,4})', command_text)
    if not match:
        bot.reply_to(message, "<b>Invalid format.\nPlease use:</b> <code>CC|MM|YY|CVV</code>", parse_mode='HTML')
        return

    full_cc_string = match.group(0)
    sent_message = bot.reply_to(message, "<i>Calling API, please wait...</i>", parse_mode='HTML')

    try:
        #@diwazz
        # We pass the card details as a URL parameter
        api_params = {'card': full_cc_string}
        api_response = requests.get(API_BASE_URL, params=api_params, timeout=45) # Increased timeout api dead
        api_response.raise_for_status()
        result = api_response.json()

        status = result.get('status', 'Declined')
        response_message = result.get('response', 'No response from API.')
        decline_type = result.get('decline_type', 'process_error')
        bin_info = result.get('bin_info', {})
        
        brand = bin_info.get('brand', 'Unknown')
        card_type = bin_info.get('type', 'Unknown')
        country = bin_info.get('country', 'Unknown')
        country_flag = bin_info.get('country_flag', '')
        bank = bin_info.get('bank', 'Unknown')

        if status == "Approved":
            final_message = f"""<b>𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅</b>

<b>𝗖𝗮𝗿𝗱:</b> <code>{full_cc_string}</code>
<b>𝐆𝐚𝐭𝐞𝐰𝐚𝐲:</b> Stripe Auth
<b>𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞:</b> {response_message}

<b>𝗜𝗻𝗳𝗼:</b> {brand} - {card_type}
<b>𝐈𝐬𝐬𝐮𝐞𝐫:</b> {bank}
<b>𝐂𝐨𝐮𝐧𝐭𝐫𝐲:</b> {country} {country_flag}"""
        else:
            if decline_type == "process_error":
                display_response = "Declined (Unable To Authenticate)"
            else:
                display_response = response_message

            final_message = f"""<b>𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌</b>

<b>𝗖𝗮𝗿𝗱:</b> <code>{full_cc_string}</code>
<b>𝐆𝐚𝐭𝐞𝐰𝐚𝐲:</b> Stripe Auth
<b>𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞:</b> {display_response}

<b>𝗜𝗻𝗳𝗼:</b> {brand} - {card_type}
<b>𝐈𝐬𝐬𝐮𝐞𝐫:</b> {bank}
<b>𝐂𝐨𝐮𝐧𝐭𝐫𝐲:</b> {country} {country_flag}"""

    except requests.exceptions.RequestException as e:
        final_message = f"<b>Error:</b> Could not connect to the API. <code>{e}</code>"
    except Exception as e:
        final_message = f"<b>An unexpected error occurred:</b> <code>{e}</code>"

    bot.edit_message_text(final_message, chat_id=message.chat.id, message_id=sent_message.message_id, parse_mode='HTML')

print(" Telegram Bot is running...With @diwazz Code ✅")
bot.polling()
