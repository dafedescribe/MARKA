import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


from handdrawn_scanner import HanddrawnScanError
from scripts import benchmark_handdrawn_a4_40 as benchmark


def test_benchmark_reports_silent_errors_and_rejections(tmp_path, monkeypatch):
    (tmp_path / "clear.png").write_bytes(b"synthetic-clear")
    (tmp_path / "missing.png").write_bytes(b"synthetic-missing")
    manifest = {
        "cases": [
            {
                "image": "clear.png",
                "expect_registration": "success",
                "expected_marks": {"1": "A", "2": "B", "3": "C", "4": "D"},
                "expected_ambiguous": [],
            },
            {
                "image": "missing.png",
                "expect_registration": "reject",
                "expected_error_code": "ANCHOR_MISSING",
                "expected_marks": {},
                "expected_ambiguous": [],
            },
        ]
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    def fake_reader(image_path, profile=None):
        if Path(image_path).name == "missing.png":
            raise HanddrawnScanError(
                "ANCHOR_MISSING", "Four anchors were not found.",
                "Include all four corner squares.",
            )
        return {
            "marks": {"1": "A", "2": "E", "3": "C", "4": "D"},
            "ambiguous": [],
            "registration": {"mode": "handdrawn-a4-40-v1"},
        }

    monkeypatch.setattr(benchmark, "read_handdrawn", fake_reader)
    report = benchmark.run_benchmark(tmp_path)
    assert report["sheets"] == 2
    assert report["clear_marks"] == 4
    assert report["silent_errors"] == 1
    assert report["registration_rejections"] == 1
    assert report["release_ready"] is False


def test_release_gate_requires_scale_accuracy_rejections_and_ambiguity(tmp_path, monkeypatch):
    cases = []
    for index in range(100):
        image = f"sheet-{index}.png"
        (tmp_path / image).write_bytes(b"field-sheet")
        cases.append({
            "sheet_id": f"sheet-{index}",
            "image": image,
            "expect_registration": "success",
            "expected_marks": {"1": "A"},
            "expected_ambiguous": ["2"] if index == 0 else [],
        })
    (tmp_path / "reject.png").write_bytes(b"reject")
    cases.append({
        "sheet_id": "sheet-0",
        "image": "reject.png",
        "expect_registration": "reject",
        "expected_error_code": "ANCHOR_MISSING",
        "expected_marks": {},
        "expected_ambiguous": [],
    })
    (tmp_path / "manifest.json").write_text(json.dumps({"cases": cases}))

    def fake_reader(image_path, profile=None):
        if Path(image_path).name == "reject.png":
            raise HanddrawnScanError("ANCHOR_MISSING", "Missing.", "Retake.")
        return {
            "marks": {"1": "A", "2": None},
            "ambiguous": ["2"] if Path(image_path).name == "sheet-0.png" else [],
        }

    monkeypatch.setattr(benchmark, "read_handdrawn", fake_reader)
    report = benchmark.run_benchmark(tmp_path)
    assert report["independent_sheets"] == 100
    assert report["accuracy"] == 1.0
    assert report["expected_rejections"] == report["correct_rejections"] == 1
    assert report["ambiguity_expected"] == report["ambiguity_flagged"] == 1
    assert report["release_ready"] is True


def test_release_gate_does_not_treat_image_names_as_independent_sheets(tmp_path, monkeypatch):
    cases = []
    for index in range(100):
        image = f"capture-{index}.png"
        (tmp_path / image).write_bytes(b"same-unidentified-sheet")
        cases.append({
            "image": image,
            "expect_registration": "success",
            "expected_marks": {"1": "A"},
            "expected_ambiguous": [],
        })
    (tmp_path / "manifest.json").write_text(json.dumps({"cases": cases}))
    monkeypatch.setattr(
        benchmark,
        "read_handdrawn",
        lambda image_path, profile=None: {"marks": {"1": "A"}, "ambiguous": []},
    )

    report = benchmark.run_benchmark(tmp_path)
    assert report["sheets"] == 100
    assert report["independent_sheets"] == 0
    assert report["missing_sheet_ids"] == 100
    assert report["release_ready"] is False
