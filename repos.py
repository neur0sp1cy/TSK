#!/usr/bin/env python3
"""
TSK Repo Manager
Clones / updates HAK5 payload repos and indexes payloads from them.
"""

import os, subprocess, json
from pathlib import Path
from typing import Callable
import config as cfg_mod

def load_cfg():
    return cfg_mod.load(cfg_mod.current_user())

def repo_path(device: str) -> Path:
    return cfg_mod.repo_path(device, cfg_mod.current_user())

def payload_path(device: str) -> Path:
    return cfg_mod.payload_path(device, cfg_mod.current_user())

REPO_URLS = {
    "ducky":  "https://github.com/hak5/usbrubberducky-payloads",
    "bunny":  "https://github.com/hak5/bashbunny-payloads",
    "turtle": "https://github.com/hak5/lanturtle-modules",
}

# Extensions we index as payloads per device
PAYLOAD_EXTS = {
    "ducky":  [".txt", ".duck"],
    "bunny":  [".txt"],
    "turtle": [".sh", ".py", ""],
    "teensy": [".ino", ".hex"],
    "usb":    [".py", ".ps1", ".bat", ".sh"],
}

def run_git(args: list, cwd=None) -> tuple[int, str, str]:
    result = subprocess.run(
        ["git"] + args,
        capture_output=True, text=True, cwd=cwd, timeout=60
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()

def clone_repo(device: str, progress_cb: Callable[[str], None] = None) -> bool:
    """Clone a device repo if not already cloned."""
    cfg = load_cfg()
    url = cfg.get("repos", {}).get(device, REPO_URLS.get(device, ""))
    if not url:
        if progress_cb: progress_cb(f"No repo URL configured for {device}")
        return False

    dest = repo_path(device)
    if dest.exists():
        if progress_cb: progress_cb(f"Repo already cloned at {dest}")
        return True

    if progress_cb: progress_cb(f"Cloning {url} ...")
    dest.parent.mkdir(parents=True, exist_ok=True)
    rc, out, err = run_git(["clone", "--depth=1", url, str(dest)])
    if rc == 0:
        if progress_cb: progress_cb(f"✓ Cloned {device} repo")
        return True
    else:
        if progress_cb: progress_cb(f"✗ Clone failed: {err}")
        return False

def update_repo(device: str, progress_cb: Callable[[str], None] = None) -> bool:
    """Pull latest changes for a cloned repo."""
    dest = repo_path(device)
    if not dest.exists():
        return clone_repo(device, progress_cb)
    if progress_cb: progress_cb(f"Updating {device} repo...")
    rc, out, err = run_git(["pull", "--ff-only"], cwd=dest)
    if rc == 0:
        if progress_cb: progress_cb(f"✓ {device}: {out or 'Already up to date'}")
        return True
    else:
        if progress_cb: progress_cb(f"✗ Update failed: {err}")
        return False

def index_payloads(device: str) -> list[dict]:
    """Return flat payload rows (one per file) from payload sets."""
    dest = repo_path(device)
    if not dest.exists():
        return []
    search_root = dest / "payloads" if (dest / "payloads").exists() else dest
    from payload_sets import index_payload_sets, flatten_set_to_rows

    sets = index_payload_sets(search_root, device, _parse_payload_header, operator_owned=False)
    rows: list[dict] = []
    for s in sets:
        rows.extend(flatten_set_to_rows(s))
    return rows


def index_payload_sets_for_device(device: str) -> list[dict]:
    dest = repo_path(device)
    if not dest.exists():
        return []
    search_root = dest / "payloads" if (dest / "payloads").exists() else dest
    from payload_sets import index_payload_sets

    return index_payload_sets(search_root, device, _parse_payload_header, operator_owned=False)


def index_user_payload_sets(device: str, username: str = "default") -> list[dict]:
    """Index MY PAYLOADS package folders under users/<user>/payloads/<device>/."""
    if device == "usb":
        return []
    base = cfg_mod.USERS_DIR / username / "payloads" / device
    if not base.exists():
        return []

    from payload_sets import index_payload_sets

    sets = index_payload_sets(base, device, _parse_payload_header, operator_owned=True)
    for s in sets:
        s["cat"] = "MY PAYLOADS"
        s["operator_owned"] = True
    return sets


def index_user_payloads(device: str, username: str = "default") -> list[dict]:
    """Index payloads saved under users/<username>/payloads/<device>/."""
    base = cfg_mod.USERS_DIR / username / "payloads" / device
    if not base.exists():
        return []

    exts = PAYLOAD_EXTS.get(device, [".txt"])
    lang_map = {
        "ducky": "DS1", "bunny": "BB", "turtle": "LT",
        "teensy": "ARD", "usb": "PY",
    }
    payloads = []
    for fpath in sorted(base.iterdir()):
        if not fpath.is_file() or fpath.name.startswith("."):
            continue
        if device == "usb":
            from dropper.lure_builder import is_lure_companion_file, iter_lure_skip_basenames
            if is_lure_companion_file(fpath) or fpath.name in iter_lure_skip_basenames(username):
                continue
        ext = fpath.suffix.lower()
        if ext not in exts and ext not in (".sh", ".ps1", ".hex"):
            continue
        lang = "PS1" if ext == ".ps1" else lang_map.get(device, "TXT")
        if ext == ".sh":
            lang = "SH"
        if ext == ".hex":
            lang = "ARD"
        desc, tags = _parse_payload_header(fpath, device)
        is_snarf = device == "usb" and _is_snarf_usb_file(fpath)
        if is_snarf:
            cat = "EXFILS"
            if "EXFIL" not in tags:
                tags = ["EXFIL"] + [t for t in tags if t != "EXFIL"][:2]
        else:
            cat = "MY PAYLOADS"
        payloads.append({
            "name": fpath.stem.replace("_", " "),
            "file": fpath.name,
            "path": str(fpath.resolve()),
            "cat": cat,
            "tags": tags,
            "lang": lang,
            "desc": desc,
            "operator_owned": True,
        })
    return payloads


def _is_snarf_usb_file(fpath: Path) -> bool:
    try:
        with open(fpath, errors="ignore") as f:
            head = f.read(280)
        return "SnarfSnarf" in head
    except OSError:
        return False

def _parse_payload_header(fpath: Path, device: str) -> tuple[str, list[str]]:
    """Extract description and tags from payload file comments."""
    desc = ""
    tags = []
    tag_keywords = {
        "cred": "CREDS", "password": "CREDS", "hash": "CREDS",
        "exfil": "EXFIL", "steal": "EXFIL", "copy": "EXFIL",
        "recon": "RECON", "enum": "RECON", "scan": "RECON", "info": "RECON",
        "persist": "PERSIST", "backdoor": "PERSIST", "install": "PERSIST",
        "exec": "EXEC", "shell": "EXEC", "run": "EXEC", "download": "EXEC",
        "net": "NET", "network": "NET", "wifi": "NET",
        "hid": "HID", "keyboard": "HID", "inject": "HID",
    }
    try:
        with open(fpath, errors="ignore") as f:
            lines = [f.readline() for _ in range(15)]
        for line in lines:
            line = line.strip()
            low = line.lower()
            # DuckyScript / bash comments
            if low.startswith(("rem ", "# ", "// ")):
                content = line.split(None, 1)[1] if " " in line else ""
                if not desc and len(content) > 8 and not any(
                    kw in content.lower() for kw in ["author:", "version:", "target:", "date:"]
                ):
                    desc = content[:80]
                # Tag detection from content
                for kw, tag in tag_keywords.items():
                    if kw in low and tag not in tags:
                        tags.append(tag)
    except Exception:
        pass

    if not desc:
        desc = f"{fpath.stem.replace('_',' ').replace('-',' ').title()} payload"
    if not tags:
        # Guess from filename
        fname = fpath.stem.lower()
        for kw, tag in tag_keywords.items():
            if kw in fname and tag not in tags:
                tags.append(tag)
    if not tags:
        tags = ["EXEC"]
    return desc, tags[:3]

def repo_status(device: str) -> dict:
    """Return status info for a device repo."""
    dest = repo_path(device)
    if not dest.exists():
        return {"cloned": False, "commits": 0, "branch": "", "payload_count": 0}
    rc, branch, _ = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=dest)
    _, log, _     = run_git(["rev-list", "--count", "HEAD"], cwd=dest)
    count = len(index_payload_sets_for_device(device))
    return {
        "cloned": True,
        "branch": branch if rc == 0 else "unknown",
        "commits": int(log) if log.isdigit() else 0,
        "payload_count": count,
    }

def all_repo_statuses() -> dict:
    return {d: repo_status(d) for d in REPO_URLS}

if __name__ == "__main__":
    for dev in REPO_URLS:
        st = repo_status(dev)
        cloned = "✓" if st["cloned"] else "○"
        print(f"  {cloned} {dev:8} payloads={st['payload_count']}  branch={st['branch']}")
