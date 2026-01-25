"""
DEPRECATED: This module is kept for backward compatibility only.
All new code should use database_mongodb.py instead.

This file now acts as a wrapper that redirects all calls to MongoDB.
"""

# Import all MongoDB functions
from database_mongodb import (
    init_db,
    add_user,
    get_user_balance,
    get_user_credits,
    update_user_credits,
    generate_pro_key,
    get_all_pro_keys,
    validate_and_use_pro_key,
    update_user_balance,
    get_user_details,
    load_products,
    save_products,
    add_admin,
    remove_admin,
    is_admin,
    add_section_admin,
    remove_section_admin,
    is_section_admin,
    add_scraper_admin,
    remove_scraper_admin,
    is_scraper_admin,
    create_order,
    get_user_orders,
    update_order_status,
    create_support_session,
    get_support_session,
    update_support_session,
    add_support_message,
    get_support_messages,
    grant_scraper_access,
    check_scraper_access,
    add_giveaway_winner,
    get_all_users,
    get_all_active_users,
    mark_user_inactive,
    mark_user_active
)

__all__ = [
    'init_db', 'add_user', 'get_user_balance', 'get_user_credits',
    'update_user_credits', 'generate_pro_key', 'get_all_pro_keys',
    'validate_and_use_pro_key', 'update_user_balance', 'get_user_details',
    'load_products', 'save_products', 'add_admin', 'remove_admin',
    'is_admin', 'add_section_admin', 'remove_section_admin',
    'is_section_admin', 'add_scraper_admin', 'remove_scraper_admin',
    'is_scraper_admin', 'create_order', 'get_user_orders',
    'update_order_status', 'create_support_session', 'get_support_session',
    'update_support_session', 'add_support_message', 'get_support_messages',
    'grant_scraper_access', 'check_scraper_access', 'add_giveaway_winner',
    'get_all_users', 'get_all_active_users', 'mark_user_inactive',
    'mark_user_active'
]
