from fastapi.testclient import TestClient
from server import app, find_layout_json
import json

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "supabase" in response.json()

def test_unauthorized_exams():
    response = client.get("/exams")
    assert response.status_code == 401  # Unauthorized without a token

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
