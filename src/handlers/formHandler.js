const { Markup } = require('telegraf');

class FormHandler {
  constructor(db) {
    this.db = db;
  }

  // Start product listing form
  async startProductForm(ctx) {
    this.db.setSessionState(ctx.from.id, 'product_form_title', {
      step: 'title'
    });

    await ctx.reply(
      '📝 *New Product Listing*\n\n' +
      'Let\'s create your product listing. I\'ll ask you a few questions.\n\n' +
      'Step 1/3: What is the product title?',
      { 
        parse_mode: 'Markdown',
        ...Markup.keyboard([['❌ Cancel']]).resize()
      }
    );
  }

  // Handle form input based on session state
  async handleFormInput(ctx, sessionState) {
    const text = ctx.message.text;

    // Check for cancel
    if (text === '❌ Cancel') {
      this.db.clearSessionState(ctx.from.id);
      await ctx.reply('❌ Operation cancelled.', Markup.removeKeyboard());
      return;
    }

    // Route to appropriate handler
    if (sessionState.state.startsWith('product_form_')) {
      await this.handleProductForm(ctx, sessionState, text);
    } else if (sessionState.state.startsWith('purchase_form_')) {
      await this.handlePurchaseForm(ctx, sessionState, text);
    } else if (sessionState.state.startsWith('dispute_form_')) {
      await this.handleDisputeForm(ctx, sessionState, text);
    }
  }

  // Handle product listing form
  async handleProductForm(ctx, sessionState, text) {
    const data = sessionState.data || {};

    switch (sessionState.state) {
      case 'product_form_title':
        if (text.length < 3 || text.length > 100) {
          return ctx.reply('⚠️ Product title must be between 3 and 100 characters. Please try again:');
        }
        
        data.title = text;
        this.db.setSessionState(ctx.from.id, 'product_form_description', data);
        
        await ctx.reply(
          '✅ Title saved!\n\n' +
          'Step 2/3: Provide a detailed description of the product:',
          { ...Markup.keyboard([['Skip', '❌ Cancel']]).resize() }
        );
        break;

      case 'product_form_description':
        if (text === 'Skip') {
          data.description = null;
        } else if (text.length > 1000) {
          return ctx.reply('⚠️ Description is too long (max 1000 characters). Please shorten it:');
        } else {
          data.description = text;
        }
        
        this.db.setSessionState(ctx.from.id, 'product_form_price', data);
        
        await ctx.reply(
          '✅ Description saved!\n\n' +
          'Step 3/3: What is the price? (Enter number only, e.g., 99.99)',
          { ...Markup.keyboard([['❌ Cancel']]).resize() }
        );
        break;

      case 'product_form_price':
        const price = parseFloat(text);
        
        if (isNaN(price) || price <= 0) {
          return ctx.reply('⚠️ Please enter a valid price (positive number):');
        }
        
        if (price > 1000000) {
          return ctx.reply('⚠️ Price is too high. Please enter a reasonable amount:');
        }
        
        // Create product
        try {
          const result = this.db.createProduct(
            ctx.from.id,
            data.title,
            data.description,
            price
          );

          this.db.clearSessionState(ctx.from.id);

          const keyboard = Markup.keyboard([
            ['📦 Browse Products', '🛒 My Purchases'],
            ['💼 My Sales', '➕ List Product'],
            ['📊 My Transactions', '❓ Help']
          ]).resize();

          await ctx.reply(
            '✅ *Product Listed Successfully!*\n\n' +
            `*${data.title}*\n` +
            `${data.description || 'No description'}\n\n` +
            `💰 Price: $${price.toFixed(2)}\n\n` +
            `Your product is now visible to buyers!`,
            { parse_mode: 'Markdown', ...keyboard }
          );
        } catch (error) {
          console.error('Error creating product:', error);
          this.db.clearSessionState(ctx.from.id);
          await ctx.reply('❌ Failed to create product. Please try again later.', Markup.removeKeyboard());
        }
        break;
    }
  }

  // Handle purchase confirmation form
  async handlePurchaseForm(ctx, sessionState, text) {
    const data = sessionState.data || {};

    if (sessionState.state === 'purchase_form_confirm') {
      if (text.toLowerCase() === 'yes' || text.toLowerCase() === 'confirm') {
        // Create transaction
        try {
          const product = this.db.getProduct(data.productId);
          
          if (!product) {
            this.db.clearSessionState(ctx.from.id);
            return ctx.reply('❌ Product not found.', Markup.removeKeyboard());
          }

          if (product.seller_id === ctx.from.id) {
            this.db.clearSessionState(ctx.from.id);
            return ctx.reply('❌ You cannot buy your own product.', Markup.removeKeyboard());
          }

          const result = this.db.createTransaction(
            ctx.from.id,
            product.seller_id,
            product.id,
            product.title,
            product.description,
            product.price
          );

          const txId = result.lastInsertRowid;
          this.db.clearSessionState(ctx.from.id);

          // Notify seller
          const seller = this.db.getUser(product.seller_id);
          if (seller) {
            const buyerInfo = ctx.from.username ? `@${ctx.from.username}` : ctx.from.first_name;
            ctx.telegram.sendMessage(
              product.seller_id,
              `🔔 *New Purchase Order!*\n\n` +
              `Transaction #${txId}\n` +
              `Product: ${product.title}\n` +
              `Amount: $${product.price.toFixed(2)}\n` +
              `Buyer: ${buyerInfo}\n\n` +
              `Waiting for buyer to confirm payment.`,
              { parse_mode: 'Markdown' }
            ).catch(err => console.error('Failed to notify seller:', err));
          }

          const buttons = Markup.inlineKeyboard([
            [Markup.button.callback('✅ Confirm Payment', `confirm_payment_${txId}`)],
            [Markup.button.callback('📋 View Details', `tx_${txId}`)]
          ]);

          await ctx.reply(
            '✅ *Purchase Initiated!*\n\n' +
            `Transaction #${txId}\n\n` +
            '*Next Steps:*\n' +
            '1. Make the payment to the seller\n' +
            '2. Click "Confirm Payment" below\n' +
            '3. Wait for delivery confirmation\n' +
            '4. Admin will release funds to seller\n\n' +
            '⚠️ Do not confirm payment until you have actually paid!',
            { parse_mode: 'Markdown', ...buttons }
          );
        } catch (error) {
          console.error('Error creating transaction:', error);
          this.db.clearSessionState(ctx.from.id);
          await ctx.reply('❌ Failed to create transaction. Please try again later.', Markup.removeKeyboard());
        }
      } else {
        this.db.clearSessionState(ctx.from.id);
        await ctx.reply('❌ Purchase cancelled.', Markup.removeKeyboard());
      }
    }
  }

  // Handle dispute form
  async handleDisputeForm(ctx, sessionState, text) {
    const data = sessionState.data || {};

    if (sessionState.state === 'dispute_form_reason') {
      if (text.length < 10) {
        return ctx.reply('⚠️ Please provide a more detailed reason (at least 10 characters):');
      }

      try {
        this.db.createDispute(data.transactionId, text);
        this.db.clearSessionState(ctx.from.id);

        const tx = this.db.getTransaction(data.transactionId);

        // Notify admin
        const config = require('../config/config');
        for (const adminId of config.adminIds) {
          ctx.telegram.sendMessage(
            adminId,
            `⚠️ *Dispute Created!*\n\n` +
            `Transaction #${data.transactionId}\n` +
            `Product: ${tx.product_title}\n` +
            `Amount: $${tx.amount.toFixed(2)}\n\n` +
            `*Reason:*\n${text}\n\n` +
            `Please review and take action.`,
            { 
              parse_mode: 'Markdown',
              ...Markup.inlineKeyboard([
                [Markup.button.callback('📋 View Details', `tx_${data.transactionId}`)]
              ])
            }
          ).catch(err => console.error('Failed to notify admin:', err));
        }

        // Notify other party
        const otherPartyId = tx.buyer_id === ctx.from.id ? tx.seller_id : tx.buyer_id;
        ctx.telegram.sendMessage(
          otherPartyId,
          `⚠️ *Dispute Opened*\n\n` +
          `Transaction #${data.transactionId} has been disputed.\n` +
          `An admin will review the case.`,
          { parse_mode: 'Markdown' }
        ).catch(err => console.error('Failed to notify other party:', err));

        await ctx.reply(
          '✅ *Dispute Submitted*\n\n' +
          'Your dispute has been recorded and admins have been notified.\n' +
          'They will review the case and contact both parties.',
          { parse_mode: 'Markdown', ...Markup.removeKeyboard() }
        );
      } catch (error) {
        console.error('Error creating dispute:', error);
        this.db.clearSessionState(ctx.from.id);
        await ctx.reply('❌ Failed to create dispute. Please try again later.', Markup.removeKeyboard());
      }
    }
  }
}

module.exports = FormHandler;
