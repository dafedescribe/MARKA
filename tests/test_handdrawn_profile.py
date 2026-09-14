import json
import subprocess
from pathlib import Path

from scripts.generate_handdrawn_a4_40_guide import generate_guide


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "data/handdrawn_profiles/HANDDRAWN_A4_40_V1.json"


def load_profile():
    return json.loads(PROFILE_PATH.read_text())


def test_profile_uses_the_approved_one_centimetre_geometry():
    profile = load_profile()
    assert profile["profile_id"] == "HANDDRAWN_A4_40_V1"
    assert profile["paper"] == {
        "size": "A4",
        "orientation": "portrait",
        "width_mm": 210,
        "height_mm": 297,
    }
    assert profile["questions"] == 40
    assert profile["choices"] == ["A", "B", "C", "D", "E"]
    assert profile["cell_mm"] == {"width": 10, "height": 10}
    assert profile["fields"] == ["Name", "Student ID", "Class", "Subject", "Date"]
    assert profile["grids"] == [
        {"id": "left", "bounds_mm": [30, 50, 90, 250], "questions": [1, 20]},
        {"id": "right", "bounds_mm": [120, 50, 180, 250], "questions": [21, 40]},
    ]


def test_profile_has_four_isolated_anchors_and_one_orientation_cue():
    profile = load_profile()
    anchors = profile["anchors"]
    assert [anchor["id"] for anchor in anchors] == [
        "top_left",
        "top_right",
        "bottom_right",
        "bottom_left",
    ]
    assert [anchor["bounds_mm"] for anchor in anchors] == [
        [10, 10, 20, 20],
        [190, 10, 200, 20],
        [190, 277, 200, 287],
        [10, 277, 20, 287],
    ]
    assert [anchor["orientation_x"] for anchor in anchors] == [True, False, False, False]


def test_every_answer_cell_is_unique_and_inside_its_grid():
    profile = load_profile()
    cells = profile["answer_cells"]
    assert len(cells) == 200
    assert len({(cell["question"], cell["option"]) for cell in cells}) == 200
    assert all(cell["width_mm"] == 10 and cell["height_mm"] == 10 for cell in cells)

    grids = {grid["id"]: grid for grid in profile["grids"]}
    for cell in cells:
        left, top, right, bottom = grids[cell["grid_id"]]["bounds_mm"]
        assert left + 10 <= cell["left_mm"] < right
        assert top <= cell["top_mm"] < bottom
        assert cell["left_mm"] + cell["width_mm"] <= right
        assert cell["top_mm"] + cell["height_mm"] <= bottom


def test_guide_generator_writes_pdf_and_png(tmp_path):
    outputs = generate_guide(PROFILE_PATH, tmp_path)
    assert outputs["pdf"].is_file()
    assert outputs["png"].is_file()
    pdf_info = subprocess.run(
        ["pdfinfo", str(outputs["pdf"])],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "Pages:           2" in pdf_info
    assert outputs["png"].stat().st_size > 10_000
