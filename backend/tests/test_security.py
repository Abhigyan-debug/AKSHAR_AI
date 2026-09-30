"""Teacher sign-in, public vs protected routes, upload checks, headers, privacy endpoints."""

import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.security import AuthConfig, sniff_audio
from tests.test_api import (
    PIN,
    SECRET,
    WAV_HEADER,
    fake_transcriber,
    new_child,
    new_session,
    read_everything_correctly,
    signed_in,
    upload,
)


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("GROQ_API_KEY", "")
    return create_app(db_url=f"sqlite:///{tmp_path / 's.db'}", storage_dir=tmp_path / "st",
                      transcriber=fake_transcriber, teacher_pin=PIN, secret=SECRET)


PROTECTED = [
    ("get", "/api/children"),
    ("post", "/api/children"),
    ("get", "/api/tests/hi"),
    ("post", "/api/sessions"),
    ("post", "/api/sessions/1/items/hi_B_01/audio"),
    ("post", "/api/sessions/1/finish"),
    ("get", "/api/children/1/report"),
    ("patch", "/api/results/1"),
    ("get", "/api/class/summary"),
    ("get", "/api/audio/1"),
    ("delete", "/api/audio/1"),
    ("delete", "/api/children/1"),
    ("delete", "/api/children/1/audio"),
    ("post", "/api/sessions/1/parent-link"),
]


@pytest.mark.parametrize("method, path", PROTECTED)
def test_teacher_routes_need_a_token(app, method, path):
    c = TestClient(app)
    assert getattr(c, method)(path).status_code == 401
    assert getattr(c, method)(path, headers={"Authorization": "Bearer not.valid"}).status_code == 401


def test_public_routes(app):
    c = TestClient(app)
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/parent/unknown-token").status_code == 404  # public, but needs a real token


def test_login(app):
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"pin": "wrong"}).status_code == 401
    r = c.post("/api/auth/login", json={"pin": PIN})
    assert r.status_code == 200 and r.json()["expires_at"] > time.time()
    token = r.json()["token"]
    assert c.get("/api/children", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_login_is_rate_limited(app):
    c = TestClient(app)
    for _ in range(5):
        assert c.post("/api/auth/login", json={"pin": "000000"}).status_code == 401
    assert c.post("/api/auth/login", json={"pin": PIN}).status_code == 429  # locked, even with the right PIN


def test_tokens_expire_and_are_signed():
    auth = AuthConfig(PIN, SECRET)
    token, exp = auth.issue_token(now=1000)
    assert auth.token_valid(token, now=1001)
    assert not auth.token_valid(token, now=exp + 1)
    assert not AuthConfig(PIN, SECRET.replace("x", "y")).token_valid(token, now=1001)  # other secret
    body, sig = token.split(".")
    assert not auth.token_valid(body + "." + sig[::-1], now=1001)


def test_weak_config_is_refused():
    with pytest.raises(RuntimeError):
        AuthConfig("123", SECRET)
    with pytest.raises(RuntimeError):
        AuthConfig(PIN, "short")


def test_missing_config_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setenv("TEACHER_PIN", "")
    monkeypatch.setenv("AKSHAR_SECRET", "")
    with pytest.raises(RuntimeError, match="TEACHER_PIN"):
        create_app(db_url=f"sqlite:///{tmp_path / 'x.db'}", storage_dir=tmp_path / "x")


def test_uploads_are_checked_by_content(app):
    c = signed_in(TestClient(app))
    sid = new_session(c, new_child(c)["id"])
    html = c.post(f"/api/sessions/{sid}/items/hi_B_01/audio",
                  files={"file": ("clip.webm", b"<script>alert(1)</script>", "audio/webm")})
    assert html.status_code == 415
    big = c.post(f"/api/sessions/{sid}/items/hi_B_01/audio",
                 files={"file": ("clip.wav", WAV_HEADER + b"0" * (10 * 1024 * 1024), "audio/wav")})
    assert big.status_code == 413
    assert upload(c, sid, "hi_B_01", "कमल").status_code == 200


def test_sniff_audio():
    assert sniff_audio(b"\x1a\x45\xdf\xa3....") == ".webm"
    assert sniff_audio(b"OggS....") == ".ogg"
    assert sniff_audio(WAV_HEADER) == ".wav"
    assert sniff_audio(b"\x00\x00\x00\x18ftypM4A ") == ".m4a"
    assert sniff_audio(b"ID3\x04") == ".mp3"
    assert sniff_audio(b"fLaC") == ".flac"
    assert sniff_audio(b"%PDF-1.7") is None


def test_security_headers_and_no_public_docs(app):
    c = TestClient(app)
    r = c.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-frame-options"] == "DENY"
    assert c.get("/api/docs").status_code == 404
    assert c.get("/api/openapi.json").status_code == 404


def test_delete_child_removes_everything(app):
    c = signed_in(TestClient(app))
    child = new_child(c)
    sid = new_session(c, child["id"])
    clip = upload(c, sid, "hi_B_01", "कमल").json()
    assert c.delete(f"/api/children/{child['id']}").status_code == 204
    assert c.get(f"/api/children/{child['id']}").status_code == 404
    assert c.get(f"/api/audio/{clip['id']}").status_code == 404
    assert c.get("/api/class/summary").json() == []


def test_new_parent_link_revokes_the_old_one(app):
    c = signed_in(TestClient(app))
    sid = new_session(c, new_child(c)["id"])
    read_everything_correctly(c, sid)
    old = c.post(f"/api/sessions/{sid}/finish").json()["report"]["parent_token"]
    assert c.get(f"/api/parent/{old}").status_code == 200
    new = c.post(f"/api/sessions/{sid}/parent-link").json()["parent_token"]
    assert new != old
    assert c.get(f"/api/parent/{old}").status_code == 404
    assert c.get(f"/api/parent/{new}").status_code == 200
