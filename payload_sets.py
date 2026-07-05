"""
Payload-set indexing: one folder = one payload (mini-repo), multiple root files.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Callable

from flash import classify_payload_file, detect_binary_type, is_text_payload_file

MAX_BINARY_BYTES = 10 * 1024 * 1024
MAX_TEXT_BYTES = 512 * 1024

LANG_MAP = {
    "ducky": "DS1",
    "bunny": "BB",
    "turtle": "LT",
    "teensy": "ARD",
    "usb": "PY",
}

EXT_LANG = {
    ".duck": "DS1",
    ".sh": "SH",
    ".py": "PY",
    ".ps1": "PS1",
    ".bat": "BAT",
    ".md": "MD",
    ".ino": "ARD",
    ".hex": "ARD",
}


def _title_name(stem: str) -> str:
    return stem.replace("_", " ").replace("-", " ").strip() or stem


def _cat_and_set_name(rel_parts: tuple[str, ...], set_folder: str) -> tuple[str, str]:
    if len(rel_parts) >= 2 and rel_parts[0].lower() == "library":
        cat = rel_parts[1].replace("_", " ").replace("-", " ").upper()
        return cat, _title_name(set_folder)
    if rel_parts:
        cat = rel_parts[0].replace("_", " ").replace("-", " ").upper()
        return cat, _title_name(set_folder)
    return "GENERAL", _title_name(set_folder)


def _file_lang(fname: str, device: str, role: str) -> str:
    if role == "readme":
        return "MD"
    ext = Path(fname).suffix.lower()
    if ext == ".ps1":
        return "PS1"
    if ext == ".sh":
        return "SH"
    if ext in EXT_LANG:
        return EXT_LANG[ext]
    if device == "ducky":
        return "DS1"
    return LANG_MAP.get(device, "TXT")


def _sort_files(files: list[dict]) -> list[dict]:
    role_order = {"readme": 0, "primary": 1, "companion": 2, "binary": 3}

    def key(f: dict) -> tuple:
        r = role_order.get(f.get("file_role"), 9)
        name = (f.get("display_name") or "").lower()
        if f.get("file_role") == "primary":
            if name == "payload.txt":
                return (r, "0")
            if name == "payload.sh":
                return (r, "1")
        return (r, name)

    return sorted(files, key=key)


def _is_payload_root(names_lower: set[str], device: str) -> bool:
    if "payload.txt" in names_lower:
        return True
    if device == "bunny" and "payload.sh" in names_lower:
        return True
    return False


def _is_hidden_bunny_deploy_slot(root: Path, search_root: Path, device: str) -> bool:
    """Hide upstream switch1/switch2 placeholder folders from browse (FLASH still uses switch UI)."""
    if device != "bunny":
        return False
    try:
        rel = root.relative_to(search_root)
    except ValueError:
        return False
    parts = tuple(p.lower() for p in rel.parts)
    return len(parts) == 1 and parts[0] in ("switch1", "switch2")


def discover_payload_roots(search_root: Path, device: str) -> list[Path]:
    roots: list[Path] = []
    if not search_root.is_dir():
        return roots

    for root, dirs, files in os.walk(search_root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        names_lower = {f.lower() for f in files}
        if _is_payload_root(names_lower, device):
            root_path = Path(root).resolve()
            if not _is_hidden_bunny_deploy_slot(root_path, search_root, device):
                roots.append(root_path)
            dirs.clear()
    return roots


def _scan_payload_root(
    root: Path,
    search_root: Path,
    device: str,
    parse_header: Callable,
    operator_owned: bool = False,
) -> dict | None:
    children = [p for p in root.iterdir() if p.is_file() and not p.name.startswith(".")]
    if not children:
        return None

    rel = root.relative_to(search_root)
    set_id = str(rel).replace("\\", "/")
    cat, set_name = _cat_and_set_name(rel.parts, root.name)

    primary_path: Path | None = None
    primary_file: str | None = None
    if (root / "payload.txt").is_file():
        primary_path = root / "payload.txt"
        primary_file = "payload.txt"
    elif device == "bunny" and (root / "payload.sh").is_file():
        primary_path = root / "payload.sh"
        primary_file = "payload.sh"

    files: list[dict] = []
    for fpath in children:
        role, skip = classify_payload_file(fpath)
        if skip:
            continue
        try:
            size = fpath.stat().st_size
        except OSError:
            continue

        rel_file = str(fpath.relative_to(search_root)).replace("\\", "/")

        if role == "binary":
            if size > MAX_BINARY_BYTES:
                continue
            btype = detect_binary_type(fpath)
            files.append({
                "display_name": fpath.name,
                "file": rel_file,
                "path": str(fpath.resolve()),
                "file_role": "binary",
                "readonly": True,
                "lang": btype or "BIN",
                "binary_type": btype or "BIN",
                "size": size,
                "is_primary": False,
            })
            continue

        if role == "readme":
            files.append({
                "display_name": fpath.name,
                "file": rel_file,
                "path": str(fpath.resolve()),
                "file_role": "readme",
                "readonly": not operator_owned,
                "lang": "MD",
                "is_primary": False,
            })
            continue

        if size > MAX_TEXT_BYTES:
            continue
        if not is_text_payload_file(fpath):
            btype = detect_binary_type(fpath)
            if btype:
                if size > MAX_BINARY_BYTES:
                    continue
                files.append({
                    "display_name": fpath.name,
                    "file": rel_file,
                    "path": str(fpath.resolve()),
                    "file_role": "binary",
                    "readonly": True,
                    "lang": btype,
                    "binary_type": btype,
                    "size": size,
                    "is_primary": False,
                })
            continue

        is_primary = primary_path is not None and fpath.resolve() == primary_path.resolve()
        file_role = "primary" if is_primary else "companion"
        files.append({
            "display_name": fpath.name,
            "file": rel_file,
            "path": str(fpath.resolve()),
            "file_role": file_role,
            "readonly": False,
            "lang": _file_lang(fpath.name, device, file_role),
            "is_primary": is_primary,
        })

    if not files:
        return None

    files = _sort_files(files)
    if not primary_path:
        for f in files:
            if f["file_role"] in ("primary", "companion") and f.get("path"):
                primary_path = Path(f["path"])
                primary_file = f["display_name"]
                f["file_role"] = "primary"
                f["is_primary"] = True
                break

    header_path = primary_path or Path(files[0]["path"])
    desc, tags = parse_header(header_path, device)

    return {
        "set_id": set_id,
        "name": set_name,
        "set_name": set_name,
        "cat": cat,
        "tags": tags,
        "desc": desc,
        "lang": LANG_MAP.get(device, "TXT"),
        "primary_path": str(primary_path.resolve()) if primary_path else files[0]["path"],
        "primary_file": primary_file or files[0]["display_name"],
        "operator_owned": operator_owned,
        "files": files,
    }


def index_payload_sets(
    search_root: Path,
    device: str,
    parse_header: Callable,
    operator_owned: bool = False,
) -> list[dict]:
    sets: list[dict] = []
    for root in discover_payload_roots(search_root, device):
        entry = _scan_payload_root(root, search_root, device, parse_header, operator_owned)
        if entry:
            sets.append(entry)
    sets.sort(key=lambda s: (s["cat"], s["name"].lower()))
    return sets


def flatten_set_to_rows(payload_set: dict) -> list[dict]:
    rows = []
    for f in payload_set.get("files", []):
        rows.append({
            "name": payload_set["name"],
            "set_id": payload_set["set_id"],
            "set_name": payload_set["set_name"],
            "cat": payload_set["cat"],
            "tags": payload_set.get("tags", []),
            "desc": payload_set.get("desc", ""),
            "lang": f.get("lang") or payload_set.get("lang", "TXT"),
            "file": f.get("file", ""),
            "path": f.get("path", ""),
            "display_name": f.get("display_name", ""),
            "file_role": f.get("file_role", "companion"),
            "readonly": f.get("readonly", False),
            "is_primary": f.get("is_primary", False),
            "operator_owned": payload_set.get("operator_owned", False),
            "primary_path": payload_set.get("primary_path", ""),
            "binary_type": f.get("binary_type"),
            "size": f.get("size"),
        })
    return rows


_PINNED_CAT_ORDER = ("MY PAYLOADS",)


def sort_payload_categories(cats: list[str]) -> list[str]:
    """Alphabetical categories with operator-owned MY PAYLOADS pinned last."""
    pinned = [c for c in _PINNED_CAT_ORDER if c in cats]
    rest = sorted((c for c in cats if c not in _PINNED_CAT_ORDER), key=str.lower)
    return rest + pinned


def sets_to_grouped_db(sets: list[dict]) -> list[dict]:
    by_cat: dict[str, list] = {}
    for s in sets:
        by_cat.setdefault(s["cat"], []).append(s)
    return [{"cat": cat, "sets": by_cat[cat]} for cat in sort_payload_categories(list(by_cat))]


def count_sets(sets: list[dict]) -> int:
    return len(sets)


def _load_turtle_module_list(modules_dir: Path) -> dict[str, str]:
    listing = modules_dir / "module_list"
    out: dict[str, str] = {}
    if not listing.is_file():
        return out
    try:
        for line in listing.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                out[parts[0]] = parts[1].strip()
    except OSError:
        pass
    return out


def _parse_turtle_module_desc(fpath: Path) -> str:
    try:
        with open(fpath, encoding="utf-8", errors="ignore") as f:
            for _ in range(25):
                line = f.readline()
                if not line:
                    break
                m = re.search(r'DESCRIPTION=["\']([^"\']+)["\']', line.strip())
                if m:
                    return m.group(1).strip()[:120]
    except OSError:
        pass
    return ""


def _turtle_module_tags(name: str, desc: str) -> list[str]:
    tag_keywords = {
        "cred": "CREDS", "password": "CREDS", "hash": "CREDS", "quickcreds": "CREDS",
        "exfil": "EXFIL", "steal": "EXFIL", "copy": "EXFIL", "dump": "EXFIL",
        "recon": "RECON", "enum": "RECON", "scan": "RECON", "nmap": "RECON", "sniff": "RECON",
        "persist": "PERSIST", "autossh": "PERSIST", "tunnel": "PERSIST", "ssh": "PERSIST",
        "exec": "EXEC", "shell": "EXEC", "meterpreter": "EXEC", "netcat": "EXEC",
        "net": "NET", "network": "NET", "dns": "NET", "vpn": "NET", "openvpn": "NET",
        "spoof": "NET", "responder": "NET", "portfwd": "NET",
    }
    tags: list[str] = []
    blob = f"{name} {desc}".lower()
    for kw, tag in tag_keywords.items():
        if kw in blob and tag not in tags:
            tags.append(tag)
    return tags[:3] if tags else ["EXEC"]


def index_turtle_module_sets(
    modules_dir: Path,
    parse_header: Callable | None = None,
) -> list[dict]:
    """Index LAN Turtle modules: single extensionless files under modules/."""
    if not modules_dir.is_dir():
        return []

    module_list = _load_turtle_module_list(modules_dir)
    skip = {"module_list"}
    sets: list[dict] = []

    for fpath in sorted(modules_dir.iterdir(), key=lambda p: p.name.lower()):
        if not fpath.is_file() or fpath.name.startswith(".") or fpath.name in skip:
            continue
        try:
            if fpath.stat().st_size > MAX_TEXT_BYTES:
                continue
        except OSError:
            continue

        stem = fpath.stem or fpath.name
        set_name = _title_name(stem)
        desc = module_list.get(fpath.name) or module_list.get(stem) or _parse_turtle_module_desc(fpath)
        if not desc and parse_header:
            desc, _ = parse_header(fpath, "turtle")
        if not desc:
            desc = f"{set_name} module"
        tags = _turtle_module_tags(stem, desc)
        rel_file = f"modules/{fpath.name}"
        resolved = str(fpath.resolve())

        sets.append({
            "set_id": rel_file,
            "name": set_name,
            "set_name": set_name,
            "cat": "MODULES",
            "tags": tags,
            "desc": desc,
            "lang": "LT",
            "primary_path": resolved,
            "primary_file": fpath.name,
            "operator_owned": False,
            "files": [{
                "display_name": fpath.name,
                "file": rel_file,
                "path": resolved,
                "file_role": "primary",
                "readonly": False,
                "lang": "SH",
                "is_primary": True,
            }],
        })

    return sets


def manifest_paths_for_set(payload_set: dict) -> list[Path]:
    return [Path(f["path"]) for f in payload_set.get("files", []) if f.get("path")]
