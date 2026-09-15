"""Small, testable safeguards around Paystack verification payloads."""

import hashlib
import hmac


def validate_verified_transaction(payload: dict, expected_email: str) -> float:
    """Return the paid NGN amount after validating a Paystack verify response."""
    data = payload.get("data") or {}
    if not payload.get("status") or data.get("status") != "success":
        raise ValueError("Payment was not successful")
    if data.get("currency") != "NGN":
        raise ValueError("Payment currency must be NGN")

    customer = data.get("customer") or {}
    paid_email = str(customer.get("email") or "").strip().casefold()
    if not paid_email or paid_email != expected_email.strip().casefold():
        raise ValueError("Payment email does not match the purchaser")

    amount_kobo = data.get("amount")
    if isinstance(amount_kobo, bool) or not isinstance(amount_kobo, (int, float)) or amount_kobo <= 0:
        raise ValueError("Payment amount is invalid")
    return amount_kobo / 100


def valid_webhook_signature(payload: bytes, signature: str | None, secret: str) -> bool:
    """Validate a Paystack SHA-512 webhook signature without timing leaks."""
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)
