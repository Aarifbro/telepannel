# Testing Guide

## Overview
This guide covers testing procedures for the Telegram Escrow Bot.

## Test Environment Setup

### 1. Create Test Bot
```bash
# Create a separate test bot with @BotFather
# Use different credentials in .env.test
```

### 2. Test Database
```bash
# The bot automatically creates a SQLite database
# For testing, use a separate database file
```

## Manual Testing Checklist

### Bot Startup
- [ ] Bot starts without errors
- [ ] Database initializes correctly
- [ ] All handlers register properly
- [ ] Welcome message displays correctly

### User Registration
- [ ] `/start` command works
- [ ] User details are saved to database
- [ ] Duplicate registration handled properly

### Transaction Creation
1. **Buyer Creates Transaction**
   - [ ] `/newtransaction` command starts form
   - [ ] Form collects all required fields
   - [ ] Transaction saves with PENDING status
   - [ ] Admin receives notification

2. **Form Validation**
   - [ ] Seller Telegram ID validation
   - [ ] Product description required
   - [ ] Amount must be positive number
   - [ ] Delivery time validation

### Admin Functions
1. **Transaction Management**
   - [ ] `/admin` shows admin panel
   - [ ] Pending transactions list correctly
   - [ ] Transaction details display properly
   - [ ] Approve button works
   - [ ] Reject button works

2. **Transaction Actions**
   - [ ] Approve: Buyer and seller both notified
   - [ ] Reject: Transaction marked correctly
   - [ ] Status changes persist in database

### Buyer Actions
1. **Confirm Delivery**
   - [ ] `/mytransactions` shows buyer's transactions
   - [ ] Active transactions display
   - [ ] Confirm delivery button appears
   - [ ] Confirmation updates status
   - [ ] Seller receives payment notification

2. **Report Issue**
   - [ ] Report issue button available
   - [ ] Issue details form appears
   - [ ] Admin receives dispute notification
   - [ ] Transaction marked as disputed

### Seller Actions
1. **View Transactions**
   - [ ] `/mysales` shows seller's transactions
   - [ ] Transaction details accurate
   - [ ] Status updates reflect correctly

2. **Mark as Shipped**
   - [ ] Ship button available for approved transactions
   - [ ] Shipping confirmation form works
   - [ ] Buyer receives notification
   - [ ] Status updates to SHIPPED

### Statistics & Reports
- [ ] `/stats` shows accurate counts
- [ ] Transaction totals calculate correctly
- [ ] User statistics display properly
- [ ] Admin statistics comprehensive

### Error Handling
- [ ] Invalid commands handled gracefully
- [ ] Database errors caught and logged
- [ ] Network errors don't crash bot
- [ ] Invalid user input validated
- [ ] Permission errors handled

### Security Tests
1. **Authorization**
   - [ ] Non-admin cannot access admin functions
   - [ ] Users can only see their own transactions
   - [ ] Transaction IDs cannot be guessed
   - [ ] Seller ID must be valid Telegram user

2. **Data Validation**
   - [ ] SQL injection attempts fail
   - [ ] XSS attempts sanitized
   - [ ] Amount manipulation prevented
   - [ ] Status changes authorized

## Automated Testing (Optional)

### Unit Tests
```javascript
// Example: Test transaction creation
const assert = require('assert');
const db = require('./src/database/database');

async function testCreateTransaction() {
    const txId = await db.createTransaction(
        12345, 67890, 'Test Product', 100, '7 days'
    );
    assert(txId > 0, 'Transaction should be created');
    console.log('✓ Transaction creation test passed');
}
```

### Integration Tests
```javascript
// Example: Test complete flow
async function testCompleteFlow() {
    // 1. Create transaction
    const txId = await db.createTransaction(...);
    
    // 2. Admin approves
    await db.updateTransactionStatus(txId, 'APPROVED');
    
    // 3. Seller ships
    await db.updateTransactionStatus(txId, 'SHIPPED');
    
    // 4. Buyer confirms
    await db.updateTransactionStatus(txId, 'COMPLETED');
    
    const tx = await db.getTransaction(txId);
    assert(tx.status === 'COMPLETED', 'Flow should complete');
    console.log('✓ Complete flow test passed');
}
```

## Load Testing

### Concurrent Users
```bash
# Test with multiple users simultaneously
# Monitor database locks and response times
```

### Database Performance
```bash
# Create 1000+ test transactions
# Test query performance
# Check index effectiveness
```

## Common Test Scenarios

### Scenario 1: Happy Path
1. Buyer creates transaction → PENDING
2. Admin approves → APPROVED
3. Seller ships product → SHIPPED
4. Buyer confirms delivery → COMPLETED

### Scenario 2: Dispute Path
1. Buyer creates transaction → PENDING
2. Admin approves → APPROVED
3. Seller ships product → SHIPPED
4. Buyer reports issue → DISPUTED
5. Admin resolves dispute

### Scenario 3: Rejection Path
1. Buyer creates transaction → PENDING
2. Admin reviews and rejects → REJECTED

### Scenario 4: Multiple Transactions
1. User creates multiple transactions
2. Mix of different statuses
3. Verify correct listing in `/mytransactions`
4. Verify correct filtering

## Bug Reporting

### Information to Include
1. **Steps to Reproduce**
2. **Expected Behavior**
3. **Actual Behavior**
4. **Screenshots/Logs**
5. **Environment Details**

### Log Files
```bash
# Check bot logs
cat bot.log

# Check for errors
grep ERROR bot.log
```

## Performance Benchmarks

### Target Metrics
- Command response time: < 500ms
- Database query time: < 100ms
- Form completion time: < 30 seconds
- Admin notification delay: < 2 seconds

## Testing Checklist Before Deployment

- [ ] All manual tests passed
- [ ] No console errors or warnings
- [ ] Database migrations successful
- [ ] Environment variables configured
- [ ] Admin user ID set correctly
- [ ] Bot token is production token
- [ ] Backup procedures tested
- [ ] Error logging working
- [ ] User notifications working
- [ ] All buttons functional
- [ ] Forms validate correctly
- [ ] Statistics accurate
- [ ] Security checks passed

## Continuous Testing

### Daily Checks
- Monitor error logs
- Check bot uptime
- Verify database integrity
- Test critical flows

### Weekly Checks
- Review transaction data
- Test new features
- Update test cases
- Performance monitoring

## Test Data Cleanup

```javascript
// Clean test data from database
async function cleanupTestData() {
    // Remove test transactions
    await db.run(`DELETE FROM transactions WHERE buyer_id < 100000`);
    
    // Remove test users
    await db.run(`DELETE FROM users WHERE telegram_id < 100000`);
    
    console.log('Test data cleaned');
}
```

## Notes
- Always test on a separate bot instance
- Never test with real money/transactions
- Keep test data separate from production
- Document any new test cases discovered
- Update this guide as features are added
