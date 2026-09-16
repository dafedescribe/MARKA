import base64

import cv2
import numpy as np
import pytest

from api.logo_profile import normalize_logo


def test_normalize_logo_returns_bounded_webp():
    image = np.full((500, 900, 3), (30, 90, 180), dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    assert ok

    result = normalize_logo(encoded.tobytes())
    assert result.startswith("data:image/webp;base64,")
    decoded = cv2.imdecode(np.frombuffer(base64.b64decode(result.split(",", 1)[1]), np.uint8), cv2.IMREAD_UNCHANGED)
    assert max(decoded.shape[:2]) <= 256
    assert len(result) <= 120_000


def test_normalize_logo_rejects_invalid_image():
    with pytest.raises(ValueError, match="valid image"):
        normalize_logo(b"not an image")
