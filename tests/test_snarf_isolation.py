"""Per-operator CATCH isolation (phone-home receiver)."""

import pytest

from dropper.receiver import SHARED_USER, list_catches, save_snarf_file


@pytest.fixture
def snarf_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr("dropper.receiver.SNARFED_DIR", tmp_path)
    return tmp_path


def _session_count(data: dict) -> int:
    return len(data.get("sessions") or [])


def test_catch_isolated_per_operator(snarf_tmp):
    save_snarf_file(b"alice-data", hostname="host-a", username="alice")
    save_snarf_file(b"bob-data", hostname="host-b", username="bob")

    alice = list_catches("alice")
    bob = list_catches("bob")

    assert _session_count(alice) == 1
    assert _session_count(bob) == 1
    assert alice["total_files"] == 1
    assert bob["total_files"] == 1
    assert (snarf_tmp / "alice").exists()
    assert (snarf_tmp / "bob").exists()
    assert not (snarf_tmp / "alice" / "bob").exists()


def test_unknown_token_falls_back_to_shared():
    from server import _resolve_catch_token

    assert _resolve_catch_token("") == SHARED_USER
    assert _resolve_catch_token("not-a-real-token") == SHARED_USER
