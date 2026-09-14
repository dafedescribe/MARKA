# MARKA R07 Lean OMR Design

**Date:** 2026-09-14
**Status:** Approved in product discussion and implemented for validation

## Purpose

R07 keeps MARKA focused on its core advantage: helping people practise on paper under realistic time pressure while preserving fast digital self-evaluation. The form must feel like a credible assessment document, not a machine calibration target.

## Printed form

Each A4 page contains two 198 × 140 mm, 100-question forms. The existing five-column answer grid, writing fields, calm plum identity, print-at-100% warning, and cut line remain. The centre registration marker is removed.

The form has eight unique ArUco markers:

- IDs 0, 2, 4, and 6 are mandatory 7.5 mm corner markers.
- IDs 1, 3, 5, and 7 are optional 6 mm edge-midpoint markers.

The answer grid uses 40 timing marks: one left and one right mark for each of 20 shared row positions. Question numbers are rendered independently, so timing geometry does not dictate the reading experience.

## Registration behavior

The scanner first detects the configured marker IDs. Missing optional markers never fail a scan; any missing mandatory corner does. Duplicate or unrelated marker IDs are ignored.

The four corners produce a global destination-to-source homography. Detected optional anchors are projected through that model and their residual error is measured. Piecewise correction activates only when at least two optional anchors are detected and the largest residual exceeds 4 px. Otherwise, global registration remains the default. Diagnostics expose the chosen mode, required IDs, detected and missing optional IDs, residual, and marker count.

## Timing behavior

The scanner detects each timing mark in a narrow local window. For each row, left and right observations are interpolated across the five answer columns. One detected side contributes its measured row offset across the row. If neither side is detected, nominal row geometry is used. Diagnostics report expected, detected, and missing tracks plus whether timing calibration contributed. Timing marks are aids, not dependencies.

## Failure behavior

- Four corners present, optional anchors absent: scan globally.
- Four corners present, timing marks absent: scan with nominal row positions.
- Optional anchors present but consistent with the global model: stay global.
- At least two optional anchors show material deformation: activate piecewise correction.
- Any required corner absent: return a clear retake error identifying the missing IDs.

## Validation

Synthetic tests cover the decision boundaries and end-to-end corners-only fallback. Field validation compares corners-only, R07 reduced geometry, and R06 full geometry on flat, rotated, shadowed, folded, and curled sheets. R07 is retained if answer accuracy is within 0.5 percentage points of R06, retry rate is no higher, and machine ink is at least 20% lower.
