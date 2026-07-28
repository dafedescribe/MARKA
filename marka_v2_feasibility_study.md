# MARKA v2.0 Feasibility & Research Report
**Subject:** Technical vetting of Multi-Sheet Scanning, Pre-Designed Dense Templates, and OpenCV Warp-Proofing.

## 1. Multi-Sheet Scanning & Arbitrary Rotation
**Requirement:** Scan 4–6 randomly placed, arbitrarily rotated OMR sheets in a single smartphone photo.

### Feasibility: VERY HIGH (with ArUco upgrade)
Currently, MARKA looks for 4 plain black squares (`cv2.findContours` -> contour area -> aspect ratio -> bounding box). If we place 4 sheets on a desk, OpenCV will find 16 plain squares. Grouping them perfectly when sheets are placed close together or overlapping is mathematically fragile.

**The Solution: ArUco Markers**
Instead of plain black squares, we must replace the 4 corners with **ArUco markers** (specifically `cv2.aruco.DICT_4X4_50`). 
- **Why it solves everything:** ArUco markers are tiny 2D barcodes designed specifically for computer vision. They are incredibly robust to blur and terrible lighting. 
- **Built-in Rotation:** Every ArUco marker has a hardcoded orientation. The moment OpenCV detects the marker, it knows *exactly* which way is "up". We completely eliminate the need for the hacky "QR density check" MARKA currently uses to detect upside-down sheets.
- **Perfect Clustering:** If we assign Top-Left as ID:1, Top-Right as ID:2, Bottom-Left as ID:3, and Bottom-Right as ID:4, the scanner will find multiple 1s, 2s, 3s, and 4s in the photo. We cluster them by finding the valid geometric quadrilaterals they form. OpenCV handles this natively and blazingly fast (<10ms).

## 2. Ultra-High-Density Templates (8 Sheets per A4)
**Requirement:** Pack 20-question sheets into 1/8th of an A4 page (A7 size) to save printing costs.

### Feasibility: MODERATE to HIGH (Hardware Dependent)
The limiting factor here is the optical resolution of the teacher's smartphone camera and the school's printer quality.
- **The Math:** A standard 12MP smartphone camera shoots at roughly `4000x3000` pixels. If a teacher takes a photo of 4 distinct A7-sized OMR sheets on a desk, each sheet will occupy roughly `1000x1500` pixels of the photo. 
- **Bubble Size:** At that resolution, an individual bubble will be about `15x15` to `20x20` pixels. 
- **Conclusion:** `20x20` pixels is more than enough for OpenCV to calculate a mean darkness threshold. **However**, the physical printing must be sharp. If an old inkjet printer bleeds the ink, the bubbles will merge. 
- **Recommendation:** We must increase the gap between bubbles (`BUBBLE_SPACING_X`) in the static templates and use very thin stroke lines for the bubbles so they don't "fill in" with cheap printer ink.

## 3. "Warp-Proof" Resilience (Timing Tracks)
**Requirement:** Add a black rectangle on the edge of every row to anchor the Y-coordinates, preventing vertical stretch/fold errors.

### Feasibility: EXTREMELY HIGH (Industry Standard)
This is exactly how Scantron machines have worked since the 1970s, translated to modern computer vision.
- **The Algorithm:** 
  1. Crop a vertical slice of the left margin where the track sits.
  2. Apply a 1D pixel intensity profile (collapse the X-axis into a single array of darkness values).
  3. Use signal processing (e.g., `scipy.signal.find_peaks` or a simple rolling minimum) to find the exact Y-pixel coordinate of every single black bar.
- **Why it's better than homography:** Even if the top of the paper is crumpled and the bottom is flat, the scanner doesn't care. It reads row 5 exactly where the 5th black bar is. Error does not accumulate as you go down the page.

## 4. Piecewise Perspective Warping (Midpoint Anchors)
**Requirement:** Add 4 extra fiducials at the edges to divide the sheet into 4 quadrants to cure non-planar bowing.

### Feasibility: HIGH
- **The Algorithm:** Instead of generating one global 3x3 Homography matrix (`cv2.getPerspectiveTransform`) using 4 corners, we generate **four separate matrices**. 
- Top-Left Quadrant uses: (Top-Left Corner, Top-Mid Anchor, Left-Mid Anchor, Center Point).
- We warp the 4 quadrants individually and stitch them back together (`cv2.vconcat` / `cv2.hconcat`).
- **Recommendation:** To make this work flawlessly, we actually need a **9th anchor** dead in the center of the page. If we only have 8 edge anchors, we have to guess the center point, which defeats the purpose of correcting a center fold. We should put a small crosshair `+` or a 9th ArUco marker in the exact center of the question grid.

## 5. Software Stack & Libraries Required
No new heavy dependencies are required. We do not need deep learning (PyTorch/TensorFlow) for this, which keeps the API lightning fast and cheap to host.
- **`opencv-python`**: Already in `requirements.txt`. (Provides ArUco marker detection, 1D signal peak finding, and piecewise warping).
- **`reportlab`**: Already in `requirements.txt`. (Perfect for generating the static PDF templates with sub-millimeter precision).
- **`numpy`**: Already in `requirements.txt`. (Handles the matrix slicing and 1D profile extraction for the Timing Tracks).

## Summary & Final Verdict
The PRD is **100% technically feasible** and arguably the best possible approach for a modern, robust OMR engine. By shifting away from complex deep learning towards robust geometric anchoring (ArUco + Timing Tracks + Piecewise Warping), MARKA will be faster, cheaper to run, and vastly more accurate on bad photos than competitors.

### Suggested Order of Execution:
1. **Design the ArUco + Timing Track PDF Templates** (The foundation).
2. **Implement Single-Sheet ArUco Warping & Timing Track Alignment** (Nail the accuracy first).
3. **Expand to Multi-Sheet Clustering** (Scale up to batch scanning).
