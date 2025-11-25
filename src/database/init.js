const DatabaseManager = require('./database');
const path = require('path');

// Initialize database
const dbPath = path.join(__dirname, '../../data/escrow.db');
const db = new DatabaseManager(dbPath);

console.log('✅ Database initialized successfully!');
console.log(`📁 Database location: ${dbPath}`);
console.log('\nTables created:');
console.log('  - users');
console.log('  - products');
console.log('  - transactions');
console.log('  - session_states');
console.log('  - notifications');

db.close();

console.log('\n🚀 You can now start the bot with: npm start');
