from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_and_homepage():
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/").status_code == 200


def test_missing_api_key_does_not_expose_configuration():
    response = client.get("/api/fixtures/today")
    assert response.status_code == 503
    assert response.json() == {"detail": "FootyStats API is not configured"}
