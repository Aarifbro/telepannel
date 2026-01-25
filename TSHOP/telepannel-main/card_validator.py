# card_validator.py
# Advanced Card Validation System

import re
import requests
from typing import Dict, Tuple, Optional

class CardValidator:
    """Advanced card validation with Luhn check and BIN lookup"""
    
    def __init__(self):
        self.card_types = {
            '^4': 'Visa',
            '^5[1-5]': 'Mastercard',
            '^2[2-7]': 'Mastercard',
            '^3[47]': 'American Express',
            '^6(?:011|5)': 'Discover',
            '^3[0689]': 'Diners Club',
            '^35': 'JCB',
        }
        
        # BIN database (simplified - in production, use API or full database)
        self.common_bins = {
            '411111': {'bank': 'Test Card', 'country': 'US', 'type': 'Visa'},
            '431060': {'bank': 'Lloyds Bank', 'country': 'UK', 'type': 'Visa'},
            '453211': {'bank': 'Barclays', 'country': 'UK', 'type': 'Visa'},
            '532201': {'bank': 'Chase', 'country': 'US', 'type': 'Mastercard'},
            '540166': {'bank': 'Bank of America', 'country': 'US', 'type': 'Mastercard'},
        }
    
    def luhn_check(self, card_number: str) -> bool:
        """Validate card using Luhn algorithm"""
        try:
            digits = [int(d) for d in str(card_number) if d.isdigit()]
            if not digits or len(digits) < 13:
                return False
            
            checksum = 0
            reverse_digits = digits[::-1]
            
            for i, digit in enumerate(reverse_digits):
                if i % 2 == 1:
                    doubled = digit * 2
                    checksum += doubled if doubled < 10 else doubled - 9
                else:
                    checksum += digit
            
            return checksum % 10 == 0
        except:
            return False
    
    def get_card_type(self, card_number: str) -> str:
        """Identify card type from number"""
        for pattern, card_type in self.card_types.items():
            if re.match(pattern, card_number):
                return card_type
        return 'Unknown'
    
    def validate_format(self, card_data: str) -> Tuple[bool, str, Dict]:
        """
        Validate card format
        Returns: (is_valid, error_message, parsed_data)
        """
        try:
            # Parse card data
            parts = card_data.replace('/', '|').replace('-', '|').split('|')
            parts = [p.strip() for p in parts if p.strip()]
            
            if len(parts) < 4:
                return False, "❌ Invalid format. Use: CC|MM|YY|CVV", {}
            
            card_number = parts[0].replace(' ', '')
            month = parts[1]
            year = parts[2]
            cvv = parts[3]
            
            # Validate card number
            if not card_number.isdigit():
                return False, "❌ Card number must contain only digits", {}
            
            if len(card_number) < 13 or len(card_number) > 19:
                return False, "❌ Card number must be 13-19 digits", {}
            
            # Validate month
            if not month.isdigit() or not (1 <= int(month) <= 12):
                return False, "❌ Invalid month (must be 01-12)", {}
            
            # Validate year
            if not year.isdigit():
                return False, "❌ Invalid year", {}
            
            year_int = int(year)
            if len(year) == 2:
                year_int = 2000 + year_int if year_int < 50 else 1900 + year_int
            
            from datetime import datetime
            current_year = datetime.now().year
            if year_int < current_year or year_int > current_year + 20:
                return False, f"❌ Card expired or invalid year", {}
            
            # Validate CVV
            if not cvv.isdigit() or len(cvv) < 3 or len(cvv) > 4:
                return False, "❌ CVV must be 3-4 digits", {}
            
            parsed = {
                'number': card_number,
                'month': month.zfill(2),
                'year': year if len(year) == 4 else f"20{year}",
                'cvv': cvv,
                'formatted': f"{card_number}|{month.zfill(2)}|{year}|{cvv}"
            }
            
            return True, "", parsed
            
        except Exception as e:
            return False, f"❌ Parse error: {str(e)}", {}
    
    def validate_card(self, card_data: str) -> Tuple[bool, str, Dict]:
        """
        Complete card validation
        Returns: (is_valid, message, card_info)
        """
        # Check format first
        is_valid, error, parsed = self.validate_format(card_data)
        if not is_valid:
            return False, error, {}
        
        card_number = parsed['number']
        
        # Luhn check
        if not self.luhn_check(card_number):
            return False, "⚠️ Card failed Luhn check (invalid number)", {}
        
        # Get card type
        card_type = self.get_card_type(card_number)
        
        # BIN lookup
        bin_number = card_number[:6]
        bin_info = self.common_bins.get(bin_number, {
            'bank': 'Unknown',
            'country': 'Unknown',
            'type': card_type
        })
        
        card_info = {
            'number': card_number,
            'month': parsed['month'],
            'year': parsed['year'],
            'cvv': parsed['cvv'],
            'formatted': parsed['formatted'],
            'type': card_type,
            'bin': bin_number,
            'bank': bin_info.get('bank', 'Unknown'),
            'country': bin_info.get('country', 'Unknown'),
            'level': 'Unknown',
            'valid': True
        }
        
        return True, "✅ Card validated successfully", card_info
    
    def get_validation_summary(self, card_info: Dict) -> str:
        """Generate validation summary message"""
        if not card_info or not card_info.get('valid'):
            return "❌ Invalid card"
        
        return (
            f"✅ **Card Validated**\n\n"
            f"**Type:** {card_info['type']}\n"
            f"**BIN:** `{card_info['bin']}`\n"
            f"**Bank:** {card_info.get('bank', 'Unknown')}\n"
            f"**Country:** {card_info.get('country', 'Unknown')}\n"
            f"**Luhn:** ✅ Passed\n\n"
            f"**Card:** `{card_info['number'][:4]}****{card_info['number'][-4:]}`\n"
            f"**Expiry:** {card_info['month']}/{card_info['year']}"
        )


# Global instance
card_validator = CardValidator()


def validate_card(card_data: str) -> Tuple[bool, str, Dict]:
    """Easy function to validate card"""
    return card_validator.validate_card(card_data)


def quick_validate(card_data: str) -> bool:
    """Quick validation - just returns True/False"""
    is_valid, _, _ = card_validator.validate_card(card_data)
    return is_valid
