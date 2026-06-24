"""
Path confinement — prevent directory traversal on file read/write APIs.
"""

import os
from pathlib import Path

from config import REPOS_DIR, USERS_DIR, PAYLOADS_DIR, BASE_DIR

STATIC_PAYLOADS_DIR = BASE_DIR / "web" / "static" / "payloads"
SNARFED_DIR = BASE_DIR / "snarfed"


def allowed_bases(username: str = "default") -> list[Path]:
    """Directories the server may read or write payload files within.
    Scoped to the authenticated user's own directory - not the whole users/ tree.
    """
    bases = [
        REPOS_DIR.resolve(),
        PAYLOADS_DIR.resolve(),
        SNARFED_DIR.resolve(),
    ]
    if STATIC_PAYLOADS_DIR.is_dir():
        bases.append(STATIC_PAYLOADS_DIR.resolve())
    user_dir = USERS_DIR / username
    user_payloads = user_dir / "payloads"
    # Only allow the authenticated user's own directory, not all of USERS_DIR
    if user_dir.exists():
        bases.append(user_dir.resolve())
    if user_payloads.exists():
        bases.append(user_payloads.resolve())
    return bases


def safe_path(path: str, username: str = "default", must_exist: bool = True) -> Path:
    """
    Resolve a user-supplied path and ensure it stays within allowed bases.
    Raises ValueError if traversal is detected or path is empty.
    """
    if not path or not str(path).strip():
        raise ValueError("Empty path")

    resolved = Path(os.path.expanduser(os.path.expandvars(str(path).strip()))).resolve()

    for base in allowed_bases(username):
        try:
            resolved.relative_to(base)
            if must_exist and not resolved.is_file():
                raise ValueError(f"Not a file: {resolved}")
            return resolved
        except ValueError:
            continue

    raise ValueError(f"Path outside allowed directories: {resolved}")


def user_payload_dir(username: str, device: str) -> Path:
    """Operator-owned payload directory (created on demand)."""
    p = USERS_DIR / username / "payloads" / device
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


def is_user_payload_path(path: str, username: str) -> bool:
    """True if path is under users/<username>/payloads/."""
    if not path:
        return False
    try:
        resolved = Path(path).resolve()
        base = (USERS_DIR / username / "payloads").resolve()
        resolved.relative_to(base)
        return True
    except (ValueError, OSError):
        return False
