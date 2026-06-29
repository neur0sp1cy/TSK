"""Tests for path confinement."""

import pytest

from paths import safe_path


def test_safe_path_accepts_repo_file(tmp_path, monkeypatch):
    monkeypatch.setattr("paths.REPOS_DIR", tmp_path)
    monkeypatch.setattr("paths.allowed_bases", lambda username="default": [tmp_path.resolve()])
    f = tmp_path / "ducky" / "payload.txt"
    f.parent.mkdir(parents=True)
    f.write_text("REM test")
    result = safe_path(str(f))
    assert result == f.resolve()


def test_safe_path_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr("paths.REPOS_DIR", tmp_path)
    monkeypatch.setattr("paths.allowed_bases", lambda username="default": [tmp_path.resolve()])
    evil = str(tmp_path / ".." / ".." / "etc" / "passwd")
    with pytest.raises(ValueError, match="outside allowed"):
        safe_path(evil, must_exist=False)
