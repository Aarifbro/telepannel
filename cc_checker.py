# cc_checker.py
# Minimal stub for credit card checking logic

def check_cc(cc_string):
    """
    Dummy CC checker. Replace with real logic or API call.
    Returns a dict with at least a 'status' key.
    """
    # For demo: Approve if card ends with even digit, else Declined
    status = "Approved" if cc_string.strip()[-1] in "02468" else "Declined"
    return {
        "status": status,
        "response": "Test response for demo.",
        "bin_info": {
            "brand": "VISA",
            "type": "Credit",
            "country": "USA",
            "country_flag": "🇺🇸",
            "bank": "Test Bank"
        },
        "decline_type": "process_error" if status == "Declined" else ""
    }

def format_cc_response(cc_string, result_obj, cost=0):
    """
    Formats the CC check result for display in the bot.
    """
    status = result_obj.get("status", "Declined")
    response = result_obj.get("response", "No response.")
    decline_type = result_obj.get("decline_type") or ""
    decline_reason_map = {
        "insufficient_funds": "Insufficient funds - try another card or smaller amount.",
        "card_expired": "Card expired - update expiry date or use a different card.",
        "incorrect_cvv": "Incorrect CVV - double-check the security code.",
        "address_mismatch": "AVS mismatch - billing address did not match.",
        "process_error": "Site rejected or processor error - try later or different site.",
        "stolen_lost": "Card reported lost/stolen - cannot be used.",
        "fraud_suspected": "Suspected fraud - transaction blocked by issuer.",
    }
    decline_help = decline_reason_map.get(decline_type, "Transaction was declined by the site or issuer.")
    bin_info = result_obj.get("bin_info", {})
    brand = bin_info.get("brand", "Unknown")
    card_type = bin_info.get("type", "Unknown")
    country = bin_info.get("country", "Unknown")
    country_flag = bin_info.get("country_flag", "")
    bank = bin_info.get("bank", "Unknown")
    if status == "Approved":
        return f"<b>✅ APPROVED</b>\n\n<b>Card:</b> <code>{cc_string}</code>\n<b>Result:</b> {response}\n<b>Brand:</b> {brand} - {card_type}\n<b>Bank:</b> {bank}\n<b>Country:</b> {country} {country_flag}\n<b>Credits Used:</b> {cost}"
    else:
        return (
            f"<b>❌ DECLINED</b>\n\n"
            f"<b>Card:</b> <code>{cc_string}</code>\n"
            f"<b>Result:</b> {response}\n"
            f"<b>Reason:</b> {decline_help}\n"
            f"<b>Brand:</b> {brand} - {card_type}\n"
            f"<b>Bank:</b> {bank}\n"
            f"<b>Country:</b> {country} {country_flag}\n"
            f"<b>Credits Used:</b> {cost}"
        )
