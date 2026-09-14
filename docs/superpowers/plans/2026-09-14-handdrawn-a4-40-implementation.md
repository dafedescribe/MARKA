# MARKA Hand-drawn A4 40 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved ruler-drawn, reusable 40-question answer sheet and let teachers scan it through MARKA's existing batch grading workflow without changing printed R07-E behavior.

**Architecture:** Add an exact JSON layout profile and construction-guide generator, then implement an isolated OpenCV hand-drawn reader that discovers the four anchors and actual grid lines on every image. A small scanner dispatcher and optional API `layout_mode` route each queued image to the printed or hand-drawn reader while both paths share grading, persistence, and exports.

**Tech Stack:** Python 3.12, OpenCV, NumPy, ReportLab, FastAPI/Pydantic, React 19/Vite, Node's built-in test runner, pytest.

---

## Scope and file structure

The implementation is one dependent vertical feature rather than separate products. Keep each responsibility in one focused file:

- `data/handdrawn_profiles/HANDDRAWN_A4_40_V1.json` — canonical physical geometry, tolerances, and marking contract.
- `scripts/generate_handdrawn_a4_40_guide.py` — generates the teacher construction guide and a clean sample; it does not generate a sheet learners must print.
- `src/handdrawn_scanner.py` — capture checks, anchor registration, adaptive grid discovery, mark reading, and hand-drawn result/overlay generation.
- `src/scanner_dispatch.py` — validates mode names and delegates to the existing printed reader or new hand-drawn reader.
- `tests/handdrawn_synthetic.py` — deterministic synthetic sheets used only by scanner tests.
- `tests/test_handdrawn_profile.py` — geometry and guide-generator contract.
- `tests/test_handdrawn_registration.py` — anchors, orientation, capture quality, and perspective.
- `tests/test_handdrawn_grid.py` — actual line discovery and topology rejection.
- `tests/test_handdrawn_marks.py` — X/tick recognition and ambiguity behavior.
- `tests/test_scanner_dispatch.py` — backward-compatible mode routing and overlay delegation.
- `migrations/002_add_scan_layout_mode.sql` — persists the reader used for each scan.
- `api/server.py` and `api/test_server.py` — request, queue, processing, and storage integration.
- `demo_site/src/lib/scanModes.js` and `scanModes.test.js` — pure mode/payload/capture-copy contract.
- `demo_site/src/components/Dashboard.jsx` and `UploadQueue.jsx` — teacher batch-level mode selection.
- `scripts/benchmark_handdrawn_a4_40.py` — field-corpus accuracy and rejection report.
- `docs/handdrawn_a4_40_field_validation.md` — repeatable physical validation protocol and release gates.

Do not modify the algorithms inside `src/omr_scanner.py`. Printed R07-E remains the default and is protected by its existing tests plus dispatcher regressions.

### Task 1: Canonical profile and first-grade construction guide

**Files:**
- Create: `data/handdrawn_profiles/HANDDRAWN_A4_40_V1.json`
- Create: `scripts/generate_handdrawn_a4_40_guide.py`
- Create: `tests/test_handdrawn_profile.py`

- [ ] **Step 1: Write failing profile tests**

Create `tests/test_handdrawn_profile.py` with explicit geometry and generator checks:

```python
import json
from pathlib import Path

from scripts.generate_handdrawn_a4_40_guide import generate_guide


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "data/handdrawn_profiles/HANDDRAWN_A4_40_V1.json"


def load_profile():
    return json.loads(PROFILE_PATH.read_text())


def test_profile_uses_the_approved_one_centimetre_geometry():
    profile = load_profile()
    assert profile["profile_id"] == "HANDDRAWN_A4_40_V1"
    assert profile["paper"] == {"size": "A4", "orientation": "portrait", "width_mm": 210, "height_mm": 297}
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
    assert [a["id"] for a in anchors] == ["top_left", "top_right", "bottom_right", "bottom_left"]
    assert [a["bounds_mm"] for a in anchors] == [
        [10, 10, 20, 20], [190, 10, 200, 20],
        [190, 277, 200, 287], [10, 277, 20, 287],
    ]
    assert [a["orientation_x"] for a in anchors] == [True, False, False, False]


def test_every_answer_cell_is_unique_and_inside_its_grid():
    profile = load_profile()
    cells = profile["answer_cells"]
    assert len(cells) == 200
    assert len({(c["question"], c["option"]) for c in cells}) == 200
    assert all(c["width_mm"] == 10 and c["height_mm"] == 10 for c in cells)


def test_guide_generator_writes_pdf_and_png(tmp_path):
    outputs = generate_guide(PROFILE_PATH, tmp_path)
    assert outputs["pdf"].is_file()
    assert outputs["png"].is_file()
    assert outputs["pdf"].stat().st_size > 10_000
    assert outputs["png"].stat().st_size > 10_000
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```bash
./.venv/bin/python -m pytest tests/test_handdrawn_profile.py -q
```

Expected: collection fails because the profile and generator do not exist.

- [ ] **Step 3: Add the exact JSON profile**

Create the JSON with top-origin millimetre coordinates and these top-level keys:

```json
{
  "profile_id": "HANDDRAWN_A4_40_V1",
  "layout_version": 1,
  "coordinate_origin": "top_left",
  "paper": {"size": "A4", "orientation": "portrait", "width_mm": 210, "height_mm": 297},
  "questions": 40,
  "choices": ["A", "B", "C", "D", "E"],
  "cell_mm": {"width": 10, "height": 10},
  "fields": ["Name", "Student ID", "Class", "Subject", "Date"],
  "anchors": [
    {"id": "top_left", "bounds_mm": [10, 10, 20, 20], "orientation_x": true},
    {"id": "top_right", "bounds_mm": [190, 10, 200, 20], "orientation_x": false},
    {"id": "bottom_right", "bounds_mm": [190, 277, 200, 287], "orientation_x": false},
    {"id": "bottom_left", "bounds_mm": [10, 277, 20, 287], "orientation_x": false}
  ],
  "grids": [
    {"id": "left", "bounds_mm": [30, 50, 90, 250], "questions": [1, 20]},
    {"id": "right", "bounds_mm": [120, 50, 180, 250], "questions": [21, 40]}
  ],
  "marking": {
    "accepted_marks": ["x", "tick"],
    "recommended_mark": "x",
    "answer_medium": "HB_or_2B_pencil",
    "inner_margin_ratio": 0.16,
    "minimum_ink_ratio": 0.025,
    "minimum_winner_gap": 0.015
  },
  "capture": {
    "minimum_image_height_px": 1000,
    "maximum_rotation_degrees": 15,
    "maximum_perspective_ratio": 0.12,
    "minimum_cell_mm": 8,
    "maximum_cell_mm": 12
  },
  "answer_cells": []
}
```

Populate `answer_cells` deterministically: for each grid row, the first 10 mm column is the question number and the next five 10 mm columns are A–E. Each entry contains `question`, `option`, `left_mm`, `top_mm`, `width_mm`, `height_mm`, `grid_id`, `row_index`, and `choice_index`.

- [ ] **Step 4: Implement the guide generator**

Implement `generate_guide(profile_path: Path, output_dir: Path) -> dict[str, Path]` with ReportLab. Page one is the four-picture construction guide; page two is a dimensionally faithful sample. Use permanent black rules, graphite-grey sample X/ticks, large step numbers, and the exact 1 cm/3 cm/6 cm/20 cm language. Render the first page to PNG with the same PyMuPDF approach already used by `scripts/generate_v2_omr_sheet.py`.

The CLI contract is:

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/v2_prototype"))
    args = parser.parse_args()
    outputs = generate_guide(args.profile, args.output_dir)
    print(f"PDF: {outputs['pdf']}")
    print(f"PNG: {outputs['png']}")
```

Use output names `marka_handdrawn_a4_40_guide.pdf` and `marka_handdrawn_a4_40_guide.png`.

- [ ] **Step 5: Run the focused tests and generate the artifacts**

Run:

```bash
./.venv/bin/python -m pytest tests/test_handdrawn_profile.py -q
./.venv/bin/python scripts/generate_handdrawn_a4_40_guide.py
```

Expected: all profile tests pass; both output files are reported and are visually inspectable.

- [ ] **Step 6: Commit the profile and guide**

```bash
git add data/handdrawn_profiles/HANDDRAWN_A4_40_V1.json scripts/generate_handdrawn_a4_40_guide.py tests/test_handdrawn_profile.py
git commit -m "feat: add hand-drawn 40 construction profile"
```

### Task 2: Synthetic sheet factory and fail-closed page registration

**Files:**
- Create: `tests/handdrawn_synthetic.py`
- Create: `src/handdrawn_scanner.py`
- Create: `tests/test_handdrawn_registration.py`

- [ ] **Step 1: Add the deterministic synthetic sheet factory**

Create helpers with no production dependency on test code:

```python
def render_sheet(profile, marks=None, px_per_mm=5, orientation_cue=True,
                 missing_anchor=None, broken_grid_line=None,
                 cell_jitter_px=0, seed=7) -> np.ndarray:
    """Return a white BGR A4 image with outlined anchors, ruler grid, and marks."""


def transform_capture(image, rotation_degrees=0, perspective_ratio=0,
                      shadow=False, blur_sigma=0, crop_px=0) -> np.ndarray:
    """Return a reproducibly degraded phone-like capture."""
```

Draw grid/anchor rules at two pixels for the default 5 px/mm image. Draw X marks as two diagonal strokes and ticks as two connected strokes centred inside the answer cell. `seed` controls all jitter.

- [ ] **Step 2: Write registration tests before the reader**

Create `tests/test_handdrawn_registration.py`:

```python
@pytest.mark.parametrize("rotation", [0, 8, -12])
def test_registration_handles_supported_rotation(profile, tmp_path, rotation):
    image = transform_capture(render_sheet(profile), rotation_degrees=rotation)
    path = write_image(tmp_path, image)
    aligned, diagnostics = align_handdrawn_page(path, profile)
    assert aligned.shape[:2] == (1485, 1050)
    assert diagnostics["mode"] == "handdrawn-four-anchor"
    assert diagnostics["orientation_cue"] == "top_left_x"


def test_registration_handles_supported_perspective(profile, tmp_path):
    image = transform_capture(render_sheet(profile), perspective_ratio=0.10)
    aligned, diagnostics = align_handdrawn_page(write_image(tmp_path, image), profile)
    assert diagnostics["perspective_ratio"] <= 0.12


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
```

Also test height below 1,000 px, severe blur, heavy crop, and perspective above 12%; each must raise its own `HanddrawnScanError.code`.

- [ ] **Step 3: Run registration tests and confirm RED**

```bash
./.venv/bin/python -m pytest tests/test_handdrawn_registration.py -q
```

Expected: import failure because `src/handdrawn_scanner.py` is absent.

- [ ] **Step 4: Implement quality gates and anchor registration**

Create these public contracts in `src/handdrawn_scanner.py`:

```python
CANONICAL_PX_PER_MM = 5


class HanddrawnScanError(ValueError):
    def __init__(self, code: str, message: str, action: str):
        super().__init__(f"{message} {action}")
        self.code = code
        self.message = message
        self.action = action


def load_handdrawn_profile(path=DEFAULT_PROFILE_PATH) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def assess_capture_quality(gray: np.ndarray, profile: dict) -> dict:
    """Return height, sharpness, exposure and contrast or raise a corrective error."""


def detect_handdrawn_anchors(gray: np.ndarray, profile: dict) -> tuple[np.ndarray, dict]:
    """Return physical TL/TR/BR/BL anchor centres plus diagnostics."""


def align_handdrawn_page(image_or_path, profile=None) -> tuple[np.ndarray, dict]:
    """Validate, orient by the X anchor, and warp to canonical A4 pixels."""
```

Anchor implementation requirements:

- adaptive-threshold the image and collect quadrilateral contours;
- retain plausible 0.7–1.3 aspect-ratio outlined squares;
- de-duplicate nested contours by centre distance;
- select the four extremal candidates whose quadrilateral spans at least 70% of image width and height;
- measure ink inside each outline and require one clear X cue;
- treat the cue candidate as physical top-left;
- among its other corners, use shortest distance as top-right, longest as bottom-right, and the remaining point as bottom-left;
- warp those points to the profile's four canonical anchor centres; and
- reject instead of reconstructing a missing square.

- [ ] **Step 5: Run registration tests and printed scanner regressions**

```bash
./.venv/bin/python -m pytest tests/test_handdrawn_registration.py tests/test_r07_scanner.py tests/test_scanner.py -q
```

Expected: all tests pass and no printed scanner source changed.

- [ ] **Step 6: Commit registration**

```bash
git add src/handdrawn_scanner.py tests/handdrawn_synthetic.py tests/test_handdrawn_registration.py
git commit -m "feat: register hand-drawn answer sheets"
```

### Task 3: Adaptive two-grid discovery

**Files:**
- Modify: `src/handdrawn_scanner.py`
- Modify: `tests/handdrawn_synthetic.py`
- Create: `tests/test_handdrawn_grid.py`

- [ ] **Step 1: Write failing topology and variation tests**

Create tests that call `detect_handdrawn_grid(aligned, profile)` and assert:

```python
def test_detects_two_twenty_by_six_grids(profile):
    aligned = render_sheet(profile)
    grid = detect_handdrawn_grid(aligned, profile)
    assert len(grid["left"]["horizontal_lines_px"]) == 21
    assert len(grid["left"]["vertical_lines_px"]) == 7
    assert len(grid["right"]["horizontal_lines_px"]) == 21
    assert len(grid["right"]["vertical_lines_px"]) == 7


def test_uses_actual_jittered_lines_not_only_nominal_coordinates(profile):
    aligned = render_sheet(profile, cell_jitter_px=5)
    grid = detect_handdrawn_grid(aligned, profile)
    assert any(abs(found - nominal) >= 2 for found, nominal in zip(
        grid["left"]["horizontal_lines_px"], range(250, 1251, 50)
    ))


def test_missing_full_boundary_rejects_grid(profile):
    aligned = render_sheet(profile, broken_grid_line=("left", "horizontal", 8, "full"))
    with pytest.raises(HanddrawnScanError) as error:
        detect_handdrawn_grid(aligned, profile)
    assert error.value.code == "GRID_TOPOLOGY_UNSAFE"


def test_small_line_gap_is_bridged_when_intersections_agree(profile):
    aligned = render_sheet(profile, broken_grid_line=("right", "horizontal", 12, "small"))
    grid = detect_handdrawn_grid(aligned, profile)
    assert len(grid["right"]["horizontal_lines_px"]) == 21
```

- [ ] **Step 2: Run grid tests and confirm RED**

```bash
./.venv/bin/python -m pytest tests/test_handdrawn_grid.py -q
```

Expected: failure because `detect_handdrawn_grid` is not defined.

- [ ] **Step 3: Implement axis-line discovery and topology validation**

Add:

```python
def _line_projection(binary: np.ndarray, orientation: str) -> np.ndarray:
    kernel = (25, 1) if orientation == "vertical" else (1, 25)
    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones(kernel, np.uint8))
    return opened.sum(axis=0 if orientation == "vertical" else 1)


def _find_expected_lines(projection, expected_px, search_radius_px, minimum_evidence):
    found = []
    for expected in expected_px:
        start = max(0, int(expected - search_radius_px))
        stop = min(len(projection), int(expected + search_radius_px + 1))
        local = projection[start:stop]
        if local.size == 0 or float(local.max()) < minimum_evidence:
            raise HanddrawnScanError(
                "GRID_TOPOLOGY_UNSAFE",
                "The two 20-row grids could not be read safely.",
                "Check every ruler line and retake the photograph.",
            )
        found.append(start + int(np.argmax(local)))
    return found


def detect_handdrawn_grid(aligned: np.ndarray, profile: dict) -> dict:
    """Return measured 21 horizontal and seven vertical boundaries per grid."""


def build_handdrawn_cells(grid: dict, profile: dict) -> dict[int, dict[str, tuple[int, int, int, int]]]:
    """Map questions 1–40 and A–E to measured pixel rectangles."""
```

Use each grid's canonical bounds only to create a ±20 px search window around expected 1 cm boundaries. Require strictly increasing lines, 40–60 px spacing at 5 px/mm, and the exact 21-by-seven topology. Permit a small broken segment only when projection evidence and neighbouring intersections establish the same line.

- [ ] **Step 4: Run grid and registration tests**

```bash
./.venv/bin/python -m pytest tests/test_handdrawn_grid.py tests/test_handdrawn_registration.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit adaptive grid discovery**

```bash
git add src/handdrawn_scanner.py tests/handdrawn_synthetic.py tests/test_handdrawn_grid.py
git commit -m "feat: detect hand-drawn answer grids"
```

### Task 4: X/tick recognition, ambiguity, and hand-drawn overlay

**Files:**
- Modify: `src/handdrawn_scanner.py`
- Modify: `tests/handdrawn_synthetic.py`
- Create: `tests/test_handdrawn_marks.py`

- [ ] **Step 1: Write failing clear-mark and fail-closed tests**

Cover X, tick, pencil strength, blanks, double marks, erasure ghosts, shifted marks, and boundary crossing:

```python
def test_reads_clear_x_and_tick_marks(profile, tmp_path):
    marks = {1: ("B", "x"), 2: ("D", "tick"), 21: ("A", "tick"), 40: ("E", "x")}
    result = read_handdrawn(write_image(tmp_path, render_sheet(profile, marks=marks)), profile)
    assert result["marks"]["1"] == "B"
    assert result["marks"]["2"] == "D"
    assert result["marks"]["21"] == "A"
    assert result["marks"]["40"] == "E"
    assert result["registration"]["mode"] == "handdrawn-a4-40-v1"


def test_blank_rows_remain_blank(profile, tmp_path):
    result = read_handdrawn(write_image(tmp_path, render_sheet(profile)), profile)
    assert set(result["marks"].values()) == {None}


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
    assert output.is_file()
```

- [ ] **Step 2: Run mark tests and confirm RED**

```bash
./.venv/bin/python -m pytest tests/test_handdrawn_marks.py -q
```

Expected: failure because mark reading and rendering are not implemented.

- [ ] **Step 3: Implement mark scoring and the result contract**

Add these contracts:

```python
def score_handdrawn_cells(gray: np.ndarray, cells: dict, profile: dict) -> dict:
    """Return per-question A–E ink and boundary-leakage measurements."""


def classify_handdrawn_marks(scores: dict, profile: dict) -> tuple[dict, dict, dict, list]:
    """Return marks, multi_marks, confidence, and ambiguous."""


def read_handdrawn(image_or_path, profile=None) -> dict:
    """Run quality, registration, grid detection, and mark classification."""


def grade_and_render_handdrawn(marks_data, answers, image_path, profile, output_path) -> dict:
    """Re-align, rediscover cells, draw feedback, save image, and return grade summary."""
```

For each measured cell, inset by `inner_margin_ratio`, normalize its grayscale against the row's blank-cell median, and measure dark connected strokes. Count a mark only when `ink_ratio >= minimum_ink_ratio` and it leads the second choice by `minimum_winner_gap`. Treat more than one qualifying choice as `multi_marks`. Treat strong ink in the excluded boundary band as ambiguous. Compute confidence as `clip((winner_score - second_score) / (minimum_winner_gap * 3), 0, 1)`.

Return all keys used by `read_bubbles`: `sheet_id`, `marks`, `multi_marks`, `confidence`, `ambiguous`, `image_quality`, `orientation`, `registration`, `threshold_used`, `blank_median`, and `time_ms`.

The overlay reuses the existing answer-key semantics (`"A"`, lists, and `"*"`) but draws rectangles around measured hand-drawn cells rather than printed circles.

- [ ] **Step 4: Run mark, grid, and registration tests**

```bash
./.venv/bin/python -m pytest tests/test_handdrawn_marks.py tests/test_handdrawn_grid.py tests/test_handdrawn_registration.py -q
```

Expected: all hand-drawn reader tests pass.

- [ ] **Step 5: Commit mark recognition**

```bash
git add src/handdrawn_scanner.py tests/handdrawn_synthetic.py tests/test_handdrawn_marks.py
git commit -m "feat: read hand-drawn X and tick marks"
```

### Task 5: Backward-compatible scanner dispatcher

**Files:**
- Create: `src/scanner_dispatch.py`
- Create: `tests/test_scanner_dispatch.py`

- [ ] **Step 1: Write failing dispatcher tests**

Use monkeypatches so routing is tested without invoking OpenCV:

```python
from scanner_dispatch import HANDDRAWN_A4_40_V1, PRINTED_R07E, read_sheet


def test_printed_mode_is_the_default(monkeypatch):
    called = []
    monkeypatch.setattr("scanner_dispatch.read_bubbles", lambda image, layout: called.append((image, layout)) or {"registration": {"mode": "printed"}})
    result = read_sheet("sheet.jpg", printed_layout="layout.json")
    assert called == [("sheet.jpg", "layout.json")]
    assert result["registration"]["mode"] == "printed"


def test_handdrawn_mode_uses_isolated_reader(monkeypatch):
    monkeypatch.setattr("scanner_dispatch.read_handdrawn", lambda image, profile: {"registration": {"mode": "handdrawn-a4-40-v1"}})
    result = read_sheet("sheet.jpg", layout_mode=HANDDRAWN_A4_40_V1, printed_layout="layout.json")
    assert result["registration"]["mode"] == "handdrawn-a4-40-v1"


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError, match="Unsupported layout mode"):
        read_sheet("sheet.jpg", layout_mode="GUESS", printed_layout="layout.json")


def test_handdrawn_mode_rejects_answer_keys_beyond_question_40():
    with pytest.raises(ValueError, match="supports questions 1–40"):
        validate_answers_for_mode({"1": "A", "41": "B"}, HANDDRAWN_A4_40_V1)
```

Also test `grade_sheet` delegates to the matching printed or hand-drawn renderer.

- [ ] **Step 2: Run dispatcher tests and confirm RED**

```bash
./.venv/bin/python -m pytest tests/test_scanner_dispatch.py -q
```

Expected: import failure because `scanner_dispatch` is absent.

- [ ] **Step 3: Implement the small dispatch boundary**

```python
PRINTED_R07E = "PRINTED_R07E"
HANDDRAWN_A4_40_V1 = "HANDDRAWN_A4_40_V1"
SUPPORTED_LAYOUT_MODES = frozenset({PRINTED_R07E, HANDDRAWN_A4_40_V1})


def normalize_layout_mode(value=None):
    mode = (value or PRINTED_R07E).strip().upper()
    if mode not in SUPPORTED_LAYOUT_MODES:
        raise ValueError(f"Unsupported layout mode: {value}")
    return mode


def read_sheet(image_path, printed_layout, layout_mode=PRINTED_R07E):
    mode = normalize_layout_mode(layout_mode)
    if mode == HANDDRAWN_A4_40_V1:
        return read_handdrawn(image_path, load_handdrawn_profile())
    return read_bubbles(image_path, printed_layout)


def validate_answers_for_mode(answers, layout_mode=PRINTED_R07E):
    mode = normalize_layout_mode(layout_mode)
    question_numbers = {int(value) for value in answers}
    if mode == HANDDRAWN_A4_40_V1 and not question_numbers.issubset(set(range(1, 41))):
        raise ValueError("Hand-drawn 40 supports questions 1–40 only.")
    return answers


def grade_sheet(marks_data, answers, image_path, printed_layout, output_path,
                layout_mode=PRINTED_R07E):
    mode = normalize_layout_mode(layout_mode)
    validate_answers_for_mode(answers, mode)
    if mode == HANDDRAWN_A4_40_V1:
        return grade_and_render_handdrawn(
            marks_data, answers, image_path, load_handdrawn_profile(), output_path
        )
    return grade_and_render(marks_data, answers, image_path, printed_layout, output_path)
```

- [ ] **Step 4: Run dispatcher and full printed scanner tests**

```bash
./.venv/bin/python -m pytest tests/test_scanner_dispatch.py tests/test_r07_scanner.py tests/test_scanner.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit dispatcher**

```bash
git add src/scanner_dispatch.py tests/test_scanner_dispatch.py
git commit -m "feat: dispatch printed and hand-drawn scans"
```

### Task 6: Persisted API mode and queue integration

**Files:**
- Create: `migrations/002_add_scan_layout_mode.sql`
- Modify: `migrations/001_initial_schema.sql`
- Modify: `api/server.py`
- Modify: `api/test_server.py`

- [ ] **Step 1: Write failing request and queue tests**

Extend `api/test_server.py`:

```python
from pydantic import ValidationError
from server import ProcessScanRequest


def test_process_scan_defaults_to_printed_r07e():
    request = ProcessScanRequest(scan_id="scan-1", exam_code="MATH")
    assert request.layout_mode == "PRINTED_R07E"


def test_process_scan_accepts_handdrawn_mode():
    request = ProcessScanRequest(
        scan_id="scan-1", exam_code="MATH", layout_mode="HANDDRAWN_A4_40_V1"
    )
    assert request.layout_mode == "HANDDRAWN_A4_40_V1"


def test_process_scan_rejects_unknown_mode():
    with pytest.raises(ValidationError):
        ProcessScanRequest(scan_id="scan-1", exam_code="MATH", layout_mode="AUTO_GUESS")
```

Extract `_enqueue_scan(scan_id, exam_code, user_id, layout_mode)` as a small testable helper and assert that the queued tuple contains all four values.

- [ ] **Step 2: Run API tests and confirm RED**

```bash
./.venv/bin/python -m pytest api/test_server.py -q
```

Expected: request objects have no `layout_mode` and the enqueue helper is absent.

- [ ] **Step 3: Add the schema migration**

Create `migrations/002_add_scan_layout_mode.sql`:

```sql
ALTER TABLE public.scans
ADD COLUMN IF NOT EXISTS layout_mode VARCHAR NOT NULL DEFAULT 'PRINTED_R07E';

ALTER TABLE public.scans
DROP CONSTRAINT IF EXISTS scans_layout_mode_check;

ALTER TABLE public.scans
ADD CONSTRAINT scans_layout_mode_check
CHECK (layout_mode IN ('PRINTED_R07E', 'HANDDRAWN_A4_40_V1'));
```

Add the same defaulted `layout_mode` column and check constraint to `migrations/001_initial_schema.sql` so fresh databases and upgraded databases converge.

- [ ] **Step 4: Route and persist the selected mode**

In `api/server.py`:

- import `Literal` from `typing`;
- import `PRINTED_R07E`, `HANDDRAWN_A4_40_V1`, `read_sheet`, and `grade_sheet` from `scanner_dispatch`;
- add `layout_mode: Literal["PRINTED_R07E", "HANDDRAWN_A4_40_V1"] = "PRINTED_R07E"` to `ProcessScanRequest`;
- change `process_scan_background` to accept `layout_mode=PRINTED_R07E`;
- insert `layout_mode` into the processing scan row;
- replace direct `read_bubbles` and `grade_and_render` calls with the dispatcher functions;
- change the queue job to `(scan_id, exam_code, user_id, layout_mode)`; and
- have `_scan_worker` unpack all four fields.

Use this queue helper:

```python
def _enqueue_scan(scan_id, exam_code, user_id, layout_mode):
    job = (scan_id, exam_code, user_id, layout_mode)
    _scan_queue.put(job)
    return _scan_queue.qsize()
```

The endpoint calls `_enqueue_scan(req.scan_id, req.exam_code, user_id, req.layout_mode)`. Printed clients that omit the field continue to send `PRINTED_R07E`.

- [ ] **Step 5: Run API, dispatcher, and scanner tests**

```bash
./.venv/bin/python -m pytest api/test_server.py tests/test_scanner_dispatch.py tests/test_r07_scanner.py tests/test_scanner.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit API integration**

```bash
git add migrations/001_initial_schema.sql migrations/002_add_scan_layout_mode.sql api/server.py api/test_server.py
git commit -m "feat: route hand-drawn scans through grading queue"
```

### Task 7: Teacher batch-mode selector and contextual capture guidance

**Files:**
- Create: `demo_site/src/lib/scanModes.js`
- Create: `demo_site/src/lib/scanModes.test.js`
- Modify: `demo_site/src/components/Dashboard.jsx`
- Modify: `demo_site/src/components/UploadQueue.jsx`
- Modify: `demo_site/package.json`

- [ ] **Step 1: Write failing pure-JavaScript mode tests**

Create `scanModes.test.js` using `node:test` and `node:assert/strict`:

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULT_SCAN_MODE,
  HANDDRAWN_A4_40_V1,
  buildProcessScanPayload,
  captureTipsForMode,
} from './scanModes.js';

test('printed R07-E remains the default', () => {
  assert.equal(DEFAULT_SCAN_MODE, 'PRINTED_R07E');
  assert.deepEqual(buildProcessScanPayload('scan-1', 'MATH'), {
    scan_id: 'scan-1', exam_code: 'MATH', layout_mode: 'PRINTED_R07E',
  });
});

test('hand-drawn mode is preserved in the process payload', () => {
  assert.equal(buildProcessScanPayload('scan-2', 'MATH', HANDDRAWN_A4_40_V1).layout_mode,
    'HANDDRAWN_A4_40_V1');
});

test('hand-drawn capture copy teaches X or tick instead of bubble shading', () => {
  const copy = captureTipsForMode(HANDDRAWN_A4_40_V1).map((tip) => tip.desc).join(' ');
  assert.match(copy, /X or tick/i);
  assert.doesNotMatch(copy, /fully shaded/i);
});
```

- [ ] **Step 2: Add the test command and confirm RED**

Add `"test": "node --test src/lib/*.test.js"` to `demo_site/package.json`, then run:

```bash
cd demo_site && npm test
```

Expected: failure because `scanModes.js` is absent.

- [ ] **Step 3: Implement the pure scan-mode contract**

Create `scanModes.js` with frozen constants, validation, payload construction, and two capture-tip arrays:

```javascript
export const PRINTED_R07E = 'PRINTED_R07E';
export const HANDDRAWN_A4_40_V1 = 'HANDDRAWN_A4_40_V1';
export const DEFAULT_SCAN_MODE = PRINTED_R07E;

export function buildProcessScanPayload(scanId, examCode, layoutMode = DEFAULT_SCAN_MODE) {
  if (![PRINTED_R07E, HANDDRAWN_A4_40_V1].includes(layoutMode)) {
    throw new Error(`Unsupported scan mode: ${layoutMode}`);
  }
  return { scan_id: scanId, exam_code: examCode, layout_mode: layoutMode };
}

export function captureTipsForMode(layoutMode) {
  return layoutMode === HANDDRAWN_A4_40_V1
    ? [
        { title: 'Even, bright light', desc: 'No shadows across the sheet' },
        { title: 'Flat and fully in frame', desc: 'All four corner squares visible' },
        { title: 'One clear answer', desc: 'Put one X or tick inside the chosen box' },
        { title: 'Straight and in focus', desc: 'Photograph from directly above' },
      ]
    : [
        { title: 'Even, bright light', desc: 'No shadows across the sheet' },
        { title: 'Flat and fully in frame', desc: 'All four corner markers visible' },
        { title: 'Fill bubbles darkly', desc: 'Dark pencil or pen, fully shaded' },
        { title: 'Straight and in focus', desc: 'Photograph from directly above' },
      ];
}
```

- [ ] **Step 4: Wire one mode choice to the entire queue**

In `Dashboard.jsx`, add `scanMode` state initialized to `DEFAULT_SCAN_MODE`, pass `scanMode` and `setScanMode` to `UploadQueue`, and replace the process body with:

```javascript
body: JSON.stringify(buildProcessScanPayload(scanId, examCode, scanMode))
```

In `UploadQueue.jsx`, render two accessible radio-style buttons above capture guidance:

- **Printed OMR** — “Use the MARKA R07-E printed sheet.”
- **Hand-drawn 40** — “Use the ruler-drawn 1 cm grid.”

Disable the choice while `uploadQueue.length > 0` so one batch cannot mix readers. Derive capture copy from `captureTipsForMode(scanMode)`. Preserve the current icons by mapping them by array index in the component.

- [ ] **Step 5: Run frontend tests, lint, and production build**

```bash
cd demo_site && npm test
cd demo_site && npm run lint
cd demo_site && npm run build
```

Expected: Node tests pass, lint exits zero, and Vite reports a successful production build.

- [ ] **Step 6: Commit the teacher interface**

```bash
git add demo_site/src/lib/scanModes.js demo_site/src/lib/scanModes.test.js demo_site/src/components/Dashboard.jsx demo_site/src/components/UploadQueue.jsx demo_site/package.json
git commit -m "feat: select hand-drawn grading batches"
```

### Task 8: Benchmark harness, release protocol, and final verification

**Files:**
- Create: `scripts/benchmark_handdrawn_a4_40.py`
- Create: `docs/handdrawn_a4_40_field_validation.md`
- Create: `tests/test_handdrawn_benchmark.py`
- Modify: `README.md`

- [ ] **Step 1: Write a failing benchmark-summary test**

The benchmark reads a directory with `manifest.json`; each entry names an image,
expected marks, and whether registration should succeed.

```python
import json
from pathlib import Path

from handdrawn_scanner import HanddrawnScanError
from scripts import benchmark_handdrawn_a4_40 as benchmark


def test_benchmark_reports_silent_errors_and_rejections(tmp_path, monkeypatch):
    (tmp_path / "clear.png").write_bytes(b"synthetic-clear")
    (tmp_path / "missing.png").write_bytes(b"synthetic-missing")
    manifest = {
        "cases": [
            {
                "image": "clear.png",
                "expect_registration": "success",
                "expected_marks": {"1": "A", "2": "B", "3": "C", "4": "D"},
                "expected_ambiguous": [],
            },
            {
                "image": "missing.png",
                "expect_registration": "reject",
                "expected_error_code": "ANCHOR_MISSING",
                "expected_marks": {},
                "expected_ambiguous": [],
            },
        ]
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    def fake_reader(image_path, profile=None):
        if Path(image_path).name == "missing.png":
            raise HanddrawnScanError(
                "ANCHOR_MISSING", "Four anchors were not found.",
                "Include all four corner squares.",
            )
        return {
            "marks": {"1": "A", "2": "E", "3": "C", "4": "D"},
            "ambiguous": [],
            "registration": {"mode": "handdrawn-a4-40-v1"},
        }

    monkeypatch.setattr(benchmark, "read_handdrawn", fake_reader)
    report = benchmark.run_benchmark(tmp_path)
    assert report["sheets"] == 2
    assert report["clear_marks"] == 4
    assert report["silent_errors"] == 1
    assert report["registration_rejections"] == 1
    assert report["release_ready"] is False
```

- [ ] **Step 2: Run the benchmark test and confirm RED**

```bash
./.venv/bin/python -m pytest tests/test_handdrawn_benchmark.py -q
```

Expected: import failure because the benchmark script is absent.

- [ ] **Step 3: Implement the benchmark CLI**

Implement:

```python
def run_benchmark(corpus_dir: Path) -> dict:
    """Return sheet, registration, clear-mark, ambiguity, and silent-error metrics."""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = run_benchmark(args.corpus)
    print(json.dumps(report, indent=2))
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n")
    raise SystemExit(0 if report["release_ready"] else 1)
```

`release_ready` is true only when there are at least 100 independently drawn
sheets, clear-mark accuracy is at least 99.5%, silent mapping/orientation errors
equal zero, every expected registration failure is rejected, and every deliberate
double/boundary mark is ambiguous.

- [ ] **Step 4: Document the physical field protocol**

`docs/handdrawn_a4_40_field_validation.md` must specify:

- participant count and age/drawing-ability spread;
- the master guide and one-time construction timing;
- required pen, ruler, pencil, and eraser variation;
- capture matrix for phones, angles, rotation, lighting, shadows, and blur;
- clean, double, boundary, faint, and erased mark cases;
- repeated erase cycles at 1, 5, 10, and 20 uses;
- manifest format with ground truth recorded before scanning;
- benchmark command and metric definitions; and
- the exact release gates from the approved design.

Update `README.md` with the hand-drawn mode's 40-question limit, teacher-only
scan workflow, guide-generation command, test command, and benchmark command.

- [ ] **Step 5: Run the entire verification matrix**

```bash
./.venv/bin/python -m pytest -q
cd demo_site && npm test
cd demo_site && npm run lint
cd demo_site && npm run build
./.venv/bin/python scripts/generate_handdrawn_a4_40_guide.py
git diff --check
```

Expected: all Python and Node tests pass, lint and build succeed, guide PDF/PNG
are regenerated, and Git reports no whitespace errors.

- [ ] **Step 6: Perform visual and regression checks**

Inspect the generated guide PNG and PDF at 100% scale. Confirm:

- the page uses only whole-centimetre construction language;
- the four anchors are isolated and the top-left X is unmistakable;
- grids are exactly 20 rows by six columns;
- question numbers and A–E labels are readable;
- sample X/tick marks do not touch cell boundaries; and
- the guide never implies that a learner needs a phone.

Run at least one clean synthetic hand-drawn scan through the dispatcher and one
R07-E fixture through the printed default. Confirm both generate graded overlays.

- [ ] **Step 7: Commit benchmark and documentation**

```bash
git add scripts/benchmark_handdrawn_a4_40.py docs/handdrawn_a4_40_field_validation.md tests/test_handdrawn_benchmark.py README.md
git commit -m "docs: add hand-drawn release validation"
```

## Completion boundary

Code completion means the synthetic suite, API tests, frontend tests, printed OMR
regressions, guide generation, lint, and production build all pass. It does not
mean the feature is field-proven. Production release remains blocked until the
100-sheet physical corpus meets the documented benchmark gates.
