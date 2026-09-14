import json
import tempfile
import unittest
from pathlib import Path
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.units import mm

from scripts import generate_v2_omr_sheet as generator
from scripts.generate_v2_omr_sheet import (
    ARUCO_MOAT_MM,
    BUBBLE_RADIUS_MM,
    BUBBLE_STROKE_WIDTH_PT,
    QUESTION_NUMBER_FONT_SIZE_PT,
    build_layout,
    generate_sheet,
)


class V2PrototypeGeneratorTests(unittest.TestCase):
    def test_default_layout_is_two_100_question_forms_on_one_a4_page(self):
        layout = build_layout()

        self.assertEqual(layout["num_questions"], 100)
        self.assertEqual(layout["sheets_per_page"], 2)
        self.assertEqual(len(layout["sheets"]), 2)
        for sheet in layout["sheets"]:
            self.assertEqual(sheet["sheet_size_mm"], [198.0, 140.0])
            self.assertEqual(sheet["answer_columns"], 5)
            first_bubble_x = [
                min(b["x_mm"] for b in sheet["bubbles"] if b["column_index"] == index)
                for index in range(5)
            ]
            self.assertEqual(first_bubble_x, [20.5, 55.5, 90.5, 125.5, 160.5])
            self.assertEqual(
                [
                    min(b["x_mm"] for b in sheet["bubbles"] if b["column_index"] == index + 1)
                    - min(b["x_mm"] for b in sheet["bubbles"] if b["column_index"] == index)
                    for index in range(4)
                ],
                [35.0, 35.0, 35.0, 35.0],
            )
            self.assertEqual(BUBBLE_RADIUS_MM, 1.9)
            self.assertEqual(min(b["y_mm"] for b in sheet["bubbles"]), 15.2)
            self.assertEqual(max(b["y_mm"] for b in sheet["bubbles"]), 96.9)
            row_centers = sorted({b["y_mm"] for b in sheet["bubbles"]})
            row_pitch = row_centers[1] - row_centers[0]
            stroke_width_mm = BUBBLE_STROKE_WIDTH_PT / 72 * 25.4
            self.assertGreater(row_pitch, 2 * BUBBLE_RADIUS_MM + stroke_width_mm)
            right_anchor = next(a for a in sheet["aruco_anchors"] if a["role"] == "right")
            right_moat_left = right_anchor["center_mm"][0] - right_anchor["size_mm"] / 2 - ARUCO_MOAT_MM
            right_bubble_edge = max(b["x_mm"] for b in sheet["bubbles"]) + BUBBLE_RADIUS_MM
            self.assertGreaterEqual(right_moat_left - right_bubble_edge, 2.0)
            self.assertNotIn("center", {a["role"] for a in sheet["aruco_anchors"]})
            self.assertEqual(len(sheet["aruco_anchors"]), 8)
            required_sizes = {a["size_mm"] for a in sheet["aruco_anchors"] if a["required"]}
            optional_sizes = {a["size_mm"] for a in sheet["aruco_anchors"] if not a["required"]}
            self.assertEqual(required_sizes, {7.5})
            self.assertEqual(optional_sizes, {6.0})
            self.assertEqual(len(sheet["timing_tracks"]), 40)
            self.assertEqual(len(sheet["bubbles"]), 100 * 5)
            self.assertEqual(
                [field["key"] for field in sheet["fields"]],
                ["name", "student_id", "class", "subject", "date"],
            )
            self.assertTrue(all(field["w_mm"] > 0 and field["h_mm"] >= 8.4 for field in sheet["fields"]))
            self.assertEqual(sheet["branding"]["logo_box"]["w_mm"], 18.0)
            self.assertIn("contact_line", sheet["branding"])

    def test_layout_contains_four_required_corners_four_optional_midpoints_and_shared_timing(self):
        layout = build_layout(num_questions=60)

        self.assertEqual(layout["layout_version"], 4)
        self.assertEqual(layout["template_revision"], "R07-E")
        self.assertNotIn("measurement_reference_mm", layout["print_spec"])
        self.assertEqual(layout["print_spec"]["scale"], "100%")
        self.assertEqual(layout["print_spec"]["cut_line"], True)
        self.assertEqual(layout["sheets_per_page"], 2)
        for sheet in layout["sheets"]:
            self.assertEqual(
                [anchor["id"] for anchor in sheet["aruco_anchors"]],
                list(range(8)),
            )
            self.assertEqual(
                [anchor["id"] for anchor in sheet["aruco_anchors"] if anchor["required"]],
                [0, 2, 4, 6],
            )
            self.assertEqual(
                [anchor["id"] for anchor in sheet["aruco_anchors"] if not anchor["required"]],
                [1, 3, 5, 7],
            )
            self.assertEqual(sheet["registration"]["required_anchor_ids"], [0, 2, 4, 6])
            self.assertEqual(sheet["registration"]["optional_anchor_ids"], [1, 3, 5, 7])
            self.assertEqual(sheet["registration"]["piecewise_min_optional_anchors"], 2)
            self.assertEqual(sheet["registration"]["piecewise_activation_error_px"], 4.0)
            self.assertEqual(len(sheet["timing_tracks"]), 24)
            self.assertEqual({track["side"] for track in sheet["timing_tracks"]}, {"left", "right"})
            self.assertEqual(
                sorted({track["row_index"] for track in sheet["timing_tracks"]}),
                list(range(12)),
            )
            self.assertEqual(len(sheet["bubbles"]), 60 * 5)
            self.assertTrue(all("timing_row_index" in bubble for bubble in sheet["bubbles"]))
            self.assertTrue(all("timing_track_id" not in bubble for bubble in sheet["bubbles"]))

    def test_left_timing_rail_clears_two_digit_labels_and_first_bubble(self):
        sheet = build_layout()["sheets"][0]
        left_track = next(
            track
            for track in sheet["timing_tracks"]
            if track["side"] == "left" and track["row_index"] == 9
        )
        first_column_x = sheet["answer_grid"]["column_starts_mm"][0]
        number_right = first_column_x + sheet["answer_grid"]["question_number_right_offset_mm"]
        label_width_mm = stringWidth("10", "Helvetica-Bold", QUESTION_NUMBER_FONT_SIZE_PT) / 72 * 25.4
        label_left = number_right - label_width_mm
        track_right = left_track["x_mm"] + left_track["width_mm"]
        first_bubble = next(
            bubble
            for bubble in sheet["bubbles"]
            if bubble["question"] == 10 and bubble["option"] == "A"
        )
        first_bubble_left = first_bubble["x_mm"] - first_bubble["radius_mm"]

        self.assertGreaterEqual(label_left - track_right, 0.8)
        self.assertGreaterEqual(first_bubble_left - number_right, 0.5)

    def test_r07e_uses_the_largest_practical_two_up_type_scale(self):
        self.assertGreaterEqual(QUESTION_NUMBER_FONT_SIZE_PT, 8.0)
        self.assertGreaterEqual(getattr(generator, "OPTION_HEADER_FONT_SIZE_PT", 0), 8.0)
        self.assertGreaterEqual(getattr(generator, "RANGE_HEADER_FONT_SIZE_PT", 0), 7.0)
        self.assertGreaterEqual(getattr(generator, "FIELD_LABEL_FONT_SIZE_PT", 0), 6.8)
        self.assertGreaterEqual(getattr(generator, "INSTRUCTION_FONT_SIZE_PT", 0), 6.5)
        self.assertGreaterEqual(getattr(generator, "FOOTER_FONT_SIZE_PT", 0), 6.0)

    def test_group_header_uses_one_baseline(self):
        sheet = build_layout()["sheets"][0]
        header = sheet["answer_grid"].get("group_header", {})

        self.assertEqual(header.get("layout"), "single-line")
        self.assertEqual(header.get("range_right_offset_mm"), 6.0)
        self.assertEqual(header.get("baseline_mm"), 100.5)

    def test_generate_sheet_writes_pdf_and_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path, json_path = generate_sheet(temp_dir, num_questions=60)

            self.assertTrue(Path(pdf_path).is_file())
            self.assertGreater(Path(pdf_path).stat().st_size, 1000)
            self.assertTrue(Path(json_path).is_file())

            saved = json.loads(Path(json_path).read_text())
            self.assertEqual(Path(pdf_path).name, "marka_r07e_omr_prototype.pdf")
            self.assertEqual(Path(json_path).name, "marka_r07e_omr_layout.json")
            self.assertEqual(saved["layout_version"], 4)
            self.assertEqual(saved["template_revision"], "R07-E")
            self.assertEqual(saved["sheets_per_page"], 2)
            self.assertEqual(saved["page_size_mm"], [210.0, 297.0])
            self.assertEqual(saved["sheets"][0]["sheet_size_mm"], [198.0, 140.0])


if __name__ == "__main__":
    unittest.main()
