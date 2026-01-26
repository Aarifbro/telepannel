"""
User Session Management - Prevents cross-user button interference
"""

# Track message ownership to prevent cross-user button interference
# Format: {message_id: user_id}
message_ownership = {}

def verify_callback_user(bot, call, expected_user_id=None):
    """
    Verify that the user clicking the button is authorized.
    Returns True if authorized, False otherwise.
    
    Args:
        bot: The bot instance
        call: The callback query object
        expected_user_id: If provided, checks if caller matches this specific user
    """
    caller_id = call.from_user.id
    message_id = call.message.message_id
    
    # If specific user expected, verify it matches
    if expected_user_id is not None and caller_id != expected_user_id:
        bot.answer_callback_query(
            call.id, 
            "❌ This is not your menu! Use /start to get your own.", 
            show_alert=True
        )
        return False
    
    # Check message ownership if tracked
    if message_id in message_ownership:
        owner_id = message_ownership[message_id]
        if caller_id != owner_id:
            bot.answer_callback_query(
                call.id,
                "❌ This is not your menu! Use /start to get your own.",
                show_alert=True
            )
            return False
    else:
        # First interaction with this message, claim ownership
        message_ownership[message_id] = caller_id
    
    return True

def track_message_owner(message, user_id):
    """Track that a message belongs to a specific user."""
    if message and hasattr(message, 'message_id'):
        message_ownership[message.message_id] = user_id

def clear_old_sessions(max_entries=1000):
    """
    Clean up old message ownership entries to prevent memory growth.
    Call this periodically or when reaching a threshold.
    """
    global message_ownership
    if len(message_ownership) > max_entries:
        # Keep only the most recent entries
        sorted_items = sorted(message_ownership.items(), key=lambda x: x[0], reverse=True)
        message_ownership = dict(sorted_items[:max_entries // 2])
        print(f"🧹 Cleaned up message ownership cache. Now tracking {len(message_ownership)} messages.")
