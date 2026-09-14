#!/usr/bin/env python3
"""Benchmark HANDDRAWN_A4_40_V1 against a ground-truthed field corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from handdrawn_scanner import HanddrawnScanError, read_handdrawn  # noqa: E402


MINIMUM_INDEPENDENT_SHEETS = 100
MINIMUM_CLEAR_MARK_ACCURACY = 0.995


def _load_cases(corpus_dir: Path) -> list[dict]:
    manifest_path = corpus_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"Manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("manifest.json must contain a non-empty 'cases' list")
    return cases


def _normalise_marks(values: dict | None) -> dict[str, str | None]:
    return {
        str(question): None if answer is None else str(answer).strip().upper()
        for question, answer in (values or {}).items()
    }


def run_benchmark(corpus_dir: Path) -> dict:
    """Return field-corpus accuracy, rejection, ambiguity, and safety metrics."""
    corpus_dir = Path(corpus_dir)
    cases = _load_cases(corpus_dir)

    sheet_ids = {str(case["sheet_id"]) for case in cases if case.get("sheet_id")}
    report = {
        "sheets": len(cases),
        "independent_sheets": len(sheet_ids),
        "missing_sheet_ids": sum(not bool(case.get("sheet_id")) for case in cases),
        "clear_marks": 0,
        "correct_marks": 0,
        "incorrect_marks": 0,
        "silent_errors": 0,
        "expected_rejections": 0,
        "registration_rejections": 0,
        "correct_rejections": 0,
        "missed_rejections": 0,
        "unexpected_rejections": 0,
        "ambiguity_expected": 0,
        "ambiguity_flagged": 0,
        "unexpected_ambiguities": 0,
        "errors": [],
    }

    for index, case in enumerate(cases):
        image_name = case.get("image")
        if not image_name:
            raise ValueError(f"Case {index} has no image")
        image_path = corpus_dir / image_name
        if not image_path.is_file():
            raise ValueError(f"Case image not found: {image_path}")

        expectation = case.get("expect_registration", "success")
        if expectation not in {"success", "reject"}:
            raise ValueError(
                f"Case {image_name} expect_registration must be 'success' or 'reject'"
            )

        expected_marks = _normalise_marks(case.get("expected_marks"))
        expected_ambiguous = {str(value) for value in case.get("expected_ambiguous", [])}
        report["ambiguity_expected"] += len(expected_ambiguous)
        if expectation == "success":
            report["clear_marks"] += len(expected_marks)
        else:
            report["expected_rejections"] += 1

        try:
            result = read_handdrawn(image_path)
        except HanddrawnScanError as error:
            report["registration_rejections"] += 1
            if expectation == "reject" and (
                not case.get("expected_error_code")
                or case["expected_error_code"] == error.code
            ):
                report["correct_rejections"] += 1
            else:
                report["unexpected_rejections"] += 1
                report["errors"].append({
                    "image": image_name,
                    "type": "unexpected_rejection",
                    "actual": error.code,
                    "expected": case.get("expected_error_code"),
                })
            continue

        if expectation == "reject":
            report["missed_rejections"] += 1
            report["errors"].append({
                "image": image_name,
                "type": "missed_rejection",
                "expected": case.get("expected_error_code"),
            })
            continue

        actual_marks = _normalise_marks(result.get("marks"))
        actual_ambiguous = {str(value) for value in result.get("ambiguous", [])}
        report["ambiguity_flagged"] += len(expected_ambiguous & actual_ambiguous)
        unexpected_ambiguities = actual_ambiguous - expected_ambiguous
        report["unexpected_ambiguities"] += len(unexpected_ambiguities)

        for question, expected in expected_marks.items():
            actual = actual_marks.get(question)
            if actual == expected and question not in actual_ambiguous:
                report["correct_marks"] += 1
                continue
            report["incorrect_marks"] += 1
            if question not in actual_ambiguous:
                report["silent_errors"] += 1
            report["errors"].append({
                "image": image_name,
                "type": "mark_mismatch",
                "question": question,
                "expected": expected,
                "actual": actual,
                "flagged_ambiguous": question in actual_ambiguous,
            })

    clear_marks = report["clear_marks"]
    report["accuracy"] = round(
        report["correct_marks"] / clear_marks if clear_marks else 0.0,
        6,
    )
    report["release_ready"] = all([
        report["independent_sheets"] >= MINIMUM_INDEPENDENT_SHEETS,
        report["missing_sheet_ids"] == 0,
        report["accuracy"] >= MINIMUM_CLEAR_MARK_ACCURACY,
        report["silent_errors"] == 0,
        report["correct_rejections"] == report["expected_rejections"],
        report["missed_rejections"] == 0,
        report["unexpected_rejections"] == 0,
        report["ambiguity_flagged"] == report["ambiguity_expected"],
        report["unexpected_ambiguities"] == 0,
    ])
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark MARKA's 40-question hand-drawn answer sheet reader."
    )
    parser.add_argument("corpus", type=Path, help="Directory containing manifest.json")
    parser.add_argument("--json", type=Path, dest="json_path", help="Also write the report here")
    args = parser.parse_args()

    report = run_benchmark(args.corpus)
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.json_path:
        args.json_path.write_text(rendered + "\n", encoding="utf-8")
    raise SystemExit(0 if report["release_ready"] else 1)


if __name__ == "__main__":
    main()
