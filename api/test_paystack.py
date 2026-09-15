import hashlib
import hmac

import pytest

from paystack import validate_verified_transaction, valid_webhook_signature


def successful_transaction(*, email="learner@example.com", currency="NGN", amount=50000):
    return {
        "status": True,
        "data": {
            "status": "success",
            "currency": currency,
            "amount": amount,
            "customer": {"email": email},
        },
    }


def test_verified_transaction_requires_matching_ngn_email():
    assert validate_verified_transaction(
        successful_transaction(email="Learner@Example.com"),
        "learner@example.com",
    ) == 500

    with pytest.raises(ValueError, match="currency"):
        validate_verified_transaction(successful_transaction(currency="USD"), "learner@example.com")

    with pytest.raises(ValueError, match="email"):
        validate_verified_transaction(successful_transaction(email="other@example.com"), "learner@example.com")


def test_webhook_signature_requires_configured_secret_and_exact_digest():
    payload = b'{"event":"charge.success"}'
    secret = "sk_live_example"
    signature = hmac.new(secret.encode(), payload, hashlib.sha512).hexdigest()

    assert valid_webhook_signature(payload, signature, secret)
    assert not valid_webhook_signature(payload, signature, "")
    assert not valid_webhook_signature(payload, "not-a-signature", secret)
