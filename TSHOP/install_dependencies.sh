#!/bin/bash

echo "📦 Installing Python dependencies for Telegram Bot..."
echo ""

# Install dependencies
pip3 install --user pyTelegramBotAPI requests Flask python-dotenv aiohttp aiofiles urllib3

echo ""
echo "✅ Installation complete!"
echo ""
echo "Now run: cd TSHOP/telepannel-main && python3 main.py"
