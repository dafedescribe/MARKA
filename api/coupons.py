import hashlib
import re


COUPON_PATTERN = re.compile(r"^[A-Z0-9-]{4,40}$")


def normalize_coupon_code(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if not COUPON_PATTERN.fullmatch(normalized):
        raise ValueError("Enter a valid coupon code")
    return normalized


def coupon_hash(value: str) -> str:
    return hashlib.sha256(normalize_coupon_code(value).encode("utf-8")).hexdigest()
