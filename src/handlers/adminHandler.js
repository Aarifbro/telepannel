const { Markup } = require('telegraf');

class AdminHandler {
  constructor(db, bot) {
    this.db = db;
    this.bot = bot;
  }

  // Show admin panel
  async showAdminPanel(ctx) {
    const stats = this.db.getStatistics();

    const message = `⚙️ *Admin Panel*\n\n` +
      `*Statistics:*\n` +
      `👥 Total Users: ${stats.totalUsers}\n` +
      `💼 Total Transactions: ${stats.totalTransactions}\n` +
      `✅ Completed: ${stats.completedTransactions}\n` +
      `⏳ Pending: ${stats.pendingTransactions}\n` +
      `💰 Total Volume: $${stats.totalVolume.toFixed(2)}\n\n` +
      `Select an action:`;

    const buttons = Markup.inlineKeyboard([
      [Markup.button.callback('⏳ Pending Transactions', 'admin_pending')],
      [Markup.button.callback('📊 Detailed Stats', 'admin_stats')],
      [Markup.button.callback('🔄 Refresh', 'admin_panel')]
    ]);

    if (ctx.callbackQuery) {
      await ctx.editMessageText(message, { parse_mode: 'Markdown', ...buttons });
    } else {
      await ctx.reply(message, { parse_mode: 'Markdown', ...buttons });
    }
  }

  // Show pending transactions
  async showPendingTransactions(ctx) {
    await ctx.answerCbQuery();

    const transactions = this.db.getPendingTransactions();

    if (transactions.length === 0) {
      return ctx.reply('✅ No pending transactions!');
    }

    await ctx.reply(`⏳ *Pending Transactions (${transactions.length})*`, { parse_mode: 'Markdown' });

    for (const tx of transactions) {
      const statusEmoji = this.getStatusEmoji(tx.status);
      
      let message = `${statusEmoji} *Transaction #${tx.id}*\n\n` +
        `*Product:* ${tx.product_title}\n` +
        `*Amount:* $${tx.amount.toFixed(2)}\n` +
        `*Status:* ${tx.status.toUpperCase()}\n\n` +
        `*Buyer:* @${tx.buyer_username || 'Unknown'}\n` +
        `*Seller:* @${tx.seller_username || 'Unknown'}\n\n` +
        `*Progress:*\n` +
        `${tx.payment_confirmed ? '✅' : '⬜️'} Payment\n` +
        `${tx.delivery_confirmed ? '✅' : '⬜️'} Delivery\n` +
        `${tx.admin_approved ? '✅' : '⬜️'} Admin Approved\n\n` +
        `Created: ${new Date(tx.created_at).toLocaleDateString()}`;

      if (tx.dispute_reason) {
        message += `\n\n⚠️ *DISPUTED*\n${tx.dispute_reason}`;
      }

      const buttons = [];
      
      if (tx.status === 'delivered' && !tx.admin_approved) {
        buttons.push([
          Markup.button.callback('✅ Approve', `admin_approve_${tx.id}`),
          Markup.button.callback('❌ Reject', `admin_reject_${tx.id}`)
        ]);
      }

      buttons.push([Markup.button.callback('📋 Full Details', `tx_${tx.id}`)]);

      await ctx.reply(message, { 
        parse_mode: 'Markdown', 
        ...Markup.inlineKeyboard(buttons)
      });
    }
  }

  // Show statistics
  async showStatistics(ctx) {
    await ctx.answerCbQuery();

    const stats = this.db.getStatistics();
    
    // Get status breakdown
    const statusBreakdown = this.db.db.prepare(`
      SELECT status, COUNT(*) as count, SUM(amount) as total
      FROM transactions
      GROUP BY status
    `).all();

    let message = `📊 *Detailed Statistics*\n\n` +
      `*Overview:*\n` +
      `👥 Total Users: ${stats.totalUsers}\n` +
      `💼 Total Transactions: ${stats.totalTransactions}\n` +
      `💰 Total Volume: $${stats.totalVolume.toFixed(2)}\n\n` +
      `*By Status:*\n`;

    for (const status of statusBreakdown) {
      const emoji = this.getStatusEmoji(status.status);
      message += `${emoji} ${status.status}: ${status.count} ($${(status.total || 0).toFixed(2)})\n`;
    }

    // Recent activity
    const recentTx = this.db.db.prepare(`
      SELECT COUNT(*) as count
      FROM transactions
      WHERE created_at > datetime('now', '-7 days')
    `).get();

    message += `\n*Recent Activity:*\n` +
      `📅 Last 7 days: ${recentTx.count} transactions`;

    const buttons = Markup.inlineKeyboard([
      [Markup.button.callback('« Back', 'admin_panel')]
    ]);

    await ctx.reply(message, { parse_mode: 'Markdown', ...buttons });
  }

  // Approve transaction
  async approveTransaction(ctx, txId) {
    await ctx.answerCbQuery('Processing...');

    const tx = this.db.getTransaction(txId);

    if (!tx) {
      return ctx.reply('❌ Transaction not found.');
    }

    if (tx.admin_approved) {
      return ctx.reply('✅ Transaction already approved.');
    }

    if (!tx.payment_confirmed || !tx.delivery_confirmed) {
      return ctx.reply('⚠️ Cannot approve: Payment or delivery not confirmed yet.');
    }

    // Approve and complete transaction
    this.db.approveRelease(txId);

    // Notify both parties
    const notifyBuyer = this.bot.telegram.sendMessage(
      tx.buyer_id,
      `✅ *Transaction Completed!*\n\n` +
      `Transaction #${txId}\n` +
      `Product: ${tx.product_title}\n` +
      `Amount: $${tx.amount.toFixed(2)}\n\n` +
      `Thank you for using our escrow service!\n` +
      `We hope to serve you again.`,
      { parse_mode: 'Markdown' }
    ).catch(err => console.error('Failed to notify buyer:', err));

    const notifySeller = this.bot.telegram.sendMessage(
      tx.seller_id,
      `💰 *Funds Released!*\n\n` +
      `Transaction #${txId}\n` +
      `Product: ${tx.product_title}\n` +
      `Amount: $${tx.amount.toFixed(2)}\n\n` +
      `The funds have been released to you.\n` +
      `Thank you for your business!`,
      { parse_mode: 'Markdown' }
    ).catch(err => console.error('Failed to notify seller:', err));

    await Promise.all([notifyBuyer, notifySeller]);

    await ctx.reply(
      `✅ *Transaction #${txId} Approved!*\n\n` +
      `Funds released to seller.\n` +
      `Both parties have been notified.`,
      { parse_mode: 'Markdown' }
    );
  }

  // Reject transaction
  async rejectTransaction(ctx, txId) {
    await ctx.answerCbQuery('Processing...');

    const tx = this.db.getTransaction(txId);

    if (!tx) {
      return ctx.reply('❌ Transaction not found.');
    }

    if (tx.admin_approved) {
      return ctx.reply('⚠️ Transaction already approved.');
    }

    // Mark as cancelled
    this.db.updateTransactionStatus(txId, 'cancelled');

    // Notify both parties
    const notifyBuyer = this.bot.telegram.sendMessage(
      tx.buyer_id,
      `❌ *Transaction Cancelled*\n\n` +
      `Transaction #${txId}\n` +
      `Product: ${tx.product_title}\n\n` +
      `This transaction has been cancelled by admin.\n` +
      `If you have any questions, please contact support.`,
      { parse_mode: 'Markdown' }
    ).catch(err => console.error('Failed to notify buyer:', err));

    const notifySeller = this.bot.telegram.sendMessage(
      tx.seller_id,
      `❌ *Transaction Cancelled*\n\n` +
      `Transaction #${txId}\n` +
      `Product: ${tx.product_title}\n\n` +
      `This transaction has been cancelled by admin.\n` +
      `If you have any questions, please contact support.`,
      { parse_mode: 'Markdown' }
    ).catch(err => console.error('Failed to notify seller:', err));

    await Promise.all([notifyBuyer, notifySeller]);

    await ctx.reply(
      `❌ *Transaction #${txId} Cancelled*\n\n` +
      `Both parties have been notified.`,
      { parse_mode: 'Markdown' }
    );
  }

  // Helper: Get status emoji
  getStatusEmoji(status) {
    const emojis = {
      'pending': '⏳',
      'paid': '💰',
      'shipped': '📦',
      'delivered': '✅',
      'completed': '🎉',
      'cancelled': '❌',
      'disputed': '⚠️'
    };
    return emojis[status] || '❓';
  }
}

// Handle admin panel callback
bot.action('admin_panel', async (ctx) => {
  if (!ctx.isAdmin) {
    return ctx.answerCbQuery('⛔ Unauthorized');
  }
  const adminHandler = new AdminHandler(ctx.db, ctx.telegram);
  await adminHandler.showAdminPanel(ctx);
});

module.exports = AdminHandler;
