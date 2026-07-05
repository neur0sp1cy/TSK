"""Phone-home CATCH receiver API smoke test (no USB hardware required)."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def snarf_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr("dropper.receiver.SNARFED_DIR", tmp_path)
    return tmp_path


def test_snarf_post_accepts_upload(snarf_tmp):
    from server import app

    client = TestClient(app)
    resp = client.post(
        "/api/snarf",
        files={"file": ("lab-test.txt", b"tsk-v1-smoke", "text/plain")},
        data={"hostname": "lab-victim", "source": "pytest"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("ok") is True
    assert body.get("size") == len(b"tsk-v1-smoke")
