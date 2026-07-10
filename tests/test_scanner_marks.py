import unittest

import numpy as np

from scanner import draw_check_mark, draw_cross_mark


class ScannerMarkDrawingTests(unittest.TestCase):
    def test_draw_check_mark_paints_green_pixels(self):
        image = np.full((200, 200, 3), 255, dtype=np.uint8)

        draw_check_mark(image, (100, 100), 40, color=(0, 255, 0), thickness=4)

        self.assertTrue(np.any(np.all(image == [0, 255, 0], axis=2)))

    def test_draw_cross_mark_paints_red_pixels(self):
        image = np.full((200, 200, 3), 255, dtype=np.uint8)

        draw_cross_mark(image, (100, 100), 40, color=(0, 0, 255), thickness=4)

        self.assertTrue(np.any(np.all(image == [0, 0, 255], axis=2)))


if __name__ == "__main__":
    unittest.main()
