from fastapi.testclient import TestClient

from forge_backend import main

ORIGIN = "http://localhost:5173"

def _client(monkeypatch):
    monkeypatch.setattr(main, "run_ingestion", lambda: {})
    return TestClient(main.app)

def test_preflight_allows_dev_origin(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.options(
            "/races",
            headers={"Origin": ORIGIN, "Access-Control-Request-Method": "GET"},
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN

def test_simple_request_echoes_allow_origin(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.get("/health", headers={"Origin": ORIGIN})
    assert response.headers["access-control-allow-origin"] == ORIGIN

def test_unlisted_origin_is_not_allowed(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in response.headers