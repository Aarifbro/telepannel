import sqlite3
import json
import time
import random
import string
from datetime import datetime, timedelta

# Temporary Key System Database
def init_temp_key_db():
    """Initialize the temporary key database"""
    conn = sqlite3.connect('temp_keys.db')
    cursor = conn.cursor()
    
    # Create table for temporary keys
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS temp_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_code TEXT UNIQUE NOT NULL,
            product_type TEXT NOT NULL,
            product_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            claimed_by INTEGER DEFAULT NULL,
            claimed_at TIMESTAMP DEFAULT NULL,
            is_active BOOLEAN DEFAULT TRUE
        )
    ''')
    
    # Create table for key claims
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS key_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key_code TEXT NOT NULL,
            claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            product_received TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

def generate_temp_key(product_type, product_data, duration_minutes=20):
    """Generate a temporary key that expires in specified minutes"""
    # Generate random key code
    key_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    key_code = f"TEMP-{key_code[:4]}-{key_code[4:8]}-{key_code[8:]}"
    
    # Calculate expiry time
    expires_at = datetime.now() + timedelta(minutes=duration_minutes)
    
    conn = sqlite3.connect('temp_keys.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO temp_keys (key_code, product_type, product_data, expires_at)
            VALUES (?, ?, ?, ?)
        ''', (key_code, product_type, json.dumps(product_data), expires_at))
        
        conn.commit()
        return key_code
    except Exception as e:
        print(f"Error generating temp key: {e}")
        return None
    finally:
        conn.close()

def claim_temp_key(user_id, key_code):
    """Claim a temporary key if it's valid and not expired"""
    conn = sqlite3.connect('temp_keys.db')
    cursor = conn.cursor()
    
    try:
        # Check if key exists and is valid
        cursor.execute('''
            SELECT id, product_type, product_data, expires_at, claimed_by, is_active
            FROM temp_keys 
            WHERE key_code = ?
        ''', (key_code,))
        
        result = cursor.fetchone()
        
        if not result:
            return {"success": False, "message": "❌ Invalid key code"}
        
        key_id, product_type, product_data, expires_at, claimed_by, is_active = result
        
        # Check if already claimed
        if claimed_by:
            return {"success": False, "message": "❌ Key already claimed by another user"}
        
        # Check if expired
        if datetime.now() > datetime.fromisoformat(expires_at):
            return {"success": False, "message": "❌ Key expired"}
        
        # Check if active
        if not is_active:
            return {"success": False, "message": "❌ Key deactivated"}
        
        # Claim the key
        cursor.execute('''
            UPDATE temp_keys 
            SET claimed_by = ?, claimed_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (user_id, key_id))
        
        # Record the claim
        cursor.execute('''
            INSERT INTO key_claims (user_id, key_code, product_received)
            VALUES (?, ?, ?)
        ''', (user_id, key_code, product_data))
        
        conn.commit()
        
        return {
            "success": True, 
            "message": "✅ Key claimed successfully!", 
            "product_type": product_type,
            "product_data": json.loads(product_data)
        }
        
    except Exception as e:
        print(f"Error claiming key: {e}")
        return {"success": False, "message": "❌ Error processing key"}
    finally:
        conn.close()

def get_active_keys():
    """Get all active temporary keys"""
    conn = sqlite3.connect('temp_keys.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT key_code, product_type, created_at, expires_at, claimed_by
            FROM temp_keys 
            WHERE is_active = TRUE
            ORDER BY created_at DESC
        ''')
        
        keys = []
        for row in cursor.fetchall():
            key_code, product_type, created_at, expires_at, claimed_by = row
            
            # Check if expired
            is_expired = datetime.now() > datetime.fromisoformat(expires_at)
            status = "Claimed" if claimed_by else ("Expired" if is_expired else "Active")
            
            keys.append({
                "key_code": key_code,
                "product_type": product_type,
                "created_at": created_at,
                "expires_at": expires_at,
                "status": status,
                "claimed_by": claimed_by
            })
        
        return keys
        
    except Exception as e:
        print(f"Error getting active keys: {e}")
        return []
    finally:
        conn.close()

def cleanup_expired_keys():
    """Remove expired keys from database"""
    conn = sqlite3.connect('temp_keys.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            DELETE FROM temp_keys 
            WHERE expires_at < CURRENT_TIMESTAMP
        ''')
        
        deleted_count = cursor.rowcount
        conn.commit()
        return deleted_count
        
    except Exception as e:
        print(f"Error cleaning up keys: {e}")
        return 0
    finally:
        conn.close()

def get_user_claims(user_id):
    """Get all keys claimed by a user"""
    conn = sqlite3.connect('temp_keys.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT key_code, claimed_at, product_received
            FROM key_claims 
            WHERE user_id = ?
            ORDER BY claimed_at DESC
        ''', (user_id,))
        
        claims = []
        for row in cursor.fetchall():
            key_code, claimed_at, product_received = row
            claims.append({
                "key_code": key_code,
                "claimed_at": claimed_at,
                "product": json.loads(product_received)
            })
        
        return claims
        
    except Exception as e:
        print(f"Error getting user claims: {e}")
        return []
    finally:
        conn.close()

# Initialize database on import
init_temp_key_db()