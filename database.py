import sqlite3
import json
from datetime import datetime, UTC
from config import DB_NAME, PRODUCTS_FILE

def init_db():
    """
    Initializes the database and ensures the schema is up-to-date.
    This function creates tables if they don't exist and adds missing 
    columns to existing tables to prevent crashes after an update.
    """
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()

        # Create the section_admins table for section-based admin permissions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS section_admins (
                user_id INTEGER NOT NULL,
                section TEXT NOT NULL,
                added_by INTEGER,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, section)
            )
        ''')

        # Create the admins table for global admin permissions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create the users table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                join_date TEXT NOT NULL
            )
        ''')

        # --- Schema Migration for the 'users' table ---
        # This section is for users who have an older database file.
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]

        # Check for and add the 'username' column if it's missing
        if 'username' not in columns:
            print("Updating database schema: Adding 'username' column...")
            cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
        
        if 'balance_usd' not in columns:
            print("Updating database schema: Adding 'balance_usd' column...")
            cursor.execute("ALTER TABLE users ADD COLUMN balance_usd REAL DEFAULT 0.0")

        if 'referral_code' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN referral_code TEXT")
        if 'referred_by' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
        if 'referral_count' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN referral_count INTEGER DEFAULT 0")

        # Track whether a user is still reachable by the bot for broadcasts
        if 'is_active' not in columns:
            print("Updating database schema: Adding 'is_active' column...")
            cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")

        # Track user credits for the CC checker
        if 'cc_credits' not in columns:
            print("Updating database schema: Adding 'cc_credits' column...")
            cursor.execute("ALTER TABLE users ADD COLUMN cc_credits INTEGER DEFAULT 0")

        # Track "pro" status for unlimited CC checks
        if 'is_pro' not in columns:
            print("Updating database schema: Adding 'is_pro' column...")
            cursor.execute("ALTER TABLE users ADD COLUMN is_pro INTEGER DEFAULT 0")

        # Create the pro_keys table for generating access keys
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pro_keys (
                key TEXT PRIMARY KEY,
                is_used INTEGER DEFAULT 0,
                used_by INTEGER,
                used_at TEXT,
                created_by INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create the giveaway winners table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS giveaway_winners (
                winner_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                selected_by INTEGER NOT NULL,
                selected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Create the orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY, 
                user_id INTEGER NOT NULL, 
                item_name TEXT NOT NULL,
                price_usd REAL NOT NULL, 
                payment_method TEXT, 
                payment_status TEXT NOT NULL,
                creation_date TEXT NOT NULL, 
                item_details TEXT
            )
        ''')
        conn.commit()

def add_user(user_id, username, referrer_code=None):
    """
    Adds a new user to the database or updates their username if they already exist.
    Handles referral logic if a referrer_code is provided.
    """
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, referral_code FROM users WHERE user_id = ?", (user_id,))
        existing_user = cursor.fetchone()
        is_new_user = not existing_user

        if is_new_user:
            import uuid
            new_referral_code = str(uuid.uuid4())[:8]
            referred_by_id = None
            if referrer_code:
                cursor.execute("SELECT user_id FROM users WHERE referral_code = ?", (referrer_code,))
                referrer = cursor.fetchone()
                if referrer:
                    referred_by_id = referrer[0]
            
            cursor.execute(
                "INSERT INTO users (user_id, username, join_date, referral_code, referred_by, cc_credits) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, username, datetime.now(UTC).isoformat(), new_referral_code, referred_by_id, 50) # New users get 50 credits
            )
            
            if referred_by_id:
                cursor.execute("UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?", (referred_by_id,))
        else:
            # Ensure existing users have a referral code
            if not existing_user[1]:
                import uuid
                new_referral_code = str(uuid.uuid4())[:8]
                cursor.execute("UPDATE users SET username = ?, referral_code = ? WHERE user_id = ?", (username, new_referral_code, user_id))
            else:
                cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
        conn.commit()

def get_user_balance(user_id):
    """Fetches the current balance for a given user."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance_usd FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0.0

def get_user_credits(user_id):
    """Fetches the current CC checker credits for a given user."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT cc_credits, is_pro FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            return {"credits": result[0], "is_pro": bool(result[1])}
        return {"credits": 0, "is_pro": False}

def update_user_credits(user_id, amount_change):
    """
    Updates a user's CC credits by a given amount (can be positive or negative).
    Does not affect pro users. Returns the new credit balance.
    """
    user_status = get_user_credits(user_id)
    if user_status["is_pro"]:
        return "unlimited" # Pro users are not affected by credit changes

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET cc_credits = cc_credits + ? WHERE user_id = ?", (amount_change, user_id))
        conn.commit()
        cursor.execute("SELECT cc_credits FROM users WHERE user_id = ?", (user_id,))
        new_credits = cursor.fetchone()[0]
        return new_credits

def generate_pro_key(admin_id):
    """Generates a new, unique key for pro access and stores it."""
    import uuid
    new_key = f"pro-{uuid.uuid4()}"
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO pro_keys (key, created_by) VALUES (?, ?)", (new_key, admin_id))
        conn.commit()
    return new_key

def get_all_pro_keys():
    """Retrieves all generated pro keys and their status."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, is_used, used_by, used_at FROM pro_keys")
        return cursor.fetchall()

def validate_and_use_pro_key(key, user_id):
    """
    Validates a pro key. If it's valid and unused, it grants the user pro access
    and marks the key as used.
    """
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, is_used FROM pro_keys WHERE key = ?", (key,))
        result = cursor.fetchone()

        if not result:
            return "invalid"
        
        if result[1]: # is_used
            return "used"

        # Key is valid and unused, grant pro access
        cursor.execute("UPDATE users SET is_pro = 1 WHERE user_id = ?", (user_id,))
        cursor.execute(
            "UPDATE pro_keys SET is_used = 1, used_by = ?, used_at = ? WHERE key = ?",
            (user_id, datetime.now(UTC).isoformat(), key)
        )
        conn.commit()
        return "success"

def update_user_balance(user_id, amount_change):
    """
    Updates a user's balance by a given amount (can be positive or negative).
    Returns the new balance.
    """
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance_usd = balance_usd + ? WHERE user_id = ?", (amount_change, user_id))
        conn.commit()
        cursor.execute("SELECT balance_usd FROM users WHERE user_id = ?", (user_id,))
        new_balance = cursor.fetchone()[0]
        return new_balance

def get_user_details(user_id):
    """
    Fetches all necessary details for a user.
    """
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, join_date, referral_code, referral_count, balance_usd FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        if user:
            # Return the data in a clean dictionary format
            return {
                "user_id": user[0],
                "username": user[1],
                "join_date": user[2],
                "referral_code": user[3],
                "referral_count": user[4],
                "balance": user[5]
            }
        return None

# The load_products and save_products functions are now managed in main.py for caching.
# You can remove them from here if they are no longer used by any other module directly.
# For now, they are left for compatibility in case other modules import them.

def load_products():
    """
    Loads the entire product data from the products.json file.
    Returns a default structure if the file is not found or is corrupted, to prevent crashes.
    """
    try:
        with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # If the file doesn't exist or is empty/invalid, return a default structure
        return {"bins": [], "ready_ccs": [], "gift_cards": [], "rdp": [], "methods": [], "other": []}

def save_products(products_data):
    """
    Saves the entire product data object back into the products.json file.
    This is used by the admin panel after adding or removing a product.
    """
    with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(products_data, f, indent=4)

