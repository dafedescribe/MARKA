from api.server import build_receipt_record


def test_receipt_record_preserves_handwritten_fields_and_branding():
    fields = {"name": "data:image/webp;base64,abc"}
    scan = {
        "scan_id": "SCAN-1",
        "score": 8,
        "total": 10,
        "raw_marks": {"marks": {"1": "A"}, "fields_b64": fields},
    }
    record = build_receipt_record(
        scan, "MATH", {"1": "B"},
        {"school_name": "Long School Name", "address": "Lagos"},
    )
    assert record["fields_b64"] == fields
    assert record["school_name"] == "Long School Name"
    assert record["address"] == "Lagos"
    assert record["student_name"] == "SCAN-1"
