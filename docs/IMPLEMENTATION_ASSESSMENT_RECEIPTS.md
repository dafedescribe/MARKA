# MARKA Assessment Receipts & Handwriting Extraction Implementation Log

## Overview
This document serves as a comprehensive changelog and implementation guide for the **Assessment Receipts** and **Coordinate-Based Handwriting Extraction** features introduced in the `feature/assessment-receipts` branch.

This system addresses a critical component of the MARKA OMR pipeline: delivering rapid, zero-bias feedback to students while bypassing the unreliability and latency of standard Optical Character Recognition (OCR).

## What We Built

### 1. Premium Assessment Receipts (`receipt_generator.py`)
We developed a highly polished, A4-compatible receipt generator designed to be printed securely and handed back to students.
- **Certificate Aesthetic:** Uses a double-lined frame and dedicated layout blocks to look official and premium, preventing the feedback from feeling like a disposable scrap of paper.
- **Non-Biased Formatting:** Implemented a universal 10-column corrections grid with a fixed **6.5pt font**. By refusing to dynamically scale the font based on the number of failed questions, we ensured identical, stigma-free formatting for every student (whether they missed 1 question or all 100).
- **Space Efficiency:** The layout elegantly stacks the header, student info, and score box to reclaim vertical space, guaranteeing that the worst-case scenario (100 failed questions) completely fits on a single slip without overflowing into other students' receipts. Prints 10 slips per A4 page.

### 2. Redesigned OMR Header (`omr_generator.py`)
The OMR sheet header was completely redesigned to support both better school branding and our new extraction pipeline.
- **School Branding:** A dedicated 13x13mm logo placeholder, school name, and contact info area was introduced to the top-left, making the sheet immediately recognizable.
- **Compact Bounded Fields:** The traditional "underlined" fields were replaced with strict, bounded rectangles (`3.5mm` height) arranged neatly in a single row (`Name`, `ID`, `Class`, `Subject`, `Date`).
- **Layout Optimization:** By removing unnecessary text and consolidating the fields, we kept the header height to `19mm`. This ensures the bubble grid below maintains a safe `4.25mm` vertical spacing (well above the `3.5mm` scanner safety minimum).
- **Coordinate Exporting:** The `omr_generator` now calculates and exports `fields_mm` (exact x, y, width, height in mm) for each handwriting box directly into the `omr_layout.json`.

### 3. Coordinate-Based Handwriting Extraction (`omr_scanner.py`)
To completely eliminate the need for error-prone OCR when identifying students:
- We leveraged the existing `_perspective_transform` pipeline, which already flattens the scanned photo into a perfect millimetre-accurate grid.
- A new `extract_fields()` function was added. It reads the `fields_mm` from the layout JSON and mathematically crops the exact pixel regions where the student wrote their details.
- This outputs raw NumPy image arrays and **Base64-encoded PNGs** for immediate use.

### 4. End-to-End Workflow Integration
- `receipt_generator.py` was updated to accept the `fields_b64` dictionary from the scanner.
- When generating a receipt, if Base64 images are provided, it dynamically renders the student's *actual handwritten* Name, Class, and Subject directly onto the receipt using ReportLab's `ImageReader`.
- This creates an indisputable feedback loop—students see their own handwriting on their final score slip. (A text-fallback remains in place for dummy generation or failed extractions).

## How it Fits into the Project Scope
This completes the core loop of the MARKA product:
1. **Generate:** Create a branded OMR sheet (with strictly defined field boundaries).
2. **Scan & Grade:** Perspective-align the sheet, read bubbles, and precisely crop handwriting without AI/OCR.
3. **Feedback:** Immediately generate a premium printable receipt featuring the student's score, their corrections, and their own handwritten identifier.

## Pitfalls & Constraints to Watch Out For
- **Bubble Grid Spacing:** The distance between rows of bubbles must remain above `3.5mm` for the scanner to accurately resolve them. The current header leaves us with `4.25mm` vertical spacing for a 100-question sheet. If further rows are added to the header, the bubble layout will compress dangerously.
- **Image Cropping Inversion:** ReportLab draws from the bottom-left (`y=0` at bottom), while OpenCV image arrays start from the top-left (`y=0` at top). The `_crop_field` function handles this inversion manually using `sheet_h_mm`. Any future coordinate tweaks must respect this flip.
- **Receipt Layout Boundaries:** The receipt student info section is highly compact. The embedded handwriting images are currently scaled to a `2.8mm` height maximum to prevent them from breaking the text lines. Modifying the receipt layout will require testing to ensure crops don't overlap with the score box or the corrections grid. 

## Next Steps for Developers
1. **Server API Wiring:** Connect `omr_scanner.extract_fields()` to the actual backend endpoints. Ensure the Base64 payloads can be passed cleanly to the receipt generator worker.
2. **Dynamic Logos:** The OMR generator and receipt generator currently use placeholders. Allow the user to upload a school logo to the server, and inject the path/base64 into the generators.
3. **Database Saving:** Persist the Base64 crops (or save them to an S3 bucket) linked to the student's ID so that digital records also carry the handwritten proof.
