import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from handdrawn_scanner import HanddrawnScanError, build_handdrawn_cells, detect_handdrawn_grid
from handdrawn_synthetic import render_sheet


@pytest.fixture
def profile():
    path = ROOT / "data/handdrawn_profiles/HANDDRAWN_A4_40_V1.json"
    return json.loads(path.read_text())


def test_detects_two_twenty_by_six_grids(profile):
    grid = detect_handdrawn_grid(render_sheet(profile), profile)
    assert len(grid["left"]["horizontal_lines_px"]) == 21
    assert len(grid["left"]["vertical_lines_px"]) == 7
    assert len(grid["right"]["horizontal_lines_px"]) == 21
    assert len(grid["right"]["vertical_lines_px"]) == 7


def test_uses_actual_jittered_lines_not_only_nominal_coordinates(profile):
    grid = detect_handdrawn_grid(render_sheet(profile, cell_jitter_px=5), profile)
    nominal = list(range(250, 1251, 50))
    assert any(
        abs(found - expected) >= 2
        for found, expected in zip(grid["left"]["horizontal_lines_px"], nominal)
    )


def test_missing_full_boundary_rejects_grid(profile):
    image = render_sheet(
        profile,
        broken_grid_line=("left", "horizontal", 8, "full"),
    )
    with pytest.raises(HanddrawnScanError) as error:
        detect_handdrawn_grid(image, profile)
    assert error.value.code == "GRID_TOPOLOGY_UNSAFE"


def test_small_line_gap_is_bridged_when_line_evidence_remains(profile):
    image = render_sheet(
        profile,
        broken_grid_line=("right", "horizontal", 12, "small"),
    )
    grid = detect_handdrawn_grid(image, profile)
    assert len(grid["right"]["horizontal_lines_px"]) == 21


def test_builds_exactly_five_answer_cells_for_every_question(profile):
    grid = detect_handdrawn_grid(render_sheet(profile), profile)
    cells = build_handdrawn_cells(grid, profile)
    assert set(cells) == set(range(1, 41))
    assert all(list(question_cells) == ["A", "B", "C", "D", "E"] for question_cells in cells.values())
    assert all(len(question_cells) == 5 for question_cells in cells.values())
