#!/bin/bash

echo "🤖 Telegram Escrow Bot - Setup Script (Python)"
echo "==============================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✅ Python found: $(python3 --version)"
echo ""

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed. Please install pip3 first."
    exit 1
fi

# Create virtual environment
echo "🔧 Creating virtual environment..."
python3 -m venv venv

if [ $? -ne 0 ]; then
    echo "❌ Failed to create virtual environment"
    exit 1
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi

echo "✅ Dependencies installed"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cat > .env << EOF
# Telegram Bot Configuration
BOT_TOKEN=your_bot_token_here
ADMIN_ID=your_telegram_user_id

# Database Configuration (optional)
DB_PATH=escrow_bot.db
EOF
    echo "✅ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env file and add:"
    echo "   1. Your bot token from @BotFather"
    echo "   2. Your Telegram user ID (get from @userinfobot)"
    echo ""
    echo "Example:"
    echo "   BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
    echo "   ADMIN_ID=123456789"
    echo ""
    read -p "Press Enter after you've edited the .env file..."
else
    echo "✅ .env file already exists"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "To start the bot, run:"
echo "   source venv/bin/activate"
echo "   python3 bot.py"
echo ""
echo "See QUICKSTART.md for testing instructions."
