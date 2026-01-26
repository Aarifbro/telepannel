#!/usr/bin/env python3
"""
Test force join configuration and bot access to channels
"""

import sys
sys.path.insert(0, '/workspaces/telepannel/TSHOP/telepannel-main')

from config import API_TOKENS, FORCE_CHANNEL_IDS, FORCE_CHANNEL_LINKS, FORCE_JOIN_FOLDER_MODE, ADMIN_ID
import telebot

def test_force_join_config():
    """Test force join configuration"""
    print("=" * 60)
    print("🔍 FORCE JOIN CONFIGURATION TEST")
    print("=" * 60)
    
    # Check configuration
    print(f"\n📋 Configuration:")
    print(f"   FORCE_JOIN_FOLDER_MODE: {FORCE_JOIN_FOLDER_MODE}")
    print(f"   Total Channels: {len(FORCE_CHANNEL_IDS)}")
    print(f"   Total Links: {len(FORCE_CHANNEL_LINKS)}")
    print(f"   Admin ID: {ADMIN_ID}")
    
    print(f"\n📂 Channels to check:")
    for i, channel_id in enumerate(FORCE_CHANNEL_IDS, 1):
        print(f"   {i}. {channel_id}")
    
    print(f"\n🔗 Force join links:")
    for i, link in enumerate(FORCE_CHANNEL_LINKS, 1):
        print(f"   {i}. {link}")
    
    # Test bot access
    print(f"\n🤖 Testing bot access to channels...")
    bot = telebot.TeleBot(API_TOKENS[0])
    
    accessible = []
    not_accessible = []
    
    for channel_id in FORCE_CHANNEL_IDS:
        try:
            chat = bot.get_chat(channel_id)
            print(f"   ✅ {channel_id}: {chat.title or 'No title'} ({chat.type})")
            accessible.append((channel_id, chat.title, chat.type))
        except Exception as e:
            error_str = str(e)
            print(f"   ❌ {channel_id}: {error_str[:80]}")
            not_accessible.append((channel_id, str(e)))
    
    # Summary
    print(f"\n" + "=" * 60)
    print(f"📊 SUMMARY")
    print("=" * 60)
    print(f"✅ Accessible: {len(accessible)}/{len(FORCE_CHANNEL_IDS)}")
    print(f"❌ Not Accessible: {len(not_accessible)}/{len(FORCE_CHANNEL_IDS)}")
    
    if accessible:
        print(f"\n✅ Accessible Channels:")
        for channel_id, title, chat_type in accessible:
            print(f"   • {title} ({channel_id}) - {chat_type}")
    
    if not_accessible:
        print(f"\n❌ Not Accessible Channels:")
        for channel_id, error in not_accessible:
            print(f"   • {channel_id}")
            print(f"     Error: {error[:100]}")
        
        print(f"\n⚠️ ACTION REQUIRED:")
        print(f"   1. Make sure bot is added to all channels/groups as ADMIN")
        print(f"   2. Check if channel IDs are correct")
        print(f"   3. Verify bot has proper permissions")
    
    # Test membership check for admin
    print(f"\n🧪 Testing membership check for admin ({ADMIN_ID})...")
    try:
        from helpers import check_force_join
        result = check_force_join(bot, ADMIN_ID)
        print(f"   Result: {'✅ PASSED' if result else '❌ FAILED'}")
        print(f"   Admin should always pass: {result}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print(f"\n" + "=" * 60)
    
    if len(accessible) == len(FORCE_CHANNEL_IDS):
        print("✅ ALL CHECKS PASSED!")
        print("   Force join is properly configured and working")
    elif len(accessible) >= len(FORCE_CHANNEL_IDS) - 1:
        print("⚠️ MOSTLY WORKING")
        print("   Some channels are not accessible but bot can still work")
    else:
        print("❌ CONFIGURATION ISSUES")
        print("   Please fix the issues above before using force join")
    
    print("=" * 60)
    
    return len(not_accessible) == 0

if __name__ == "__main__":
    try:
        success = test_force_join_config()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
