from pymongo.mongo_client import MongoClient
from pymongo import ASCENDING, DESCENDING
from datetime import datetime, UTC
import uuid
from config import MONGO_URI, MONGO_DB_NAME

# MongoDB Client Connection with SSL configuration for development environments
# Try multiple connection methods to handle SSL issues in containers/codespaces
client = None
connection_errors = []

connection_attempts = [
    {"tlsAllowInvalidCertificates": True, "serverSelectionTimeoutMS": 10000},
    {"tls": True, "tlsAllowInvalidCertificates": True},
    {}  # Fallback to basic connection
]

for attempt_params in connection_attempts:
    try:
        client = MongoClient(MONGO_URI, **attempt_params)
        # Test the connection
        client.admin.command('ping')
        break  # Connection successful
    except Exception as e:
        connection_errors.append(str(e)[:100])
        client = None

if not client:
    print("=" * 60)
    print("ERROR: Failed to connect to MongoDB")
    print("=" * 60)
    print("All connection attempts failed:")
    for i, error in enumerate(connection_errors, 1):
        print(f"  {i}. {error}...")
    print()
    print("Please check:")
    print("  1. MONGO_URI in .env file is correct")
    print("  2. MongoDB Atlas Network Access allows your IP")
    print("  3. Database user credentials are valid")
    print("=" * 60)
    raise Exception("Failed to establish MongoDB connection")

db = client[MONGO_DB_NAME]

# Collections
users_collection = db['users']
admins_collection = db['admins']
section_admins_collection = db['section_admins']
scraper_admins_collection = db['scraper_admins']
user_scraper_access_collection = db['user_scraper_access']
pro_keys_collection = db['pro_keys']
giveaway_winners_collection = db['giveaway_winners']
orders_collection = db['orders']
support_sessions_collection = db['support_sessions']
support_messages_collection = db['support_messages']
support_tickets_collection = db['support_tickets']
support_analytics_collection = db['support_analytics']
products_collection = db['products']

# New collections for migrating JSON files
config_collection = db['config']
support_settings_collection = db['support_settings']
section_status_collection = db['section_status']
gift_card_status_collection = db['gift_card_status']
force_links_cache_collection = db['force_links_cache']
proxies_collection = db['proxies']
bgmi_accounts_collection = db['bgmi_accounts']
accounts_db_collection = db['accounts_db']
referrals_db_collection = db['referrals_db']

def init_db():
    """
    Initializes MongoDB collections and creates necessary indexes.
    Tests the connection with a ping command.
    """
    try:
        # Test connection
        client.admin.command('ping')
        print("✓ Successfully connected to MongoDB!")
        
        # Create indexes for better query performance
        users_collection.create_index([("user_id", ASCENDING)], unique=True)
        users_collection.create_index([("referral_code", ASCENDING)])
        
        admins_collection.create_index([("user_id", ASCENDING)], unique=True)
        
        section_admins_collection.create_index([("user_id", ASCENDING), ("section", ASCENDING)], unique=True)
        
        scraper_admins_collection.create_index([("user_id", ASCENDING)], unique=True)
        
        user_scraper_access_collection.create_index([("user_id", ASCENDING)], unique=True)
        
        pro_keys_collection.create_index([("key", ASCENDING)], unique=True)
        
        orders_collection.create_index([("order_id", ASCENDING)], unique=True)
        orders_collection.create_index([("user_id", ASCENDING)])
        
        support_sessions_collection.create_index([("user_id", ASCENDING)])
        support_sessions_collection.create_index([("admin_id", ASCENDING)])
        support_sessions_collection.create_index([("status", ASCENDING)])
        
        support_messages_collection.create_index([("session_id", ASCENDING)])
        
        support_tickets_collection.create_index([("user_id", ASCENDING)])
        support_tickets_collection.create_index([("assigned_admin", ASCENDING)])
        
        support_analytics_collection.create_index([("date", ASCENDING)])
        
        print("MongoDB database initialized successfully with indexes")
    except Exception as e:
        print(f"Error initializing MongoDB: {e}")

def add_user(user_id, username, referrer_code=None):
    """
    Adds a new user to the database or updates their username if they already exist.
    Handles referral logic if a referrer_code is provided.
    """
    try:
        existing_user = users_collection.find_one({"user_id": user_id})
        is_new_user = not existing_user
        
        if is_new_user:
            new_referral_code = str(uuid.uuid4())[:8]
            referred_by_id = None
            
            if referrer_code:
                referrer = users_collection.find_one({"referral_code": referrer_code})
                if referrer:
                    referred_by_id = referrer['user_id']
            
            user_doc = {
                "user_id": user_id,
                "username": username,
                "join_date": datetime.now(UTC).isoformat(),
                "referral_code": new_referral_code,
                "referred_by": referred_by_id,
                "referral_count": 0,
                "balance_usd": 0.0,
                "cc_credits": 50,  # New users get 50 credits
                "is_pro": False,
                "is_active": True
            }
            users_collection.insert_one(user_doc)
            
            if referred_by_id:
                users_collection.update_one(
                    {"user_id": referred_by_id},
                    {"$inc": {"referral_count": 1}}
                )
        else:
            # Update username and ensure referral code exists
            update_data = {"username": username}
            if not existing_user.get('referral_code'):
                update_data['referral_code'] = str(uuid.uuid4())[:8]
            
            users_collection.update_one(
                {"user_id": user_id},
                {"$set": update_data}
            )
    except Exception as e:
        print(f"Error adding/updating user {user_id}: {e}")

def get_user_balance(user_id):
    """Fetches the current balance for a given user."""
    try:
        user = users_collection.find_one({"user_id": user_id}, {"balance_usd": 1})
        return user['balance_usd'] if user else 0.0
    except Exception as e:
        print(f"Error getting balance for user {user_id}: {e}")
        return 0.0

def get_user_credits(user_id):
    """Fetches the current CC checker credits for a given user."""
    try:
        user = users_collection.find_one({"user_id": user_id}, {"cc_credits": 1, "is_pro": 1})
        if user:
            return {"credits": user.get('cc_credits', 0), "is_pro": user.get('is_pro', False)}
        return {"credits": 0, "is_pro": False}
    except Exception as e:
        print(f"Error getting credits for user {user_id}: {e}")
        return {"credits": 0, "is_pro": False}

def update_user_credits(user_id, amount_change):
    """
    Updates a user's CC credits by a given amount (can be positive or negative).
    Does not affect pro users. Returns the new credit balance.
    """
    try:
        user_status = get_user_credits(user_id)
        if user_status["is_pro"]:
            return "unlimited"  # Pro users are not affected by credit changes
        
        users_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"cc_credits": amount_change}}
        )
        
        updated_user = users_collection.find_one({"user_id": user_id}, {"cc_credits": 1})
        return updated_user['cc_credits'] if updated_user else 0
    except Exception as e:
        print(f"Error updating credits for user {user_id}: {e}")
        return 0

def generate_pro_key(admin_id):
    """Generates a new, unique key for pro access and stores it."""
    try:
        new_key = f"pro-{uuid.uuid4()}"
        pro_key_doc = {
            "key": new_key,
            "is_used": False,
            "used_by": None,
            "used_at": None,
            "created_by": admin_id,
            "created_at": datetime.now(UTC).isoformat()
        }
        pro_keys_collection.insert_one(pro_key_doc)
        return new_key
    except Exception as e:
        print(f"Error generating pro key: {e}")
        return None

def get_all_pro_keys():
    """Retrieves all generated pro keys and their status."""
    try:
        keys = pro_keys_collection.find({}, {"_id": 0, "key": 1, "is_used": 1, "used_by": 1, "used_at": 1})
        return [(k['key'], k['is_used'], k.get('used_by'), k.get('used_at')) for k in keys]
    except Exception as e:
        print(f"Error getting pro keys: {e}")
        return []

def validate_and_use_pro_key(key, user_id):
    """
    Validates a pro key. If it's valid and unused, it grants the user pro access
    and marks the key as used.
    """
    try:
        pro_key = pro_keys_collection.find_one({"key": key})
        
        if not pro_key:
            return "invalid"
        
        if pro_key['is_used']:
            return "used"
        
        # Key is valid and unused, grant pro access
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"is_pro": True}}
        )
        
        pro_keys_collection.update_one(
            {"key": key},
            {"$set": {
                "is_used": True,
                "used_by": user_id,
                "used_at": datetime.now(UTC).isoformat()
            }}
        )
        return "success"
    except Exception as e:
        print(f"Error validating pro key: {e}")
        return "error"

def update_user_balance(user_id, amount_change):
    """
    Updates a user's balance by a given amount (can be positive or negative).
    Returns the new balance.
    """
    try:
        users_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"balance_usd": amount_change}}
        )
        
        user = users_collection.find_one({"user_id": user_id}, {"balance_usd": 1})
        return user['balance_usd'] if user else 0.0
    except Exception as e:
        print(f"Error updating balance for user {user_id}: {e}")
        return 0.0

def get_user_details(user_id):
    """
    Fetches all necessary details for a user.
    """
    try:
        user = users_collection.find_one(
            {"user_id": user_id},
            {"_id": 0, "user_id": 1, "username": 1, "join_date": 1, "referral_code": 1, "referral_count": 1, "balance_usd": 1}
        )
        if user:
            return {
                "user_id": user['user_id'],
                "username": user.get('username'),
                "join_date": user.get('join_date'),
                "referral_code": user.get('referral_code'),
                "referral_count": user.get('referral_count', 0),
                "balance": user.get('balance_usd', 0.0)
            }
        return None
    except Exception as e:
        print(f"Error getting user details for {user_id}: {e}")
        return None

# Product management functions
def load_products():
    """
    Loads the entire product data from MongoDB.
    Returns a default structure if no products exist.
    """
    try:
        product_doc = products_collection.find_one({"_id": "main_products"})
        if product_doc:
            # Remove MongoDB _id field
            product_doc.pop('_id', None)
            return product_doc
        # Return default structure
        return {"bins": [], "custom_ccs": [], "gift_cards": [], "rdp": [], "methods": [], "other": []}
    except Exception as e:
        print(f"Error loading products: {e}")
        return {"bins": [], "custom_ccs": [], "gift_cards": [], "rdp": [], "methods": [], "other": []}

def save_products(products_data):
    """
    Saves the entire product data object to MongoDB.
    This is used by the admin panel after adding or removing a product.
    """
    try:
        products_data['_id'] = "main_products"
        products_collection.replace_one(
            {"_id": "main_products"},
            products_data,
            upsert=True
        )
    except Exception as e:
        print(f"Error saving products: {e}")

# Admin management functions
def add_admin(user_id, added_by):
    """Add a global admin."""
    try:
        admin_doc = {
            "user_id": user_id,
            "added_by": added_by,
            "added_at": datetime.now(UTC).isoformat()
        }
        admins_collection.replace_one({"user_id": user_id}, admin_doc, upsert=True)
    except Exception as e:
        print(f"Error adding admin: {e}")

def remove_admin(user_id):
    """Remove a global admin."""
    try:
        admins_collection.delete_one({"user_id": user_id})
    except Exception as e:
        print(f"Error removing admin: {e}")

def is_admin(user_id):
    """Check if a user is a global admin."""
    try:
        return admins_collection.find_one({"user_id": user_id}) is not None
    except Exception as e:
        print(f"Error checking admin status: {e}")
        return False

def add_section_admin(user_id, section, added_by):
    """Add a section-specific admin."""
    try:
        section_admin_doc = {
            "user_id": user_id,
            "section": section,
            "added_by": added_by,
            "added_at": datetime.now(UTC).isoformat()
        }
        section_admins_collection.replace_one(
            {"user_id": user_id, "section": section},
            section_admin_doc,
            upsert=True
        )
    except Exception as e:
        print(f"Error adding section admin: {e}")

def remove_section_admin(user_id, section):
    """Remove a section-specific admin."""
    try:
        section_admins_collection.delete_one({"user_id": user_id, "section": section})
    except Exception as e:
        print(f"Error removing section admin: {e}")

def is_section_admin(user_id, section):
    """Check if a user is an admin for a specific section."""
    try:
        return section_admins_collection.find_one({"user_id": user_id, "section": section}) is not None
    except Exception as e:
        print(f"Error checking section admin status: {e}")
        return False

def add_scraper_admin(user_id, added_by):
    """Add a scraper admin."""
    try:
        scraper_admin_doc = {
            "user_id": user_id,
            "added_by": added_by,
            "added_at": datetime.now(UTC).isoformat()
        }
        scraper_admins_collection.replace_one({"user_id": user_id}, scraper_admin_doc, upsert=True)
    except Exception as e:
        print(f"Error adding scraper admin: {e}")

def remove_scraper_admin(user_id):
    """Remove a scraper admin."""
    try:
        scraper_admins_collection.delete_one({"user_id": user_id})
    except Exception as e:
        print(f"Error removing scraper admin: {e}")

def is_scraper_admin(user_id):
    """Check if a user is a scraper admin."""
    try:
        return scraper_admins_collection.find_one({"user_id": user_id}) is not None
    except Exception as e:
        print(f"Error checking scraper admin status: {e}")
        return False

# Order management
def create_order(order_id, user_id, item_name, price_usd, payment_method, payment_status, item_details=None):
    """Create a new order."""
    try:
        order_doc = {
            "order_id": order_id,
            "user_id": user_id,
            "item_name": item_name,
            "price_usd": price_usd,
            "payment_method": payment_method,
            "payment_status": payment_status,
            "creation_date": datetime.now(UTC).isoformat(),
            "item_details": item_details
        }
        orders_collection.insert_one(order_doc)
    except Exception as e:
        print(f"Error creating order: {e}")

def get_user_orders(user_id):
    """Get all orders for a user."""
    try:
        orders = orders_collection.find({"user_id": user_id}, {"_id": 0}).sort("creation_date", DESCENDING)
        return list(orders)
    except Exception as e:
        print(f"Error getting user orders: {e}")
        return []

def update_order_status(order_id, new_status):
    """Update order payment status."""
    try:
        orders_collection.update_one(
            {"order_id": order_id},
            {"$set": {"payment_status": new_status}}
        )
    except Exception as e:
        print(f"Error updating order status: {e}")

# Support session management
def create_support_session(user_id, category="general", priority=1, subject=None):
    """Create a new support session."""
    try:
        session_doc = {
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
            "last_message_at": datetime.now(UTC).isoformat()
        }
        result = support_sessions_collection.insert_one(session_doc)
        return result.inserted_id
    except Exception as e:
        print(f"Error creating support session: {e}")
        return None

def get_support_session(session_id):
    """Get a support session by ID."""
    try:
        from bson.objectid import ObjectId
        return support_sessions_collection.find_one({"_id": ObjectId(session_id)})
    except Exception as e:
        print(f"Error getting support session: {e}")
        return None

def update_support_session(session_id, update_data):
    """Update a support session."""
    try:
        from bson.objectid import ObjectId
        update_data['updated_at'] = datetime.now(UTC).isoformat()
        support_sessions_collection.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": update_data}
        )
    except Exception as e:
        print(f"Error updating support session: {e}")

def add_support_message(session_id, sender_id, sender_type, message_text, message_type="text", file_id=None):
    """Add a message to a support session."""
    try:
        from bson.objectid import ObjectId
        message_doc = {
            "session_id": ObjectId(session_id),
            "sender_id": sender_id,
            "sender_type": sender_type,
            "message_text": message_text,
            "message_type": message_type,
            "file_id": file_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "is_read": False
        }
        support_messages_collection.insert_one(message_doc)
        
        # Update last_message_at in session
        support_sessions_collection.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"last_message_at": datetime.now(UTC).isoformat()}}
        )
    except Exception as e:
        print(f"Error adding support message: {e}")

def get_support_messages(session_id):
    """Get all messages for a support session."""
    try:
        from bson.objectid import ObjectId
        messages = support_messages_collection.find(
            {"session_id": ObjectId(session_id)},
            {"_id": 0}
        ).sort("timestamp", ASCENDING)
        return list(messages)
    except Exception as e:
        print(f"Error getting support messages: {e}")
        return []

# User scraper access management
def grant_scraper_access(user_id, expiry_date, price_paid=0.0):
    """Grant paid scraper access to a user."""
    try:
        access_doc = {
            "user_id": user_id,
            "expiry_date": expiry_date,
            "purchased_at": datetime.now(UTC).isoformat(),
            "price_paid": price_paid
        }
        user_scraper_access_collection.replace_one({"user_id": user_id}, access_doc, upsert=True)
    except Exception as e:
        print(f"Error granting scraper access: {e}")

def check_scraper_access(user_id):
    """Check if a user has valid scraper access."""
    try:
        access = user_scraper_access_collection.find_one({"user_id": user_id})
        if not access:
            return False
        
        if access.get('expiry_date'):
            from datetime import datetime
            expiry = datetime.fromisoformat(access['expiry_date'])
            return datetime.now(UTC) < expiry
        return True
    except Exception as e:
        print(f"Error checking scraper access: {e}")
        return False

# Giveaway winners
def add_giveaway_winner(user_id, selected_by):
    """Add a giveaway winner."""
    try:
        winner_doc = {
            "user_id": user_id,
            "selected_by": selected_by,
            "selected_at": datetime.now(UTC).isoformat()
        }
        giveaway_winners_collection.insert_one(winner_doc)
    except Exception as e:
        print(f"Error adding giveaway winner: {e}")

def get_all_users():
    """Get all users."""
    try:
        users = users_collection.find({}, {"_id": 0})
        return list(users)
    except Exception as e:
        print(f"Error getting all users: {e}")
        return []

def get_all_active_users():
    """Get all active users."""
    try:
        users = users_collection.find({"is_active": True}, {"user_id": 1, "_id": 0})
        return [u['user_id'] for u in users]
    except Exception as e:
        print(f"Error getting active users: {e}")
        return []

def mark_user_inactive(user_id):
    """Mark a user as inactive (for broadcast tracking)."""
    try:
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"is_active": False}}
        )
    except Exception as e:
        print(f"Error marking user inactive: {e}")

def mark_user_active(user_id):
    """Mark a user as active."""
    try:
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"is_active": True}}
        )
    except Exception as e:
        print(f"Error marking user active: {e}")


# ============================================================
# CONFIG MANAGEMENT (Replaces config.json)
# ============================================================
def get_config(key=None, default=None):
    """Get config value from MongoDB"""
    try:
        if key is None:
            # Return all config
            config_doc = config_collection.find_one({"_id": "main_config"})
            return config_doc.get("data", {}) if config_doc else {}
        else:
            config_doc = config_collection.find_one({"_id": "main_config"})
            if config_doc and "data" in config_doc:
                return config_doc["data"].get(key, default)
            return default
    except Exception as e:
        print(f"Error getting config: {e}")
        return default

def set_config(key, value):
    """Set config value in MongoDB"""
    try:
        config_collection.update_one(
            {"_id": "main_config"},
            {"$set": {f"data.{key}": value}},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error setting config: {e}")
        return False

def update_config(data_dict):
    """Update multiple config values"""
    try:
        update_dict = {f"data.{k}": v for k, v in data_dict.items()}
        config_collection.update_one(
            {"_id": "main_config"},
            {"$set": update_dict},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error updating config: {e}")
        return False


# ============================================================
# SUPPORT SETTINGS (Replaces support_settings.json)
# ============================================================
def get_support_settings():
    """Get support settings from MongoDB"""
    try:
        settings = support_settings_collection.find_one({"_id": "main_settings"})
        return settings.get("data", {}) if settings else {}
    except Exception as e:
        print(f"Error getting support settings: {e}")
        return {}

def update_support_settings(settings_dict):
    """Update support settings in MongoDB"""
    try:
        support_settings_collection.update_one(
            {"_id": "main_settings"},
            {"$set": {"data": settings_dict}},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error updating support settings: {e}")
        return False


# ============================================================
# SECTION STATUS (Replaces section_status.json)
# ============================================================
def get_section_status(section=None):
    """Get section status from MongoDB"""
    try:
        if section:
            status_doc = section_status_collection.find_one({"section": section})
            return status_doc.get("enabled", True) if status_doc else True
        else:
            # Return all sections
            all_status = {}
            for doc in section_status_collection.find():
                all_status[doc["section"]] = doc.get("enabled", True)
            return all_status
    except Exception as e:
        print(f"Error getting section status: {e}")
        return True if section else {}

def set_section_status(section, enabled):
    """Set section status in MongoDB"""
    try:
        section_status_collection.update_one(
            {"section": section},
            {"$set": {"enabled": enabled, "updated_at": datetime.now(UTC)}},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error setting section status: {e}")
        return False


# ============================================================
# GIFT CARD STATUS (Replaces gift_card_status.json)
# ============================================================
def get_gift_card_status():
    """Get gift card status from MongoDB"""
    try:
        status = gift_card_status_collection.find_one({"_id": "main_status"})
        return status.get("data", {}) if status else {}
    except Exception as e:
        print(f"Error getting gift card status: {e}")
        return {}

def update_gift_card_status(status_dict):
    """Update gift card status in MongoDB"""
    try:
        gift_card_status_collection.update_one(
            {"_id": "main_status"},
            {"$set": {"data": status_dict}},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error updating gift card status: {e}")
        return False


# ============================================================
# FORCE LINKS CACHE (Replaces force_links_cache.json)
# ============================================================
def get_force_link_cache(link_id=None):
    """Get force link cache from MongoDB"""
    try:
        if link_id:
            cache = force_links_cache_collection.find_one({"link_id": link_id})
            return cache.get("data", {}) if cache else {}
        else:
            # Return all cached links
            all_cache = {}
            for doc in force_links_cache_collection.find():
                all_cache[doc["link_id"]] = doc.get("data", {})
            return all_cache
    except Exception as e:
        print(f"Error getting force link cache: {e}")
        return {} if link_id else {}

def set_force_link_cache(link_id, data):
    """Set force link cache in MongoDB"""
    try:
        force_links_cache_collection.update_one(
            {"link_id": link_id},
            {"$set": {"data": data, "updated_at": datetime.now(UTC)}},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error setting force link cache: {e}")
        return False


# ============================================================
# PROXIES (Replaces proxies.json)
# ============================================================
def get_proxies():
    """Get proxies list from MongoDB"""
    try:
        proxies_doc = proxies_collection.find_one({"_id": "proxy_list"})
        return proxies_doc.get("proxies", []) if proxies_doc else []
    except Exception as e:
        print(f"Error getting proxies: {e}")
        return []

def set_proxies(proxy_list):
    """Set proxies list in MongoDB"""
    try:
        proxies_collection.update_one(
            {"_id": "proxy_list"},
            {"$set": {"proxies": proxy_list, "updated_at": datetime.now(UTC)}},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error setting proxies: {e}")
        return False

def add_proxy(proxy):
    """Add a single proxy to the list"""
    try:
        proxies_collection.update_one(
            {"_id": "proxy_list"},
            {"$addToSet": {"proxies": proxy}},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error adding proxy: {e}")
        return False

def remove_proxy(proxy):
    """Remove a proxy from the list"""
    try:
        proxies_collection.update_one(
            {"_id": "proxy_list"},
            {"$pull": {"proxies": proxy}}
        )
        return True
    except Exception as e:
        print(f"Error removing proxy: {e}")
        return False


# ============================================================
# BGMI ACCOUNTS (Replaces bgmi_accounts.json)
# ============================================================
def get_bgmi_accounts():
    """Get BGMI accounts from MongoDB"""
    try:
        accounts_doc = bgmi_accounts_collection.find_one({"_id": "bgmi_data"})
        return accounts_doc.get("accounts", []) if accounts_doc else []
    except Exception as e:
        print(f"Error getting BGMI accounts: {e}")
        return []

def set_bgmi_accounts(accounts_list):
    """Set BGMI accounts in MongoDB"""
    try:
        bgmi_accounts_collection.update_one(
            {"_id": "bgmi_data"},
            {"$set": {"accounts": accounts_list, "updated_at": datetime.now(UTC)}},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error setting BGMI accounts: {e}")
        return False

def add_bgmi_account(account):
    """Add a BGMI account"""
    try:
        bgmi_accounts_collection.update_one(
            {"_id": "bgmi_data"},
            {"$push": {"accounts": account}},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error adding BGMI account: {e}")
        return False


# ============================================================
# SERVICE ACCOUNTS (Replaces accounts/accounts_db.json)
# ============================================================
def get_service_accounts(service=None):
    """Get service accounts from MongoDB"""
    try:
        if service:
            accounts = list(accounts_db_collection.find({"service": service}))
            return accounts
        else:
            accounts = list(accounts_db_collection.find())
            return accounts
    except Exception as e:
        print(f"Error getting service accounts: {e}")
        return []

def add_service_account(service, account_data):
    """Add a service account"""
    try:
        account_data["service"] = service
        account_data["created_at"] = datetime.now(UTC)
        accounts_db_collection.insert_one(account_data)
        return True
    except Exception as e:
        print(f"Error adding service account: {e}")
        return False

def remove_service_account(account_id):
    """Remove a service account"""
    try:
        from bson.objectid import ObjectId
        accounts_db_collection.delete_one({"_id": ObjectId(account_id)})
        return True
    except Exception as e:
        print(f"Error removing service account: {e}")
        return False


# ============================================================
# REFERRALS DB (Replaces accounts/referrals_db.json)
# ============================================================
def get_referrals():
    """Get all referrals from MongoDB"""
    try:
        referrals_doc = referrals_db_collection.find_one({"_id": "referrals_data"})
        return referrals_doc.get("referrals", {}) if referrals_doc else {}
    except Exception as e:
        print(f"Error getting referrals: {e}")
        return {}

def set_referrals(referrals_dict):
    """Set referrals data in MongoDB"""
    try:
        referrals_db_collection.update_one(
            {"_id": "referrals_data"},
            {"$set": {"referrals": referrals_dict, "updated_at": datetime.now(UTC)}},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error setting referrals: {e}")
        return False

def add_referral(user_id, referral_data):
    """Add a referral for a user"""
    try:
        referrals_db_collection.update_one(
            {"_id": "referrals_data"},
            {"$set": {f"referrals.{user_id}": referral_data}},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error adding referral: {e}")
        return False
