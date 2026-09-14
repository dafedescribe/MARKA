import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import scanner_dispatch
from scanner_dispatch import (
    HANDDRAWN_A4_40_V1,
    PRINTED_R07E,
    grade_sheet,
    read_sheet,
    validate_answers_for_mode,
)


def test_printed_mode_is_the_default(monkeypatch):
    called = []
    monkeypatch.setattr(
        scanner_dispatch,
        "read_bubbles",
        lambda image, layout: called.append((image, layout))
        or {"registration": {"mode": "printed"}},
    )
    result = read_sheet("sheet.jpg", printed_layout="layout.json")
    assert called == [("sheet.jpg", "layout.json")]
    assert result["registration"]["mode"] == "printed"
    assert PRINTED_R07E == "PRINTED_R07E"


def test_handdrawn_mode_uses_isolated_reader(monkeypatch):
    monkeypatch.setattr(
        scanner_dispatch,
        "read_handdrawn",
        lambda image, profile: {"registration": {"mode": "handdrawn-a4-40-v1"}},
    )
    result = read_sheet(
        "sheet.jpg",
        layout_mode=HANDDRAWN_A4_40_V1,
        printed_layout="layout.json",
    )
    assert result["registration"]["mode"] == "handdrawn-a4-40-v1"


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError, match="Unsupported layout mode"):
        read_sheet("sheet.jpg", layout_mode="GUESS", printed_layout="layout.json")


def test_handdrawn_mode_rejects_answer_keys_beyond_question_40():
    with pytest.raises(ValueError, match="supports questions 1–40"):
        validate_answers_for_mode({"1": "A", "41": "B"}, HANDDRAWN_A4_40_V1)


def test_grade_sheet_delegates_to_handdrawn_renderer(monkeypatch, tmp_path):
    called = []
    monkeypatch.setattr(
        scanner_dispatch,
        "grade_and_render_handdrawn",
        lambda marks, answers, image, profile, output: called.append(output)
        or {"score": 1, "total": 1},
    )
    output = tmp_path / "graded.webp"
    result = grade_sheet(
        {"marks": {"1": "A"}},
        {"1": "A"},
        "sheet.jpg",
        "layout.json",
        output,
        HANDDRAWN_A4_40_V1,
    )
    assert result == {"score": 1, "total": 1}
    assert called == [output]
