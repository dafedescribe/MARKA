"""Stable routing boundary for printed and hand-drawn MARKA scanners."""

from handdrawn_scanner import (
    grade_and_render_handdrawn,
    load_handdrawn_profile,
    read_handdrawn,
)
from omr_scanner import grade_and_render, read_bubbles


PRINTED_R07E = "PRINTED_R07E"
HANDDRAWN_A4_40_V1 = "HANDDRAWN_A4_40_V1"
SUPPORTED_LAYOUT_MODES = frozenset({PRINTED_R07E, HANDDRAWN_A4_40_V1})


def normalize_layout_mode(value=None):
    mode = (value or PRINTED_R07E).strip().upper()
    if mode not in SUPPORTED_LAYOUT_MODES:
        raise ValueError(f"Unsupported layout mode: {value}")
    return mode


def read_sheet(image_path, printed_layout, layout_mode=PRINTED_R07E):
    mode = normalize_layout_mode(layout_mode)
    if mode == HANDDRAWN_A4_40_V1:
        return read_handdrawn(image_path, load_handdrawn_profile())
    return read_bubbles(image_path, printed_layout)


def validate_answers_for_mode(answers, layout_mode=PRINTED_R07E):
    mode = normalize_layout_mode(layout_mode)
    try:
        question_numbers = {int(value) for value in answers}
    except (TypeError, ValueError) as error:
        raise ValueError("Answer-key question numbers must be integers.") from error
    if mode == HANDDRAWN_A4_40_V1 and not question_numbers.issubset(set(range(1, 41))):
        raise ValueError("Hand-drawn 40 supports questions 1–40 only.")
    return answers


def grade_sheet(
    marks_data,
    answers,
    image_path,
    printed_layout,
    output_path,
    layout_mode=PRINTED_R07E,
):
    mode = normalize_layout_mode(layout_mode)
    validate_answers_for_mode(answers, mode)
    if mode == HANDDRAWN_A4_40_V1:
        return grade_and_render_handdrawn(
            marks_data,
            answers,
            image_path,
            load_handdrawn_profile(),
            output_path,
        )
    return grade_and_render(
        marks_data,
        answers,
        image_path,
        printed_layout,
        output_path,
    )
