"""Tests for speedtest result storage, the results page, and a single result."""

import json
import re

import pytest

from wlanpi_webui.app import create_app


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


@pytest.fixture()
def results_path(tmp_path, monkeypatch):
    path = tmp_path / "speedtest.json"
    monkeypatch.setattr(
        "wlanpi_webui.config.Config.SESSION_KEY_PATH", str(tmp_path / "session_key")
    )
    monkeypatch.setattr("wlanpi_webui.config.Config.SPEEDTEST_RESULTS_PATH", str(path))
    return path


@pytest.fixture()
def app(results_path):
    return create_app()


@pytest.fixture()
def client(app):
    return app.test_client()


def _login(client, monkeypatch):
    from wlanpi_webui.auth import auth

    monkeypatch.setattr(
        auth, "make_api_request", lambda *a, **k: FakeResponse({"status": "success"})
    )
    page = client.get("/login")
    csrf = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
    resp = client.post(
        "/login",
        data={"username": "wlanpi", "password": "x", "csrf_token": csrf},
    )
    assert resp.status_code == 302


PAYLOAD = {
    "download_mbps": 940.2,
    "upload_mbps": 918.5,
    "ping_ms": 12.4,
    "jitter_ms": 1.2,
    "loaded_ping_ms": 30.0,
    "loaded_jitter_ms": 4.0,
    "download_min_mbps": 800,
    "download_max_mbps": 950,
    "upload_min_mbps": 700,
    "upload_max_mbps": 930,
    "download_mb": 1200,
    "upload_mb": 1100,
    "client_ip": "192.168.6.50",
    "duration_s": 30,
}


class TestSpeedtestReport:
    def test_post_stores_and_returns_url(self, client, monkeypatch, results_path):
        _login(client, monkeypatch)
        resp = client.post("/app/librespeed/results", json=PAYLOAD)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["url"] == f"/app/librespeed/results/{body['id']}"
        stored = json.loads(results_path.read_text())
        assert stored[0]["download_mbps"] == 940.2
        assert stored[0]["id"] == body["id"]

    def test_post_rejects_junk(self, client, monkeypatch):
        _login(client, monkeypatch)
        assert (
            client.post("/app/librespeed/results", json={"nonsense": 1}).status_code
            == 400
        )
        assert (
            client.post("/app/librespeed/results", data="not json").status_code == 400
        )

    def test_post_rejects_cross_origin(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.post(
            "/app/librespeed/results",
            json=PAYLOAD,
            headers={"Origin": "https://evil.example"},
        )
        assert resp.status_code == 403

    def test_requires_login(self, client):
        assert client.post("/app/librespeed/results", json=PAYLOAD).status_code in (
            302,
            401,
        )

    def test_result_page_renders(self, client, monkeypatch):
        _login(client, monkeypatch)
        rid = client.post("/app/librespeed/results", json=PAYLOAD).get_json()["id"]
        resp = client.get(f"/app/librespeed/results/{rid}")
        assert resp.status_code == 200
        assert b"940.20" in resp.data
        assert b"Download (Mbps)" in resp.data
        assert b"Loaded" in resp.data
        assert b"Client" not in resp.data

    def test_note_saves(self, client, monkeypatch, results_path):
        _login(client, monkeypatch)
        rid = client.post("/app/librespeed/results", json=PAYLOAD).get_json()["id"]
        with client.session_transaction() as sess:
            csrf = sess["csrf_token"]
        resp = client.post(
            f"/app/librespeed/results/{rid}/note",
            data={"note": "office 5GHz, Pixel 8", "csrf_token": csrf},
        )
        assert resp.status_code == 302
        stored = json.loads(results_path.read_text())
        assert stored[0]["note"] == "office 5GHz, Pixel 8"

    def test_note_rejects_overlong(self, client, monkeypatch):
        _login(client, monkeypatch)
        rid = client.post("/app/librespeed/results", json=PAYLOAD).get_json()["id"]
        with client.session_transaction() as sess:
            csrf = sess["csrf_token"]
        resp = client.post(
            f"/app/librespeed/results/{rid}/note",
            data={"note": "x" * 201, "csrf_token": csrf},
        )
        assert resp.status_code == 400

    def test_old_report_url_redirects(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/speedtest/report")
        assert resp.status_code == 301
        assert resp.headers["Location"].endswith("/app/librespeed/results")

    def test_permalink_and_unknown_id(self, client, monkeypatch):
        _login(client, monkeypatch)
        result_id = client.post("/app/librespeed/results", json=PAYLOAD).get_json()[
            "id"
        ]
        assert client.get(f"/app/librespeed/results/{result_id}").status_code == 200
        assert client.get("/app/librespeed/results/nope").status_code == 404

    def test_results_page_is_a_table(self, client, monkeypatch):
        _login(client, monkeypatch)
        client.post("/app/librespeed/results", json=PAYLOAD)
        resp = client.get("/app/librespeed/results")
        assert resp.status_code == 200
        assert b"<th>Tested</th>" in resp.data
        assert b"<th>Download (Mbps)</th>" in resp.data
        assert b"940.20" in resp.data
        # The image belongs to a single result, not the list.
        assert b"result-image" not in resp.data

    def test_result_page_has_the_image_and_expanded_details(self, client, monkeypatch):
        _login(client, monkeypatch)
        rid = client.post("/app/librespeed/results", json=PAYLOAD).get_json()["id"]
        resp = client.get(f"/app/librespeed/results/{rid}")
        assert resp.status_code == 200
        assert b"result-image" in resp.data
        assert b"Copy image" in resp.data
        assert b"speedtest-stat-value" in resp.data
        assert b'<details class="disclosure" open>' in resp.data

    def test_results_are_capped(self, client, monkeypatch, results_path):
        _login(client, monkeypatch)
        for _ in range(25):
            client.post("/app/librespeed/results", json=PAYLOAD)
        assert len(json.loads(results_path.read_text())) == 20
