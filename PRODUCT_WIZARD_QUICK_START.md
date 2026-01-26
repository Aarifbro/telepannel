# Quick Start Guide - Product Management

## 🚀 Setup (One-Time)

```bash
# 1. Add demo products to MongoDB
cd /workspaces/telepannel
python TSHOP/telepannel-main/add_demo_products.py

# 2. Start the bot
cd TSHOP/telepannel-main
python main.py
```

---

## 👨‍💼 Admin Quick Commands

### Add a Product:
1. `/admin` → Products Management
2. Select category (e.g., Gift Cards)
3. Click "➕ Add Item"
4. Enter: Name → Price → Stock → Description
5. ✅ Done! Product is live

### Edit a Product:
1. `/admin` → Products Management
2. Select category
3. Click "✏️ Edit Item"
4. Select product
5. Choose field to edit
6. Enter new value
7. ✅ Done!

### Delete a Product:
1. `/admin` → Products Management
2. Select category
3. Click "🗑️ Remove Item"
4. Select product
5. Confirm deletion
6. ✅ Done!

---

## 🛒 User Experience

### Browse Products:
- Main Menu → Gift Cards / Accounts / RDP / etc.
- See all available products with prices and stock
- Out of stock items shown with ❌

### Purchase:
- Click on product
- Choose payment method
- Complete payment
- Product delivered automatically

---

## 📦 Product Categories

| Category | Icon | MongoDB Key | Description |
|----------|------|-------------|-------------|
| Gift Cards | 🎁 | `gift_cards` / `giftcards` | Amazon, Steam, PlayStation, etc. |
| Accounts | 👤 | `accounts` | Netflix, Spotify, Disney+, etc. |
| RDP | 🖥️ | `rdp` | Windows/Linux VPS services |
| Hacks & Tools | 🔓 | `hacks` | VPN, Trackers, Automation tools |
| Dumps | 💳 | `dumps` | Live/Charged dumps |
| CC Shop | 💎 | `custom_ccs` | Custom credit cards |
| BINs | 💳 | `bins` | BIN database |
| Methods | 📦 | `methods` | Carding methods |
| Bundles | 🎁 | `method_bins` | Method + BIN bundles |

---

## 🔧 Troubleshooting

### Products not showing?
- Check MongoDB connection in `mongodb_config.py`
- Run `add_demo_products.py` to add test products
- Check bot logs for errors

### Can't add products?
- Verify you have admin permissions
- Check user ID in `config.py` ADMIN_ID
- Add yourself as global admin in database

### Gift cards section empty?
- Run `add_demo_products.py`
- Or add products manually via wizard
- Category must be `gift_cards` or `giftcards`

### Stock not updating?
- Check `update_product_stock` function
- Verify purchase handlers call stock decrement
- Check MongoDB products collection

---

## 💡 Tips

✅ **Always test with demo products first**  
✅ **Use clear product names**  
✅ **Set realistic stock numbers**  
✅ **Add helpful descriptions**  
✅ **Monitor stock levels regularly**  
✅ **Delete old/expired products**  

---

## 📞 Support

For issues or questions:
1. Check [PRODUCT_WIZARD_COMPLETE.md](PRODUCT_WIZARD_COMPLETE.md)
2. Review bot logs
3. Test with demo products
4. Check MongoDB connection

---

## 🎯 Common Tasks

### Add 10 Gift Cards:
```python
python add_demo_products.py
# Edit script to add more gift cards
```

### Change Product Price:
1. `/admin` → Products → Gift Cards
2. Edit Item → Select product
3. Choose "💰 Price"
4. Enter new price
5. ✅ Done!

### Restock Product:
1. `/admin` → Products → Category
2. Edit Item → Select product
3. Choose "📊 Stock"
4. Enter new stock quantity
5. ✅ Done!

### Remove Out of Stock Items:
1. `/admin` → Products → Category
2. Remove Item
3. Select products with 0 stock
4. ✅ Confirm deletion

---

## ✅ Checklist

Before going live:

- [ ] MongoDB connection working
- [ ] Demo products added
- [ ] Admin permissions set
- [ ] Test adding product via wizard
- [ ] Test editing product
- [ ] Test deleting product
- [ ] Test user product browsing
- [ ] Test purchase flow
- [ ] Check stock decrements
- [ ] Verify all categories work

**System Status:** 🟢 READY FOR PRODUCTION
