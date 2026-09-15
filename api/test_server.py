import json
import queue
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import server
from server import ProcessScanRequest, app, find_layout_json


client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "supabase" in response.json()


def test_unauthorized_exams():
    response = client.get("/exams")
    assert response.status_code == 401


def test_unauthorized_upload():
    response = client.get("/upload/presigned-url?scan_id=test")
    assert response.status_code == 401


def test_marka_uses_r07_layout():
    path = find_layout_json("MARKA")
    with open(path) as handle:
        layout = json.load(handle)
    assert layout["layout_version"] == 4
    assert len(layout["sheets"][0]["aruco_anchors"]) == 8
    assert [
        anchor["id"] for anchor in layout["sheets"][0]["aruco_anchors"]
        if anchor["required"]
    ] == [0, 2, 4, 6]
    assert len(layout["sheets"][0]["timing_tracks"]) == 40


def test_process_scan_defaults_to_printed_r07e():
    request = ProcessScanRequest(scan_id="scan-1", exam_code="MATH")
    assert request.layout_mode == "PRINTED_R07E"


def test_process_scan_accepts_handdrawn_mode():
    request = ProcessScanRequest(
        scan_id="scan-1",
        exam_code="MATH",
        layout_mode="HANDDRAWN_A4_40_V1",
    )
    assert request.layout_mode == "HANDDRAWN_A4_40_V1"


def test_process_scan_rejects_unknown_mode():
    with pytest.raises(ValidationError):
        ProcessScanRequest(
            scan_id="scan-1",
            exam_code="MATH",
            layout_mode="AUTO_GUESS",
        )


def test_enqueue_preserves_layout_mode(monkeypatch):
    isolated_queue = queue.Queue()
    monkeypatch.setattr(server, "_scan_queue", isolated_queue)
    depth = server._enqueue_scan(
        "scan-1",
        "MATH",
        "teacher-1",
        "HANDDRAWN_A4_40_V1",
    )
    assert depth == 1
    assert isolated_queue.get_nowait() == (
        "scan-1",
        "MATH",
        "teacher-1",
        "HANDDRAWN_A4_40_V1",
    )


def test_scan_schema_persists_layout_mode():
    root = Path(__file__).resolve().parents[1]
    initial = (root / "migrations/001_initial_schema.sql").read_text()
    upgrade = (root / "migrations/002_add_scan_layout_mode.sql").read_text()
    assert "layout_mode" in initial
    assert "HANDDRAWN_A4_40_V1" in upgrade


def test_render_no_longer_exposes_scheduled_retention():
    paths = {route.path for route in server.app.routes}
    assert "/admin/wipe-expired" not in paths
    assert "/scans/{scan_id}/wipe-image" in paths
    assert "/scans/clear-library" in paths
    assert "/scans/wipe-all-raw" in paths
