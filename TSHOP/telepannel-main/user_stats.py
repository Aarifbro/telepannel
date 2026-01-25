# user_stats.py
# User Statistics and Dashboard System
import sqlite3
import datetime
from typing import Dict, List, Optional
from config import DB_NAME

class UserStats:
    """Advanced user statistics and analytics system"""
    
    def __init__(self):
        self.db_name = DB_NAME
        self._init_stats_tables()
    
    def _init_stats_tables(self):
        """Initialize statistics tables if they don't exist"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                c = conn.cursor()
                
                # User activity log table
                c.execute('''
                    CREATE TABLE IF NOT EXISTS user_activity (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        activity_type TEXT NOT NULL,
                        details TEXT,
                        credits_used INTEGER DEFAULT 0,
                        credits_cost INTEGER DEFAULT 0,
                        success BOOLEAN DEFAULT 0,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # User statistics summary table
                c.execute('''
                    CREATE TABLE IF NOT EXISTS user_statistics (
                        user_id INTEGER PRIMARY KEY,
                        total_checks INTEGER DEFAULT 0,
                        successful_checks INTEGER DEFAULT 0,
                        failed_checks INTEGER DEFAULT 0,
                        total_credits_spent INTEGER DEFAULT 0,
                        total_money_spent REAL DEFAULT 0.0,
                        favorite_gateway TEXT DEFAULT 'Auto',
                        join_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        last_active DATETIME DEFAULT CURRENT_TIMESTAMP,
                        success_rate REAL DEFAULT 0.0,
                        avg_daily_usage REAL DEFAULT 0.0
                    )
                ''')
                
                conn.commit()
                
        except Exception as e:
            print(f"Error initializing stats tables: {e}")
    
    def log_activity(self, user_id: int, activity_type: str, details: str = None, 
                    credits_used: int = 0, credits_cost: int = 0, success: bool = False):
        """Log user activity for statistics"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with sqlite3.connect(self.db_name, timeout=30.0) as conn:
                    conn.execute('PRAGMA journal_mode=WAL')
                    conn.execute('PRAGMA synchronous=NORMAL')
                    conn.execute('BEGIN IMMEDIATE')
                    c = conn.cursor()
                    
                    c.execute('''
                        INSERT INTO user_activity 
                        (user_id, activity_type, details, credits_used, credits_cost, success)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (user_id, activity_type, details, credits_used, credits_cost, success))
                    
                    # Update user statistics summary
                    self._update_user_stats_direct(conn, user_id, activity_type, credits_used, success)
                    
                    conn.commit()
                    break  # Success, exit retry loop
                    
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    import time
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    print(f"Database error after {attempt + 1} attempts: {e}")
                    break
            except Exception as e:
                print(f"Error logging activity: {e}")
                break
    
    def _update_user_stats(self, user_id: int, activity_type: str, credits_used: int, success: bool):
        """Update user statistics summary"""
        try:
            with sqlite3.connect(self.db_name, timeout=30.0) as conn:
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA synchronous=NORMAL')
                conn.execute('PRAGMA cache_size=1000')
                conn.execute('PRAGMA temp_store=memory')
                c = conn.cursor()
                
                # Initialize user stats if not exists
                c.execute('''
                    INSERT OR IGNORE INTO user_statistics (user_id) VALUES (?)
                ''', (user_id,))
                
                # Update statistics based on activity
                if activity_type in ['cc_check', 'cc_file_check']:
                    c.execute('''
                        UPDATE user_statistics SET
                            total_checks = total_checks + 1,
                            successful_checks = successful_checks + ?,
                            failed_checks = failed_checks + ?,
                            total_credits_spent = total_credits_spent + ?,
                            last_active = CURRENT_TIMESTAMP
                        WHERE user_id = ?
                    ''', (1 if success else 0, 0 if success else 1, credits_used, user_id))
                
                # Recalculate success rate
                c.execute('''
                    UPDATE user_statistics SET
                        success_rate = CASE 
                            WHEN total_checks > 0 THEN (successful_checks * 100.0 / total_checks)
                            ELSE 0.0
                        END
                    WHERE user_id = ?
                ''', (user_id,))
                
                conn.commit()
                
        except Exception as e:
            print(f"Error updating user stats: {e}")
    
    def _update_user_stats_direct(self, conn, user_id: int, activity_type: str, credits_used: int, success: bool):
        """Update user statistics using existing connection"""
        try:
            c = conn.cursor()
            
            # Initialize user stats if not exists
            c.execute('''
                INSERT OR IGNORE INTO user_statistics (user_id) VALUES (?)
            ''', (user_id,))
            
            # Update statistics based on activity
            if activity_type in ['cc_check', 'cc_file_check']:
                c.execute('''
                    UPDATE user_statistics SET
                        total_checks = total_checks + 1,
                        successful_checks = successful_checks + ?,
                        failed_checks = failed_checks + ?,
                        total_credits_spent = total_credits_spent + ?,
                        last_active = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                ''', (1 if success else 0, 0 if success else 1, credits_used, user_id))
            
            # Recalculate success rate
            c.execute('''
                UPDATE user_statistics SET
                    success_rate = CASE 
                        WHEN total_checks > 0 THEN (successful_checks * 100.0 / total_checks)
                        ELSE 0.0
                    END
                WHERE user_id = ?
            ''', (user_id,))
                
        except Exception as e:
            print(f"Error updating user stats directly: {e}")
    
    def get_user_dashboard(self, user_id: int) -> Dict:
        """Get comprehensive user dashboard data"""
        try:
            with sqlite3.connect(self.db_name, timeout=30.0) as conn:
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA synchronous=NORMAL')
                c = conn.cursor()
                
                # Get user basic info
                c.execute('''
                    SELECT username, cc_credits, is_pro, referral_count
                    FROM users WHERE user_id = ?
                ''', (user_id,))
                
                user_data = c.fetchone()
                if not user_data:
                    return {"error": "User not found"}
                
                username, credits, is_pro, referrals = user_data
                total_spent = 0.0  # Default value for now
                
                # Get user statistics
                c.execute('''
                    SELECT * FROM user_statistics WHERE user_id = ?
                ''', (user_id,))
                
                stats_data = c.fetchone()
                
                if stats_data:
                    stats = {
                        "total_checks": stats_data[1],
                        "successful_checks": stats_data[2],
                        "failed_checks": stats_data[3],
                        "total_credits_spent": stats_data[4],
                        "total_money_spent": stats_data[5],
                        "favorite_gateway": stats_data[6],
                        "join_date": stats_data[7],
                        "last_active": stats_data[8],
                        "success_rate": round(stats_data[9], 1),
                        "avg_daily_usage": round(stats_data[10], 1)
                    }
                else:
                    stats = {
                        "total_checks": 0,
                        "successful_checks": 0,
                        "failed_checks": 0,
                        "total_credits_spent": 0,
                        "total_money_spent": 0.0,
                        "favorite_gateway": "Auto",
                        "join_date": datetime.datetime.now().strftime("%Y-%m-%d"),
                        "last_active": datetime.datetime.now().strftime("%Y-%m-%d"),
                        "success_rate": 0.0,
                        "avg_daily_usage": 0.0
                    }
                
                # Get recent activity (last 10 activities)
                c.execute('''
                    SELECT activity_type, details, credits_used, success, timestamp
                    FROM user_activity 
                    WHERE user_id = ?
                    ORDER BY timestamp DESC 
                    LIMIT 10
                ''', (user_id,))
                
                recent_activity = []
                for row in c.fetchall():
                    recent_activity.append({
                        "activity": row[0],
                        "details": row[1],
                        "credits": row[2],
                        "success": bool(row[3]),
                        "timestamp": row[4]
                    })
                
                # Get weekly statistics (last 7 days)
                c.execute('''
                    SELECT 
                        DATE(timestamp) as date,
                        COUNT(*) as count,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                        SUM(credits_used) as credits_used
                    FROM user_activity 
                    WHERE user_id = ? AND timestamp >= datetime('now', '-7 days')
                    GROUP BY DATE(timestamp)
                    ORDER BY date
                ''', (user_id,))
                
                weekly_stats = []
                for row in c.fetchall():
                    weekly_stats.append({
                        "date": row[0],
                        "total_checks": row[1],
                        "successes": row[2],
                        "credits_used": row[3],
                        "success_rate": round((row[2] / row[1] * 100) if row[1] > 0 else 0, 1)
                    })
                
                return {
                    "user_info": {
                        "username": username or "Unknown",
                        "user_id": user_id,
                        "credits": credits,
                        "is_pro": bool(is_pro),
                        "referrals": referrals or 0,
                        "total_spent": total_spent or 0.0
                    },
                    "statistics": stats,
                    "recent_activity": recent_activity,
                    "weekly_stats": weekly_stats
                }
                
        except Exception as e:
            print(f"Error getting user dashboard: {e}")
            return {"error": str(e)}
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get top users leaderboard"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                c = conn.cursor()
                
                c.execute('''
                    SELECT 
                        u.username,
                        u.user_id,
                        COALESCE(s.total_checks, 0) as total_checks,
                        COALESCE(s.successful_checks, 0) as successful_checks,
                        COALESCE(s.success_rate, 0) as success_rate,
                        u.referral_count
                    FROM users u
                    LEFT JOIN user_statistics s ON u.user_id = s.user_id
                    WHERE COALESCE(s.total_checks, 0) > 0
                    ORDER BY s.successful_checks DESC
                    LIMIT ?
                ''', (limit,))
                
                leaderboard = []
                for i, row in enumerate(c.fetchall(), 1):
                    leaderboard.append({
                        "rank": i,
                        "username": row[0] or f"User{row[1]}",
                        "user_id": row[1],
                        "total_checks": row[2],
                        "successful_checks": row[3],
                        "success_rate": round(row[4], 1),
                        "referrals": row[5] or 0
                    })
                
                return leaderboard
                
        except Exception as e:
            print(f"Error getting leaderboard: {e}")
            return []

# Global stats instance
user_stats = UserStats()

def log_user_activity(user_id: int, activity_type: str, details: str = None, 
                     credits_used: int = 0, success: bool = False):
    """Easy function to log user activity"""
    try:
        user_stats.log_activity(user_id, activity_type, details, credits_used, 0, success)
    except Exception as e:
        print(f"Failed to log activity for user {user_id}: {e}")
        # Don't raise the exception to avoid breaking the main flow

def get_user_dashboard_data(user_id: int) -> Dict:
    """Easy function to get user dashboard"""
    return user_stats.get_user_dashboard(user_id)