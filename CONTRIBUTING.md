# Contributing to Telegram Escrow Bot

Thank you for considering contributing to this project! This document provides guidelines for contributing.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Follow the project's coding standards

## How to Contribute

### Reporting Bugs

1. **Check existing issues** to avoid duplicates
2. **Use the bug report template**
3. **Include detailed information:**
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Screenshots if applicable
   - System information

### Suggesting Features

1. **Check if feature already exists**
2. **Open an issue with:**
   - Clear description
   - Use cases
   - Potential implementation approach
   - Why it benefits users

### Pull Requests

#### Before Starting
1. Fork the repository
2. Create a new branch from `main`
3. Discuss major changes in an issue first

#### Development Process
```bash
# Clone your fork
git clone https://github.com/yourusername/telegram-escrow-bot.git

# Create feature branch
git checkout -b feature/your-feature-name

# Make changes and commit
git add .
git commit -m "Add: your feature description"

# Push to your fork
git push origin feature/your-feature-name
```

#### Code Standards

**JavaScript Style**
- Use ES6+ features
- Follow existing code style
- Use meaningful variable names
- Add comments for complex logic
- Keep functions small and focused

**Example:**
```javascript
// Good
async function approveTransaction(transactionId, adminId) {
    try {
        await db.updateTransactionStatus(transactionId, 'APPROVED');
        await notifyParties(transactionId);
        return { success: true };
    } catch (error) {
        logger.error('Transaction approval failed:', error);
        return { success: false, error: error.message };
    }
}

// Avoid
async function approve(id, uid) {
    await db.updateTransactionStatus(id, 'APPROVED');
    await notifyParties(id);
}
```

**Database Queries**
- Use prepared statements
- Handle errors gracefully
- Close connections properly
- Add indexes for performance

**Error Handling**
- Always use try-catch blocks
- Log errors with context
- Return user-friendly messages
- Don't expose sensitive info

#### Testing
- Test your changes manually
- Add test cases for new features
- Ensure existing tests pass
- Test edge cases

#### Commit Messages
Use conventional commits format:
```
feat: add dispute resolution feature
fix: resolve database connection issue
docs: update installation guide
style: format code with prettier
refactor: simplify transaction handler
test: add tests for admin functions
```

#### Pull Request Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How to test these changes

## Checklist
- [ ] Code follows project style
- [ ] Self-reviewed code
- [ ] Commented complex code
- [ ] Updated documentation
- [ ] No new warnings
- [ ] Added tests
- [ ] All tests pass
```

## Project Structure

```
src/
├── bot.js              # Main bot file
├── config/
│   └── config.js       # Configuration
├── database/
│   ├── database.js     # Database operations
│   └── init.js         # Database initialization
└── handlers/
    ├── adminHandler.js     # Admin commands
    ├── formHandler.js      # Form handling
    └── transactionHandler.js # Transaction logic
```

## Adding New Features

### 1. New Command
```javascript
// In appropriate handler file
bot.command('newcommand', async (ctx) => {
    try {
        // Command logic here
        await ctx.reply('Response');
    } catch (error) {
        logger.error('Error in newcommand:', error);
        await ctx.reply('Error message');
    }
});
```

### 2. New Database Table
```javascript
// In database/init.js
async function createNewTable() {
    await db.run(`
        CREATE TABLE IF NOT EXISTS table_name (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field1 TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    `);
}
```

### 3. New Handler
```javascript
// Create new file in handlers/
const setupNewHandler = (bot) => {
    bot.command('command', async (ctx) => {
        // Handler logic
    });
};

module.exports = { setupNewHandler };

// Register in bot.js
const { setupNewHandler } = require('./handlers/newHandler');
setupNewHandler(bot);
```

## Development Setup

### Local Development
```bash
# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Edit .env with your credentials
nano .env

# Run bot
npm start
```

### Development Tips
- Use separate test bot for development
- Keep test data separate
- Test with multiple user roles
- Check logs regularly
- Use debugging tools

### Debugging
```javascript
// Add debug logging
const DEBUG = process.env.DEBUG === 'true';

if (DEBUG) {
    console.log('Debug info:', data);
}
```

## Documentation

### Code Documentation
```javascript
/**
 * Approves a transaction and notifies all parties
 * @param {number} transactionId - The transaction ID
 * @param {number} adminId - Admin's Telegram ID
 * @returns {Promise<boolean>} Success status
 */
async function approveTransaction(transactionId, adminId) {
    // Implementation
}
```

### README Updates
- Keep README.md up to date
- Update feature list
- Add examples for new features
- Include screenshots if relevant

## Review Process

1. **Submit PR** with clear description
2. **Automated checks** must pass
3. **Code review** by maintainers
4. **Address feedback** if any
5. **Approval and merge**

## Versioning

We use Semantic Versioning (SemVer):
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

## Release Process

1. Update version in package.json
2. Update CHANGELOG.md
3. Create release branch
4. Test thoroughly
5. Merge to main
6. Tag release
7. Deploy

## Community

- Join our Telegram group
- Follow project updates
- Help others in issues
- Share your use cases

## Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Credited in release notes
- Thanked in project README

## Questions?

- Open an issue for questions
- Ask in community chat
- Email maintainers

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing! 🎉
