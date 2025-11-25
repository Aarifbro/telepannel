const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

class DatabaseManager {
  constructor(dbPath) {
    // Ensure data directory exists
    const dataDir = path.dirname(dbPath);
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }

    this.db = new Database(dbPath);
    this.db.pragma('journal_mode = WAL');
    this.initializeTables();
  }

  initializeTables() {
    // Users table
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        is_admin INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        balance REAL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Products table
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seller_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        status TEXT DEFAULT 'active',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (seller_id) REFERENCES users(user_id)
      )
    `);

    // Transactions table
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        buyer_id INTEGER NOT NULL,
        seller_id INTEGER NOT NULL,
        product_id INTEGER,
        product_title TEXT NOT NULL,
        product_description TEXT,
        amount REAL NOT NULL,
        status TEXT DEFAULT 'pending',
        payment_confirmed INTEGER DEFAULT 0,
        delivery_confirmed INTEGER DEFAULT 0,
        admin_approved INTEGER DEFAULT 0,
        dispute_reason TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME,
        FOREIGN KEY (buyer_id) REFERENCES users(user_id),
        FOREIGN KEY (seller_id) REFERENCES users(user_id),
        FOREIGN KEY (product_id) REFERENCES products(id)
      )
    `);

    // Session states for form handling
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS session_states (
        user_id INTEGER PRIMARY KEY,
        state TEXT,
        data TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
      )
    `);

    // Notifications/Messages log
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        transaction_id INTEGER,
        message TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (transaction_id) REFERENCES transactions(id)
      )
    `);
  }

  // User methods
  createOrUpdateUser(userData) {
    const stmt = this.db.prepare(`
      INSERT INTO users (user_id, username, first_name, last_name, updated_at)
      VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
      ON CONFLICT(user_id) DO UPDATE SET
        username = excluded.username,
        first_name = excluded.first_name,
        last_name = excluded.last_name,
        updated_at = CURRENT_TIMESTAMP
    `);
    return stmt.run(userData.user_id, userData.username, userData.first_name, userData.last_name);
  }

  getUser(userId) {
    const stmt = this.db.prepare('SELECT * FROM users WHERE user_id = ?');
    return stmt.get(userId);
  }

  setAdmin(userId, isAdmin) {
    const stmt = this.db.prepare('UPDATE users SET is_admin = ? WHERE user_id = ?');
    return stmt.run(isAdmin ? 1 : 0, userId);
  }

  // Product methods
  createProduct(sellerId, title, description, price) {
    const stmt = this.db.prepare(`
      INSERT INTO products (seller_id, title, description, price)
      VALUES (?, ?, ?, ?)
    `);
    return stmt.run(sellerId, title, description, price);
  }

  getProduct(productId) {
    const stmt = this.db.prepare('SELECT * FROM products WHERE id = ?');
    return stmt.get(productId);
  }

  getSellerProducts(sellerId, status = 'active') {
    const stmt = this.db.prepare('SELECT * FROM products WHERE seller_id = ? AND status = ? ORDER BY created_at DESC');
    return stmt.all(sellerId, status);
  }

  getAllActiveProducts() {
    const stmt = this.db.prepare('SELECT p.*, u.username as seller_username FROM products p JOIN users u ON p.seller_id = u.user_id WHERE p.status = ? ORDER BY p.created_at DESC');
    return stmt.all('active');
  }

  // Transaction methods
  createTransaction(buyerId, sellerId, productId, productTitle, productDescription, amount) {
    const stmt = this.db.prepare(`
      INSERT INTO transactions (buyer_id, seller_id, product_id, product_title, product_description, amount)
      VALUES (?, ?, ?, ?, ?, ?)
    `);
    return stmt.run(buyerId, sellerId, productId, productTitle, productDescription, amount);
  }

  getTransaction(transactionId) {
    const stmt = this.db.prepare(`
      SELECT t.*, 
             b.username as buyer_username, b.first_name as buyer_first_name,
             s.username as seller_username, s.first_name as seller_first_name
      FROM transactions t
      JOIN users b ON t.buyer_id = b.user_id
      JOIN users s ON t.seller_id = s.user_id
      WHERE t.id = ?
    `);
    return stmt.get(transactionId);
  }

  getUserTransactions(userId, role = 'all') {
    let query = `
      SELECT t.*, 
             b.username as buyer_username,
             s.username as seller_username
      FROM transactions t
      JOIN users b ON t.buyer_id = b.user_id
      JOIN users s ON t.seller_id = s.user_id
      WHERE 1=1
    `;
    
    if (role === 'buyer') {
      query += ' AND t.buyer_id = ?';
    } else if (role === 'seller') {
      query += ' AND t.seller_id = ?';
    } else {
      query += ' AND (t.buyer_id = ? OR t.seller_id = ?)';
    }
    
    query += ' ORDER BY t.created_at DESC';
    
    const stmt = this.db.prepare(query);
    return role === 'all' ? stmt.all(userId, userId) : stmt.all(userId);
  }

  getPendingTransactions() {
    const stmt = this.db.prepare(`
      SELECT t.*, 
             b.username as buyer_username,
             s.username as seller_username
      FROM transactions t
      JOIN users b ON t.buyer_id = b.user_id
      JOIN users s ON t.seller_id = s.user_id
      WHERE t.status IN ('pending', 'paid', 'shipped')
      ORDER BY t.created_at DESC
    `);
    return stmt.all();
  }

  updateTransactionStatus(transactionId, status) {
    const stmt = this.db.prepare(`
      UPDATE transactions 
      SET status = ?, updated_at = CURRENT_TIMESTAMP
      WHERE id = ?
    `);
    return stmt.run(status, transactionId);
  }

  confirmPayment(transactionId) {
    const stmt = this.db.prepare(`
      UPDATE transactions 
      SET payment_confirmed = 1, status = 'paid', updated_at = CURRENT_TIMESTAMP
      WHERE id = ?
    `);
    return stmt.run(transactionId);
  }

  confirmDelivery(transactionId) {
    const stmt = this.db.prepare(`
      UPDATE transactions 
      SET delivery_confirmed = 1, status = 'delivered', updated_at = CURRENT_TIMESTAMP
      WHERE id = ?
    `);
    return stmt.run(transactionId);
  }

  approveRelease(transactionId) {
    const stmt = this.db.prepare(`
      UPDATE transactions 
      SET admin_approved = 1, status = 'completed', 
          completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
      WHERE id = ?
    `);
    return stmt.run(transactionId);
  }

  createDispute(transactionId, reason) {
    const stmt = this.db.prepare(`
      UPDATE transactions 
      SET status = 'disputed', dispute_reason = ?, updated_at = CURRENT_TIMESTAMP
      WHERE id = ?
    `);
    return stmt.run(reason, transactionId);
  }

  // Session state methods
  setSessionState(userId, state, data = null) {
    const stmt = this.db.prepare(`
      INSERT INTO session_states (user_id, state, data, created_at)
      VALUES (?, ?, ?, CURRENT_TIMESTAMP)
      ON CONFLICT(user_id) DO UPDATE SET
        state = excluded.state,
        data = excluded.data,
        created_at = CURRENT_TIMESTAMP
    `);
    return stmt.run(userId, state, data ? JSON.stringify(data) : null);
  }

  getSessionState(userId) {
    const stmt = this.db.prepare('SELECT * FROM session_states WHERE user_id = ?');
    const result = stmt.get(userId);
    if (result && result.data) {
      result.data = JSON.parse(result.data);
    }
    return result;
  }

  clearSessionState(userId) {
    const stmt = this.db.prepare('DELETE FROM session_states WHERE user_id = ?');
    return stmt.run(userId);
  }

  // Notification methods
  createNotification(userId, transactionId, message) {
    const stmt = this.db.prepare(`
      INSERT INTO notifications (user_id, transaction_id, message)
      VALUES (?, ?, ?)
    `);
    return stmt.run(userId, transactionId, message);
  }

  getUnreadNotifications(userId) {
    const stmt = this.db.prepare(`
      SELECT * FROM notifications 
      WHERE user_id = ? AND is_read = 0 
      ORDER BY created_at DESC
    `);
    return stmt.all(userId);
  }

  markNotificationRead(notificationId) {
    const stmt = this.db.prepare('UPDATE notifications SET is_read = 1 WHERE id = ?');
    return stmt.run(notificationId);
  }

  // Statistics
  getStatistics() {
    const totalUsers = this.db.prepare('SELECT COUNT(*) as count FROM users').get().count;
    const totalTransactions = this.db.prepare('SELECT COUNT(*) as count FROM transactions').get().count;
    const completedTransactions = this.db.prepare('SELECT COUNT(*) as count FROM transactions WHERE status = ?').get('completed').count;
    const totalVolume = this.db.prepare('SELECT SUM(amount) as total FROM transactions WHERE status = ?').get('completed').total || 0;
    const pendingTransactions = this.db.prepare('SELECT COUNT(*) as count FROM transactions WHERE status IN (?, ?, ?)').get('pending', 'paid', 'shipped').count;
    
    return {
      totalUsers,
      totalTransactions,
      completedTransactions,
      totalVolume,
      pendingTransactions
    };
  }

  close() {
    this.db.close();
  }
}

module.exports = DatabaseManager;
