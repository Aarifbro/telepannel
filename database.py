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
        
        if 'referral_code' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN referral_code TEXT")
        if 'referred_by' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
        if 'referral_count' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN referral_count INTEGER DEFAULT 0")

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
                "INSERT INTO users (user_id, username, join_date, referral_code, referred_by) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, datetime.now(UTC).isoformat(), new_referral_code, referred_by_id)
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

def get_user_details(user_id):
    """
    Fetches all necessary details for a user.
    """
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, join_date, referral_code, referral_count FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        if user:
            # Return the data in a clean dictionary format
            return {
                "user_id": user[0],
                "username": user[1],
                "join_date": user[2],
                "referral_code": user[3],
                "referral_count": user[4]
            }
        return None

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

