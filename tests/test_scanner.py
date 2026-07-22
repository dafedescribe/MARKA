import unittest
import sys
import os
import cv2
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from omr_scanner import _find_fiducials





class ScannerFiducialTests(unittest.TestCase):
    def test_detect_fiducials_ignores_extra_square_contours(self):
        image = np.full((1400, 1000), 255, dtype=np.uint8)

        # Four corner fiducials.
        squares = [
            (20, 20),
            (940, 20),
            (940, 1340),
            (20, 1340),
            # Extra square-like noise that should not affect alignment.
            (400, 500),
            (700, 400),
            (500, 1000),
        ]

        for x, y in squares:
            cv2.rectangle(image, (x, y), (x + 40, y + 40), 0, -1)

        fiducials = _find_fiducials(image)

        self.assertEqual(len(fiducials), 4)
        expected = np.array(
            [
                [40, 40],
                [960, 40],
                [960, 1360],
                [40, 1360],
            ],
            dtype=np.float32,
        )
        np.testing.assert_allclose(np.array(fiducials, dtype=np.float32), expected, atol=20)


if __name__ == "__main__":
    unittest.main()
