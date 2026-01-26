"""
NEW BALANCE SYSTEM - Complete Rewrite
This replaces the old broken balance system with a clean, working implementation
"""

from datetime import datetime, UTC
from mongodb_config import get_users_collection, get_database

class BalanceManager:
    """Clean new balance management system"""
    
    def __init__(self):
        self.users_col = None
        self.db = None
        self.transactions_col = None
    
    def _ensure_connected(self):
        """Ensure MongoDB connection is established"""
        if self.users_col is None:
            try:
                self.users_col = get_users_collection()
                self.db = get_database()
                self.transactions_col = self.db['balance_transactions']
                print("✅ Balance system connected to MongoDB")
            except Exception as e:
                print(f"❌ Balance system MongoDB connection error: {e}")
                raise
    
    def get_balance(self, user_id):
        """Get user's current balance"""
        self._ensure_connected()
        
        user = self.users_col.find_one({"user_id": user_id})
        
        if not user:
            # Initialize new user
            print(f"[Balance] Initializing new user {user_id}")
            self._initialize_user(user_id)
            return 0.0
        
        balance = user.get("balance", 0.0)
        print(f"[Balance] User {user_id} current balance: ${balance}")
        return float(balance) if balance is not None else 0.0
    
    def add_balance(self, user_id, amount, reason="deposit", order_id=None):
        """Add money to user's balance"""
        self._ensure_connected()
        
        amount = float(amount)
        current_balance = self.get_balance(user_id)
        new_balance = current_balance + amount
        
        print(f"[Balance] Adding ${amount} to user {user_id}: ${current_balance} → ${new_balance}")
        
        # Update balance in MongoDB
        result = self.users_col.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "balance": new_balance,
                    "last_balance_update": datetime.now(UTC).isoformat()
                }
            },
            upsert=True
        )
        
        print(f"[Balance] MongoDB update result - matched: {result.matched_count}, modified: {result.modified_count}, upserted: {result.upserted_id}")
        
        # Record transaction
        self._record_transaction(user_id, amount, "credit", reason, order_id, new_balance)
        
        # Verify the update
        verified_balance = self.get_balance(user_id)
        print(f"[Balance] Verified new balance: ${verified_balance}")
        
        return new_balance
    
    def deduct_balance(self, user_id, amount, reason="purchase", order_id=None):
        """Deduct money from user's balance"""
        self._ensure_connected()
        
        amount = float(amount)
        current_balance = self.get_balance(user_id)
        
        if current_balance < amount:
            print(f"[Balance] Insufficient balance for user {user_id}: ${current_balance} < ${amount}")
            return None  # Insufficient balance
        
        new_balance = current_balance - amount
        
        print(f"[Balance] Deducting ${amount} from user {user_id}: ${current_balance} → ${new_balance}")
        
        # Update balance
        result = self.users_col.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "balance": new_balance,
                    "last_balance_update": datetime.now(UTC).isoformat()
                }
            }
        )
        
        print(f"[Balance] MongoDB update result - matched: {result.matched_count}, modified: {result.modified_count}")
        
        # Record transaction
        self._record_transaction(user_id, amount, "debit", reason, order_id, new_balance)
        
        return new_balance
    
    def get_transaction_history(self, user_id, limit=10):
        """Get user's transaction history"""
        self._ensure_connected()
        
        transactions = self.transactions_col.find(
            {"user_id": user_id}
        ).sort("timestamp", -1).limit(limit)
        
        return list(transactions)
    
    def _initialize_user(self, user_id):
        """Initialize new user with zero balance"""
        self._ensure_connected()
        
        result = self.users_col.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "balance": 0.0,
                    "created_at": datetime.now(UTC).isoformat()
                }
            },
            upsert=True
        )
        print(f"[Balance] User {user_id} initialized - matched: {result.matched_count}, upserted: {result.upserted_id}")
    
    def _record_transaction(self, user_id, amount, trans_type, reason, order_id, new_balance):
        """Record a transaction in history"""
        self._ensure_connected()
        
        transaction = {
            "user_id": user_id,
            "amount": amount,
            "type": trans_type,  # credit or debit
            "reason": reason,
            "order_id": order_id,
            "balance_after": new_balance,
            "timestamp": datetime.now(UTC).isoformat()
        }
        
        result = self.transactions_col.insert_one(transaction)
        print(f"[Balance] Transaction recorded: {trans_type} ${amount} for user {user_id} - ID: {result.inserted_id}")

# Global instance
balance_manager = BalanceManager()

# Helper functions for easy access
def get_user_balance(user_id):
    """Get user's balance"""
    return balance_manager.get_balance(user_id)

def add_funds(user_id, amount, reason="deposit", order_id=None):
    """Add funds to user's balance"""
    return balance_manager.add_balance(user_id, amount, reason, order_id)

def deduct_funds(user_id, amount, reason="purchase", order_id=None):
    """Deduct funds from user's balance"""
    return balance_manager.deduct_balance(user_id, amount, reason, order_id)

def get_transaction_history(user_id, limit=10):
    """Get user's transaction history"""
    return balance_manager.get_transaction_history(user_id, limit)
