# Product Requirements Document (PRD)
**Product:** MARKA v2.0 OMR Engine
**Focus:** Pre-Designed Templates, Multi-Sheet Scanning, and Warp-Proof OpenCV Resilience

---

## 1. Executive Summary
MARKA v2.0 aims to redefine OMR processing for resource-constrained environments by introducing extreme paper-saving layouts using pre-designed templates, drastically speeding up grading times through single-photo multi-sheet scanning, and ensuring 99.9% grading accuracy even on heavily folded, crumpled, or arbitrarily rotated paper. 

## 2. Core Features & Requirements

### 2.1 Pre-Designed Ultra-High-Density Templates (Eco-OMR)
Instead of relying on a fragile dynamic layout generator at runtime, we will use robust, **pre-designed fixed templates**. These fixed layouts will be optimized to pack as many sheets as possible per A4 page to drastically save paper costs for schools.

**Requirements:**
- The system will include pre-designed static templates (PDF + Layout JSON) for:
  - **100 Questions:** 2 sheets per A4
  - **80 Questions:** 3 sheets per A4
  - **60 Questions:** 4 sheets per A4
  - **40 Questions:** 6 sheets per A4
  - **20 Questions:** 8 sheets per A4
- These fixed designs guarantee that bubbles and column gutters always remain legible to the smartphone camera because they have been manually perfected and tested.

### 2.2 Single-Photo Multi-Sheet Scanning with Arbitrary Rotations
Teachers should be able to throw 4 to 6 sheets on a desk haphazardly and take a single photo. **The sheets may be in different orientations (upside down, tilted, rotated 90 degrees).**

**Requirements:**
- Upgrade `_find_fiducials` in `omr_scanner.py` to cluster groups of fiducial markers.
- **Rotation Resilience:** For each clustered sheet, the scanner must independently determine its rotation (using the QR code or asymmetric fiducials) and warp it to a perfectly flat, upright orientation, regardless of how it was thrown onto the table.
- The `/process-scan` API will iterate over the array of cropped/upright sheets, grading each independently, and return a batch result payload.

### 2.3 "Warp-Proof" Resilient Sheet Designs
To handle crumpled paper and bent edges without relying on slow Deep Learning models, we will implement classic hardware-grade structural anchors into the pre-designed templates.

**Requirements:**
- **Timing Tracks:** Draw a small, thick black rectangle on the left margin exactly aligned with every row of bubbles. The scanner will use these marks to find the exact Y-coordinate of each row, making the scanner completely immune to vertical stretching or folds.
- **Midpoint Anchors (8-Point Grid):** Add 4 additional fiducials at the midpoints of the top, bottom, left, and right edges. The scanner will split the sheet into 4 quadrants and apply 4 separate perspective transforms. This cures non-planar bowing.

### 2.4 Handwriting Field Extraction & Assessment Receipts
MARKA already supports coordinate-based cropping of student handwriting (Name, ID, Date, Subject).

**Requirements:**
- Ensure the new pre-designed dense templates maintain absolute physical coordinate tracking for handwriting zones.
- When multiple sheets are scanned in one photo, the scanner must extract the handwriting snippets for *each* sheet, despite their original arbitrary rotations in the master photo.
- These base64 image snippets will continue to be embedded into the itemized Assessment Receipts for visual verification by the teacher.

---

## 3. Technical Implementation Phases

### Phase 1: Static Template Generation
1. Create the fixed `omr_layout.json` files and PDF templates for the 20, 40, 60, 80, and 100 question variants.
2. Embed the Timing Tracks and Midpoint Anchors into these fixed designs.

### Phase 2: OpenCV Pipeline Upgrades (`src/omr_scanner.py`)
1. Implement marker clustering to detect `N` sheets in a single image.
2. Ensure orientation auto-correction (the QR bottom-left check) runs independently for every clustered sheet.
3. Update `_read_all_bubbles` to use the Timing Tracks for Y-coordinate row alignment.
4. Replace the single `cv2.getPerspectiveTransform` with a Piecewise Transform (4 quadrants per sheet).

### Phase 3: API & Frontend Integration
1. Update `api/server.py` to handle the array of results returned by the upgraded `read_bubbles`.
2. Update the React frontend (`demo_site`) to display multiple graded results from a single photo upload.

---
*Created by Antigravity*
