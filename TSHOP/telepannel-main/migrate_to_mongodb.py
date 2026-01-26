#!/usr/bin/env python3
"""
MongoDB Migration Tool
Migrates data from SQLite (shop_bot.db) to MongoDB
"""

import sqlite3
import os
from datetime import datetime
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "telepannel_shop")
SQLITE_DB = "shop_bot.db"

def check_prerequisites():
    """Check if all prerequisites are met"""
    print("Checking prerequisites...")
    
    if not MONGO_URI:
        print("❌ Error: MONGO_URI not found in .env file")
        return False
    
    if "<db_password>" in MONGO_URI:
        print("❌ Error: Please replace <db_password> in .env with your actual password")
        return False
    
    if not os.path.exists(SQLITE_DB):
        print(f"⚠️  Warning: SQLite database '{SQLITE_DB}' not found")
        print("   Starting with fresh MongoDB database")
        return True
    
    print("✓ Prerequisites met")
    return True

def connect_mongodb():
    """Connect to MongoDB"""
    try:
        client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
        client.admin.command('ping')
        print("✓ Connected to MongoDB")
        return client[MONGO_DB_NAME]
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        return None

def migrate_users(sqlite_conn, mongo_db):
    """Migrate users from SQLite to MongoDB"""
    print("\n📊 Migrating users...")
    cursor = sqlite_conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM users")
        columns = [description[0] for description in cursor.description]
        users = cursor.fetchall()
        
        if not users:
            print("   No users to migrate")
            return 0
        
        users_collection = mongo_db['users']
        migrated = 0
        
        for user_row in users:
            user_dict = dict(zip(columns, user_row))
            # Convert is_active and is_pro to boolean
            if 'is_active' in user_dict:
                user_dict['is_active'] = bool(user_dict['is_active'])
            if 'is_pro' in user_dict:
                user_dict['is_pro'] = bool(user_dict['is_pro'])
            
            try:
                users_collection.replace_one(
                    {"user_id": user_dict['user_id']},
                    user_dict,
                    upsert=True
                )
                migrated += 1
            except Exception as e:
                print(f"   ⚠️  Failed to migrate user {user_dict.get('user_id')}: {e}")
        
        print(f"   ✓ Migrated {migrated} users")
        return migrated
    except Exception as e:
        print(f"   ❌ Error migrating users: {e}")
        return 0

def migrate_table(sqlite_conn, mongo_db, table_name, collection_name=None, unique_key=None):
    """Generic function to migrate a table to MongoDB collection"""
    if collection_name is None:
        collection_name = table_name
    
    print(f"\n📊 Migrating {table_name}...")
    cursor = sqlite_conn.cursor()
    
    try:
        cursor.execute(f"SELECT * FROM {table_name}")
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        
        if not rows:
            print(f"   No {table_name} to migrate")
            return 0
        
        collection = mongo_db[collection_name]
        migrated = 0
        
        for row in rows:
            doc = dict(zip(columns, row))
            
            # Convert boolean-like integers
            for key in doc:
                if key.startswith('is_') and isinstance(doc[key], int):
                    doc[key] = bool(doc[key])
            
            try:
                if unique_key and unique_key in doc:
                    collection.replace_one(
                        {unique_key: doc[unique_key]},
                        doc,
                        upsert=True
                    )
                else:
                    collection.insert_one(doc)
                migrated += 1
            except Exception as e:
                print(f"   ⚠️  Failed to migrate record: {e}")
        
        print(f"   ✓ Migrated {migrated} records")
        return migrated
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            print(f"   ⚠️  Table {table_name} doesn't exist in SQLite")
        else:
            print(f"   ❌ Error: {e}")
        return 0
    except Exception as e:
        print(f"   ❌ Error migrating {table_name}: {e}")
        return 0

def migrate_products(mongo_db):
    """Migrate products from products.json to MongoDB"""
    print("\n📊 Migrating products...")
    
    if not os.path.exists("products.json"):
        print("   ⚠️  products.json not found, skipping")
        return 0
    
    try:
        import json
        with open("products.json", 'r') as f:
            products = json.load(f)
        
        products['_id'] = 'main_products'
        mongo_db['products'].replace_one(
            {"_id": "main_products"},
            products,
            upsert=True
        )
        
        total_products = sum(len(products.get(key, [])) for key in products if key != '_id')
        print(f"   ✓ Migrated {total_products} products")
        return total_products
    except Exception as e:
        print(f"   ❌ Error migrating products: {e}")
        return 0

def main():
    """Main migration function"""
    print("=" * 60)
    print("MongoDB Migration Tool")
    print("=" * 60)
    print()
    
    if not check_prerequisites():
        return
    
    # Connect to MongoDB
    mongo_db = connect_mongodb()
    if mongo_db is None:
        return
    
    # Check for SQLite database
    if not os.path.exists(SQLITE_DB):
        print("\n✓ No SQLite database found - starting fresh")
        print("✓ MongoDB is ready to use")
        return
    
    # Connect to SQLite
    print(f"\n📂 Opening SQLite database: {SQLITE_DB}")
    try:
        sqlite_conn = sqlite3.connect(SQLITE_DB)
        print("✓ SQLite database opened")
    except Exception as e:
        print(f"❌ Failed to open SQLite database: {e}")
        return
    
    # Migrate all tables
    total_migrated = 0
    
    total_migrated += migrate_users(sqlite_conn, mongo_db)
    total_migrated += migrate_table(sqlite_conn, mongo_db, "admins", unique_key="user_id")
    total_migrated += migrate_table(sqlite_conn, mongo_db, "section_admins")
    total_migrated += migrate_table(sqlite_conn, mongo_db, "scraper_admins", unique_key="user_id")
    total_migrated += migrate_table(sqlite_conn, mongo_db, "user_scraper_access", unique_key="user_id")
    total_migrated += migrate_table(sqlite_conn, mongo_db, "pro_keys", unique_key="key")
    total_migrated += migrate_table(sqlite_conn, mongo_db, "giveaway_winners")
    total_migrated += migrate_table(sqlite_conn, mongo_db, "orders", unique_key="order_id")
    total_migrated += migrate_table(sqlite_conn, mongo_db, "support_sessions")
    total_migrated += migrate_table(sqlite_conn, mongo_db, "support_messages")
    total_migrated += migrate_table(sqlite_conn, mongo_db, "support_tickets")
    total_migrated += migrate_table(sqlite_conn, mongo_db, "support_analytics")
    
    # Migrate products.json
    total_migrated += migrate_products(mongo_db)
    
    sqlite_conn.close()
    
    print("\n" + "=" * 60)
    print(f"Migration Complete!")
    print(f"Total records migrated: {total_migrated}")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Verify data in MongoDB Atlas dashboard")
    print("2. Backup SQLite database: mv shop_bot.db shop_bot.db.backup")
    print("3. Start the bot: python main.py")
    print()

if __name__ == "__main__":
    main()
