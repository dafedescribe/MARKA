from fastapi.testclient import TestClient
from server import app

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

