const { Markup } = require('telegraf');

class TransactionHandler {
  constructor(db, bot) {
    this.db = db;
    this.bot = bot;
  }

  // Get status emoji
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

  // Initiate purchase
  async initiatePurchase(ctx, productId) {
    await ctx.answerCbQuery();

    const product = this.db.getProduct(productId);

    if (!product) {
      return ctx.reply('❌ Product not found or no longer available.');
    }

    if (product.seller_id === ctx.from.id) {
      return ctx.reply('❌ You cannot buy your own product.');
    }

    if (product.status !== 'active') {
      return ctx.reply('❌ This product is no longer available.');
    }

    const seller = this.db.getUser(product.seller_id);
    const sellerName = seller.username ? `@${seller.username}` : seller.first_name;

    this.db.setSessionState(ctx.from.id, 'purchase_form_confirm', {
      productId: product.id
    });

    await ctx.reply(
      '🛒 *Purchase Confirmation*\n\n' +
      `*Product:* ${product.title}\n` +
      `*Description:* ${product.description || 'N/A'}\n` +
      `*Price:* $${product.price.toFixed(2)}\n` +
      `*Seller:* ${sellerName}\n\n` +
      '⚠️ *Important:*\n' +
      '• Funds will be held in escrow\n' +
      '• Release only after delivery confirmation\n' +
      '• Admin mediates any disputes\n\n' +
      'Type "confirm" or "yes" to proceed, or anything else to cancel:',
      { 
        parse_mode: 'Markdown',
        ...Markup.keyboard([['Confirm', 'Cancel']]).resize()
      }
    );
  }

  // Show transaction details
  async showTransactionDetails(ctx, txId) {
    await ctx.answerCbQuery();

    const tx = this.db.getTransaction(txId);

    if (!tx) {
      return ctx.reply('❌ Transaction not found.');
    }

    // Check if user is involved in transaction
    if (tx.buyer_id !== ctx.from.id && tx.seller_id !== ctx.from.id && !ctx.isAdmin) {
      return ctx.reply('⛔ You are not authorized to view this transaction.');
    }

    const role = tx.buyer_id === ctx.from.id ? 'BUYER' : 'SELLER';
    const otherParty = role === 'BUYER' ? 
      (tx.seller_username ? `@${tx.seller_username}` : tx.seller_first_name) :
      (tx.buyer_username ? `@${tx.buyer_username}` : tx.buyer_first_name);

    const statusEmoji = this.getStatusEmoji(tx.status);

    let message = `${statusEmoji} *Transaction #${tx.id}*\n\n` +
      `*Your Role:* ${role}\n` +
      `*${role === 'BUYER' ? 'Seller' : 'Buyer'}:* ${otherParty}\n\n` +
      `*Product:* ${tx.product_title}\n` +
      `*Amount:* $${tx.amount.toFixed(2)}\n` +
      `*Status:* ${tx.status.toUpperCase()}\n\n` +
      `*Timeline:*\n` +
      `Created: ${new Date(tx.created_at).toLocaleString()}\n`;

    if (tx.updated_at !== tx.created_at) {
      message += `Updated: ${new Date(tx.updated_at).toLocaleString()}\n`;
    }

    if (tx.completed_at) {
      message += `Completed: ${new Date(tx.completed_at).toLocaleString()}\n`;
    }

    message += '\n*Progress:*\n';
    message += tx.payment_confirmed ? '✅' : '⬜️';
    message += ' Payment Confirmed\n';
    message += tx.delivery_confirmed ? '✅' : '⬜️';
    message += ' Delivery Confirmed\n';
    message += tx.admin_approved ? '✅' : '⬜️';
    message += ' Admin Approved\n';

    if (tx.dispute_reason) {
      message += `\n⚠️ *Dispute Reason:*\n${tx.dispute_reason}`;
    }

    // Action buttons based on status and role
    const buttons = this.getTransactionButtons(tx, role, ctx.isAdmin);

    await ctx.reply(message, { parse_mode: 'Markdown', ...buttons });
  }

  // Get action buttons for transaction
  getTransactionButtons(tx, role, isAdmin) {
    const buttons = [];

    if (tx.status === 'pending' && role === 'BUYER' && !tx.payment_confirmed) {
      buttons.push([Markup.button.callback('✅ Confirm Payment', `confirm_payment_${tx.id}`)]);
    }

    if (tx.status === 'paid' && role === 'SELLER' && !tx.delivery_confirmed) {
      buttons.push([Markup.button.callback('📦 Confirm Delivery', `confirm_delivery_${tx.id}`)]);
    }

    if (tx.status === 'delivered' && role === 'BUYER') {
      buttons.push([Markup.button.callback('✅ Confirm Receipt', `confirm_delivery_${tx.id}`)]);
    }

    if (['paid', 'shipped', 'delivered'].includes(tx.status) && !tx.dispute_reason) {
      buttons.push([Markup.button.callback('⚠️ Open Dispute', `dispute_${tx.id}`)]);
    }

    if (isAdmin && tx.status === 'delivered' && !tx.admin_approved) {
      buttons.push([
        Markup.button.callback('✅ Approve Release', `admin_approve_${tx.id}`),
        Markup.button.callback('❌ Reject', `admin_reject_${tx.id}`)
      ]);
    }

    return buttons.length > 0 ? Markup.inlineKeyboard(buttons) : {};
  }

  // Confirm payment
  async confirmPayment(ctx, txId) {
    await ctx.answerCbQuery();

    const tx = this.db.getTransaction(txId);

    if (!tx) {
      return ctx.reply('❌ Transaction not found.');
    }

    if (tx.buyer_id !== ctx.from.id) {
      return ctx.reply('⛔ Only the buyer can confirm payment.');
    }

    if (tx.payment_confirmed) {
      return ctx.reply('✅ Payment already confirmed.');
    }

    this.db.confirmPayment(txId);

    // Notify seller
    const buyerInfo = ctx.from.username ? `@${ctx.from.username}` : ctx.from.first_name;
    this.bot.telegram.sendMessage(
      tx.seller_id,
      `💰 *Payment Confirmed!*\n\n` +
      `Transaction #${txId}\n` +
      `Product: ${tx.product_title}\n` +
      `Amount: $${tx.amount.toFixed(2)}\n\n` +
      `${buyerInfo} has confirmed payment.\n` +
      `Please ship the product and confirm delivery.`,
      { 
        parse_mode: 'Markdown',
        ...Markup.inlineKeyboard([
          [Markup.button.callback('📦 Confirm Delivery', `confirm_delivery_${txId}`)],
          [Markup.button.callback('📋 View Details', `tx_${txId}`)]
        ])
      }
    ).catch(err => console.error('Failed to notify seller:', err));

    await ctx.reply(
      '✅ *Payment Confirmed!*\n\n' +
      `Transaction #${txId}\n\n` +
      'The seller has been notified.\n' +
      'You will be notified when the product is shipped.',
      { parse_mode: 'Markdown' }
    );
  }

  // Confirm delivery
  async confirmDelivery(ctx, txId) {
    await ctx.answerCbQuery();

    const tx = this.db.getTransaction(txId);

    if (!tx) {
      return ctx.reply('❌ Transaction not found.');
    }

    // Seller confirms shipped, buyer confirms received
    if (tx.seller_id === ctx.from.id && !tx.delivery_confirmed) {
      this.db.confirmDelivery(txId);

      // Notify buyer
      const sellerInfo = ctx.from.username ? `@${ctx.from.username}` : ctx.from.first_name;
      this.bot.telegram.sendMessage(
        tx.buyer_id,
        `📦 *Product Shipped!*\n\n` +
        `Transaction #${txId}\n` +
        `Product: ${tx.product_title}\n\n` +
        `${sellerInfo} has confirmed shipment.\n` +
        `Please confirm when you receive the product.`,
        { 
          parse_mode: 'Markdown',
          ...Markup.inlineKeyboard([
            [Markup.button.callback('✅ Confirm Receipt', `confirm_delivery_${txId}`)],
            [Markup.button.callback('📋 View Details', `tx_${txId}`)]
          ])
        }
      ).catch(err => console.error('Failed to notify buyer:', err));

      // Notify admin
      const config = require('../config/config');
      for (const adminId of config.adminIds) {
        this.bot.telegram.sendMessage(
          adminId,
          `📦 *Delivery Confirmation Pending*\n\n` +
          `Transaction #${txId}\n` +
          `Product: ${tx.product_title}\n` +
          `Amount: $${tx.amount.toFixed(2)}\n\n` +
          `Seller has shipped. Waiting for buyer confirmation.`,
          { 
            parse_mode: 'Markdown',
            ...Markup.inlineKeyboard([
              [Markup.button.callback('📋 View Details', `tx_${txId}`)]
            ])
          }
        ).catch(err => console.error('Failed to notify admin:', err));
      }

      await ctx.reply(
        '✅ *Shipment Confirmed!*\n\n' +
        `Transaction #${txId}\n\n` +
        'The buyer has been notified.\n' +
        'Funds will be released after buyer confirms receipt and admin approves.',
        { parse_mode: 'Markdown' }
      );
    } else if (tx.buyer_id === ctx.from.id && tx.delivery_confirmed) {
      // Buyer confirms receipt
      this.db.updateTransactionStatus(txId, 'delivered');

      // Notify seller and admin
      const buyerInfo = ctx.from.username ? `@${ctx.from.username}` : ctx.from.first_name;
      
      this.bot.telegram.sendMessage(
        tx.seller_id,
        `✅ *Delivery Confirmed!*\n\n` +
        `Transaction #${txId}\n` +
        `Product: ${tx.product_title}\n\n` +
        `${buyerInfo} has confirmed receipt.\n` +
        `Waiting for admin to release funds.`,
        { 
          parse_mode: 'Markdown',
          ...Markup.inlineKeyboard([
            [Markup.button.callback('📋 View Details', `tx_${txId}`)]
          ])
        }
      ).catch(err => console.error('Failed to notify seller:', err));

      // Notify admin
      const config = require('../config/config');
      for (const adminId of config.adminIds) {
        this.bot.telegram.sendMessage(
          adminId,
          `✅ *Ready for Fund Release*\n\n` +
          `Transaction #${txId}\n` +
          `Product: ${tx.product_title}\n` +
          `Amount: $${tx.amount.toFixed(2)}\n\n` +
          `Both parties confirmed. Please approve fund release.`,
          { 
            parse_mode: 'Markdown',
            ...Markup.inlineKeyboard([
              [Markup.button.callback('✅ Approve', `admin_approve_${txId}`)],
              [Markup.button.callback('📋 Details', `tx_${txId}`)]
            ])
          }
        ).catch(err => console.error('Failed to notify admin:', err));
      }

      await ctx.reply(
        '✅ *Receipt Confirmed!*\n\n' +
        `Transaction #${txId}\n\n` +
        'Thank you for confirming receipt!\n' +
        'Admin will review and release funds to the seller.',
        { parse_mode: 'Markdown' }
      );
    } else {
      return ctx.reply('⚠️ Cannot perform this action at this time.');
    }
  }

  // Start dispute
  async startDispute(ctx, txId) {
    await ctx.answerCbQuery();

    const tx = this.db.getTransaction(txId);

    if (!tx) {
      return ctx.reply('❌ Transaction not found.');
    }

    if (tx.buyer_id !== ctx.from.id && tx.seller_id !== ctx.from.id) {
      return ctx.reply('⛔ You are not authorized to dispute this transaction.');
    }

    if (tx.status === 'completed' || tx.status === 'cancelled') {
      return ctx.reply('❌ This transaction is already closed.');
    }

    if (tx.dispute_reason) {
      return ctx.reply('⚠️ A dispute is already open for this transaction.');
    }

    this.db.setSessionState(ctx.from.id, 'dispute_form_reason', {
      transactionId: txId
    });

    await ctx.reply(
      '⚠️ *Open Dispute*\n\n' +
      `Transaction #${txId}\n\n` +
      'Please describe the issue in detail.\n' +
      'An admin will review your dispute and mediate.\n\n' +
      'Type your reason:',
      { 
        parse_mode: 'Markdown',
        ...Markup.keyboard([['❌ Cancel']]).resize()
      }
    );
  }
}

module.exports = TransactionHandler;
