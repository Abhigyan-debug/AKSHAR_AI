"""API end to end with a fake transcriber and fake LLM (no network)."""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services import bank, cache
from app.services.transcribe import Segment, Transcript, Word
from tests.test_llm import GOOD


WAV_HEADER = b"RIFF\x00\x00\x00\x00WAVE"  # passes the upload content check
PIN = "246810"
SECRET = "test-secret-" + "x" * 40


def fake_transcriber(audio: bytes, filename: str, lang: str) -> Transcript:
    """The 'audio' is a WAV header + the text the child read ('LOW:' = low confidence)."""
    text = audio[len(WAV_HEADER):].decode("utf-8")
    logprob = -0.2
    if text.startswith("LOW:"):
        text, logprob = text[4:], -0.9
    if text == "FAIL":
        raise RuntimeError("groq down")
    words = [Word(w, 1.0 + 0.5 * i, 1.4 + 0.5 * i) for i, w in enumerate(text.split())]
    return Transcript(text=text, words=words, segments=[Segment(text, 0.0, 2.0, logprob, 0.05)])


class FakeLLM:
    def __init__(self):
        self.calls = 0
        self.chat = self
        self.completions = self

    def create(self, **kw):
        self.calls += 1
        system = kw["messages"][0]["content"]
        body = {"labels": []} if "label children's reading errors" in system else GOOD
        msg = type("M", (), {"content": json.dumps(body, ensure_ascii=False)})
        return type("R", (), {"choices": [type("C", (), {"message": msg})]})


@pytest.fixture
def llm():
    return FakeLLM()


@pytest.fixture
def client(tmp_path, llm, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / "cache")
    app = create_app(db_url=f"sqlite:///{tmp_path / 'test.db'}", storage_dir=tmp_path / "storage",
                     transcriber=fake_transcriber, llm_client=llm, teacher_pin=PIN, secret=SECRET)
    return signed_in(TestClient(app))


def signed_in(c: TestClient) -> TestClient:
    token = c.post("/api/auth/login", json={"pin": PIN}).json()["token"]
    c.headers["Authorization"] = f"Bearer {token}"
    return c


def new_child(client, code="R01", grade=3):
    r = client.post("/api/children", json={"code": code, "grade": grade, "home_lang": "Hindi"})
    assert r.status_code == 201, r.text
    return r.json()


def new_session(client, child_id):
    r = client.post("/api/sessions", json={"child_id": child_id})
    assert r.status_code == 201
    return r.json()["id"]


def upload(client, sid, item_id, spoken, live_tap=None):
    data = {"live_tap": live_tap} if live_tap else {}
    return client.post(f"/api/sessions/{sid}/items/{item_id}/audio",
                       files={"file": ("clip.wav", WAV_HEADER + spoken.encode("utf-8"), "audio/wav")}, data=data)


def read_everything_correctly(client, sid):
    for item in bank.items().values():
        tap = "correct" if item["scoring"] == "manual" else None
        r = upload(client, sid, item["id"], item["text"], tap)
        assert r.status_code == 200, (item["id"], r.text)


def test_children(client):
    c = new_child(client, "ab-12")
    assert c["code"] == "AB-12"
    assert client.post("/api/children", json={"code": "AB-12", "grade": 3, "home_lang": "Hindi"}).status_code == 409
    assert client.post("/api/children", json={"code": "Riya Sharma", "grade": 3, "home_lang": "Hindi"}).status_code == 422
    assert client.post("/api/children", json={"code": "X1", "grade": 12, "home_lang": "Hindi"}).status_code == 422
    assert [x["code"] for x in client.get("/api/children").json()] == ["AB-12"]


def test_tests_endpoint(client):
    assert len(client.get("/api/tests/hi").json()["items"]) == 36
    assert client.get("/api/tests/fr").status_code == 404


def test_upload_scores_and_stores_audio(client):
    sid = new_session(client, new_child(client)["id"])
    r = upload(client, sid, "hi_C_01", "पनीर")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "auto" and body["correct"] is False
    assert [e["type"] for e in body["errors"]] == ["lexicalization"]
    audio = client.get(body["audio_url"])
    assert audio.status_code == 200 and audio.content == WAV_HEADER + "पनीर".encode()


def test_upload_rules(client):
    sid = new_session(client, new_child(client)["id"])
    assert upload(client, sid, "hi_A_01", "ब").status_code == 422                    # manual needs a tap
    assert upload(client, sid, "hi_B_01", "कमल", "correct").status_code == 422      # auto can't take one
    assert upload(client, sid, "hi_Z_99", "x").status_code == 404
    assert upload(client, 999, "hi_B_01", "कमल").status_code == 404
    r = upload(client, sid, "hi_A_01", "बाद", "correct")
    assert r.json()["status"] == "manual" and r.json()["correct"] is True and not r.json()["awaiting_verification"]


def test_low_confidence_and_failed_transcription_go_to_verify(client):
    sid = new_session(client, new_child(client)["id"])
    low = upload(client, sid, "hi_B_02", "LOW:पिला").json()
    assert low["status"] == "teacher_verify" and low["correct"] is None and low["awaiting_verification"]
    failed = upload(client, sid, "hi_B_03", "FAIL").json()
    assert failed["status"] == "teacher_verify" and "transcription failed" in failed["confidence"]["reasons"]
    assert failed["audio_url"]  # the clip is kept so the teacher can listen


def test_reupload_replaces_the_result(client):
    sid = new_session(client, new_child(client)["id"])
    first = upload(client, sid, "hi_B_01", "कलम").json()
    second = upload(client, sid, "hi_B_01", "कमल").json()
    assert second["id"] == first["id"] and second["correct"] is True


def test_full_session_provisional_then_verified(client, llm):
    child = new_child(client)
    sid = new_session(client, child["id"])
    read_everything_correctly(client, sid)

    fin = client.post(f"/api/sessions/{sid}/finish").json()
    report = fin["report"]
    assert fin["session"]["status"] == "finished"
    assert report["risk_level"] == "provisional"          # English auto items need confirming
    assert report["summary_source"] == "template"         # partial data is never summarised by the LLM
    parent = client.get(f"/api/parent/{report['parent_token']}").json()
    assert parent["ready"] is False
    assert upload(client, sid, "hi_B_01", "कमल").status_code == 409  # finished

    rep = client.get(f"/api/children/{child['id']}/report").json()
    queue = [i for i in rep["items"] if i["awaiting_verification"]]
    assert queue and all(i["lang"] == "en" for i in queue)
    last = None
    for i in queue:
        last = client.patch(f"/api/results/{i['id']}", json={"decision": "correct"}).json()
    final = last["report"]
    assert final["risk_level"] == "low_risk"
    # the result became final with the last verification, so the LLM summary was written then
    assert final["summary_source"] == "llm" and final["summary_stale"] is False
    assert final["teacher_summary"] == GOOD["teacher_summary"]

    # a later change to a final result marks the summary stale; finish refreshes it
    hi_items = [i for i in rep["items"] if i["lang"] == "hi" and i["section"] == "B"]
    for i in hi_items[:5]:
        stale = client.patch(f"/api/results/{i['id']}", json={"decision": "incorrect"}).json()["report"]
    assert stale["risk_level"] == "hindi_support" and stale["summary_stale"] is True
    calls = llm.calls
    refreshed = client.post(f"/api/sessions/{sid}/finish").json()["report"]
    assert refreshed["summary_stale"] is False and llm.calls > calls

    breakdown = refreshed["scoring_breakdown"]
    assert breakdown["hi"]["live_tap_pct"] > 0 and breakdown["en"]["pending_verify"] == 0

    parent = client.get(f"/api/parent/{refreshed['parent_token']}").json()
    assert parent["ready"] and parent["summary_hi"] == GOOD["parent_summary_hi"] and parent["show_help"]
    assert len(parent["tips_hi"]) == 3 and "R01" not in json.dumps(parent, ensure_ascii=False)
    assert client.get("/api/parent/not-a-token").status_code == 404

    summary = client.get("/api/class/summary").json()
    assert summary[0]["risk_level"] == "hindi_support" and summary[0]["pending_verify"] == 0


def test_passage_verification_needs_teacher_count(client):
    sid = new_session(client, new_child(client)["id"])
    passage = bank.items()["en_D_01"]
    words = passage["text"].split()
    r = upload(client, sid, "en_D_01", " ".join(words[:30])).json()
    assert r["words_correct"] == 30
    bad = client.patch(f"/api/results/{r['id']}", json={"decision": "incorrect"})
    assert bad.status_code == 422
    ok = client.patch(f"/api/results/{r['id']}", json={"decision": "incorrect", "words_correct": 35}).json()
    assert ok["result"]["words_correct"] == 35 and ok["result"]["verified"]


def test_manual_tap_can_be_corrected(client):
    sid = new_session(client, new_child(client)["id"])
    r = upload(client, sid, "en_A_01", "b", "correct").json()
    fixed = client.patch(f"/api/results/{r['id']}", json={"decision": "incorrect"}).json()["result"]
    assert fixed["live_tap"] == "incorrect" and fixed["correct"] is False and fixed["status"] == "manual"


def test_audio_can_be_deleted(client):
    child = new_child(client)
    sid = new_session(client, child["id"])
    a = upload(client, sid, "hi_B_01", "कमल").json()
    b = upload(client, sid, "hi_B_02", "पीला").json()
    assert client.delete(f"/api/audio/{a['id']}").status_code == 204
    assert client.get(f"/api/audio/{a['id']}").status_code == 404
    assert client.delete(f"/api/children/{child['id']}/audio").status_code == 204
    assert client.get(f"/api/audio/{b['id']}").status_code == 404
    items = client.get(f"/api/children/{child['id']}/report").json()["items"]
    assert all(i["audio_url"] is None for i in items) and items[0]["correct"] is True  # scores stay


def test_llm_failure_still_gives_a_report(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / "cache")
    # Empty, not deleted: create_app() loads .env, which would restore a deleted key.
    monkeypatch.setenv("GROQ_API_KEY", "")
    app = create_app(db_url=f"sqlite:///{tmp_path / 't.db'}", storage_dir=tmp_path / "s", transcriber=fake_transcriber,
                     teacher_pin=PIN, secret=SECRET)
    c = signed_in(TestClient(app))
    sid = new_session(c, new_child(c)["id"])
    read_everything_correctly(c, sid)
    rep = c.get("/api/children/1/report").json()
    for i in rep["items"]:
        if i["awaiting_verification"]:
            c.patch(f"/api/results/{i['id']}", json={"decision": "correct"})
    report = c.post(f"/api/sessions/{sid}/finish").json()["report"]
    assert report["risk_level"] == "low_risk"
    assert report["summary_source"] == "template" and report["teacher_summary"].startswith("Result: Low risk")
