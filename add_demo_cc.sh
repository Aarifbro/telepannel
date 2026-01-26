#!/bin/bash

SSH_KEY="ttbot.pem"
SERVER_USER="ubuntu"
SERVER_IP="13.63.29.233"

chmod 400 "$SSH_KEY"

echo "================================"
echo "Adding Demo Custom CCs"
echo "================================"
echo ""

ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" << 'ENDSSH'
cd /home/ubuntu/TTbot
source venv/bin/activate

python3 << 'PYEND'
import json
import os

print("📦 Adding demo custom CC cards...")

# Load or create products.json
if os.path.exists('products.json'):
    with open('products.json', 'r') as f:
        data = json.load(f)
    print("✅ Loaded existing products.json")
else:
    data = {}
    print("✅ Creating new products.json")

# Ensure custom_ccs exists
if 'custom_ccs' not in data:
    data['custom_ccs'] = []

custom_ccs = data['custom_ccs']

# Get next ID
next_id = (max([item.get('id', 0) for item in custom_ccs]) + 1) if custom_ccs else 1

# Demo cards with different countries
demo_cards = [
    {
        "id": next_id,
        "name": "🇺🇸 US VISA Gold 4532",
        "price": 5.00,
        "bin": "453266",
        "cc": "4532********1234",
        "mm": "12",
        "yy": "27",
        "cvv": "123",
        "country": "United States",
        "country_flag": "🇺🇸",
        "country_code": "US",
        "card_type": "VISA",
        "brand": "VISA",
        "level": "GOLD",
        "bank": "Chase Bank",
        "description": "Demo US VISA Gold Card"
    },
    {
        "id": next_id + 1,
        "name": "🇬🇧 UK MasterCard Platinum 5425",
        "price": 10.00,
        "bin": "542519",
        "cc": "5425********5678",
        "mm": "06",
        "yy": "28",
        "cvv": "456",
        "country": "United Kingdom",
        "country_flag": "🇬🇧",
        "country_code": "GB",
        "card_type": "MASTERCARD",
        "brand": "MASTERCARD",
        "level": "PLATINUM",
        "bank": "Barclays Bank",
        "description": "Demo UK MasterCard Platinum"
    },
    {
        "id": next_id + 2,
        "name": "🇨🇦 Canada VISA Classic 4026",
        "price": 3.00,
        "bin": "402678",
        "cc": "4026********9012",
        "mm": "09",
        "yy": "26",
        "cvv": "789",
        "country": "Canada",
        "country_flag": "🇨🇦",
        "country_code": "CA",
        "card_type": "VISA",
        "brand": "VISA",
        "level": "CLASSIC",
        "bank": "Royal Bank of Canada",
        "description": "Demo Canada VISA Classic"
    },
    {
        "id": next_id + 3,
        "name": "🇦🇺 Australia AMEX Gold 3782",
        "price": 15.00,
        "bin": "378282",
        "cc": "3782********3456",
        "mm": "03",
        "yy": "29",
        "cvv": "234",
        "country": "Australia",
        "country_flag": "🇦🇺",
        "country_code": "AU",
        "card_type": "AMEX",
        "brand": "AMERICAN EXPRESS",
        "level": "GOLD",
        "bank": "American Express Australia",
        "description": "Demo Australia AMEX Gold"
    },
    {
        "id": next_id + 4,
        "name": "🇩🇪 Germany VISA Platinum 4716",
        "price": 12.00,
        "bin": "471622",
        "cc": "4716********7890",
        "mm": "11",
        "yy": "27",
        "cvv": "567",
        "country": "Germany",
        "country_flag": "🇩🇪",
        "country_code": "DE",
        "card_type": "VISA",
        "brand": "VISA",
        "level": "PLATINUM",
        "bank": "Deutsche Bank",
        "description": "Demo Germany VISA Platinum"
    }
]

# Add demo cards
for card in demo_cards:
    # Check if already exists (by name or BIN)
    exists = any(
        c.get('name') == card['name'] or c.get('bin') == card['bin']
        for c in custom_ccs
    )
    
    if not exists:
        custom_ccs.append(card)
        print(f"✅ Added: {card['name']} - ${card['price']}")
    else:
        print(f"⏭️  Skipped (exists): {card['name']}")

# Save
data['custom_ccs'] = custom_ccs
with open('products.json', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\n✅ Total custom CCs: {len(custom_ccs)}")
print("💾 Saved to products.json")

PYEND

echo ""
echo "Restarting bot to load new cards..."
ENDSSH

ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" "sudo systemctl restart ttbot && sleep 2 && sudo systemctl status ttbot --no-pager"

echo ""
echo "================================"
echo "✅ Demo CCs Added Successfully!"
echo "================================"
echo ""
echo "You can now test:"
echo "1. Browse Custom CCs"
echo "2. Search by BIN"
echo "3. Configure Custom CC (by country)"
echo "4. Purchase with wallet"
echo ""
