import hashlib

import pytest

from api.coupons import coupon_hash, normalize_coupon_code


def test_coupon_codes_are_normalized_before_hashing():
    assert normalize_coupon_code("  marka-launch50 ") == "MARKA-LAUNCH50"
    assert coupon_hash(" marka-launch50 ") == hashlib.sha256(b"MARKA-LAUNCH50").hexdigest()


@pytest.mark.parametrize("value", ["", "A B C", "x", "A" * 41, "SAVE_50"])
def test_invalid_coupon_shapes_are_rejected(value):
    with pytest.raises(ValueError, match="valid coupon"):
        normalize_coupon_code(value)
