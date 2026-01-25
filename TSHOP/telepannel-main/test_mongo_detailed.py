#!/usr/bin/env python3
"""
Detailed MongoDB Connection Test
Provides verbose error information and tries multiple connection methods
"""

from pymongo.mongo_client import MongoClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

uri = os.environ.get("MONGO_URI")
db_name = os.environ.get("MONGO_DB_NAME", "telepannel_shop")

print("=" * 60)
print("MongoDB Connection Debug Test")
print("=" * 60)
print()

# Check URI
if not uri:
    print("❌ Error: MONGO_URI not found in .env file")
    exit(1)

# Mask password for display
masked_uri = uri
if ":" in uri and "@" in uri:
    parts = uri.split("://")
    if len(parts) == 2:
        auth_part = parts[1].split("@")[0]
        if ":" in auth_part:
            username = auth_part.split(":")[0]
            masked_uri = uri.replace(auth_part, f"{username}:****")

print(f"Connection URI: {masked_uri}")
print(f"Database Name: {db_name}")
print()

# Try multiple connection methods
connection_methods = [
    {
        "name": "Method 1: Standard with TLS",
        "params": {"tlsAllowInvalidCertificates": True, "serverSelectionTimeoutMS": 5000}
    },
    {
        "name": "Method 2: Without ServerApi",
        "params": {"tls": True, "tlsAllowInvalidCertificates": True}
    },
    {
        "name": "Method 3: Basic connection",
        "params": {}
    }
]

client = None
for method in connection_methods:
    print(f"Trying {method['name']}...")
    try:
        client = MongoClient(uri, **method['params'])
        client.admin.command('ping')
        print(f"✅ SUCCESS with {method['name']}!")
        break
    except Exception as e:
        print(f"   Failed: {str(e)[:100]}...")
        client = None

print()

if not client:
    print("❌ All connection methods failed!")
    print()
    print("Troubleshooting steps:")
    print("1. Check MongoDB Atlas Network Access - whitelist 0.0.0.0/0")
    print("2. Verify password is correct in MongoDB Atlas")
    print("3. Ensure database user has read/write permissions")
    print("4. Check if your IP changed (VPN/network change)")
    exit(1)

try:
    # Get server info
    server_info = client.server_info()
    print(f"MongoDB Version: {server_info.get('version', 'unknown')}")
    
    # List databases
    db_list = client.list_database_names()
    print(f"Available databases: {', '.join(db_list)}")
    
    # Check target database
    db = client[db_name]
    collections = db.list_collection_names()
    
    if collections:
        print(f"\nCollections in '{db_name}': {', '.join(collections)}")
        for coll in collections:
            count = db[coll].count_documents({})
            print(f"  - {coll}: {count} documents")
    else:
        print(f"\n'{db_name}' database is ready (no collections yet)")
    
    print()
    print("✅ All tests passed!")
    
except Exception as e:
    print(f"❌ Error during verification: {e}")
    exit(1)

print()
print("=" * 60)
