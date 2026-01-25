# hitter_3d.py — FIXED (Telebot-safe, no closed loops)

from telebot import types
import aiohttp
import asyncio
import threading
import time
import re
import json
import os
import base64
from urllib.parse import unquote

# =======================
# ASYNC LOOP (SAFE)
# =======================

_thread_local = threading.local()

def run_async(coro):
    loop = getattr(_thread_local, "loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        _thread_local.loop = loop
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

# =======================
# CONFIG
# =======================

PROXY_FILE = "proxies.json"

HEADERS = {
    "accept": "application/json",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://checkout.stripe.com",
    "referer": "https://checkout.stripe.com/",
    "user-agent": "Mozilla/5.0"
}

_session = None

# =======================
# SESSION
# =======================

async def get_session():
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=100, ssl=False),
            timeout=aiohttp.ClientTimeout(total=25)
        )
    return _session

# =======================
# PROXY MANAGEMENT
# =======================

def load_proxies():
    if os.path.exists(PROXY_FILE):
        try:
            with open(PROXY_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_proxies(data):
    with open(PROXY_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user_proxies(user_id):
    return load_proxies().get(str(user_id), [])

def add_user_proxy(user_id, proxy):
    data = load_proxies()
    key = str(user_id)
    data.setdefault(key, [])
    if proxy not in data[key]:
        data[key].append(proxy)
    save_proxies(data)

def remove_user_proxy(user_id, proxy=None):
    data = load_proxies()
    key = str(user_id)
    if key not in data:
        return False
    if proxy is None or proxy == "all":
        del data[key]
    else:
        data[key] = [p for p in data[key] if p != proxy]
        if not data[key]:
            del data[key]
    save_proxies(data)
    return True

def get_user_proxy(user_id):
    proxies = get_user_proxies(user_id)
    if not proxies:
        return None
    import random
    return random.choice(proxies)

# =======================
# HELPERS
# =======================

def extract_checkout_url(text):
    m = re.search(r'https?://(checkout|buy)\.stripe\.com/[^\s]+', text)
    return m.group(0) if m else None

def parse_cards(text):
    cards = []
    for line in text.splitlines():
        parts = re.split(r"[|:/ ]+", line)
        if len(parts) >= 4:
            cc, mm, yy, cvv = parts[:4]
            cards.append({
                "cc": cc,
                "month": mm.zfill(2),
                "year": yy[-2:],
                "cvv": cvv
            })
    return cards

# =======================
# CORE ASYNC FUNCTIONS
# (UNCHANGED LOGIC)
# =======================

# 🔹 get_checkout_info
# 🔹 charge_card
# 🔹 check_proxy_alive
# 🔹 check_proxies_batch
# 🔹 get_proxy_info
# ⬆️ KEEP YOUR EXISTING IMPLEMENTATIONS
# ⬆️ (They are already async-safe now)

# =======================
# BOT HANDLERS
# =======================

def register_3d_hitter_handlers(bot, user_states):

    @bot.message_handler(commands=["addproxy"])
    def addproxy(message):
        user_id = message.from_user.id
        args = message.text.split(maxsplit=1)

        if len(args) < 2:
            bot.reply_to(
                message,
                "🧩 <b>PROXY CONSOLE</b>\n\n"
                "➕ <code>/addproxy host:port:user:pass</code>\n"
                "🗑️ <code>/removeproxy proxy</code>\n"
                "📡 <code>/proxy check</code>",
                parse_mode="HTML"
            )
            return

        proxies = [p.strip() for p in args[1].splitlines() if p.strip()]
        msg = bot.reply_to(message, "⏳ <b>SCANNING PROXIES…</b>", parse_mode="HTML")

        results = run_async(check_proxies_batch(proxies, max_threads=10))

        alive = 0
        for r in results:
            if r["status"] == "alive":
                add_user_proxy(user_id, r["proxy"])
                alive += 1

        bot.edit_message_text(
            f"🟢 <b>PROXY SCAN COMPLETE</b>\n\n"
            f"Alive: <b>{alive}</b>\n"
            f"Dead: <b>{len(results) - alive}</b>",
            msg.chat.id,
            msg.message_id,
            parse_mode="HTML"
        )

    @bot.message_handler(commands=["3d", "co3d"])
    def co3d(message):
        start = time.perf_counter()
        user_id = message.from_user.id

        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(
                message,
                "🧠 <b>3D STRIPE ENGINE</b>\n\n"
                "<code>/3d checkout_url cc|mm|yy|cvv</code>",
                parse_mode="HTML"
            )
            return

        url = extract_checkout_url(args[1])
        cards = parse_cards(" ".join(args[2:]))

        proxy = get_user_proxy(user_id)
        if not proxy:
            bot.reply_to(message, "❌ <b>No proxy set</b>", parse_mode="HTML")
            return

        hud = bot.reply_to(
            message,
            "╔══════════════════════╗\n"
            "║  ⚙ STRIPE 3D CORE   ║\n"
            "╚══════════════════════╝\n\n"
            "🔌 Initializing checkout…",
            parse_mode="HTML"
        )

        checkout = run_async(get_checkout_info(url))
        if checkout.get("error"):
            bot.edit_message_text(
                f"❌ <b>ERROR</b>\n\n<code>{checkout['error']}</code>",
                hud.chat.id,
                hud.message_id,
                parse_mode="HTML"
            )
            return

        results = []
        for card in cards:
            r = run_async(charge_card(card, checkout, proxy))
            results.append(r)
            if r["status"] == "CHARGED":
                break

        charged = next((r for r in results if r["status"] == "CHARGED"), None)
        elapsed = round(time.perf_counter() - start, 2)

        if charged:
            text = (
                "🟢 <b>CHARGE SUCCESS</b>\n\n"
                f"💳 <code>{charged['card']}</code>\n"
                f"⏱ {charged['time']}s\n"
                f"⚡ Total: {elapsed}s"
            )
        else:
            text = (
                "🔴 <b>NO SUCCESSFUL CHARGE</b>\n\n"
                f"Tried: <b>{len(results)}</b>\n"
                f"⏱ {elapsed}s"
            )

        bot.edit_message_text(
            text,
            hud.chat.id,
            hud.message_id,
            parse_mode="HTML"
        )

