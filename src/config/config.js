require('dotenv').config();

module.exports = {
  botToken: process.env.BOT_TOKEN,
  adminIds: process.env.ADMIN_IDS ? process.env.ADMIN_IDS.split(',').map(id => parseInt(id.trim())) : [],
  dbPath: process.env.DB_PATH || './data/escrow.db',
  botUsername: process.env.BOT_USERNAME || 'EscrowBot',
  supportChatId: process.env.SUPPORT_CHAT_ID || null,
};
