#!/usr/bin/env python3
"""
Telegram Escrow Bot
A secure transaction mediator bot for buyers and sellers
"""

import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)

from src.config import Config
from src.database import Database
from src.handlers.start_handler import start_command, help_command
from src.handlers.transaction_handler import (
    new_transaction, get_seller_id, get_product_description,
    get_amount, get_delivery_time, cancel_transaction,
    my_transactions, my_sales,
    SELLER_ID, PRODUCT_DESC, AMOUNT, DELIVERY_TIME
)
from src.handlers.callback_handler import (
    handle_callback, get_dispute_reason, get_shipping_info,
    SHIPPING_INFO, DISPUTE_REASON
)
from src.handlers.admin_handler import admin_panel, stats_command
from src.handlers.listing_handler import (
    browse_services, show_category_listings, view_listing_details,
    create_listing_start, get_listing_title, get_listing_description,
    get_listing_category, get_listing_price, get_listing_delivery_time,
    my_listings, manage_listing, toggle_listing,
    LISTING_TITLE, LISTING_DESC, LISTING_CATEGORY, LISTING_PRICE, LISTING_DELIVERY
)
from src.handlers.menu_handler import handle_menu_buttons
from src.handlers.purchase_handler import buy_listing_handler

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def post_init(application: Application):
    """Initialize database after bot starts"""
    db = Database()
    await db.initialize()
    logger.info("Database initialized successfully")

def main():
    """Start the bot"""
    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return
    
    # Create application
    application = Application.builder().token(Config.BOT_TOKEN).post_init(post_init).build()
    
    # Basic commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    
    # Admin commands
    application.add_handler(CommandHandler("admin", admin_panel))
    
    # Transaction commands
    application.add_handler(CommandHandler("mytransactions", my_transactions))
    application.add_handler(CommandHandler("mysales", my_sales))
    
    # Listing commands
    application.add_handler(CommandHandler("browse", browse_services))
    application.add_handler(CommandHandler("mylistings", my_listings))
    
    # Menu button handler (must be before conversation handlers)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_menu_buttons
    ))
    
    # New transaction conversation handler
    new_transaction_handler = ConversationHandler(
        entry_points=[CommandHandler("newtransaction", new_transaction)],
        states={
            SELLER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_seller_id)],
            PRODUCT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_product_description)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
            DELIVERY_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delivery_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel_transaction)]
    )
    application.add_handler(new_transaction_handler)
    
    # Create listing conversation handler
    create_listing_handler = ConversationHandler(
        entry_points=[
            CommandHandler("createlisting", create_listing_start),
            MessageHandler(filters.Regex("^🆕 (Create Listing|Sell Digital Product)$"), create_listing_start)
        ],
        states={
            LISTING_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_listing_title)],
            LISTING_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_listing_description)],
            LISTING_CATEGORY: [CallbackQueryHandler(get_listing_category, pattern="^set_category_")],
            LISTING_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_listing_price)],
            LISTING_DELIVERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_listing_delivery_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel_transaction)]
    )
    application.add_handler(create_listing_handler)
    
    # Callback handlers for navigation and actions
    application.add_handler(CallbackQueryHandler(browse_services, pattern="^browse_services$"))
    application.add_handler(CallbackQueryHandler(browse_services, pattern="^back_to_menu$"))
    application.add_handler(CallbackQueryHandler(show_category_listings, pattern="^category_"))
    application.add_handler(CallbackQueryHandler(view_listing_details, pattern="^view_listing_"))
    application.add_handler(CallbackQueryHandler(manage_listing, pattern="^manage_listing_"))
    application.add_handler(CallbackQueryHandler(toggle_listing, pattern="^(activate|deactivate)_"))
    application.add_handler(CallbackQueryHandler(buy_listing_handler, pattern="^buy_listing_"))
    application.add_handler(CallbackQueryHandler(lambda u, c: my_listings(u, c), pattern="^my_listings_back$"))
    
    # Callback conversation handler for shipping and disputes
    callback_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_callback)],
        states={
            SHIPPING_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_shipping_info)],
            DISPUTE_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_dispute_reason)],
        },
        fallbacks=[CommandHandler("cancel", cancel_transaction)],
        per_message=False
    )
    application.add_handler(callback_conv_handler)
    
    # Start bot
    logger.info("Starting Escrow Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
