import base64

import cv2
import numpy as np


MAX_LOGO_DATA_LENGTH = 120_000


def normalize_logo(content: bytes) -> str:
    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None or image.ndim not in (2, 3):
        raise ValueError("Logo must be a valid image")
    height, width = image.shape[:2]
    scale = min(1.0, 256.0 / max(height, width))
    if scale < 1.0:
        image = cv2.resize(image, (max(1, round(width * scale)), max(1, round(height * scale))), interpolation=cv2.INTER_AREA)
    ok, encoded = cv2.imencode(".webp", image, [cv2.IMWRITE_WEBP_QUALITY, 82])
    if not ok:
        raise ValueError("Logo could not be processed")
    result = "data:image/webp;base64," + base64.b64encode(encoded).decode("ascii")
    if len(result) > MAX_LOGO_DATA_LENGTH:
        raise ValueError("Logo remains too complex after compression")
    return result
