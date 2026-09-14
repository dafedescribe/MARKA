# MARKA Hand-drawn A4 40 Design

**Date:** 2026-09-14
**Status:** Approved for implementation planning
**Profile ID:** `HANDDRAWN_A4_40_V1`

## 1. Decision

MARKA will support one hand-drawn answer-sheet format: a reusable, ruler-drawn,
40-question A4 sheet that a learner can construct without a phone. It behaves
like MARKA's printed OMR from the teacher's point of view: the teacher selects an
exam, uploads one or more completed sheets, receives grades, reviews uncertain
marks, and exports results.

The hand-drawn format is not a free-form handwriting reader and is not a second
grading product. It has a separate registration and mark-recognition pipeline,
then returns the existing OMR result contract.

This design supersedes the earlier 100-question, dimension-only and calibration-
dependent hand-drawn proposals.

## 2. Product goal

Enable a learner to draw a reusable answer sheet once with ordinary A4 paper, a
ruler, and a dark pen, then complete repeated practices in pencil while a teacher
uses MARKA to mark the sheets.

The design optimizes, in order, for:

1. a construction rule simple enough to teach to a first grader;
2. low recurring learner and teacher effort;
3. fail-closed scan accuracy;
4. isolation from the printed R07-E scanner; and
5. reuse of MARKA's existing grading and result workflow.

## 3. Users and operating assumptions

- Learners do not have phones during construction or assessment.
- A teacher may show one master construction guide to a class.
- Learners use a ruler and permanent dark pen to construct the sheet.
- Learners use an HB/2B pencil for answers and erase answers between sessions.
- Teachers capture or upload sheets after the assessment.
- The first release supports one 40-question response per sheet.
- The teacher controls assessment start and stop time. The sheet does not measure
  individual duration.

## 4. Non-goals for V1

- 100 questions on one hand-drawn page
- freehand construction without a ruler
- learner-side phone setup or blank-sheet calibration
- handwritten name, number, or answer OCR
- arbitrary question offsets or multi-page answer merging
- automatic individual duration measurement
- changing the printed R07-E scanner or its default behavior
- guessing answers when registration, grid structure, or marks are uncertain

## 5. The one-centimetre construction system

The construction guide uses one measurement: **1 cm**. Learners count centimetre
boxes rather than calculate coordinates or work with decimal measurements.

### 5.1 Page and coordinate convention

- Paper: A4 portrait, 210 mm × 297 mm.
- Coordinates below are measured from the top-left paper corner.
- Measurements are construction targets, not exact scan coordinates. The reader
  detects the actual ruler-drawn lines on every photograph.

### 5.2 Registration anchors

Four 10 mm × 10 mm outlined squares sit outside the information and answer areas.
The outer edge of each square is 10 mm inward from its two nearest paper edges:

| Anchor | Bounds in millimetres `(left, top, right, bottom)` |
| --- | --- |
| Top-left | `(10, 10, 20, 20)` |
| Top-right | `(190, 10, 200, 20)` |
| Bottom-left | `(10, 277, 20, 287)` |
| Bottom-right | `(190, 277, 200, 287)` |

The learner draws a large X inside the top-left anchor only. The X can be
imperfect but must stay inside the square. The other three anchors remain empty.
This extra internal ink is the orientation cue; the scanner does not depend on a
precise diagonal angle.

Every anchor has at least 10 mm of blank paper between it and the paper edge. The
answer grids do not enter any anchor's surrounding area.

### 5.3 Answer grids

There are two separate 20-row grids:

| Grid | Bounds in millimetres | Questions |
| --- | --- | --- |
| Left | `(30, 50, 90, 250)` | `1–20` |
| Right | `(120, 50, 180, 250)` | `21–40` |

Each grid is 60 mm wide and 200 mm tall. It contains:

- one 10 mm question-number column;
- five 10 mm answer columns labelled A, B, C, D, and E; and
- twenty 10 mm answer rows.

The page-width rule is therefore:

```text
3 cm margin + 6 cm grid + 3 cm gap + 6 cm grid + 3 cm margin = 21 cm
```

The learner writes fixed question numbers 1–20 in the left number column and
21–40 in the right number column. Question numbers and A–E labels guide the
learner but are not read by OCR.

### 5.4 Information fields

The top centre area provides simple handwritten fields matching the printed OMR:

- Name
- Student ID
- Class
- Subject
- Date

The construction guide presents these as two uncomplicated writing lines between
the top anchors and the answer grids. Their exact line length and handwriting do
not participate in registration or grading.

### 5.5 Permanent and erasable marks

- Anchors, grid lines, field labels, question numbers, and A–E labels are drawn
  once in permanent dark pen.
- Answers are made in pencil.
- A learner marks exactly one choice with a clear X or tick centred inside the
  selected cell.
- X is the recommended mark because it is the most consistent. Ticks are accepted.
- Marks that touch a cell boundary may be sent to review.
- The learner erases answers cleanly after the teacher has captured the sheet.
- A sheet with persistent erasure ghosts or damaged grid lines must be redrawn.

## 6. First-grade construction guide

One master guide can be printed once, displayed by the teacher, or copied onto a
board. No learner device is required. It uses four large illustrated steps and
minimal text:

1. Draw four 1 cm corner squares; put an X in the top-left square.
2. Draw two rectangles, each six boxes wide and twenty boxes tall.
3. Mark every 1 cm with the ruler and join the marks.
4. Write 1–40 and A–E; answer with one X or tick.

The guide must show that long ruled lines create the cells. It must not imply that
the learner draws 200 boxes individually. A first construction may take 8–15
minutes; recurring setup is limited to writing and erasing answers.

## 7. Teacher workflow

1. Create or select an exam and answer key through the existing MARKA workflow.
2. Open **Scan & Grade**.
3. Select `Printed OMR` or `Hand-drawn 40` once for the upload batch.
4. Photograph or upload all completed sheets.
5. Let the existing serialized queue grade each sheet.
6. Review only rejected sheets and highlighted uncertain answers.
7. Use the existing results, corrections, receipts, and exports.

The handwritten identity fields remain visible to the teacher in the sheet image.
V1 does not OCR or automatically attach those fields to a roster.

## 8. Integration architecture

### 8.1 Mode dispatch

Add an optional layout-mode value to the existing processing request and queued
job. The default remains the printed R07-E mode, preserving existing clients.

```text
Upload queue
    └── process request: exam_code + layout_mode
            ├── PRINTED_R07E → existing read_bubbles path
            └── HANDDRAWN_A4_40_V1 → hand-drawn reader
                                      └── existing grade/store/export path
```

The selected mode is stored with the scan so a retry or future reprocessing cannot
interpret the photograph with a different reader.

### 8.2 Isolated hand-drawn reader

The new reader is divided into bounded stages:

1. `assess_capture_quality` checks resolution, blur, exposure, and page visibility.
2. `detect_handdrawn_anchors` finds the four outer outlined squares and the
   top-left X.
3. `rectify_handdrawn_page` maps the detected frame into canonical A4 space.
4. `detect_handdrawn_grid` finds both actual ruler-drawn grids and their line
   intersections.
5. `build_handdrawn_cells` constructs the 40 × 5 answer polygons from detected
   lines rather than ideal coordinates.
6. `read_handdrawn_marks` masks grid boundaries, measures new interior ink, and
   classifies clear, blank, multiple, and uncertain cells.
7. `to_omr_result` emits the existing scanner result structure.

Each stage returns diagnostics and can reject independently. The existing printed
reader is not imported into or rewritten around hand-drawn assumptions.

### 8.3 Result contract

The hand-drawn reader returns the existing logical structure:

```json
{
  "marks": {"1": "B", "2": "D"},
  "multi_marks": {},
  "confidence": {"1": 0.96, "2": 0.93},
  "ambiguous": [],
  "registration": {"mode": "handdrawn-a4-40-v1"}
}
```

Grading, answer keys, correction generation, storage, overrides, receipts, and
exports consume this result without a second implementation.

## 9. Registration and grid recognition

### 9.1 Capture support target

V1 must handle acceptable full-page photographs with:

- image height of at least 1,000 pixels;
- page rotation up to 15 degrees;
- perspective displacement up to 12% of page width or height;
- anchor side lengths equivalent to 8–12 mm after page-scale estimation;
- ruler-drawn cell widths and heights between 8–12 mm; and
- mild shadows and non-uniform illumination that preserve visible grid contrast.

These are support limits, not reasons to guess. Images beyond the limits are
rejected with a corrective instruction.

### 9.2 Anchor selection

The reader finds plausible outlined squares near the four page extremities using
contour size, rectangularity, aspect ratio, solidity, and relative position. It
selects the largest plausible outer quadrilateral and rejects missing, duplicated,
cropped, or geometrically inconsistent anchors.

After rectification, exactly one anchor must contain materially higher diagonal
interior ink consistent with an X. Its position defines top-left. Missing or
ambiguous orientation cues reject the page; the reader never infers orientation
from question labels.

### 9.3 Adaptive grid model

The canonical coordinates define search regions only. The reader detects the
actual horizontal and vertical lines using morphology and line evidence, then
regularizes them against the expected two-grid, 20-row, six-column topology.

Small line gaps may be bridged when both neighbouring intersections support the
same line. The system must not invent an entire missing boundary or silently
change the row count. Both grids must independently resolve to 20 rows and six
columns before answers are scored.

## 10. Mark recognition

After rectification and grid detection:

1. Normalize illumination locally.
2. Mask a narrow band around each detected grid boundary.
3. Measure connected dark strokes inside every answer cell.
4. Combine dark-pixel area, stroke length, centre occupancy, and boundary leakage
   into a choice score.
5. Compare the strongest and second-strongest choices for each question.

A choice is accepted only when it exceeds the minimum mark strength, leads every
other choice by the configured winner gap, and does not create unsafe boundary
leakage. The thresholds are set through benchmark data rather than hard-coded from
one synthetic sample.

Clear X marks and ticks are shape-independent foreground strokes; the reader does
not need to classify which of the two shapes was used. Multiple strong choices,
faint erasures, stray marks, and boundary-crossing strokes become ambiguous or
blank according to measured evidence. They never become confident answers by
default.

## 11. Errors and teacher recovery

Whole-sheet failures return one primary error and one corrective action:

| Condition | Result | Teacher message |
| --- | --- | --- |
| Fewer than four anchors | Reject | “Move back and include all four corner squares.” |
| Missing/unclear top-left X | Reject | “Check that only the top-left square contains an X.” |
| Blur | Reject | “Hold the camera steady and retake the photograph.” |
| Severe shadow or glare | Reject | “Move to even light and retake the photograph.” |
| Grid has the wrong row/column count | Reject | “This grid is incomplete. Check both 20-row blocks.” |
| Page is folded or strongly curved | Reject | “Flatten the sheet before retaking the photograph.” |
| One uncertain answer | Continue to review | Highlight the question and candidate cells. |
| Multiple strong answers | Continue to review | Highlight all detected choices for teacher correction. |

The teacher can override ambiguous answers through the existing result-review
mechanism. Registration failures cannot be overridden into a grade because the
question mapping is unsafe.

## 12. Testing strategy

### 12.1 Unit and synthetic tests

- profile geometry and non-overlap;
- four-anchor detection and top-left-X orientation;
- rotation, perspective, scale, blur, illumination, and cropping;
- adaptive line detection with reasonable ruler variation and small line gaps;
- correct mapping of every question and option;
- X, tick, faint pencil, heavy pencil, off-centre marks, erasures, stray dots,
  boundary marks, and multiple marks;
- structured failure for incomplete anchors or grid topology;
- API mode dispatch and preservation of the result contract; and
- complete regression coverage of printed R07-E scanning.

### 12.2 Field validation

Before production release, test at least 100 independently constructed sheets
from multiple ages and drawing abilities. Capture them with varied phones, angles,
lighting, rulers, pens, and pencils. Include repeated answer-and-erase cycles and
teacher batch uploads.

The minimum release gates are:

- at least 99.5% correct recognition of clear marks;
- zero silent orientation, row, column, or question-mapping errors;
- 100% structured rejection when an anchor is missing or the grid topology is
  unsafe;
- every deliberate double mark and unsafe boundary mark flagged for review;
- no score produced after a failed capture-quality or registration gate; and
- all existing printed OMR tests passing unchanged.

## 13. Known limitations

- A first grader may require teacher demonstration and 8–15 minutes for the first
  construction.
- Dirty erasure residue can create ambiguous marks and eventually require a new
  sheet.
- Handwritten identity fields remain visual metadata in V1.
- Assessments longer than 40 questions require a future explicit multi-sheet
  design; V1 must not imply automatic merging.
- Real-world reliability remains a hypothesis until the field-validation gates
  pass.

## 14. Acceptance summary

The feature is ready for implementation planning when the build preserves these
invariants:

- one A4 portrait profile, 40 questions, and the one-centimetre rule;
- two separate 20-row grids with five A–E answer cells per row;
- four isolated 1 cm outlined anchors and an X only in the top-left anchor;
- no learner phone, calibration, or OCR;
- one teacher batch-level scanner-mode choice;
- adaptive per-image grid detection;
- fail-closed registration and teacher review for mark uncertainty; and
- no regression or behavioral change in printed R07-E scanning.
