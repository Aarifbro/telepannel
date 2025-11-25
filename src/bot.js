const { Telegraf, Markup } = require('telegraf');
const config = require('./config/config');
const DatabaseManager = require('./database/database');
const FormHandler = require('./handlers/formHandler');
const TransactionHandler = require('./handlers/transactionHandler');
const AdminHandler = require('./handlers/adminHandler');

// Initialize bot
const bot = new Telegraf(config.botToken);
const db = new DatabaseManager(config.dbPath);

// Initialize handlers
const formHandler = new FormHandler(db);
const transactionHandler = new TransactionHandler(db, bot);
const adminHandler = new AdminHandler(db, bot);

// Middleware to track users
bot.use(async (ctx, next) => {
  if (ctx.from) {
    db.createOrUpdateUser({
      user_id: ctx.from.id,
      username: ctx.from.username || null,
      first_name: ctx.from.first_name || null,
      last_name: ctx.from.last_name || null,
    });
  }
  return next();
});

// Middleware to check if user is admin
bot.use((ctx, next) => {
  if (ctx.from) {
    const user = db.getUser(ctx.from.id);
    ctx.isAdmin = user && (user.is_admin === 1 || config.adminIds.includes(ctx.from.id));
    
    // Auto-set admin status if in config
    if (config.adminIds.includes(ctx.from.id) && (!user || user.is_admin === 0)) {
      db.setAdmin(ctx.from.id, true);
      ctx.isAdmin = true;
    }
  }
  return next();
});

// Start command
bot.command('start', async (ctx) => {
  const keyboard = Markup.keyboard([
    ['📦 Browse Products', '🛒 My Purchases'],
    ['💼 My Sales', '➕ List Product'],
    ['📊 My Transactions', '❓ Help']
  ]).resize();

  const adminKeyboard = Markup.keyboard([
    ['📦 Browse Products', '🛒 My Purchases'],
    ['💼 My Sales', '➕ List Product'],
    ['📊 My Transactions', '⚙️ Admin Panel'],
    ['❓ Help']
  ]).resize();

  await ctx.reply(
    `🤝 *Welcome to Escrow Bot!*\n\n` +
    `I'm your trusted mediator for safe transactions.\n\n` +
    `*How it works:*\n` +
    `1️⃣ Seller lists a product\n` +
    `2️⃣ Buyer initiates purchase\n` +
    `3️⃣ Buyer confirms payment\n` +
    `4️⃣ Seller ships & confirms delivery\n` +
    `5️⃣ Admin approves fund release\n` +
    `6️⃣ Both parties confirm completion\n\n` +
    `Choose an option below:`,
    { parse_mode: 'Markdown', ...ctx.isAdmin ? adminKeyboard : keyboard }
  );
});

// Help command
bot.command('help', async (ctx) => {
  await ctx.reply(
    `📖 *Help & Commands*\n\n` +
    `*For Buyers:*\n` +
    `/start - Start the bot\n` +
    `📦 Browse Products - View available products\n` +
    `🛒 My Purchases - View your purchases\n\n` +
    `*For Sellers:*\n` +
    `➕ List Product - Add a new product\n` +
    `💼 My Sales - View your sales\n\n` +
    `*General:*\n` +
    `📊 My Transactions - View all transactions\n` +
    `/cancel - Cancel current operation\n\n` +
    `*Transaction Process:*\n` +
    `1. Browse and select a product\n` +
    `2. Confirm purchase details\n` +
    `3. Pay and confirm payment\n` +
    `4. Wait for delivery\n` +
    `5. Confirm receipt\n` +
    `6. Admin releases funds to seller\n\n` +
    `Need help? Contact support!`,
    { parse_mode: 'Markdown' }
  );
});

// Cancel command
bot.command('cancel', async (ctx) => {
  db.clearSessionState(ctx.from.id);
  await ctx.reply('❌ Operation cancelled.', Markup.removeKeyboard());
  await ctx.reply('Use /start to see the main menu.');
});

// Browse Products
bot.hears('📦 Browse Products', async (ctx) => {
  const products = db.getAllActiveProducts();
  
  if (products.length === 0) {
    return ctx.reply('No products available at the moment. Check back later!');
  }

  await ctx.reply('📦 *Available Products:*', { parse_mode: 'Markdown' });

  for (const product of products) {
    const buttons = Markup.inlineKeyboard([
      [Markup.button.callback('🛒 Buy Now', `buy_${product.id}`)]
    ]);

    await ctx.reply(
      `*${product.title}*\n\n` +
      `${product.description || 'No description provided'}\n\n` +
      `💰 Price: $${product.price.toFixed(2)}\n` +
      `👤 Seller: @${product.seller_username || 'Unknown'}`,
      { parse_mode: 'Markdown', ...buttons }
    );
  }
});

// List Product button
bot.hears('➕ List Product', async (ctx) => {
  formHandler.startProductForm(ctx);
});

// My Purchases
bot.hears('🛒 My Purchases', async (ctx) => {
  const transactions = db.getUserTransactions(ctx.from.id, 'buyer');
  
  if (transactions.length === 0) {
    return ctx.reply('You have no purchases yet. Browse products to get started!');
  }

  await ctx.reply('🛒 *Your Purchases:*', { parse_mode: 'Markdown' });

  for (const tx of transactions) {
    const statusEmoji = transactionHandler.getStatusEmoji(tx.status);
    const buttons = Markup.inlineKeyboard([
      [Markup.button.callback('📋 Details', `tx_${tx.id}`)]
    ]);

    await ctx.reply(
      `${statusEmoji} Transaction #${tx.id}\n\n` +
      `Product: ${tx.product_title}\n` +
      `Amount: $${tx.amount.toFixed(2)}\n` +
      `Seller: @${tx.seller_username}\n` +
      `Status: ${tx.status.toUpperCase()}\n` +
      `Date: ${new Date(tx.created_at).toLocaleDateString()}`,
      buttons
    );
  }
});

// My Sales
bot.hears('💼 My Sales', async (ctx) => {
  const transactions = db.getUserTransactions(ctx.from.id, 'seller');
  
  if (transactions.length === 0) {
    return ctx.reply('You have no sales yet. List a product to start selling!');
  }

  await ctx.reply('💼 *Your Sales:*', { parse_mode: 'Markdown' });

  for (const tx of transactions) {
    const statusEmoji = transactionHandler.getStatusEmoji(tx.status);
    const buttons = Markup.inlineKeyboard([
      [Markup.button.callback('📋 Details', `tx_${tx.id}`)]
    ]);

    await ctx.reply(
      `${statusEmoji} Transaction #${tx.id}\n\n` +
      `Product: ${tx.product_title}\n` +
      `Amount: $${tx.amount.toFixed(2)}\n` +
      `Buyer: @${tx.buyer_username}\n` +
      `Status: ${tx.status.toUpperCase()}\n` +
      `Date: ${new Date(tx.created_at).toLocaleDateString()}`,
      buttons
    );
  }
});

// My Transactions
bot.hears('📊 My Transactions', async (ctx) => {
  const transactions = db.getUserTransactions(ctx.from.id, 'all');
  
  if (transactions.length === 0) {
    return ctx.reply('You have no transactions yet.');
  }

  await ctx.reply('📊 *All Your Transactions:*', { parse_mode: 'Markdown' });

  for (const tx of transactions) {
    const role = tx.buyer_id === ctx.from.id ? '🛒 BUYER' : '💼 SELLER';
    const statusEmoji = transactionHandler.getStatusEmoji(tx.status);
    const buttons = Markup.inlineKeyboard([
      [Markup.button.callback('📋 Details', `tx_${tx.id}`)]
    ]);

    await ctx.reply(
      `${statusEmoji} ${role} - Transaction #${tx.id}\n\n` +
      `Product: ${tx.product_title}\n` +
      `Amount: $${tx.amount.toFixed(2)}\n` +
      `Status: ${tx.status.toUpperCase()}\n` +
      `Date: ${new Date(tx.created_at).toLocaleDateString()}`,
      buttons
    );
  }
});

// Admin Panel
bot.hears('⚙️ Admin Panel', async (ctx) => {
  if (!ctx.isAdmin) {
    return ctx.reply('⛔ You are not authorized to access the admin panel.');
  }
  adminHandler.showAdminPanel(ctx);
});

// Callback query handlers
bot.action(/^buy_(\d+)$/, async (ctx) => {
  const productId = parseInt(ctx.match[1]);
  await transactionHandler.initiatePurchase(ctx, productId);
});

bot.action(/^tx_(\d+)$/, async (ctx) => {
  const txId = parseInt(ctx.match[1]);
  await transactionHandler.showTransactionDetails(ctx, txId);
});

bot.action(/^confirm_payment_(\d+)$/, async (ctx) => {
  const txId = parseInt(ctx.match[1]);
  await transactionHandler.confirmPayment(ctx, txId);
});

bot.action(/^confirm_delivery_(\d+)$/, async (ctx) => {
  const txId = parseInt(ctx.match[1]);
  await transactionHandler.confirmDelivery(ctx, txId);
});

bot.action(/^dispute_(\d+)$/, async (ctx) => {
  const txId = parseInt(ctx.match[1]);
  await transactionHandler.startDispute(ctx, txId);
});

bot.action(/^admin_approve_(\d+)$/, async (ctx) => {
  if (!ctx.isAdmin) {
    return ctx.answerCbQuery('⛔ Unauthorized');
  }
  const txId = parseInt(ctx.match[1]);
  await adminHandler.approveTransaction(ctx, txId);
});

bot.action(/^admin_reject_(\d+)$/, async (ctx) => {
  if (!ctx.isAdmin) {
    return ctx.answerCbQuery('⛔ Unauthorized');
  }
  const txId = parseInt(ctx.match[1]);
  await adminHandler.rejectTransaction(ctx, txId);
});

bot.action('admin_pending', async (ctx) => {
  if (!ctx.isAdmin) {
    return ctx.answerCbQuery('⛔ Unauthorized');
  }
  await adminHandler.showPendingTransactions(ctx);
});

bot.action('admin_stats', async (ctx) => {
  if (!ctx.isAdmin) {
    return ctx.answerCbQuery('⛔ Unauthorized');
  }
  await adminHandler.showStatistics(ctx);
});

// Handle text messages for form filling
bot.on('text', async (ctx) => {
  const sessionState = db.getSessionState(ctx.from.id);
  
  if (sessionState) {
    await formHandler.handleFormInput(ctx, sessionState);
  }
});

// Error handling
bot.catch((err, ctx) => {
  console.error('Bot error:', err);
  ctx.reply('❌ An error occurred. Please try again or contact support.');
});

// Graceful shutdown
process.once('SIGINT', () => {
  console.log('Shutting down gracefully...');
  db.close();
  bot.stop('SIGINT');
});

process.once('SIGTERM', () => {
  console.log('Shutting down gracefully...');
  db.close();
  bot.stop('SIGTERM');
});

// Launch bot
console.log('🤖 Starting Escrow Bot...');
bot.launch().then(() => {
  console.log('✅ Bot is running!');
}).catch(err => {
  console.error('Failed to start bot:', err);
  process.exit(1);
});
