"""
JSON-based database backend.
Replaces the old MongoDB implementation with local JSON file storage.
All function signatures remain the same for backward compatibility.
"""
import json
import os
import threading
import uuid
from datetime import datetime, UTC

# Directory to store all JSON data files
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Thread lock for safe file writes
_lock = threading.Lock()


def _json_path(name):
    return os.path.join(DATA_DIR, f"{name}.json")


def _load(name, default=None):
    path = _json_path(name)
    if not os.path.exists(path):
        return default if default is not None else []
    with open(path, "r") as f:
        return json.load(f)


def _save(name, data):
    path = _json_path(name)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp, path)


def _load_safe(name, default=None):
    with _lock:
        return _load(name, default)


def _save_safe(name, data):
    with _lock:
        _save(name, data)


# ============================================================
# INIT
# ============================================================
def init_db():
    """Initialize JSON data files if they don't exist."""
    defaults = {
        "users": [],
        "admins": [],
        "section_admins": [],
        "scraper_admins": [],
        "user_scraper_access": [],
        "pro_keys": [],
        "giveaway_winners": [],
        "orders": [],
        "support_sessions": [],
        "support_messages": [],
        "support_tickets": [],
        "support_analytics": [],
        "products": {"bins": [], "custom_ccs": [], "gift_cards": [], "rdp": [], "methods": [], "other": []},
        "config": {},
        "support_settings": {},
        "section_status": {},
        "gift_card_status": {},
        "force_links_cache": {},
        "proxies": [],
        "bgmi_accounts": [],
        "accounts_db": [],
        "referrals_db": {},
        "balance_transactions": [],
    }
    for name, default in defaults.items():
        path = _json_path(name)
        if not os.path.exists(path):
            _save(name, default)
    print("✓ JSON database initialized successfully!")


# ============================================================
# HELPER – find / update in a list-of-dicts
# ============================================================
def _find_one(collection_name, match_fn):
    data = _load_safe(collection_name, [])
    for item in data:
        if match_fn(item):
            return item
    return None


def _find_many(collection_name, match_fn=None):
    data = _load_safe(collection_name, [])
    if match_fn is None:
        return data
    return [item for item in data if match_fn(item)]


def _insert_one(collection_name, doc):
    with _lock:
        data = _load(collection_name, [])
        data.append(doc)
        _save(collection_name, data)


def _update_one(collection_name, match_fn, update_dict, upsert=False):
    with _lock:
        data = _load(collection_name, [])
        found = False
        for item in data:
            if match_fn(item):
                item.update(update_dict)
                found = True
                break
        if not found and upsert:
            data.append(update_dict)
        _save(collection_name, data)
        return found


def _delete_one(collection_name, match_fn):
    with _lock:
        data = _load(collection_name, [])
        new_data = [item for item in data if not match_fn(item)]
        removed = len(data) - len(new_data)
        _save(collection_name, new_data)
        return removed > 0


# ============================================================
# USER MANAGEMENT
# ============================================================
def add_user(user_id, username, referrer_code=None):
    try:
        existing = _find_one("users", lambda u: u["user_id"] == user_id)
        if not existing:
            new_referral_code = str(uuid.uuid4())[:8]
            referred_by_id = None
            if referrer_code:
                referrer = _find_one("users", lambda u: u.get("referral_code") == referrer_code)
                if referrer:
                    referred_by_id = referrer["user_id"]
            user_doc = {
                "user_id": user_id,
                "username": username,
                "join_date": datetime.now(UTC).isoformat(),
                "referral_code": new_referral_code,
                "referred_by": referred_by_id,
                "referral_count": 0,
                "balance_usd": 0.0,
                "balance": 0.0,
                "cc_credits": 50,
                "is_pro": False,
                "is_active": True,
            }
            _insert_one("users", user_doc)
            if referred_by_id:
                referrer_user = _find_one("users", lambda u: u["user_id"] == referred_by_id)
                new_count = (referrer_user.get("referral_count", 0) + 1) if referrer_user else 1
                _update_one(
                    "users",
                    lambda u: u["user_id"] == referred_by_id,
                    {"referral_count": new_count},
                )
        else:
            update_data = {"username": username}
            if not existing.get("referral_code"):
                update_data["referral_code"] = str(uuid.uuid4())[:8]
            _update_one("users", lambda u: u["user_id"] == user_id, update_data)
    except Exception as e:
        print(f"Error adding/updating user {user_id}: {e}")


def get_user_balance(user_id):
    try:
        user = _find_one("users", lambda u: u["user_id"] == user_id)
        return user.get("balance_usd", 0.0) if user else 0.0
    except Exception as e:
        print(f"Error getting balance for user {user_id}: {e}")
        return 0.0


def get_user_credits(user_id):
    try:
        user = _find_one("users", lambda u: u["user_id"] == user_id)
        if user:
            return {"credits": user.get("cc_credits", 0), "is_pro": user.get("is_pro", False)}
        return {"credits": 0, "is_pro": False}
    except Exception as e:
        print(f"Error getting credits for user {user_id}: {e}")
        return {"credits": 0, "is_pro": False}


def update_user_credits(user_id, amount_change):
    try:
        user_status = get_user_credits(user_id)
        if user_status["is_pro"]:
            return "unlimited"
        user = _find_one("users", lambda u: u["user_id"] == user_id)
        if user:
            new_credits = user.get("cc_credits", 0) + amount_change
            _update_one("users", lambda u: u["user_id"] == user_id, {"cc_credits": new_credits})
            return new_credits
        return 0
    except Exception as e:
        print(f"Error updating credits for user {user_id}: {e}")
        return 0


def generate_pro_key(admin_id):
    try:
        new_key = f"pro-{uuid.uuid4()}"
        pro_key_doc = {
            "key": new_key,
            "is_used": False,
            "used_by": None,
            "used_at": None,
            "created_by": admin_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
        _insert_one("pro_keys", pro_key_doc)
        return new_key
    except Exception as e:
        print(f"Error generating pro key: {e}")
        return None


def get_all_pro_keys():
    try:
        keys = _find_many("pro_keys")
        return [(k["key"], k["is_used"], k.get("used_by"), k.get("used_at")) for k in keys]
    except Exception as e:
        print(f"Error getting pro keys: {e}")
        return []


def validate_and_use_pro_key(key, user_id):
    try:
        pro_key = _find_one("pro_keys", lambda k: k["key"] == key)
        if not pro_key:
            return "invalid"
        if pro_key["is_used"]:
            return "used"
        _update_one("users", lambda u: u["user_id"] == user_id, {"is_pro": True})
        _update_one(
            "pro_keys",
            lambda k: k["key"] == key,
            {"is_used": True, "used_by": user_id, "used_at": datetime.now(UTC).isoformat()},
        )
        return "success"
    except Exception as e:
        print(f"Error validating pro key: {e}")
        return "error"


def update_user_balance(user_id, amount_change):
    try:
        user = _find_one("users", lambda u: u["user_id"] == user_id)
        if user:
            new_balance = user.get("balance_usd", 0.0) + amount_change
            _update_one("users", lambda u: u["user_id"] == user_id, {"balance_usd": new_balance, "balance": new_balance})
            return new_balance
        return 0.0
    except Exception as e:
        print(f"Error updating balance for user {user_id}: {e}")
        return 0.0


def get_user_details(user_id):
    try:
        user = _find_one("users", lambda u: u["user_id"] == user_id)
        if user:
            return {
                "user_id": user["user_id"],
                "username": user.get("username"),
                "join_date": user.get("join_date"),
                "referral_code": user.get("referral_code"),
                "referral_count": user.get("referral_count", 0),
                "balance": user.get("balance_usd", 0.0),
            }
        return None
    except Exception as e:
        print(f"Error getting user details for {user_id}: {e}")
        return None


# ============================================================
# PRODUCT MANAGEMENT
# ============================================================
def load_products():
    try:
        products = _load_safe("products", None)
        if products:
            return products
        return {"bins": [], "custom_ccs": [], "gift_cards": [], "rdp": [], "methods": [], "other": []}
    except Exception as e:
        print(f"Error loading products: {e}")
        return {"bins": [], "custom_ccs": [], "gift_cards": [], "rdp": [], "methods": [], "other": []}


def save_products(products_data):
    try:
        products_data.pop("_id", None)
        _save_safe("products", products_data)
    except Exception as e:
        print(f"Error saving products: {e}")


# ============================================================
# ADMIN MANAGEMENT
# ============================================================
def add_admin(user_id, added_by):
    try:
        existing = _find_one("admins", lambda a: a["user_id"] == user_id)
        doc = {"user_id": user_id, "added_by": added_by, "added_at": datetime.now(UTC).isoformat()}
        if existing:
            _update_one("admins", lambda a: a["user_id"] == user_id, doc)
        else:
            _insert_one("admins", doc)
    except Exception as e:
        print(f"Error adding admin: {e}")


def remove_admin(user_id):
    try:
        _delete_one("admins", lambda a: a["user_id"] == user_id)
    except Exception as e:
        print(f"Error removing admin: {e}")


def is_admin(user_id):
    try:
        return _find_one("admins", lambda a: a["user_id"] == user_id) is not None
    except Exception as e:
        print(f"Error checking admin status: {e}")
        return False


def add_section_admin(user_id, section, added_by):
    try:
        existing = _find_one("section_admins", lambda a: a["user_id"] == user_id and a["section"] == section)
        doc = {"user_id": user_id, "section": section, "added_by": added_by, "added_at": datetime.now(UTC).isoformat()}
        if existing:
            _update_one("section_admins", lambda a: a["user_id"] == user_id and a["section"] == section, doc)
        else:
            _insert_one("section_admins", doc)
    except Exception as e:
        print(f"Error adding section admin: {e}")


def remove_section_admin(user_id, section):
    try:
        _delete_one("section_admins", lambda a: a["user_id"] == user_id and a["section"] == section)
    except Exception as e:
        print(f"Error removing section admin: {e}")


def is_section_admin(user_id, section):
    try:
        return _find_one("section_admins", lambda a: a["user_id"] == user_id and a["section"] == section) is not None
    except Exception as e:
        print(f"Error checking section admin status: {e}")
        return False


def add_scraper_admin(user_id, added_by):
    try:
        existing = _find_one("scraper_admins", lambda a: a["user_id"] == user_id)
        doc = {"user_id": user_id, "added_by": added_by, "added_at": datetime.now(UTC).isoformat()}
        if existing:
            _update_one("scraper_admins", lambda a: a["user_id"] == user_id, doc)
        else:
            _insert_one("scraper_admins", doc)
    except Exception as e:
        print(f"Error adding scraper admin: {e}")


def remove_scraper_admin(user_id):
    try:
        _delete_one("scraper_admins", lambda a: a["user_id"] == user_id)
    except Exception as e:
        print(f"Error removing scraper admin: {e}")


def is_scraper_admin(user_id):
    try:
        return _find_one("scraper_admins", lambda a: a["user_id"] == user_id) is not None
    except Exception as e:
        print(f"Error checking scraper admin status: {e}")
        return False


# ============================================================
# ORDER MANAGEMENT
# ============================================================
def create_order(order_id, user_id, item_name, price_usd, payment_method, payment_status, item_details=None):
    try:
        order_doc = {
            "order_id": order_id,
            "user_id": user_id,
            "item_name": item_name,
            "price_usd": price_usd,
            "payment_method": payment_method,
            "payment_status": payment_status,
            "creation_date": datetime.now(UTC).isoformat(),
            "item_details": item_details,
        }
        _insert_one("orders", order_doc)
    except Exception as e:
        print(f"Error creating order: {e}")


def get_user_orders(user_id):
    try:
        orders = _find_many("orders", lambda o: o["user_id"] == user_id)
        return sorted(orders, key=lambda o: o.get("creation_date", ""), reverse=True)
    except Exception as e:
        print(f"Error getting user orders: {e}")
        return []


def update_order_status(order_id, new_status):
    try:
        _update_one("orders", lambda o: o["order_id"] == order_id, {"payment_status": new_status})
    except Exception as e:
        print(f"Error updating order status: {e}")


# ============================================================
# SUPPORT SESSION MANAGEMENT
# ============================================================
def create_support_session(user_id, category="general", priority=1, subject=None):
    try:
        session_id = str(uuid.uuid4())
        session_doc = {
            "session_id": session_id,
            "user_id": user_id,
            "admin_id": None,
            "status": "open",
            "category": category,
            "priority": priority,
            "subject": subject,
            "first_response_time": None,
            "resolution_time": None,
            "user_rating": None,
            "admin_notes": None,
            "started_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "ended_at": None,
            "last_message_at": datetime.now(UTC).isoformat(),
        }
        _insert_one("support_sessions", session_doc)
        return session_id
    except Exception as e:
        print(f"Error creating support session: {e}")
        return None


def get_support_session(session_id):
    try:
        return _find_one("support_sessions", lambda s: s.get("session_id") == str(session_id))
    except Exception as e:
        print(f"Error getting support session: {e}")
        return None


def update_support_session(session_id, update_data):
    try:
        update_data["updated_at"] = datetime.now(UTC).isoformat()
        _update_one("support_sessions", lambda s: s.get("session_id") == str(session_id), update_data)
    except Exception as e:
        print(f"Error updating support session: {e}")


def add_support_message(session_id, sender_id, sender_type, message_text, message_type="text", file_id=None):
    try:
        message_doc = {
            "session_id": str(session_id),
            "sender_id": sender_id,
            "sender_type": sender_type,
            "message_text": message_text,
            "message_type": message_type,
            "file_id": file_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "is_read": False,
        }
        _insert_one("support_messages", message_doc)
        _update_one(
            "support_sessions",
            lambda s: s.get("session_id") == str(session_id),
            {"last_message_at": datetime.now(UTC).isoformat()},
        )
    except Exception as e:
        print(f"Error adding support message: {e}")


def get_support_messages(session_id):
    try:
        messages = _find_many("support_messages", lambda m: m.get("session_id") == str(session_id))
        return sorted(messages, key=lambda m: m.get("timestamp", ""))
    except Exception as e:
        print(f"Error getting support messages: {e}")
        return []


# ============================================================
# SCRAPER ACCESS
# ============================================================
def grant_scraper_access(user_id, expiry_date, price_paid=0.0):
    try:
        doc = {
            "user_id": user_id,
            "expiry_date": expiry_date,
            "purchased_at": datetime.now(UTC).isoformat(),
            "price_paid": price_paid,
        }
        existing = _find_one("user_scraper_access", lambda a: a["user_id"] == user_id)
        if existing:
            _update_one("user_scraper_access", lambda a: a["user_id"] == user_id, doc)
        else:
            _insert_one("user_scraper_access", doc)
    except Exception as e:
        print(f"Error granting scraper access: {e}")


def check_scraper_access(user_id):
    try:
        access = _find_one("user_scraper_access", lambda a: a["user_id"] == user_id)
        if not access:
            return False
        if access.get("expiry_date"):
            expiry = datetime.fromisoformat(access["expiry_date"])
            return datetime.now(UTC) < expiry
        return True
    except Exception as e:
        print(f"Error checking scraper access: {e}")
        return False


# ============================================================
# GIVEAWAY WINNERS
# ============================================================
def add_giveaway_winner(user_id, selected_by):
    try:
        winner_doc = {
            "user_id": user_id,
            "selected_by": selected_by,
            "selected_at": datetime.now(UTC).isoformat(),
        }
        _insert_one("giveaway_winners", winner_doc)
    except Exception as e:
        print(f"Error adding giveaway winner: {e}")


# ============================================================
# USER QUERIES
# ============================================================
def get_all_users():
    try:
        return _find_many("users")
    except Exception as e:
        print(f"Error getting all users: {e}")
        return []


def get_all_active_users():
    try:
        users = _find_many("users", lambda u: u.get("is_active", True))
        return [u["user_id"] for u in users]
    except Exception as e:
        print(f"Error getting active users: {e}")
        return []


def mark_user_inactive(user_id):
    try:
        _update_one("users", lambda u: u["user_id"] == user_id, {"is_active": False})
    except Exception as e:
        print(f"Error marking user inactive: {e}")


def mark_user_active(user_id):
    try:
        _update_one("users", lambda u: u["user_id"] == user_id, {"is_active": True})
    except Exception as e:
        print(f"Error marking user active: {e}")


# ============================================================
# CONFIG MANAGEMENT
# ============================================================
def get_config(key=None, default=None):
    try:
        config = _load_safe("config", {})
        if key is None:
            return config
        return config.get(key, default)
    except Exception as e:
        print(f"Error getting config: {e}")
        return default


def set_config(key, value):
    try:
        with _lock:
            config = _load("config", {})
            config[key] = value
            _save("config", config)
        return True
    except Exception as e:
        print(f"Error setting config: {e}")
        return False


def update_config(data_dict):
    try:
        with _lock:
            config = _load("config", {})
            config.update(data_dict)
            _save("config", config)
        return True
    except Exception as e:
        print(f"Error updating config: {e}")
        return False


# ============================================================
# SUPPORT SETTINGS
# ============================================================
def get_support_settings():
    try:
        return _load_safe("support_settings", {})
    except Exception as e:
        print(f"Error getting support settings: {e}")
        return {}


def update_support_settings(settings_dict):
    try:
        _save_safe("support_settings", settings_dict)
        return True
    except Exception as e:
        print(f"Error updating support settings: {e}")
        return False


# ============================================================
# SECTION STATUS
# ============================================================
def get_section_status(section=None):
    try:
        statuses = _load_safe("section_status", {})
        if section:
            return statuses.get(section, True)
        return statuses
    except Exception as e:
        print(f"Error getting section status: {e}")
        return True if section else {}


def set_section_status(section, enabled):
    try:
        with _lock:
            statuses = _load("section_status", {})
            statuses[section] = enabled
            _save("section_status", statuses)
        return True
    except Exception as e:
        print(f"Error setting section status: {e}")
        return False


# ============================================================
# GIFT CARD STATUS
# ============================================================
def get_gift_card_status():
    try:
        return _load_safe("gift_card_status", {})
    except Exception as e:
        print(f"Error getting gift card status: {e}")
        return {}


def update_gift_card_status(status_dict):
    try:
        _save_safe("gift_card_status", status_dict)
        return True
    except Exception as e:
        print(f"Error updating gift card status: {e}")
        return False


# ============================================================
# FORCE LINKS CACHE
# ============================================================
def get_force_link_cache(link_id=None):
    try:
        cache = _load_safe("force_links_cache", {})
        if link_id:
            return cache.get(link_id, {})
        return cache
    except Exception as e:
        print(f"Error getting force link cache: {e}")
        return {}


def set_force_link_cache(link_id, data):
    try:
        with _lock:
            cache = _load("force_links_cache", {})
            cache[link_id] = data
            _save("force_links_cache", cache)
        return True
    except Exception as e:
        print(f"Error setting force link cache: {e}")
        return False


# ============================================================
# PROXIES
# ============================================================
def get_proxies():
    try:
        return _load_safe("proxies", [])
    except Exception as e:
        print(f"Error getting proxies: {e}")
        return []


def set_proxies(proxy_list):
    try:
        _save_safe("proxies", proxy_list)
        return True
    except Exception as e:
        print(f"Error setting proxies: {e}")
        return False


def add_proxy(proxy):
    try:
        with _lock:
            proxies = _load("proxies", [])
            if proxy not in proxies:
                proxies.append(proxy)
            _save("proxies", proxies)
        return True
    except Exception as e:
        print(f"Error adding proxy: {e}")
        return False


def remove_proxy(proxy):
    try:
        with _lock:
            proxies = _load("proxies", [])
            proxies = [p for p in proxies if p != proxy]
            _save("proxies", proxies)
        return True
    except Exception as e:
        print(f"Error removing proxy: {e}")
        return False


# ============================================================
# BGMI ACCOUNTS
# ============================================================
def get_bgmi_accounts():
    try:
        return _load_safe("bgmi_accounts", [])
    except Exception as e:
        print(f"Error getting BGMI accounts: {e}")
        return []


def set_bgmi_accounts(accounts_list):
    try:
        _save_safe("bgmi_accounts", accounts_list)
        return True
    except Exception as e:
        print(f"Error setting BGMI accounts: {e}")
        return False


def add_bgmi_account(account):
    try:
        with _lock:
            accounts = _load("bgmi_accounts", [])
            accounts.append(account)
            _save("bgmi_accounts", accounts)
        return True
    except Exception as e:
        print(f"Error adding BGMI account: {e}")
        return False


# ============================================================
# SERVICE ACCOUNTS
# ============================================================
def get_service_accounts(service=None):
    try:
        accounts = _load_safe("accounts_db", [])
        if service:
            return [a for a in accounts if a.get("service") == service]
        return accounts
    except Exception as e:
        print(f"Error getting service accounts: {e}")
        return []


def add_service_account(service, account_data):
    try:
        account_data["service"] = service
        account_data["created_at"] = datetime.now(UTC).isoformat()
        account_data["account_id"] = str(uuid.uuid4())
        _insert_one("accounts_db", account_data)
        return True
    except Exception as e:
        print(f"Error adding service account: {e}")
        return False


def remove_service_account(account_id):
    try:
        return _delete_one("accounts_db", lambda a: a.get("account_id") == str(account_id))
    except Exception as e:
        print(f"Error removing service account: {e}")
        return False


# ============================================================
# REFERRALS DB
# ============================================================
def get_referrals():
    try:
        return _load_safe("referrals_db", {})
    except Exception as e:
        print(f"Error getting referrals: {e}")
        return {}


def set_referrals(referrals_dict):
    try:
        _save_safe("referrals_db", referrals_dict)
        return True
    except Exception as e:
        print(f"Error setting referrals: {e}")
        return False


def add_referral(user_id, referral_data):
    try:
        with _lock:
            referrals = _load("referrals_db", {})
            referrals[str(user_id)] = referral_data
            _save("referrals_db", referrals)
        return True
    except Exception as e:
        print(f"Error adding referral: {e}")
        return False
