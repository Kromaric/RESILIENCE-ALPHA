import pytest

from app.ratelimit import SlidingWindowLimiter
from app.security import hash_api_key, mask_phone, normalize_email


@pytest.mark.parametrize(
    ("phone", "masked"),
    [
        ("+33612345678", "+33 6 •• •• •• 78"),
        ("+447911123456", "+44 •••• 56"),
    ],
)
def test_mask_phone(phone, masked):
    assert mask_phone(phone) == masked


def test_normalize_email():
    assert normalize_email("  Camille.Test@Orbe.TEST ") == "camille.test@orbe.test"


def test_hash_api_key_is_a_sha256_hex_digest():
    digest = hash_api_key("orbe_sk_test_abc")

    assert len(digest) == 64
    assert digest == hash_api_key("orbe_sk_test_abc")
    assert digest != hash_api_key("orbe_sk_test_abd")


def test_limiter_is_per_key():
    limiter = SlidingWindowLimiter(limit=2)

    assert limiter.allow("10.0.0.1")
    assert limiter.allow("10.0.0.1")
    assert not limiter.allow("10.0.0.1")
    assert limiter.allow("10.0.0.2")


def test_limiter_window_slides():
    limiter = SlidingWindowLimiter(limit=1, window_seconds=0.0)

    assert limiter.allow("10.0.0.1")
    assert limiter.allow("10.0.0.1")
