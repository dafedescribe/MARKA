# HANDDRAWN_A4_40_V1 Field Validation

This protocol decides whether MARKA's ruler-drawn 40-question sheet is safe to
release. Passing synthetic tests means the implementation is ready for field
testing; it does not prove real-world reliability.

## 1. Corpus and participants

Test at least **100 independently constructed A4 sheets**. Do not photocopy one
master sheet and count the copies as independent constructions. Recruit at least
20 people across the intended range of ages and drawing ability, including
children who can use a ruler, older adults, people with unsteady lines, and
first-time users. Record anonymized participant and sheet IDs.

Give each participant the generated master guide and the same spoken instruction:
"Use a ruler and permanent pen. Every box is 1 cm. Put an X only in the top-left
corner square. Mark answers later with one pencil X or tick." Do not provide a
phone to the learner. Record first-construction time; 8–15 minutes is the design
expectation, not a pass/fail gate.

Generate the guide from the versioned profile:

```bash
./.venv/bin/python scripts/generate_handdrawn_a4_40_guide.py
```

## 2. Required variation

Distribute variation across the corpus instead of changing every factor at once.

- Rulers: clear plastic, opaque plastic, wooden, and worn-edge examples.
- Permanent lines: black and blue ballpoint/fine-tip pens with light, normal, and
  heavy pressure.
- Answers: HB and 2B pencils from at least three brands; include light, normal,
  and heavy marks.
- Erasers: soft vinyl and ordinary school erasers.
- Devices: at least five teacher phones across low-, mid-, and high-resolution
  cameras. Keep the original images; do not apply beauty filters.
- Capture: straight, ±5°, ±10°, and near the supported ±15° rotation; mild
  perspective angles; portrait and corrected upside-down attempts; bright
  daylight, indoor light, uneven light, light shadow, and deliberately unsafe
  shadow/blur cases.

Every normal capture must include the entire page and all four corner squares.
Deliberate failure cases must include missing/covered anchors, cropped grids,
wrong row or column counts, severe blur, and extreme light/dark exposure.

## 3. Mark and reuse cases

Ground-truth answers before any image is processed. Across the clear-mark set,
balance A–E and questions 1–40, and include both X and tick marks. Also include:

- blank rows;
- deliberate double marks;
- marks touching or crossing a cell boundary;
- faint marks;
- incompletely erased answers and erasure ghosts; and
- clean answers after erase cycles 1, 5, 10, and 20.

Photograph the sheet before erasing. After each scheduled reuse cycle, inspect
whether grid lines are damaged or ghosts remain. Retire and record a sheet when a
human teacher would reasonably redraw it.

## 4. Ground-truth manifest

Place images and `manifest.json` in one corpus directory. One construction can
have several capture cases, but every case from it must share `sheet_id`.

```json
{
  "cases": [
    {
      "sheet_id": "P07-S03",
      "image": "P07-S03-cycle05-indoor.jpg",
      "expect_registration": "success",
      "expected_marks": {"1": "B", "2": "E", "40": "A"},
      "expected_ambiguous": ["7"],
      "participant_age_band": "adult",
      "construction_seconds": 642,
      "reuse_cycle": 5,
      "device": "device-03",
      "capture_condition": "indoor-mild-shadow"
    },
    {
      "sheet_id": "P07-S03",
      "image": "P07-S03-anchor-covered.jpg",
      "expect_registration": "reject",
      "expected_error_code": "ANCHOR_MISSING",
      "expected_marks": {},
      "expected_ambiguous": []
    }
  ]
}
```

`expected_marks` contains only clear, single answers. Put deliberate double or
unsafe boundary question numbers in `expected_ambiguous`. For a deliberate
registration/capture failure, use `expect_registration: "reject"` and record the
expected structured error code. A second person should verify the manifest
against the physical sheet or source photograph before scanning begins.

## 5. Run and interpret the benchmark

```bash
./.venv/bin/python scripts/benchmark_handdrawn_a4_40.py path/to/corpus \
  --json path/to/corpus/report.json
```

The command exits zero only when `release_ready` is true. Important metrics:

- `independent_sheets`: distinct, explicit `sheet_id` values. Missing IDs keep
  `release_ready` false because image names cannot prove independent construction.
- `accuracy`: correctly recognized clear marks divided by all expected clear marks.
- `silent_errors`: wrong or missing clear answers not flagged as ambiguous.
- `correct_rejections`: expected failures rejected with the expected error code.
- `ambiguity_flagged`: deliberate double/boundary marks sent to review.
- `unexpected_rejections` and `unexpected_ambiguities`: safe cases the scanner
  rejected or unnecessarily flagged.

## 6. Release gates

Production release requires all of the following in one reviewed corpus:

1. At least 100 independently constructed sheets.
2. At least 99.5% accuracy on clear marks.
3. Zero silent orientation, row, column, or question-mapping errors.
4. Every expected missing-anchor, unsafe-grid, or capture-quality case rejected;
   no score may be produced after such a failure.
5. Every deliberate double mark and unsafe boundary mark flagged for review.
6. Zero unexpected registration rejections or ambiguity flags in the release run.
7. The full printed R07-E regression suite still passes unchanged.

If any gate fails, keep the feature in prototype/field-test status. Save the
report and misclassified images, fix the narrow failure mode, and rerun the full
corpus rather than excluding difficult samples.
