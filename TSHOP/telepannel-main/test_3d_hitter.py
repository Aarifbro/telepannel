#!/usr/bin/env python3
"""
Test script to verify 3D hitter integration
"""

import sys
import os

# Add the TSHOP/telepannel-main directory to path
sys.path.insert(0, '/workspaces/telepannel/TSHOP/telepannel-main')

def test_imports():
    """Test that all required imports work"""
    print("🔍 Testing imports...")
    
    try:
        from hitter_3d import register_3d_hitter_handlers
        print("✅ hitter_3d module imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import hitter_3d: {e}")
        return False
    
    try:
        import aiohttp
        print("✅ aiohttp available")
    except ImportError:
        print("❌ aiohttp not installed - run: pip install aiohttp")
        return False
    
    try:
        import telebot
        print("✅ pyTelegramBotAPI available")
    except ImportError:
        print("❌ pyTelegramBotAPI not installed - run: pip install pyTelegramBotAPI")
        return False
    
    return True

def test_functions():
    """Test that key functions are accessible"""
    print("\n🔍 Testing functions...")
    
    try:
        from hitter_3d import (
            parse_card,
            extract_checkout_url,
            get_currency_symbol,
            parse_proxy_format
        )
        
        # Test card parsing
        card = parse_card("4111111111111111|12|2027|123")
        if card and card['cc'] == '4111111111111111':
            print("✅ Card parsing works")
        else:
            print("❌ Card parsing failed")
            return False
        
        # Test URL extraction
        url = extract_checkout_url("Check this out: https://checkout.stripe.com/c/pay/cs_test_123abc")
        if url and 'checkout.stripe.com' in url:
            print("✅ URL extraction works")
        else:
            print("❌ URL extraction failed")
            return False
        
        # Test currency symbol
        symbol = get_currency_symbol("USD")
        if symbol == "$":
            print("✅ Currency symbol lookup works")
        else:
            print("❌ Currency symbol lookup failed")
            return False
        
        # Test proxy parsing
        proxy = parse_proxy_format("123.45.67.89:8080:user:pass")
        if proxy['host'] == '123.45.67.89' and proxy['port'] == 8080:
            print("✅ Proxy parsing works")
        else:
            print("❌ Proxy parsing failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Function test failed: {e}")
        return False

def test_proxy_file():
    """Test proxy file creation"""
    print("\n🔍 Testing proxy storage...")
    
    try:
        from hitter_3d import add_user_proxy, get_user_proxies, remove_user_proxy
        
        test_user_id = 999999999
        test_proxy = "127.0.0.1:8080:test:test"
        
        # Add proxy
        add_user_proxy(test_user_id, test_proxy)
        print("✅ Proxy added to storage")
        
        # Get proxies
        proxies = get_user_proxies(test_user_id)
        if test_proxy in proxies:
            print("✅ Proxy retrieval works")
        else:
            print("❌ Proxy retrieval failed")
            return False
        
        # Remove proxy
        remove_user_proxy(test_user_id, "all")
        proxies = get_user_proxies(test_user_id)
        if len(proxies) == 0:
            print("✅ Proxy removal works")
        else:
            print("❌ Proxy removal failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Proxy storage test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 50)
    print("3D Hitter Integration Test")
    print("=" * 50)
    
    all_passed = True
    
    # Test imports
    if not test_imports():
        all_passed = False
        print("\n⚠️ Import tests failed - fix dependencies first")
        return
    
    # Test functions
    if not test_functions():
        all_passed = False
    
    # Test proxy storage
    if not test_proxy_file():
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
        print("=" * 50)
        print("\n🎉 3D Hitter is ready to use!")
        print("\nQuick start:")
        print("1. /addproxy <host:port:user:pass>")
        print("2. /proxy check")
        print("3. /3d <stripe_checkout_url>")
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 50)
        print("\nPlease fix the issues above before using the 3D hitter")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
