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
    """
    Walk a cloned repo and return a list of payload dicts.
    Each dict has: name, file, path, cat, tags, lang, desc
    """
    dest = repo_path(device)
    if not dest.exists():
        return []

    exts = PAYLOAD_EXTS.get(device, [".txt"])
    payloads = []

    # HAK5 repos have a payloads/ subdir
    search_root = dest / "payloads" if (dest / "payloads").exists() else dest

    for root, dirs, files in os.walk(search_root):
        # Skip hidden dirs and .git
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            fpath = Path(root) / fname
            ext = fpath.suffix.lower()
            if ext not in exts and ext != "":
                continue
            if fname.startswith("."):
                continue

            rel   = fpath.relative_to(search_root)
            parts = rel.parts

            lang_map = {
                "ducky": "DS1", "bunny": "BB", "turtle": "LT",
                "teensy": "ARD", "usb": "PY",
            }

            # HAK5 repo structure:
            #   payloads/<Category>/<PayloadName>/payload.txt
            # Use parent folder name as payload name when possible
            if len(parts) >= 3:
                # e.g. credentials/WifiGrabber/payload.txt
                cat  = parts[0].replace("_"," ").replace("-"," ").title().upper()
                name = parts[-2].replace("_"," ").replace("-"," ").title()
            elif len(parts) == 2:
                # e.g. credentials/quickcreds.txt
                cat  = parts[0].replace("_"," ").replace("-"," ").title().upper()
                name = fpath.stem.replace("_"," ").replace("-"," ").title()
            else:
                cat  = "GENERAL"
                name = fpath.stem.replace("_"," ").replace("-"," ").title()

            # Read first few lines for description / tags
            desc, tags = _parse_payload_header(fpath, device)

            payloads.append({
                "name": name,
                "file": str(rel),
                "path": str(fpath),
                "cat":  cat,
                "tags": tags,
                "lang": lang_map.get(device, "TXT"),
                "desc": desc,
            })

    # Sort by category then name
    payloads.sort(key=lambda p: (p["cat"], p["name"]))
    return payloads


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
            cat = "SNARFSNARF"
            if "EXFIL" not in tags:
                tags = ["EXFIL"] + [t for t in tags if t != "EXFIL"][:2]
        else:
            cat = "MY PAYLOADS"
        payloads.append({
            "name": fpath.stem.replace("_", " ").title(),
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
    count = len(index_payloads(device))
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
