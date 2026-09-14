import sys
import os
import unittest

import cv2
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from scripts.generate_v2_omr_sheet import build_layout
from omr_scanner import (
    _calibrate_r07_timing_rows,
    _detect_aruco_anchors,
    _is_structured_layout,
    _registration_maps,
    read_bubbles,
)


class R07ScannerTests(unittest.TestCase):
    def setUp(self):
        self.layout = build_layout()
        self.sheet = self.layout["sheets"][0]

    def test_r07_layout_dispatch_exposes_adaptive_geometry(self):
        self.assertTrue(_is_structured_layout(self.layout))
        self.assertEqual(self.layout["aruco_dictionary"], "DICT_4X4_50")
        self.assertEqual(len(self.sheet["aruco_anchors"]), 8)
        self.assertEqual(len(self.sheet["timing_tracks"]), 40)
        self.assertEqual(self.sheet["answer_grid"]["column_pitch_mm"], 35.0)

    def test_shared_timing_tracks_interpolate_across_columns(self):
        height = int(self.sheet["sheet_size_mm"][1] * 10)
        width = int(self.sheet["sheet_size_mm"][0] * 10)
        image = np.full((height, width), 255, dtype=np.uint8)
        for track in self.sheet["timing_tracks"]:
            drift_mm = 0.4 if track["side"] == "left" else 1.2
            observed_y_mm = track["y_mm"] + drift_mm
            cx = int(track["x_mm"] * 10)
            cy = int((self.sheet["sheet_size_mm"][1] - observed_y_mm) * 10)
            cv2.rectangle(image, (cx, cy - 10), (cx + 14, cy + 10), 0, -1)

        calibrated, diagnostics = _calibrate_r07_timing_rows(image, self.sheet)

        self.assertEqual(len(calibrated), 100)
        self.assertEqual(diagnostics["expected"], 40)
        self.assertEqual(diagnostics["detected"], 40)
        self.assertTrue(diagnostics["used"])
        left_column_y = calibrated[(0, 0)]
        right_column_y = calibrated[(4, 0)]
        self.assertLess(right_column_y, left_column_y)

    def test_missing_timing_tracks_fall_back_to_nominal_rows(self):
        height = int(self.sheet["sheet_size_mm"][1] * 10)
        width = int(self.sheet["sheet_size_mm"][0] * 10)
        image = np.full((height, width), 255, dtype=np.uint8)

        calibrated, diagnostics = _calibrate_r07_timing_rows(image, self.sheet)

        self.assertEqual(len(calibrated), 100)
        self.assertEqual(diagnostics["expected"], 40)
        self.assertEqual(diagnostics["detected"], 0)
        self.assertFalse(diagnostics["used"])
        first_row_y_mm = next(
            bubble["y_mm"] for bubble in self.sheet["bubbles"]
            if bubble["column_index"] == 0 and bubble["row_index"] == 0
        )
        expected_y = (self.sheet["sheet_size_mm"][1] - first_row_y_mm) * 10
        self.assertAlmostEqual(calibrated[(0, 0)], expected_y, delta=0.1)

    def _observed_markers(self, marker_ids):
        sheet_h_mm = self.sheet["sheet_size_mm"][1]
        return {
            anchor["id"]: np.array(
                [anchor["center_mm"][0] * 10, (sheet_h_mm - anchor["center_mm"][1]) * 10],
                dtype=np.float32,
            )
            for anchor in self.sheet["aruco_anchors"]
            if anchor["id"] in marker_ids
        }

    def test_four_required_corners_succeed_without_optional_anchors(self):
        width = int(self.sheet["sheet_size_mm"][0] * 10)
        height = int(self.sheet["sheet_size_mm"][1] * 10)
        observed = self._observed_markers([0, 2, 4, 6])

        map_x, map_y, diagnostics = _registration_maps(
            self.sheet, observed, width, height
        )

        self.assertEqual(map_x.shape, (height, width))
        self.assertEqual(map_y.shape, (height, width))
        self.assertEqual(diagnostics["mode"], "r07-global")
        self.assertEqual(diagnostics["required_marker_ids"], [0, 2, 4, 6])
        self.assertEqual(diagnostics["missing_optional_marker_ids"], [1, 3, 5, 7])

    def test_missing_required_corner_fails(self):
        height = int(self.sheet["sheet_size_mm"][1] * 10)
        width = int(self.sheet["sheet_size_mm"][0] * 10)
        image = np.full((height, width), 255, dtype=np.uint8)
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        for anchor in self.sheet["aruco_anchors"]:
            if anchor["id"] not in {0, 2, 4}:
                continue
            marker = cv2.aruco.generateImageMarker(dictionary, int(anchor["id"]), 75)
            x_mm, y_mm = anchor["center_mm"]
            x = int(x_mm * 10 - 37)
            y = int((self.sheet["sheet_size_mm"][1] - y_mm) * 10 - 37)
            image[y:y + 75, x:x + 75] = marker

        with self.assertRaisesRegex(ValueError, "required corner markers"):
            _detect_aruco_anchors(image, self.sheet)

    def test_small_optional_residual_stays_global(self):
        width = int(self.sheet["sheet_size_mm"][0] * 10)
        height = int(self.sheet["sheet_size_mm"][1] * 10)
        observed = self._observed_markers(range(8))

        _, _, diagnostics = _registration_maps(self.sheet, observed, width, height)

        self.assertEqual(diagnostics["mode"], "r07-global")
        self.assertEqual(diagnostics["optional_marker_ids"], [1, 3, 5, 7])
        self.assertLessEqual(diagnostics["optional_residual_px"], 4.0)

    def test_meaningful_optional_residual_activates_piecewise(self):
        width = int(self.sheet["sheet_size_mm"][0] * 10)
        height = int(self.sheet["sheet_size_mm"][1] * 10)
        observed = self._observed_markers(range(8))
        observed[1] = observed[1] + np.array([0.0, 8.0], dtype=np.float32)
        observed[5] = observed[5] + np.array([0.0, -8.0], dtype=np.float32)

        _, _, diagnostics = _registration_maps(self.sheet, observed, width, height)

        self.assertEqual(diagnostics["mode"], "r07-piecewise")
        self.assertGreater(diagnostics["optional_residual_px"], 4.0)

    def test_r07_reader_succeeds_with_corners_only_and_no_timing_marks(self):
        height = int(self.sheet["sheet_size_mm"][1] * 10)
        width = int(self.sheet["sheet_size_mm"][0] * 10)
        image = np.full((height, width), 255, dtype=np.uint8)
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        for anchor in self.sheet["aruco_anchors"]:
            if not anchor["required"]:
                continue
            marker = cv2.aruco.generateImageMarker(dictionary, int(anchor["id"]), 75)
            x_mm, y_mm = anchor["center_mm"]
            x = int(x_mm * 10 - 37)
            y = int((self.sheet["sheet_size_mm"][1] - y_mm) * 10 - 37)
            image[y:y + 75, x:x + 75] = marker

        for bubble in self.sheet["bubbles"]:
            center = (int(bubble["x_mm"] * 10), int((self.sheet["sheet_size_mm"][1] - bubble["y_mm"]) * 10))
            cv2.circle(image, center, int(bubble["radius_mm"] * 10), 0, 2)
            if bubble["question"] == 1 and bubble["option"] == "B":
                cv2.circle(image, center, int(bubble["radius_mm"] * 0.65 * 10), 0, -1)

        with __import__("tempfile").NamedTemporaryFile(suffix=".png") as handle:
            cv2.imwrite(handle.name, image)
            result = read_bubbles(handle.name, self.layout)

        self.assertEqual(result["marks"]["1"], "B")
        self.assertEqual(result["registration"]["mode"], "r07-global")
        self.assertEqual(result["registration"]["timing_tracks"]["detected"], 0)
        self.assertFalse(result["registration"]["timing_tracks"]["used"])
        self.assertEqual(result["registration"]["marker_ids"], [0, 2, 4, 6])
        self.assertEqual(
            result["registration"]["missing_optional_marker_ids"],
            [1, 3, 5, 7],
        )


if __name__ == "__main__":
    unittest.main()
