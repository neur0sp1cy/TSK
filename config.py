#!/usr/bin/env python3
"""
TSK Config Manager
Per-user configs stored in users/<username>/
Repos stored in repos/ (shared) or users/<username>/repos/ (per-user)
"""

import json, os, hashlib, hmac, re
from pathlib import Path

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False

MIN_PASSWORD_LEN = 8
OPERATOR_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{2,32}$")

SENSITIVE_CONFIG_KEYS = frozenset({"turtle_password", "catch_token"})

# ── Base paths - always relative to this file's location ─────────────────────
BASE_DIR     = Path(__file__).resolve().parent   # absolute path to TSK dir
USERS_DIR    = BASE_DIR / "users"
REPOS_DIR    = BASE_DIR / "repos"
PAYLOADS_DIR = BASE_DIR / "payloads"

# Ensure base dirs exist
REPOS_DIR.mkdir(parents=True, exist_ok=True)
PAYLOADS_DIR.mkdir(parents=True, exist_ok=True)
USERS_DIR.mkdir(parents=True, exist_ok=True)

# ── User auth ─────────────────────────────────────────────────────────────────

USERS_FILE = USERS_DIR / "users.json"

DEFAULTS = {
    "lhost":          "",
    "lport":          "1337",
    "catch_token":    "",   # per-operator routing token embedded in phone-home URLs
    "editor":         os.environ.get("EDITOR", "nano"),
    "encoder_jar":    str(BASE_DIR / "encoder.jar"),
    "ducky_mount":    "",
    "bunny_mount":    "",
    "usb_mount":      "",
    "usb_auto_eject": False,
    "turtle_ip":       "172.16.84.1",
    "turtle_user":     "root",
    "turtle_port":     "22",
    "turtle_password": "",  # OG Turtle: blank (Enter) or hak5lan
    "theme":          "neon",
    "clock_24h":      True,
    "music_enabled":  True,
    "repos": {
        "ducky":  "https://github.com/hak5/usbrubberducky-payloads",
        "bunny":  "https://github.com/hak5/bashbunny-payloads",
        "turtle": "https://github.com/hak5/lanturtle-modules",
    },
    "last_device": "ducky",
    "repo_dir":    str(REPOS_DIR),      # shared repos by default
    "teensy_mcu":  "mk20dx256",         # Teensy 3.2 default; use TEENSY40 for Teensy 4.0
}

def _hash_password(password: str) -> str:
    if HAS_BCRYPT:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    return "sha256:" + hashlib.sha256(password.encode()).hexdigest()

def _verify_password(password: str, stored: str) -> bool:
    if stored.startswith("$2") and HAS_BCRYPT:
        try:
            return bcrypt.checkpw(password.encode(), stored.encode())
        except ValueError:
            return False
    legacy = stored[7:] if stored.startswith("sha256:") else stored
    computed = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(computed, legacy)

def public_config(cfg: dict) -> dict:
    """Strip secrets before sending config to the browser."""
    pub = dict(cfg)
    for key in SENSITIVE_CONFIG_KEYS:
        pub[f"{key}_set"] = bool(pub.get(key))
        pub[key] = ""
    return pub


def redact_for_log(data: dict) -> dict:
    return {
        k: ("***" if k in SENSITIVE_CONFIG_KEYS and v else v)
        for k, v in data.items()
    }

def _needs_rehash(stored: str) -> bool:
    return HAS_BCRYPT and not stored.startswith("$2")

def load_users() -> dict:
    if not USERS_FILE.exists():
        return {}
    try:
        with open(USERS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(users: dict) -> None:
    USERS_DIR.mkdir(parents=True, exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def create_user(username: str, password: str) -> dict:
    """Create a new user. Returns user dict."""
    username = username.strip()
    if not OPERATOR_NAME_RE.match(username):
        raise ValueError("Operator name must be 2-32 characters: letters, numbers, underscore, hyphen")
    if len(password) < MIN_PASSWORD_LEN:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LEN} characters")
    users = load_users()
    if username in users:
        raise ValueError(f"User '{username}' already exists")
    user_dir = USERS_DIR / username
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "payloads").mkdir(exist_ok=True)
    user = {
        "username":   username,
        "password":   _hash_password(password),
        "created":    __import__("datetime").datetime.now().isoformat(),
        "user_dir":   str(user_dir),
        "repo_dir":   str(REPOS_DIR),   # shared by default
        "config":     DEFAULTS.copy(),
    }
    users[username] = user
    save_users(users)
    return user

def authenticate(username: str, password: str) -> dict | None:
    """Returns user dict if auth succeeds, None otherwise."""
    users = load_users()
    user = users.get(username)
    if not user:
        return None
    if _verify_password(password, user["password"]):
        if _needs_rehash(user["password"]):
            user["password"] = _hash_password(password)
            users[username] = user
            save_users(users)
        return user
    return None

def change_password(username: str, current_password: str, new_password: str) -> None:
    """Verify current password and set a new one."""
    if len(new_password) < MIN_PASSWORD_LEN:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LEN} characters")
    users = load_users()
    user = users.get(username)
    if not user:
        raise ValueError("Operator not found")
    if not _verify_password(current_password, user["password"]):
        raise ValueError("Current password is incorrect")
    user["password"] = _hash_password(new_password)
    users[username] = user
    save_users(users)


def rename_user(old_username: str, new_username: str, password: str) -> None:
    """Rename operator account, user directory, and snarfed catches folder."""
    old = old_username.strip()
    new = new_username.strip()
    if not OPERATOR_NAME_RE.match(new):
        raise ValueError("Operator name must be 2-32 characters: letters, numbers, underscore, hyphen")
    if new == old:
        raise ValueError("New name is the same as the current name")
    if not authenticate(old, password):
        raise ValueError("Current password is incorrect")
    users = load_users()
    if old not in users:
        raise ValueError("Operator not found")
    if new in users:
        raise ValueError(f"Operator '{new}' already exists")

    user = users.pop(old)
    user["username"] = new
    user["user_dir"] = str(USERS_DIR / new)

    old_dir = USERS_DIR / old
    new_dir = USERS_DIR / new
    if old_dir.exists():
        old_dir.rename(new_dir)
    else:
        new_dir.mkdir(parents=True, exist_ok=True)
        (new_dir / "payloads").mkdir(exist_ok=True)

    cfg = load(new)
    cfg["username"] = new
    save(cfg, new)

    snarfed_root = BASE_DIR / "snarfed"
    snarfed_old = snarfed_root / old
    snarfed_new = snarfed_root / new
    if snarfed_old.is_dir() and not snarfed_new.exists():
        snarfed_old.rename(snarfed_new)

    users[new] = user
    save_users(users)

def list_users() -> list[str]:
    return list(load_users().keys())

def delete_user(username: str) -> bool:
    users = load_users()
    if username not in users:
        return False
    del users[username]
    save_users(users)
    return True

# ── Per-user config ───────────────────────────────────────────────────────────

def user_config_path(username: str) -> Path:
    return USERS_DIR / username / "config.json"

def load(username: str = "default") -> dict:
    """Load config for a user, merging with defaults."""
    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    PAYLOADS_DIR.mkdir(parents=True, exist_ok=True)

    cfg_path = user_config_path(username)
    if not cfg_path.exists():
        cfg = DEFAULTS.copy()
        cfg["username"] = username
        save(cfg, username)
        return cfg
    try:
        with open(cfg_path) as f:
            data = json.load(f)
        merged = DEFAULTS.copy()
        merged.update(data)
        merged["username"] = username
        return merged
    except Exception:
        return {**DEFAULTS, "username": username}

def save(cfg: dict, username: str = "default") -> None:
    user_dir = USERS_DIR / username
    user_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = user_config_path(username)
    with open(cfg_path, "w") as f:
        json.dump(cfg, f, indent=2)

def get_or_create_catch_token(username: str) -> str:
    """Return the operator's catch routing token, generating one if absent."""
    import secrets as _secrets
    cfg = load(username)
    token = (cfg.get("catch_token") or "").strip()
    if not token:
        token = _secrets.token_hex(8)   # 16-char hex, embedded in scripts
        cfg["catch_token"] = token
        save(cfg, username)
    return token


def get(key: str, username: str = "default", fallback=None):
    return load(username).get(key, fallback)

def set_key(key: str, value, username: str = "default") -> None:
    cfg = load(username)
    cfg[key] = value
    save(cfg, username)

# ── Repo paths (now project-relative) ────────────────────────────────────────

def repo_path(device: str, username: str = "default") -> Path:
    """Get repo path - shared REPOS_DIR by default."""
    return REPOS_DIR / device

def payload_path(device: str, username: str = "default") -> Path:
    """Get user's local payload path."""
    p = USERS_DIR / username / "payloads" / device
    p.mkdir(parents=True, exist_ok=True)
    return p

# ── Session (active logged-in user) ──────────────────────────────────────────

_session: dict = {"username": "default", "user": None}

def set_session(username: str, user: dict) -> None:
    _session["username"] = username
    _session["user"]     = user

def get_session() -> dict:
    return _session

def current_user() -> str:
    return _session["username"]
