#!/usr/bin/env python3
"""
Migrate all remaining JSON files to MongoDB
Run this once to move all JSON data to MongoDB collections
"""

import json
import os
from database_mongodb import (
    update_config, update_support_settings, set_section_status,
    update_gift_card_status, set_force_link_cache, set_proxies,
    set_bgmi_accounts, add_service_account, set_referrals
)

def migrate_json_file(filename, handler_func, collection_name):
    """Generic migration function"""
    if not os.path.exists(filename):
        print(f"   ⚠️  {filename} not found, skipping")
        return False
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        result = handler_func(data)
        if result:
            print(f"   ✅ Migrated {filename} to {collection_name}")
            # Rename file to .bak
            os.rename(filename, f"{filename}.bak")
            return True
        else:
            print(f"   ❌ Failed to migrate {filename}")
            return False
    except Exception as e:
        print(f"   ❌ Error migrating {filename}: {e}")
        return False

def main():
    print("=" * 60)
    print("📦 Migrating JSON Files to MongoDB")
    print("=" * 60)
    
    migrations_done = 0
    migrations_failed = 0
    
    # 1. Config.json
    print("\n1. Migrating config.json...")
    if migrate_json_file("config.json", update_config, "config_collection"):
        migrations_done += 1
    else:
        migrations_failed += 1
    
    # 2. Support Settings
    print("\n2. Migrating support_settings.json...")
    if migrate_json_file("support_settings.json", update_support_settings, "support_settings_collection"):
        migrations_done += 1
    else:
        migrations_failed += 1
    
    # 3. Section Status
    print("\n3. Migrating section_status.json...")
    if os.path.exists("section_status.json"):
        try:
            with open("section_status.json", 'r') as f:
                section_data = json.load(f)
            
            for section, enabled in section_data.items():
                set_section_status(section, enabled)
            
            print(f"   ✅ Migrated section_status.json to section_status_collection")
            os.rename("section_status.json", "section_status.json.bak")
            migrations_done += 1
        except Exception as e:
            print(f"   ❌ Error: {e}")
            migrations_failed += 1
    else:
        print("   ⚠️  section_status.json not found, skipping")
        migrations_failed += 1
    
    # 4. Gift Card Status
    print("\n4. Migrating gift_card_status.json...")
    if migrate_json_file("gift_card_status.json", update_gift_card_status, "gift_card_status_collection"):
        migrations_done += 1
    else:
        migrations_failed += 1
    
    # 5. Force Links Cache
    print("\n5. Migrating force_links_cache.json...")
    if os.path.exists("force_links_cache.json"):
        try:
            with open("force_links_cache.json", 'r') as f:
                cache_data = json.load(f)
            
            for link_id, data in cache_data.items():
                set_force_link_cache(link_id, data)
            
            print(f"   ✅ Migrated force_links_cache.json to force_links_cache_collection")
            os.rename("force_links_cache.json", "force_links_cache.json.bak")
            migrations_done += 1
        except Exception as e:
            print(f"   ❌ Error: {e}")
            migrations_failed += 1
    else:
        print("   ⚠️  force_links_cache.json not found, skipping")
        migrations_failed += 1
    
    # 6. Proxies
    print("\n6. Migrating proxies.json...")
    if os.path.exists("proxies.json"):
        try:
            with open("proxies.json", 'r') as f:
                proxies_data = json.load(f)
            
            # Handle both list and dict formats
            if isinstance(proxies_data, list):
                set_proxies(proxies_data)
            elif isinstance(proxies_data, dict):
                proxy_list = proxies_data.get("proxies", [])
                set_proxies(proxy_list)
            
            print(f"   ✅ Migrated proxies.json to proxies_collection")
            os.rename("proxies.json", "proxies.json.bak")
            migrations_done += 1
        except Exception as e:
            print(f"   ❌ Error: {e}")
            migrations_failed += 1
    else:
        print("   ⚠️  proxies.json not found, skipping")
        migrations_failed += 1
    
    # 7. BGMI Accounts
    print("\n7. Migrating bgmi_accounts.json...")
    if os.path.exists("bgmi_accounts.json"):
        try:
            with open("bgmi_accounts.json", 'r') as f:
                bgmi_data = json.load(f)
            
            # Handle both list and dict formats
            if isinstance(bgmi_data, list):
                set_bgmi_accounts(bgmi_data)
            elif isinstance(bgmi_data, dict):
                accounts = bgmi_data.get("accounts", [])
                set_bgmi_accounts(accounts)
            
            print(f"   ✅ Migrated bgmi_accounts.json to bgmi_accounts_collection")
            os.rename("bgmi_accounts.json", "bgmi_accounts.json.bak")
            migrations_done += 1
        except Exception as e:
            print(f"   ❌ Error: {e}")
            migrations_failed += 1
    else:
        print("   ⚠️  bgmi_accounts.json not found, skipping")
        migrations_failed += 1
    
    # 8. Service Accounts
    print("\n8. Migrating accounts/accounts_db.json...")
    if os.path.exists("accounts/accounts_db.json"):
        try:
            with open("accounts/accounts_db.json", 'r') as f:
                accounts_data = json.load(f)
            
            # Handle different formats
            if isinstance(accounts_data, dict):
                for service, accounts in accounts_data.items():
                    if isinstance(accounts, list):
                        for account in accounts:
                            add_service_account(service, account)
            
            print(f"   ✅ Migrated accounts/accounts_db.json to accounts_db_collection")
            os.rename("accounts/accounts_db.json", "accounts/accounts_db.json.bak")
            migrations_done += 1
        except Exception as e:
            print(f"   ❌ Error: {e}")
            migrations_failed += 1
    else:
        print("   ⚠️  accounts/accounts_db.json not found, skipping")
        migrations_failed += 1
    
    # 9. Referrals DB
    print("\n9. Migrating accounts/referrals_db.json...")
    if migrate_json_file("accounts/referrals_db.json", set_referrals, "referrals_db_collection"):
        migrations_done += 1
    else:
        migrations_failed += 1
    
    # Summary
    print("\n" + "=" * 60)
    print(f"✅ Migration Complete!")
    print(f"   Successful: {migrations_done}")
    print(f"   Failed/Skipped: {migrations_failed}")
    print("=" * 60)
    print("\n📝 Note: Original files renamed to .bak")
    print("   You can delete .bak files once you verify everything works")
    print("\n🚀 All data is now in MongoDB!")

if __name__ == "__main__":
    main()
