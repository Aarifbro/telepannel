"""
NEW BALANCE SYSTEM - Complete Rewrite
Uses JSON file storage instead of MongoDB.
"""

from datetime import datetime, UTC
from database_json import _find_one, _update_one, _insert_one, _find_many, _load_safe


class BalanceManager:
    """Clean balance management system using JSON storage"""

    def get_balance(self, user_id):
        """Get user's current balance"""
        user = _find_one("users", lambda u: u["user_id"] == user_id)

        if not user:
            print(f"[Balance] Initializing new user {user_id}")
            self._initialize_user(user_id)
            return 0.0

        balance = user.get("balance", user.get("balance_usd", 0.0))
        return float(balance) if balance is not None else 0.0

    def add_balance(self, user_id, amount, reason="deposit", order_id=None):
        """Add money to user's balance"""
        amount = float(amount)
        current_balance = self.get_balance(user_id)
        new_balance = current_balance + amount

        print(f"[Balance] Adding ${amount} to user {user_id}: ${current_balance} → ${new_balance}")

        _update_one(
            "users",
            lambda u: u["user_id"] == user_id,
            {"balance": new_balance, "balance_usd": new_balance, "last_balance_update": datetime.now(UTC).isoformat()},
            upsert=True,
        )

        self._record_transaction(user_id, amount, "credit", reason, order_id, new_balance)
        return new_balance

    def deduct_balance(self, user_id, amount, reason="purchase", order_id=None):
        """Deduct money from user's balance"""
        amount = float(amount)
        current_balance = self.get_balance(user_id)

        if current_balance < amount:
            print(f"[Balance] Insufficient balance for user {user_id}: ${current_balance} < ${amount}")
            return None

        new_balance = current_balance - amount

        print(f"[Balance] Deducting ${amount} from user {user_id}: ${current_balance} → ${new_balance}")

        _update_one(
            "users",
            lambda u: u["user_id"] == user_id,
            {"balance": new_balance, "balance_usd": new_balance, "last_balance_update": datetime.now(UTC).isoformat()},
        )

        self._record_transaction(user_id, amount, "debit", reason, order_id, new_balance)
        return new_balance

    def get_transaction_history(self, user_id, limit=10):
        """Get user's transaction history"""
        transactions = _find_many("balance_transactions", lambda t: t["user_id"] == user_id)
        transactions.sort(key=lambda t: t.get("timestamp", ""), reverse=True)
        return transactions[:limit]

    def _initialize_user(self, user_id):
        """Initialize new user with zero balance"""
        _update_one(
            "users",
            lambda u: u["user_id"] == user_id,
            {"user_id": user_id, "balance": 0.0, "balance_usd": 0.0, "created_at": datetime.now(UTC).isoformat()},
            upsert=True,
        )
        print(f"[Balance] User {user_id} initialized")

    def _record_transaction(self, user_id, amount, trans_type, reason, order_id, new_balance):
        """Record a transaction in history"""
        transaction = {
            "user_id": user_id,
            "amount": amount,
            "type": trans_type,
            "reason": reason,
            "order_id": order_id,
            "balance_after": new_balance,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        _insert_one("balance_transactions", transaction)
        print(f"[Balance] Transaction recorded: {trans_type} ${amount} for user {user_id}")

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
