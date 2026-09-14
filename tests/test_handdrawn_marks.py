import json
import sys
from pathlib import Path

import cv2
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from handdrawn_scanner import grade_and_render_handdrawn, read_handdrawn
from handdrawn_synthetic import render_sheet


@pytest.fixture
def profile():
    path = ROOT / "data/handdrawn_profiles/HANDDRAWN_A4_40_V1.json"
    return json.loads(path.read_text())


def write_image(tmp_path, image, name="sheet.png"):
    path = tmp_path / name
    assert cv2.imwrite(str(path), image)
    return path


def test_reads_clear_x_and_tick_marks(profile, tmp_path):
    marks = {
        1: ("B", "x"),
        2: ("D", "tick"),
        21: ("A", "tick"),
        40: ("E", "x"),
    }
    result = read_handdrawn(write_image(tmp_path, render_sheet(profile, marks=marks)), profile)
    assert result["marks"]["1"] == "B"
    assert result["marks"]["2"] == "D"
    assert result["marks"]["21"] == "A"
    assert result["marks"]["40"] == "E"
    assert result["registration"]["mode"] == "handdrawn-a4-40-v1"


def test_blank_rows_remain_blank(profile, tmp_path):
    result = read_handdrawn(write_image(tmp_path, render_sheet(profile)), profile)
    assert set(result["marks"].values()) == {None}
    assert result["ambiguous"] == []


def test_double_mark_is_ambiguous(profile, tmp_path):
    image = render_sheet(profile, marks={7: [("B", "x"), ("E", "tick")]})
    result = read_handdrawn(write_image(tmp_path, image), profile)
    assert result["marks"]["7"] is None
    assert result["multi_marks"]["7"] == ["B", "E"]
    assert "7" in result["ambiguous"]


def test_boundary_crossing_mark_is_never_confident(profile, tmp_path):
    image = render_sheet(profile, marks={11: ("C", "x-boundary")})
    result = read_handdrawn(write_image(tmp_path, image), profile)
    assert result["marks"]["11"] is None
    assert "11" in result["ambiguous"]


def test_grading_overlay_is_written(profile, tmp_path):
    source = write_image(tmp_path, render_sheet(profile, marks={1: ("B", "x")}))
    result = read_handdrawn(source, profile)
    output = tmp_path / "graded.webp"
    summary = grade_and_render_handdrawn(result, {"1": "B"}, source, profile, output)
    assert summary["score"] == 1
    assert summary["total"] == 1
    assert output.is_file()
