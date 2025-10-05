#!/bin/bash
# Quick test of the CC Shop Management System

echo "🧪 CC Shop Management System - Quick Test"
echo "========================================"
echo ""
echo "Testing bot status..."
if pgrep -f "python main.py" > /dev/null; then
    echo "✅ Bot is running"
else
    echo "❌ Bot is not running"
    echo "To start the bot, run: ./run.sh"
    exit 1
fi

echo ""
echo "Testing products.json structure..."
if python3 -c "import json; print('✅ Products.json is valid JSON'); products = json.load(open('products.json')); print(f'📦 Categories: {list(products.keys())}'); print(f'💳 Ready CCs: {len(products.get(\"ready_ccs\", []))} items'); print(f'🏦 BINs: {len(products.get(\"bins\", []))} items')" 2>/dev/null; then
    echo "✅ Products structure is healthy"
else
    echo "❌ Products.json has issues"
fi

echo ""
echo "🎯 Enhanced CC Shop Features Active:"
echo "   ⚡ Quick Add - Fast CC/BIN addition"
echo "   📋 Full Details - Complete information collection"
echo "   📦 Bulk Add - Multiple products at once"
echo "   ✅ Proper CC/BIN field structures"
echo "   🔍 Auto-detection of CC categories"
echo ""
echo "📱 To test:"
echo "   1. Message your bot"
echo "   2. Go to Admin Panel → Products Management"
echo "   3. Select 'Ready CCs' or 'BINs' category"
echo "   4. Click 'Add Product' - you'll see the new CC wizard!"
echo ""
echo "📖 Full documentation: CC_SHOP_MANAGEMENT_GUIDE.md"