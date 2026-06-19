"""Per-operator flash deployment log."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from config import USERS_DIR

_MAX_ENTRIES = 100


def _path(user: str) -> Path:
    return USERS_DIR / user / "deployments.json"


def append_deployment(user: str, entry: dict[str, Any]) -> None:
    path = _path(user)
    path.parent.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    if path.is_file():
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            entries = []
    row = {"time": datetime.now().isoformat(timespec="seconds"), **entry}
    entries.insert(0, row)
    path.write_text(json.dumps(entries[:_MAX_ENTRIES], indent=2), encoding="utf-8")


def list_deployments(user: str, limit: int = 50) -> list[dict[str, Any]]:
    path = _path(user)
    if not path.is_file():
        return []
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    limit = max(1, min(limit, _MAX_ENTRIES))
    return entries[:limit]
