# tools_handler.py

from telebot import types
import random
import datetime
import re
import requests
import time

# TSHOP ---> MAXOUT BOT
# =============================
# ===== LUHN ALGORITHM =======
# =============================

def luhn_checksum(card_number: str) -> bool:
    digits = [int(d) for d in card_number]
    checksum = 0
    parity = len(digits) % 2

    for i, digit in enumerate(digits):
        if i % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit

    return checksum % 10 == 0


def generate_luhn(bin_prefix: str) -> str:
    number = bin_prefix
    while len(number) < 15:
        number += str(random.randint(0, 9))

    for check_digit in range(10):
        if luhn_checksum(number + str(check_digit)):
            return number + str(check_digit)

    return number + "0"


#----NEW-OP-STUFF----#

def update_live_proxy_progress(
    bot,
    chat_id,
    message_id,
    target,
    checked,
    live,
    status="RUNNING"
):
    percent = min(int((checked / target) * 100), 100)
    blocks = int(percent / 10)
    bar = "█" * blocks + "░" * (10 - blocks)

    ui = f"""
<blockquote>
<b>LIVE PROXY FETCHER TERMINAL</b>

────────────────────────
🌐 <b>Status</b> : {status}
────────────────────────

<b>Target</b>   : {target}
<b>Checked</b>  : {checked}
<b>Live</b>     : {live}

<b>Progress</b> : [{bar}] {percent}%

⏳ Updating every 10 seconds
</blockquote>
"""

    try:
        bot.edit_message_text(
            ui,
            chat_id,
            message_id,
            parse_mode="HTML"
        )
    except Exception:
        pass


# HELPER #

def finish_live_proxy_job(
    bot,
    user_states,
    user_id,
    chat_id,
    message_id,
    target,
    checked,
    live
):
    final_ui = f"""
<blockquote>
<b>LIVE PROXY FETCHER TERMINAL</b>

────────────────────────
🌐 <b>Status</b> : COMPLETED
────────────────────────

<b>Target</b>   : {target}
<b>Checked</b>  : {checked}
<b>Live</b>     : {live}

<b>Progress</b> : [██████████] 100%

✅ <b>Job finished successfully</b>
</blockquote>
"""

    try:
        bot.edit_message_text(
            final_ui,
            chat_id,
            message_id,
            parse_mode="HTML"
        )
    except Exception:
        pass

    # unlock user
    user_states.pop(user_id, None)

    # send file
    with open("working_proxies.txt", "rb") as f:
        bot.send_document(
            chat_id,
            f,
            caption="📁 <b>working_proxies.txt</b>",
            parse_mode="HTML"
        )

# =============================
# ===== TOOLS HANDLERS =======
# =============================

def register_tools_handlers(bot, user_states):

    # ===== TOOLS MENU =====
    @bot.callback_query_handler(func=lambda call: call.data == "tools_menu")
    def tools_menu(call):
        bot.answer_callback_query(call.id)

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("💳 CC Generator", callback_data="tool_cc_gen"),
            types.InlineKeyboardButton("🧮 BIN Lookup", callback_data="tool_bin_lookup"),
            types.InlineKeyboardButton("🧾 CC Cleaner", callback_data="tool_cc_cleaner"),
            types.InlineKeyboardButton("🌐 Proxy Checker", callback_data="tool_proxy_checker"),
#            types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"),
            types.InlineKeyboardButton("🪪 Fake Address Generator", callback_data="tool_fake_address"),
            types.InlineKeyboardButton("📸 Website SS", callback_data="tool_screenshot"),
            types.InlineKeyboardButton("⚡ Live Proxy Fetcher", callback_data="tool_live_proxy_fetcher")
        )
               
        markup.add(
            types.InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")
        )

        bot.edit_message_text(
            "🧰 <b>TOOLS TERMINAL</b>\n\nSelect a tool:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )


 
# ===== BIN LOOKUP ENTRY =====
    @bot.callback_query_handler(func=lambda call: call.data == "tool_bin_lookup")
    def bin_lookup_entry(call):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        user_states[user_id] = "tool_bin_lookup_wait_bin"

        bot.send_message(
            user_id,
            "🧮 <b>BIN LOOKUP</b>\n\n"
            "Send a <b>6-digit BIN</b>:\n"
            "<code>Example: 424242</code>",
            parse_mode="HTML"
        )

    # ===== BIN LOOKUP PROCESS =====
    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "tool_bin_lookup_wait_bin")
    def bin_lookup_run(message):
        user_id = message.from_user.id
        bin_code = message.text.strip()

        del user_states[user_id]

        if not (bin_code.isdigit() and len(bin_code) == 6):
            bot.send_message(user_id, "⚠️ Invalid BIN. Must be exactly 6 digits.")
            return

        bot.send_chat_action(user_id, "typing")

        data = None
        error = None

        # ---- Free BIN lookup sources (fallback chain) ----
        sources = [
            f"https://lookup.binlist.net/{bin_code}",
            f"https://bins.su/api/{bin_code}"
        ]

        for url in sources:
            try:
                r = requests.get(url, timeout=8)
                if r.status_code == 200:
                    data = r.json()
                    break
            except Exception as e:
                error = e

        if not data:
            bot.send_message(user_id, "❌ BIN lookup failed. Try again later.")
            return

        # ---- Normalize data from different sources ----
        scheme = data.get("scheme", "Unknown").upper()
        brand = data.get("brand", "Unknown")
        card_type = data.get("type", "Unknown")
        bank = (data.get("bank") or {}).get("name", "Unknown")

        country_data = data.get("country") or {}
        country = country_data.get("name", "Unknown")
        emoji = country_data.get("emoji", "")

        html_response = f"""
<blockquote>
<b>BIN LOOKUP TERMINAL</b>

──────────────────────
🧮  <b>BIN INFORMATION</b>
──────────────────────

<b>BIN:</b> <code>{bin_code}</code>
<b>Scheme:</b> {scheme}
<b>Type:</b> {card_type}
<b>Brand:</b> {brand}

<b>Bank:</b> {bank}
<b>Country:</b> {country} {emoji}

──────────────────────
<b>Status:</b> Lookup Successful
</blockquote>
"""

        bot.send_message(
            user_id,
            html_response,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
        # =============================
    # ===== CC GENERATOR ==========
    # =============================

    @bot.callback_query_handler(func=lambda call: call.data == "tool_cc_gen")
    def cc_gen_entry(call):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        user_states[user_id] = "tool_cc_gen_wait_bin"

        bot.send_message(
            user_id,
            "💳 <b>CC GENERATOR</b>\n\n"
            "Send a BIN (only first <b>6 digits</b> are required).\n\n"
            "<code>Examples:</code>\n"
            "<code>446226xxx|06|28|xxx</code>\n"
            "<code>446226</code>",
            parse_mode="HTML"
        )

    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "tool_cc_gen_wait_bin")
    def cc_gen_get_bin(message):
        user_id = message.from_user.id
        raw_input = message.text.strip()

        # ---- extract first 6 digits anywhere ----
        match = re.search(r'(\d{6})', raw_input)
        if not match:
            bot.send_message(
                user_id,
                "⚠️ Invalid BIN.\n"
                "I need at least the first <b>6 digits</b>.",
                parse_mode="HTML"
            )
            return

        bin_code = match.group(1)

        user_states[user_id] = f"tool_cc_gen_wait_amount::{bin_code}"

        bot.send_message(
            user_id,
            "🔢 How many cards to generate?\n"
            "<code>1 – 10000</code>",
            parse_mode="HTML"
        )

    @bot.message_handler(func=lambda m: str(user_states.get(m.from_user.id, "")).startswith("tool_cc_gen_wait_amount::"))
    def cc_gen_run(message):
        user_id = message.from_user.id
        amount_text = message.text.strip()

        state = user_states.get(user_id)
        bin_code = state.split("::", 1)[1]
        del user_states[user_id]

        if not amount_text.isdigit():
            bot.send_message(user_id, "⚠️ Amount must be a number.")
            return

        amount = int(amount_text)
        if amount < 1 or amount > 10000:
            bot.send_message(
                user_id,
                "⚠️ Amount must be between <b>1</b> and <b>10000</b>.",
                parse_mode="HTML"
            )
            return

        year_now = datetime.datetime.now().year % 100
        results = []

        for _ in range(amount):
            cc = generate_luhn(bin_code)
            mm = f"{random.randint(1,12):02}"
            yy = str(random.randint(year_now + 1, year_now + 6))
            cvv = str(random.randint(100,999))
            results.append(f"{cc}|{mm}|{yy}|{cvv}")

        output_text = "\n".join(results)

        # ===== SEND FILE IF LARGE =====
        if amount > 30:
            bot.send_document(
                user_id,
                output_text.encode(),
                visible_file_name=f"generated_ccs_{bin_code}.txt",
                caption=f"💳 CC Generator\nBIN: {bin_code}\nTotal: {amount}"
            )
            return

        # ===== TERMINAL VIEW =====
        html = f"""
<blockquote>
<b>CC GENERATOR TERMINAL</b>

──────────────────────
💳 <b>Generated Cards</b>
──────────────────────

<code>{output_text}</code>

──────────────────────
<b>BIN:</b> {bin_code}
<b>Count:</b> {amount}
</blockquote>
"""
        bot.send_message(user_id, html, parse_mode="HTML")
        



# ===== PROXY CHECKER ENTRY =====
    @bot.callback_query_handler(func=lambda call: call.data == "tool_proxy_checker")
    def proxy_checker_entry(call):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        user_states[user_id] = "tool_proxy_checker_wait_list"

        bot.send_message(
            user_id,
            "🌐 <b>PROXY CHECKER</b>\n\n"
            "Paste proxies below (one per line):\n"
            "<code>ip:port</code> or <code>ip:port:user:pass</code>\n\n"
            "<i>Max 20 proxies per check</i>",
            parse_mode="HTML"
        )

    # ===== PROXY CHECKER PROCESS =====
    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "tool_proxy_checker_wait_list")
    def proxy_checker_run(message):
        user_id = message.from_user.id
        text = message.text.strip()

        del user_states[user_id]

        proxies_raw = [line.strip() for line in text.splitlines() if line.strip()]
        proxies_raw = proxies_raw[:20]  # hard limit for safety

        if not proxies_raw:
            bot.send_message(user_id, "❌ No proxies provided.")
            return

        bot.send_chat_action(user_id, "typing")

        live, dead = [], []

        test_url = "https://httpbin.org/ip"

        for proxy in proxies_raw:
            start = time.time()

            try:
                parts = proxy.split(":")
                if len(parts) == 2:
                    ip, port = parts
                    proxy_auth = f"http://{ip}:{port}"
                elif len(parts) == 4:
                    ip, port, user, pwd = parts
                    proxy_auth = f"http://{user}:{pwd}@{ip}:{port}"
                else:
                    dead.append(f"{proxy}   INVALID FORMAT")
                    continue

                proxies_cfg = {
                    "http": proxy_auth,
                    "https": proxy_auth
                }

                r = requests.get(test_url, proxies=proxies_cfg, timeout=6)
                latency = int((time.time() - start) * 1000)

                if r.status_code == 200:
                    live.append(f"{proxy}   LIVE ({latency} ms)")
                else:
                    dead.append(f"{proxy}   DEAD")

            except Exception:
                dead.append(f"{proxy}   DEAD")

        # ===== BUILD TERMINAL UI =====
        live_text = "\n".join(live) if live else "None"
        dead_text = "\n".join(dead) if dead else "None"

        html_response = f"""
<blockquote>
<b>PROXY CHECKER TERMINAL</b>

──────────────────────
🌐  <b>RESULTS</b>
──────────────────────

<b>LIVE:</b>
<code>{live_text}</code>

<b>DEAD:</b>
<code>{dead_text}</code>

──────────────────────
<b>Total:</b> {len(proxies_raw)}
<b>Live:</b> {len(live)}
<b>Dead:</b> {len(dead)}
</blockquote>
"""

        bot.send_message(
            user_id,
            html_response,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
        
        
        

    @bot.callback_query_handler(func=lambda call: call.data == "tool_cc_cleaner")
    def cc_cleaner_entry(call):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)
        user_states[user_id] = "tool_cc_cleaner_wait_input"
        bot.send_message(
            user_id,
            "🧾 <b>CC CLEANER</b>\n\n"
            "Paste text / logs or upload a <b>.txt file</b>.\n"
            "I will auto-detect and clean CCs.",
            parse_mode="HTML"
        )

    @bot.message_handler(
        func=lambda m: user_states.get(m.from_user.id) == "tool_cc_cleaner_wait_input",
        content_types=["text", "document"]
    )
    def cc_cleaner_run(message):
        user_id = message.from_user.id
        del user_states[user_id]

        if message.content_type == "document":
            if not message.document.file_name.lower().endswith(".txt"):
                bot.send_message(user_id, "⚠️ Only .txt files are supported.")
                return
            file_info = bot.get_file(message.document.file_id)
            file_bytes = bot.download_file(file_info.file_path)
            text = file_bytes.decode(errors="ignore")
        else:
            text = message.text or ""

        pattern = re.compile(
            r'(\d{13,16})[^\d]{0,3}'
            r'(0[1-9]|1[0-2])[^\d]{0,3}'
            r'(\d{2,4})[^\d]{0,3}'
            r'(\d{3,4})'
        )

        cleaned = set()
        for cc, mm, yy, cvv in pattern.findall(text):
            if len(yy) == 4:
                yy = yy[2:]
            cleaned.add(f"{cc}|{mm}|{yy}|{cvv}")

        if not cleaned:
            bot.send_message(user_id, "❌ No valid CCs found.")
            return

        cleaned_list = sorted(cleaned)
        result_text = "\n".join(cleaned_list)

        if message.content_type == "document":
            bot.send_document(
               user_id,
                result_text.encode(),
                visible_file_name="cleaned_ccs.txt",
                caption=f"🧾 CC Cleaner\nTotal Found: {len(cleaned_list)}"
            )
            return

        html = f"""
<blockquote>
<b>CC CLEANER TERMINAL</b>

──────────────────────
🧾 <b>Cleaned Cards</b>
──────────────────────

<code>{result_text[:3500]}</code>

──────────────────────
<b>Total Found:</b> {len(cleaned_list)}
</blockquote>
"""
        bot.send_message(user_id, html, parse_mode="HTML")
        
        
        

    @bot.callback_query_handler(func=lambda c: c.data == "tool_fake_address")
    def tool_fake_address(call):
        user_states[call.from_user.id] = "awaiting_fake_country"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Tools", callback_data="tools_menu"))
        bot.edit_message_text(
            "🪪 <b>Fake Address Generator</b>\n\n"
            "Send a <b>2-letter country code</b>:\n\n"
            "• IN = India\n"
            "• MY = Malaysia\n"
            "• AU = Australia\n"
            "• US = United States\n\n"
            "<i>Example:</i> <code>IN</code>",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )   

    


    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "awaiting_fake_country")
    def handle_fake_address(message):
        from fake_address import fetch_fake_address

        user_states.pop(message.from_user.id, None)
        code = message.text.strip().upper()

        if len(code) != 2:
             bot.reply_to(message, "❌ Invalid country code. Use 2 letters (e.g. IN, MY).")
             return
 
        try:
            profile = fetch_fake_address(code)
 
            text = (
                    "🪪 <b>Fake Profile Generated</b>\n\n"
                    f"👤 <b>Name:</b> {profile['name']}\n"
                    f"⚧ <b>Gender:</b> {profile['gender']}\n"
                    f"🏠 <b>Address:</b>\n"
                    f"{profile['street']}\n"
                    f"{profile['city']}, {profile['state']}\n"
                    f"{profile['country']} - {profile['postcode']}\n\n"
                    f"📧 <b>Email:</b> {profile['email']}\n"
                    f"📞 <b>Phone:</b> {profile['phone']}\n\n"
                    f"👤 <b>Username:</b> <code>{profile['username']}</code>\n"
                    f"🔑 <b>Password:</b> <code>{profile['password']}</code>\n"
                    f"🌍 <b>Nationality:</b> {profile['nat']}"
            )

            bot.send_message(message.chat.id, text, parse_mode="HTML")

        except Exception as e:
            bot.reply_to(message, f"❌ Failed to generate profile.\n{e}")


    @bot.callback_query_handler(func=lambda call: call.data == "tool_screenshot")
    def tool_screenshot(call):
        user_states[call.from_user.id] = "awaiting_screenshot_url"
 
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back to Tools", callback_data="tools_menu"))

        bot.edit_message_text(
            "📸 <b>Website Screenshot Tool</b>\n\n"
            "Send a website URL to capture.\n\n"
            "<b>Examples:</b>\n"
            "• https://google.com\n"
            "• https://github.com\n\n"
            "⚠️ <i>Only public websites are supported</i>",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )


    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "awaiting_screenshot_url")
    def handle_screenshot(message):
        user_states.pop(message.from_user.id, None)

        url = message.text.strip()

        if not (url.startswith("http://") or url.startswith("https://")):
            bot.reply_to(message, "❌ Invalid URL.\nSend a full URL starting with http:// or https://")
            return

        screenshot_url = f"https://image.thum.io/get/width/1280/crop/700/noanimate/{url}"

        try:
            bot.send_photo(
                message.chat.id,
                screenshot_url,
                caption=f"📸 <b>Screenshot</b>\n<code>{url}</code>",
                parse_mode="HTML"
            )
        except Exception as e:
            bot.reply_to(message, f"❌ Failed to capture screenshot.\n{e}")


    
    @bot.callback_query_handler(func=lambda call: call.data == "tool_live_proxy_fetcher")
    def live_proxy_fetcher_entry(call):
        bot.answer_callback_query(call.id)
        user_id = call.from_user.id

        user_states[user_id] = "live_proxy_wait_amount"

        ui = """
<blockquote>
<b>LIVE PROXY FETCHER TERMINAL</b>

────────────────────────
🌐 <b>MODE</b> : Auto Fetch + Live Check
────────────────────────

<b>Default Check</b> : 5000 proxies

<b>Estimated Time</b>
• 1000   → 40–50 sec
• 5000   → 120–150 sec
• 10000  → 210–250 sec

<b>Estimated Live Proxies</b>
• 1000   → 10–15
• 5000   → 40–60
• 10000  → 120–150

────────────────────────
⚠️ <b>NOTE</b>
Fast checking may cause false checks.
Please manually verify <code>working_proxies.txt</code>
on <b>proxyscrape.com</b> for best results.

────────────────────────
✍️ <b>Send proxy amount</b>
<code>1000</code> | <code>5000</code> | <code>10000</code> | <code>20000</code>
</blockquote>
"""

        bot.edit_message_text(
            ui,
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML"
        )


    

    @bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "live_proxy_wait_amount")
    def live_proxy_fetcher_start(message):
        user_id = message.from_user.id
        chat_id = message.chat.id

        try:
            amount = int(message.text.strip())
            if amount not in (1000, 5000, 10000, 20000):
                raise ValueError
        except ValueError:
            bot.send_message(
                chat_id,
                "❌ Invalid amount.\nChoose one of: 1000, 5000, 10000, 20000"
            )
            return

    # lock state
        user_states[user_id] = "live_proxy_running"

        progress_ui = f"""
<blockquote>
<b>LIVE PROXY FETCHER TERMINAL</b>

────────────────────────
🌐 <b>Status</b> : INITIALIZING
────────────────────────

<b>Target</b>   : {amount}
<b>Checked</b>  : 0
<b>Live</b>     : 0

<b>Progress</b> : [░░░░░░░░░░] 0%

⏳ Updating every 10 seconds
</blockquote>
"""

        sent = bot.send_message(
            chat_id,
            progress_ui,
            parse_mode="HTML"
        )

    # Hand off to background job (to be implemented next)
        from live_proxy_job import start_live_proxy_job

        start_live_proxy_job(
          bot=bot,
          user_states=user_states,
          user_id=user_id,
          chat_id=chat_id,
          message_id=sent.message_id,
          target_amount=amount
        )
