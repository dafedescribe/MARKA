# MARKA R07-E Compact Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Maximize printed legibility within MARKA's existing two-forms-per-A4, 100-question format without weakening scanner geometry.

**Architecture:** Reclaim vertical space by moving the answer instruction into the plum header and extending the grid between the header band and bottom midpoint moat. Increase the size and weight of user-facing text and bubbles, narrow the peripheral timing rails, and express every important size as a tested generator constant. Preserve the R07 adaptive scanner contract and install the regenerated R07-E layout as MARKA's canonical API layout.

**Tech Stack:** Python 3, ReportLab, OpenCV, JSON, unittest, pytest

---

### Task 1: Lock the compact-visibility geometry in tests

**Files:**
- Modify: `tests/test_v2_prototype_generator.py`
- Test: `tests/test_v2_prototype_generator.py`

- [ ] **Step 1: Write failing visibility tests**

Import the generator's typography constants and assert the approved minimums:

```python
self.assertEqual(layout["template_revision"], "R07-E")
self.assertGreaterEqual(QUESTION_NUMBER_FONT_SIZE_PT, 8.0)
self.assertGreaterEqual(OPTION_HEADER_FONT_SIZE_PT, 8.0)
self.assertGreaterEqual(RANGE_HEADER_FONT_SIZE_PT, 7.0)
self.assertGreaterEqual(FIELD_LABEL_FONT_SIZE_PT, 6.8)
self.assertGreaterEqual(INSTRUCTION_FONT_SIZE_PT, 6.5)
self.assertGreaterEqual(FOOTER_FONT_SIZE_PT, 6.0)
self.assertEqual(BUBBLE_RADIUS_MM, 1.9)
self.assertEqual(min(b["y_mm"] for b in sheet["bubbles"]), 15.2)
self.assertEqual(max(b["y_mm"] for b in sheet["bubbles"]), 96.9)
self.assertTrue(all(field["h_mm"] >= 8.4 for field in sheet["fields"]))
```

Calculate outer bubble diameter from the stroke and assert it remains smaller than the 4.3 mm row pitch. Update the timing-rail clearance test to measure the actual `QUESTION_NUMBER_FONT_SIZE_PT` and require at least 0.8 mm rail-to-label clearance and 0.5 mm label-to-bubble clearance.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python3 -m unittest tests.test_v2_prototype_generator -v`

Expected: FAIL because R07 still uses 6.6 pt question numbers, 3.5 mm bubbles, 4.0 mm rows, and 7.2 mm writing fields.

### Task 2: Reflow the two-up sheet and increase essential sizes

**Files:**
- Modify: `scripts/generate_v2_omr_sheet.py`
- Test: `tests/test_v2_prototype_generator.py`

- [ ] **Step 1: Implement the minimum tested constants**

Use these values:

```python
BUBBLE_RADIUS_MM = 1.9
BUBBLE_STROKE_WIDTH_PT = 0.8
QUESTION_NUMBER_FONT_SIZE_PT = 8.0
QUESTION_NUMBER_BASELINE_OFFSET_MM = 0.75
OPTION_HEADER_FONT_SIZE_PT = 8.0
RANGE_HEADER_FONT_SIZE_PT = 7.0
FIELD_LABEL_FONT_SIZE_PT = 6.8
INSTRUCTION_FONT_SIZE_PT = 6.5
FOOTER_FONT_SIZE_PT = 6.0
TIMING_TRACK_WIDTH_MM = 1.0
TIMING_TRACK_LEFT_X_MM = 12.9
GRID_TOP_MM = 96.9
GRID_BOTTOM_MM = 15.2
```

Increase every field height from 7.2 mm to 8.4 mm. Keep five columns and all 500 bubbles.

- [ ] **Step 2: Reflow printable elements**

Move the instruction into the plum header as `SHADE ONE OPTION FULLY  •  DARK PENCIL OR PEN`. Move the answer-group band to start at 99.3 mm with 4.2 mm height; draw the range and option letters on one 100.5 mm baseline. Use bold 8 pt question numbers, the new font constants for labels, and 6 pt footer copy. Keep every anchor moat free of bubbles and timing rails.

- [ ] **Step 3: Brand and output the revision**

Set `template_revision` and footer to `R07-E`, generate `marka_r07e_omr_prototype.pdf` and `marka_r07e_omr_layout.json`, and set the PDF title to `MARKA R07-E High-Visibility Two-up OMR Template`.

- [ ] **Step 4: Run generator tests and verify GREEN**

Run: `python3 -m unittest tests.test_v2_prototype_generator -v`

Expected: PASS.

### Task 3: Regenerate, inspect, and synchronize

**Files:**
- Regenerate: `outputs/v2_prototype/marka_r07e_omr_prototype.pdf`
- Regenerate: `outputs/v2_prototype/marka_r07e_omr_layout.json`
- Regenerate: `outputs/v2_prototype/marka_r07e_omr_prototype.png`
- Modify: `data/MARKA/layout.json`
- Modify: `docs/r07_field_validation_protocol.md`
- Modify: `docs/superpowers/specs/2026-09-14-r07-lean-omr-design.md`

- [ ] **Step 1: Generate and install the layout**

Run: `.venv/bin/python scripts/generate_v2_omr_sheet.py`

Copy the generated R07-E JSON to `data/MARKA/layout.json`.

- [ ] **Step 2: Visually inspect at print scale**

Rasterize the PDF at 150 DPI. Inspect the full page and a high-resolution crop of questions 1–20. Confirm that 10–20 remain unobstructed, row circles do not touch, the bottom row clears the midpoint-anchor moat, the group band clears the first row, and header/footer copy is not clipped.

- [ ] **Step 3: Update validation documentation**

Describe R07-E as the reduced production candidate. Update the machine-geometry proxy to 457 mm²: 369 mm² of anchor bounding area plus 88 mm² from forty 1.0 × 2.2 mm timing marks, a 45.4% reduction from R06's 836.25 mm².

### Task 4: Verify and commit

**Files:**
- Test: `tests/test_v2_prototype_generator.py`
- Test: `tests/test_r07_scanner.py`
- Test: `api/test_server.py`

- [ ] **Step 1: Run complete verification**

Run: `.venv/bin/pytest -q`

Expected: all tests PASS.

Run: `git diff --check`

Expected: no output and exit code 0.

- [ ] **Step 2: Commit only scoped files**

```bash
git add scripts/generate_v2_omr_sheet.py tests/test_v2_prototype_generator.py data/MARKA/layout.json docs/r07_field_validation_protocol.md docs/superpowers/specs/2026-09-14-r07-lean-omr-design.md docs/superpowers/plans/2026-09-14-r07e-compact-visibility.md
git commit -m "feat: maximize two-up OMR visibility"
```
