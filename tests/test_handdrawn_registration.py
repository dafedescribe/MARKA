import json
import sys
from pathlib import Path

import cv2
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from handdrawn_scanner import HanddrawnScanError, align_handdrawn_page
from handdrawn_synthetic import render_sheet, transform_capture


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def profile():
    path = ROOT / "data/handdrawn_profiles/HANDDRAWN_A4_40_V1.json"
    return json.loads(path.read_text())


def write_image(tmp_path, image, name="sheet.png"):
    path = tmp_path / name
    assert cv2.imwrite(str(path), image)
    return path


@pytest.mark.parametrize("rotation", [0, 8, -12])
def test_registration_handles_supported_rotation(profile, tmp_path, rotation):
    image = transform_capture(render_sheet(profile), rotation_degrees=rotation)
    aligned, diagnostics = align_handdrawn_page(write_image(tmp_path, image), profile)
    assert aligned.shape[:2] == (1485, 1050)
    assert diagnostics["mode"] == "handdrawn-four-anchor"
    assert diagnostics["orientation_cue"] == "top_left_x"


def test_registration_handles_supported_perspective(profile, tmp_path):
    image = transform_capture(render_sheet(profile), perspective_ratio=0.10)
    aligned, diagnostics = align_handdrawn_page(write_image(tmp_path, image), profile)
    assert aligned.shape[:2] == (1485, 1050)
    assert diagnostics["anchor_count"] == 4


@pytest.mark.parametrize("missing", ["top_left", "top_right", "bottom_right", "bottom_left"])
def test_missing_anchor_rejects_instead_of_reconstructing(profile, tmp_path, missing):
    image = render_sheet(profile, missing_anchor=missing)
    with pytest.raises(HanddrawnScanError, match="all four corner squares") as error:
        align_handdrawn_page(write_image(tmp_path, image), profile)
    assert error.value.code == "ANCHOR_MISSING"


def test_missing_orientation_x_rejects(profile, tmp_path):
    image = render_sheet(profile, orientation_cue=False)
    with pytest.raises(HanddrawnScanError) as error:
        align_handdrawn_page(write_image(tmp_path, image), profile)
    assert error.value.code == "ORIENTATION_CUE_MISSING"


def test_low_resolution_rejects_with_action(profile, tmp_path):
    image = render_sheet(profile, px_per_mm=3)
    with pytest.raises(HanddrawnScanError) as error:
        align_handdrawn_page(write_image(tmp_path, image), profile)
    assert error.value.code == "IMAGE_TOO_SMALL"
    assert "closer" in error.value.action.lower()


def test_severe_blur_rejects_with_action(profile, tmp_path):
    image = transform_capture(render_sheet(profile), blur_sigma=12)
    with pytest.raises(HanddrawnScanError) as error:
        align_handdrawn_page(write_image(tmp_path, image), profile)
    assert error.value.code == "IMAGE_BLURRY"
    assert "steady" in error.value.action.lower()
