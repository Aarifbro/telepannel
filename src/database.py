import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict
from src.config import Config

class Database:
    """Database operations for escrow bot"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.DB_PATH
    
    async def initialize(self):
        """Initialize database tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Users table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    rating REAL DEFAULT 0.0,
                    total_sales INTEGER DEFAULT 0,
                    total_purchases INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Listings/Services table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS listings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    seller_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    price REAL NOT NULL,
                    delivery_time TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    views INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (seller_id) REFERENCES users (telegram_id)
                )
            """)
            
            # Transactions table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_id INTEGER,
                    buyer_id INTEGER NOT NULL,
                    seller_id INTEGER NOT NULL,
                    product_description TEXT NOT NULL,
                    amount REAL NOT NULL,
                    delivery_time TEXT NOT NULL,
                    status TEXT DEFAULT 'PENDING',
                    shipping_info TEXT,
                    dispute_reason TEXT,
                    rating INTEGER,
                    review TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (listing_id) REFERENCES listings (id),
                    FOREIGN KEY (buyer_id) REFERENCES users (telegram_id),
                    FOREIGN KEY (seller_id) REFERENCES users (telegram_id)
                )
            """)
            
            # Create indexes
            await db.execute("CREATE INDEX IF NOT EXISTS idx_buyer ON transactions(buyer_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_seller ON transactions(seller_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_status ON transactions(status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_listing_seller ON listings(seller_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_listing_active ON listings(is_active)")
            
            await db.commit()
    
    async def add_user(self, telegram_id: int, username: str = None, 
                       first_name: str = None, last_name: str = None):
        """Add or update user"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO users (telegram_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            """, (telegram_id, username, first_name, last_name))
            await db.commit()
    
    async def create_transaction(self, buyer_id: int, seller_id: int, 
                                  product_description: str, amount: float, 
                                  delivery_time: str) -> int:
        """Create new transaction"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO transactions (buyer_id, seller_id, product_description, amount, delivery_time)
                VALUES (?, ?, ?, ?, ?)
            """, (buyer_id, seller_id, product_description, amount, delivery_time))
            await db.commit()
            return cursor.lastrowid
    
    async def get_transaction(self, transaction_id: int) -> Optional[Dict]:
        """Get transaction by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM transactions WHERE id = ?
            """, (transaction_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def update_transaction_status(self, transaction_id: int, status: str):
        """Update transaction status"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE transactions 
                SET status = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (status, transaction_id))
            await db.commit()
    
    async def update_shipping_info(self, transaction_id: int, shipping_info: str):
        """Update shipping information"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE transactions 
                SET shipping_info = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (shipping_info, transaction_id))
            await db.commit()
    
    async def add_dispute(self, transaction_id: int, reason: str):
        """Add dispute reason"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE transactions 
                SET status = 'DISPUTED', dispute_reason = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (reason, transaction_id))
            await db.commit()
    
    async def get_pending_transactions(self) -> List[Dict]:
        """Get all pending transactions"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM transactions WHERE status = 'PENDING' ORDER BY created_at DESC
            """)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_user_transactions(self, user_id: int, as_buyer: bool = True) -> List[Dict]:
        """Get transactions for a user"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            field = "buyer_id" if as_buyer else "seller_id"
            cursor = await db.execute(f"""
                SELECT * FROM transactions 
                WHERE {field} = ? AND status != 'COMPLETED' AND status != 'REJECTED'
                ORDER BY created_at DESC
            """, (user_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_statistics(self) -> Dict:
        """Get transaction statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            # Total transactions
            cursor = await db.execute("SELECT COUNT(*) FROM transactions")
            total = (await cursor.fetchone())[0]
            
            # By status
            cursor = await db.execute("""
                SELECT status, COUNT(*) as count FROM transactions GROUP BY status
            """)
            status_counts = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Total amount
            cursor = await db.execute("""
                SELECT SUM(amount) FROM transactions WHERE status = 'COMPLETED'
            """)
            total_amount = (await cursor.fetchone())[0] or 0
            
            # Total users
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total_users = (await cursor.fetchone())[0]
            
            return {
                'total_transactions': total,
                'status_counts': status_counts,
                'total_amount': total_amount,
                'total_users': total_users
            }
    
    async def create_listing(self, seller_id: int, title: str, description: str,
                            category: str, price: float, delivery_time: str) -> int:
        """Create new listing"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO listings (seller_id, title, description, category, price, delivery_time)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (seller_id, title, description, category, price, delivery_time))
            await db.commit()
            return cursor.lastrowid
    
    async def get_active_listings(self, category: str = None, limit: int = 20) -> List[Dict]:
        """Get active listings"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if category:
                cursor = await db.execute("""
                    SELECT l.*, u.first_name, u.username, u.rating, u.total_sales 
                    FROM listings l 
                    JOIN users u ON l.seller_id = u.telegram_id
                    WHERE l.is_active = 1 AND l.category = ?
                    ORDER BY l.created_at DESC LIMIT ?
                """, (category, limit))
            else:
                cursor = await db.execute("""
                    SELECT l.*, u.first_name, u.username, u.rating, u.total_sales 
                    FROM listings l 
                    JOIN users u ON l.seller_id = u.telegram_id
                    WHERE l.is_active = 1 
                    ORDER BY l.created_at DESC LIMIT ?
                """, (limit,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_listing(self, listing_id: int) -> Optional[Dict]:
        """Get listing by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT l.*, u.first_name, u.username, u.rating, u.total_sales 
                FROM listings l 
                JOIN users u ON l.seller_id = u.telegram_id
                WHERE l.id = ?
            """, (listing_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def increment_listing_views(self, listing_id: int):
        """Increment listing view count"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE listings SET views = views + 1 WHERE id = ?
            """, (listing_id,))
            await db.commit()
    
    async def get_user_listings(self, seller_id: int) -> List[Dict]:
        """Get user's listings"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM listings WHERE seller_id = ? ORDER BY created_at DESC
            """, (seller_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def toggle_listing_status(self, listing_id: int, is_active: bool):
        """Activate or deactivate listing"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE listings SET is_active = ? WHERE id = ?
            """, (1 if is_active else 0, listing_id))
            await db.commit()
    
    async def get_user_profile(self, user_id: int) -> Optional[Dict]:
        """Get user profile with stats"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM users WHERE telegram_id = ?
            """, (user_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def increment_sales(self, seller_id: int):
        """Increment seller's total sales count"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users SET total_sales = total_sales + 1 WHERE telegram_id = ?
            """, (seller_id,))
            await db.commit()
    
    async def update_user_rating(self, user_id: int, new_rating: float):
        """Update user's average rating"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users SET rating = ? WHERE telegram_id = ?
            """, (new_rating, user_id))
            await db.commit()
    
    async def add_transaction_review(self, transaction_id: int, rating: int, review: str):
        """Add review to completed transaction"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE transactions SET rating = ?, review = ? WHERE id = ?
            """, (rating, review, transaction_id))
            await db.commit()
