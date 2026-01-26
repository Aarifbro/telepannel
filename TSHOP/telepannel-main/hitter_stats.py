# hitter_stats.py
# Advanced Hitter Statistics, History, and Rate Limiting System

import sqlite3
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from config import DB_NAME, ADMIN_ID

class HitterStats:
    """Comprehensive hitter statistics and tracking system"""
    
    def __init__(self):
        self.db_name = DB_NAME
        self._init_hitter_tables()
        
        # Rate limiting config
        self.HITTER_COOLDOWN = 30  # seconds between hits
        self.DAILY_FREE_LIMIT = 50  # free users daily limit
        self.DAILY_PREMIUM_LIMIT = 500  # premium users daily limit
        
        # Credit costs
        self.BASIC_HITTER_COST = 5  # credits per basic hit
        self.THREED_HITTER_COST = 10  # credits per 3D hit
        self.BULK_MULTIPLIER = 0.8  # 20% discount for bulk
        
    def _init_hitter_tables(self):
        """Initialize all hitter tracking tables"""
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            
            # Hitter history table
            c.execute('''
                CREATE TABLE IF NOT EXISTS hitter_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    hitter_type TEXT NOT NULL,
                    card_masked TEXT NOT NULL,
                    card_bin TEXT,
                    status TEXT NOT NULL,
                    response TEXT,
                    amount TEXT,
                    currency TEXT,
                    gateway TEXT,
                    merchant TEXT,
                    proxy_used TEXT,
                    credits_cost INTEGER DEFAULT 0,
                    success BOOLEAN DEFAULT 0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Rate limiting table
            c.execute('''
                CREATE TABLE IF NOT EXISTS hitter_rate_limits (
                    user_id INTEGER PRIMARY KEY,
                    last_hit_time REAL,
                    daily_hits INTEGER DEFAULT 0,
                    daily_successes INTEGER DEFAULT 0,
                    last_reset_date TEXT,
                    premium_tier INTEGER DEFAULT 0
                )
            ''')
            
            # Success statistics table
            c.execute('''
                CREATE TABLE IF NOT EXISTS hitter_success_stats (
                    user_id INTEGER PRIMARY KEY,
                    total_hits INTEGER DEFAULT 0,
                    total_successes INTEGER DEFAULT 0,
                    total_fails INTEGER DEFAULT 0,
                    success_rate REAL DEFAULT 0.0,
                    total_charged_amount REAL DEFAULT 0.0,
                    favorite_gateway TEXT,
                    best_bin TEXT,
                    total_credits_spent INTEGER DEFAULT 0,
                    last_success_time DATETIME
                )
            ''')
            
            # Proxy health monitoring
            c.execute('''
                CREATE TABLE IF NOT EXISTS proxy_health (
                    proxy_address TEXT PRIMARY KEY,
                    user_id INTEGER,
                    total_uses INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    fail_count INTEGER DEFAULT 0,
                    last_check_time DATETIME,
                    last_status TEXT,
                    response_time INTEGER,
                    is_alive BOOLEAN DEFAULT 1
                )
            ''')
            
            # Admin notifications queue
            c.execute('''
                CREATE TABLE IF NOT EXISTS admin_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    notification_type TEXT,
                    message TEXT,
                    details TEXT,
                    sent BOOLEAN DEFAULT 0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def mask_card(self, card: str) -> str:
        """Mask card number for privacy"""
        if not card or len(card) < 12:
            return "****"
        return f"{card[:4]}****{card[-4:]}"
    
    def get_card_bin(self, card: str) -> str:
        """Extract BIN from card"""
        if not card or len(card) < 6:
            return ""
        return card[:6]
    
    def check_rate_limit(self, user_id: int, is_premium: bool = False) -> Tuple[bool, str]:
        """
        Check if user can make a hit
        Returns: (allowed, message)
        """
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            
            # Get or create rate limit record
            c.execute('SELECT * FROM hitter_rate_limits WHERE user_id = ?', (user_id,))
            row = c.fetchone()
            
            current_time = time.time()
            today = datetime.now().strftime('%Y-%m-%d')
            
            if not row:
                # First time user
                c.execute('''
                    INSERT INTO hitter_rate_limits 
                    (user_id, last_hit_time, daily_hits, last_reset_date, premium_tier)
                    VALUES (?, ?, 0, ?, ?)
                ''', (user_id, current_time, today, 1 if is_premium else 0))
                conn.commit()
                return True, ""
            
            last_hit_time, daily_hits, last_reset_date, premium_tier = row[1], row[2], row[4], row[5]
            
            # Reset daily counter if new day
            if last_reset_date != today:
                daily_hits = 0
                c.execute('''
                    UPDATE hitter_rate_limits 
                    SET daily_hits = 0, daily_successes = 0, last_reset_date = ?
                    WHERE user_id = ?
                ''', (today, user_id))
                conn.commit()
            
            # Check cooldown
            time_since_last = current_time - (last_hit_time or 0)
            if time_since_last < self.HITTER_COOLDOWN:
                remaining = int(self.HITTER_COOLDOWN - time_since_last)
                return False, f"⏳ Cooldown active. Wait {remaining}s before next hit."
            
            # Check daily limit
            daily_limit = self.DAILY_PREMIUM_LIMIT if (is_premium or premium_tier) else self.DAILY_FREE_LIMIT
            if daily_hits >= daily_limit:
                return False, f"⛔ Daily limit reached ({daily_limit} hits/day). Upgrade to premium for more!"
            
            return True, ""
    
    def update_rate_limit(self, user_id: int):
        """Update rate limit after successful hit check"""
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            current_time = time.time()
            c.execute('''
                UPDATE hitter_rate_limits 
                SET last_hit_time = ?, daily_hits = daily_hits + 1
                WHERE user_id = ?
            ''', (current_time, user_id))
            conn.commit()
    
    def log_hitter_result(self, user_id: int, hitter_type: str, card: str, 
                         status: str, response: str = "", amount: str = "", 
                         currency: str = "", gateway: str = "", merchant: str = "",
                         proxy_used: str = "", credits_cost: int = 0) -> int:
        """
        Log a hitter attempt result
        Returns: history_id
        """
        success = status.upper() in ['CHARGED', 'SUCCESS', 'APPROVED', 'CVV MATCH']
        card_masked = self.mask_card(card)
        card_bin = self.get_card_bin(card)
        
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            
            # Insert history record
            c.execute('''
                INSERT INTO hitter_history 
                (user_id, hitter_type, card_masked, card_bin, status, response, 
                 amount, currency, gateway, merchant, proxy_used, credits_cost, success)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, hitter_type, card_masked, card_bin, status, response,
                  amount, currency, gateway, merchant, proxy_used, credits_cost, success))
            
            history_id = c.lastrowid
            
            # Update success statistics
            self._update_success_stats(conn, user_id, success, amount, currency, 
                                      gateway, card_bin, credits_cost)
            
            # Update rate limit success counter if successful
            if success:
                c.execute('''
                    UPDATE hitter_rate_limits 
                    SET daily_successes = daily_successes + 1
                    WHERE user_id = ?
                ''', (user_id,))
                
                # Queue admin notification
                self._queue_admin_notification(conn, user_id, card_masked, 
                                               amount, currency, gateway, merchant)
            
            conn.commit()
            return history_id
    
    def _update_success_stats(self, conn, user_id: int, success: bool, 
                             amount: str, currency: str, gateway: str, 
                             card_bin: str, credits_cost: int):
        """Update user success statistics"""
        c = conn.cursor()
        
        # Get or create stats record
        c.execute('SELECT * FROM hitter_success_stats WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        
        if not row:
            c.execute('''
                INSERT INTO hitter_success_stats 
                (user_id, total_hits, total_successes, total_fails, 
                 success_rate, total_charged_amount, favorite_gateway, 
                 best_bin, total_credits_spent, last_success_time)
                VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, 1 if success else 0, 0 if success else 1,
                  100.0 if success else 0.0, 0.0, gateway or '', card_bin or '',
                  credits_cost, datetime.now().isoformat() if success else None))
        else:
            total_hits = row[1] + 1
            total_successes = row[2] + (1 if success else 0)
            total_fails = row[3] + (0 if success else 1)
            success_rate = (total_successes / total_hits * 100) if total_hits > 0 else 0.0
            
            # Parse amount
            charged_amount = 0.0
            if success and amount:
                try:
                    charged_amount = float(amount.replace('$', '').replace(',', '').strip())
                except:
                    charged_amount = 0.0
            
            total_charged = row[5] + charged_amount
            total_credits = row[8] + credits_cost
            
            c.execute('''
                UPDATE hitter_success_stats 
                SET total_hits = ?, total_successes = ?, total_fails = ?,
                    success_rate = ?, total_charged_amount = ?,
                    total_credits_spent = ?, last_success_time = ?
                WHERE user_id = ?
            ''', (total_hits, total_successes, total_fails, success_rate,
                  total_charged, total_credits,
                  datetime.now().isoformat() if success else row[9], user_id))
    
    def _queue_admin_notification(self, conn, user_id: int, card_masked: str,
                                  amount: str, currency: str, gateway: str, merchant: str):
        """Queue admin notification for successful charge"""
        c = conn.cursor()
        
        message = f"💰 Successful Charge!\n\nUser: {user_id}\nCard: {card_masked}\nAmount: {amount} {currency}\nGateway: {gateway}\nMerchant: {merchant}"
        details = json.dumps({
            'user_id': user_id,
            'card': card_masked,
            'amount': amount,
            'currency': currency,
            'gateway': gateway,
            'merchant': merchant
        })
        
        c.execute('''
            INSERT INTO admin_notifications 
            (user_id, notification_type, message, details, sent)
            VALUES (?, ?, ?, ?, 0)
        ''', (user_id, 'success_charge', message, details))
    
    def get_user_history(self, user_id: int, limit: int = 10, 
                        success_only: bool = False) -> List[Dict]:
        """Get user's hitter history"""
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            
            query = '''
                SELECT hitter_type, card_masked, status, response, 
                       amount, currency, gateway, merchant, timestamp, success
                FROM hitter_history 
                WHERE user_id = ?
            '''
            
            if success_only:
                query += ' AND success = 1'
            
            query += ' ORDER BY timestamp DESC LIMIT ?'
            
            c.execute(query, (user_id, limit))
            rows = c.fetchall()
            
            history = []
            for row in rows:
                history.append({
                    'hitter_type': row[0],
                    'card': row[1],
                    'status': row[2],
                    'response': row[3],
                    'amount': row[4],
                    'currency': row[5],
                    'gateway': row[6],
                    'merchant': row[7],
                    'timestamp': row[8],
                    'success': bool(row[9])
                })
            
            return history
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Get comprehensive user statistics"""
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            
            # Get success stats
            c.execute('SELECT * FROM hitter_success_stats WHERE user_id = ?', (user_id,))
            stats_row = c.fetchone()
            
            # Get rate limit info
            c.execute('SELECT daily_hits, daily_successes FROM hitter_rate_limits WHERE user_id = ?', (user_id,))
            rate_row = c.fetchone()
            
            if not stats_row:
                return {
                    'total_hits': 0,
                    'total_successes': 0,
                    'total_fails': 0,
                    'success_rate': 0.0,
                    'total_charged': 0.0,
                    'credits_spent': 0,
                    'daily_hits': 0,
                    'daily_successes': 0
                }
            
            return {
                'total_hits': stats_row[1],
                'total_successes': stats_row[2],
                'total_fails': stats_row[3],
                'success_rate': stats_row[4],
                'total_charged': stats_row[5],
                'favorite_gateway': stats_row[6],
                'best_bin': stats_row[7],
                'credits_spent': stats_row[8],
                'last_success': stats_row[9],
                'daily_hits': rate_row[0] if rate_row else 0,
                'daily_successes': rate_row[1] if rate_row else 0
            }
    
    def export_history_txt(self, user_id: int, success_only: bool = False) -> str:
        """Export user history as formatted text"""
        history = self.get_user_history(user_id, limit=100, success_only=success_only)
        
        if not history:
            return "No history found."
        
        lines = ["═══════════════════════════════════════════",
                 "     HITTER HISTORY EXPORT",
                 f"     {'SUCCESSFUL CHARGES ONLY' if success_only else 'ALL ATTEMPTS'}",
                 "═══════════════════════════════════════════\n"]
        
        for i, item in enumerate(history, 1):
            status_emoji = "✅" if item['success'] else "❌"
            lines.append(f"{i}. {status_emoji} {item['timestamp']}")
            lines.append(f"   Type: {item['hitter_type']}")
            lines.append(f"   Card: {item['card']}")
            lines.append(f"   Status: {item['status']}")
            if item['amount']:
                lines.append(f"   Amount: {item['amount']} {item['currency']}")
            if item['gateway']:
                lines.append(f"   Gateway: {item['gateway']}")
            if item['merchant']:
                lines.append(f"   Merchant: {item['merchant']}")
            if item['response']:
                lines.append(f"   Response: {item['response']}")
            lines.append("")
        
        lines.append("═══════════════════════════════════════════")
        lines.append(f"Total Records: {len(history)}")
        lines.append(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("═══════════════════════════════════════════")
        
        return "\n".join(lines)
    
    def get_leaderboard(self, limit: int = 10, metric: str = 'successes') -> List[Dict]:
        """Get top users leaderboard"""
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            
            order_by = {
                'successes': 'total_successes DESC',
                'rate': 'success_rate DESC',
                'hits': 'total_hits DESC',
                'charged': 'total_charged_amount DESC'
            }.get(metric, 'total_successes DESC')
            
            query = f'''
                SELECT user_id, total_hits, total_successes, success_rate, 
                       total_charged_amount, total_credits_spent
                FROM hitter_success_stats 
                WHERE total_hits > 0
                ORDER BY {order_by}
                LIMIT ?
            '''
            
            c.execute(query, (limit,))
            rows = c.fetchall()
            
            leaderboard = []
            for rank, row in enumerate(rows, 1):
                leaderboard.append({
                    'rank': rank,
                    'user_id': row[0],
                    'total_hits': row[1],
                    'total_successes': row[2],
                    'success_rate': row[3],
                    'total_charged': row[4],
                    'credits_spent': row[5]
                })
            
            return leaderboard
    
    def update_proxy_health(self, proxy: str, user_id: int, success: bool, response_time: int):
        """Update proxy health statistics"""
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            
            c.execute('SELECT * FROM proxy_health WHERE proxy_address = ?', (proxy,))
            row = c.fetchone()
            
            if not row:
                c.execute('''
                    INSERT INTO proxy_health 
                    (proxy_address, user_id, total_uses, success_count, fail_count,
                     last_check_time, last_status, response_time, is_alive)
                    VALUES (?, ?, 1, ?, ?, ?, ?, ?, 1)
                ''', (proxy, user_id, 1 if success else 0, 0 if success else 1,
                      datetime.now().isoformat(), 'success' if success else 'fail', response_time))
            else:
                total_uses = row[2] + 1
                success_count = row[3] + (1 if success else 0)
                fail_count = row[4] + (0 if success else 1)
                
                c.execute('''
                    UPDATE proxy_health 
                    SET total_uses = ?, success_count = ?, fail_count = ?,
                        last_check_time = ?, last_status = ?, response_time = ?
                    WHERE proxy_address = ?
                ''', (total_uses, success_count, fail_count,
                      datetime.now().isoformat(), 'success' if success else 'fail',
                      response_time, proxy))
            
            conn.commit()
    
    def get_pending_admin_notifications(self) -> List[Dict]:
        """Get unsent admin notifications"""
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT id, user_id, notification_type, message, details, timestamp
                FROM admin_notifications 
                WHERE sent = 0
                ORDER BY timestamp DESC
                LIMIT 10
            ''')
            rows = c.fetchall()
            
            notifications = []
            for row in rows:
                notifications.append({
                    'id': row[0],
                    'user_id': row[1],
                    'type': row[2],
                    'message': row[3],
                    'details': json.loads(row[4]) if row[4] else {},
                    'timestamp': row[5]
                })
            
            return notifications
    
    def mark_notification_sent(self, notification_id: int):
        """Mark notification as sent"""
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute('UPDATE admin_notifications SET sent = 1 WHERE id = ?', (notification_id,))
            conn.commit()


# Global instance
hitter_stats = HitterStats()


def log_hit(user_id: int, hitter_type: str, card: str, status: str, **kwargs):
    """Easy function to log hitter result"""
    return hitter_stats.log_hitter_result(user_id, hitter_type, card, status, **kwargs)


def check_can_hit(user_id: int, is_premium: bool = False) -> Tuple[bool, str]:
    """Easy function to check if user can hit"""
    return hitter_stats.check_rate_limit(user_id, is_premium)


def update_hit_limit(user_id: int):
    """Easy function to update rate limit"""
    hitter_stats.update_rate_limit(user_id)


def get_history(user_id: int, limit: int = 10, success_only: bool = False):
    """Easy function to get user history"""
    return hitter_stats.get_user_history(user_id, limit, success_only)


def get_stats(user_id: int):
    """Easy function to get user stats"""
    return hitter_stats.get_user_stats(user_id)


def export_txt(user_id: int, success_only: bool = False):
    """Easy function to export history"""
    return hitter_stats.export_history_txt(user_id, success_only)
