"""Bounded receipt-field encoding shared by printed and hand-drawn scanners."""

import base64

import cv2


def encode_field_crop(crop, max_width=600, max_height=96):
    if crop is None or crop.size == 0:
        return None
    gray = crop if crop.ndim == 2 else cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    scale = min(1.0, max_width / gray.shape[1], max_height / gray.shape[0])
    if scale < 1:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    ok, encoded = cv2.imencode(".webp", gray, [cv2.IMWRITE_WEBP_QUALITY, 68])
    if not ok:
        return None
    return "data:image/webp;base64," + base64.b64encode(encoded).decode("ascii")
