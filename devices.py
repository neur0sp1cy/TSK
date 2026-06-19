#!/usr/bin/env python3
"""
TSK Device Detection
Polls USB for known Hak5 / HID devices and reports status.
Works without root on Linux/macOS via /sys or hid enumeration.
Falls back gracefully if pyusb / hid not installed.
"""

import os
import sys
import glob
import subprocess
from dataclasses import dataclass, field
from typing import Optional

# ── Known device USB IDs ──────────────────────────────────────────────────────

KNOWN_DEVICES = {
    # Hak5 USB Rubber Ducky (OG) — HID keyboard mode
    (0x03eb, 0x2042): {
        "name": "USB Rubber Ducky",
        "short": "DUCKY",
        "key": "ducky",
        "color": "yellow",
        "mount_type": "hid",
    },
    # OG Rubber Ducky — Atmel HID (your device)
    (0x03eb, 0x2401): {
        "name": "USB Rubber Ducky",
        "short": "DUCKY",
        "key": "ducky",
        "color": "yellow",
        "mount_type": "hid",
    },
    # Hak5 Bash Bunny (OG) — multiple modes
    (0x1d6b, 0x0104): {
        "name": "Bash Bunny",
        "short": "BUNNY",
        "key": "bunny",
        "color": "white",
        "mount_type": "mass_storage",
    },
    # Bash Bunny OG — RNDIS/Ethernet Gadget mode (most common)
    (0xf000, 0xfff0): {
        "name": "Bash Bunny",
        "short": "BUNNY",
        "key": "bunny",
        "color": "white",
        "mount_type": "mass_storage",
    },
    # Bash Bunny arming mode (storage)
    (0xf000, 0x0001): {
        "name": "Bash Bunny",
        "short": "BUNNY",
        "key": "bunny",
        "color": "white",
        "mount_type": "mass_storage",
    },
    # Bash Bunny CDC serial
    (0x0525, 0xa4a7): {
        "name": "Bash Bunny",
        "short": "BUNNY",
        "key": "bunny",
        "color": "white",
        "mount_type": "mass_storage",
    },
    # Hak5 LAN Turtle (CDC Ethernet)
    (0x0525, 0xa4a2): {
        "name": "LAN Turtle",
        "short": "TURTLE",
        "key": "turtle",
        "color": "green",
        "mount_type": "ethernet",
    },
    # OG LAN Turtle — Realtek RTL8152 Fast Ethernet (your device)
    (0x0bda, 0x8152): {
        "name": "LAN Turtle",
        "short": "TURTLE",
        "key": "turtle",
        "color": "green",
        "mount_type": "ethernet",
    },
    # Teensy 4.0
    (0x16c0, 0x0486): {
        "name": "Teensy",
        "short": "TEENSY",
        "key": "teensy",
        "color": "magenta",
        "mount_type": "hid",
    },
    # Arduino Pro Micro (common clone VID/PID)
    (0x1b4f, 0x9206): {
        "name": "Arduino Pro Micro",
        "short": "ARDUINO",
        "key": "teensy",
        "color": "magenta",
        "mount_type": "hid",
    },
}

# ── Device status dataclass ───────────────────────────────────────────────────

@dataclass
class DeviceStatus:
    key: str
    name: str
    short: str
    color: str
    connected: bool = False
    mount_path: Optional[str] = None
    vid: Optional[int] = None
    pid: Optional[int] = None
    extra: dict = field(default_factory=dict)

# ── Detection backends ────────────────────────────────────────────────────────

def _detect_via_pyusb() -> list[tuple[int, int]]:
    """Use pyusb to enumerate connected USB devices."""
    try:
        import usb.core
        devices = usb.core.find(find_all=True)
        return [(d.idVendor, d.idProduct) for d in devices]
    except Exception:
        return []

def _detect_via_sysfs() -> list[tuple[int, int]]:
    """Parse /sys/bus/usb/devices on Linux — no root needed."""
    found = []
    try:
        base = "/sys/bus/usb/devices"
        if not os.path.isdir(base):
            return found
        for dev in os.listdir(base):
            vid_path = os.path.join(base, dev, "idVendor")
            pid_path = os.path.join(base, dev, "idProduct")
            if os.path.exists(vid_path) and os.path.exists(pid_path):
                try:
                    vid = int(open(vid_path).read().strip(), 16)
                    pid = int(open(pid_path).read().strip(), 16)
                    found.append((vid, pid))
                except Exception:
                    pass
    except Exception:
        pass
    return found

def _detect_via_lsusb() -> list[tuple[int, int]]:
    """Fall back to parsing lsusb output."""
    found = []
    try:
        result = subprocess.run(
            ["lsusb"], capture_output=True, text=True, timeout=3
        )
        for line in result.stdout.splitlines():
            # Format: Bus 001 Device 002: ID 03eb:2042 ...
            parts = line.split("ID ")
            if len(parts) > 1:
                id_part = parts[1].split()[0]
                if ":" in id_part:
                    vid_str, pid_str = id_part.split(":")
                    found.append((int(vid_str, 16), int(pid_str, 16)))
    except Exception:
        pass
    return found

def _bunny_signature(path: str) -> bool:
    """Return True if path looks like a Bash Bunny arming-mode mount (payloads/ + loot/ dirs)."""
    try:
        return os.path.isdir(os.path.join(path, "payloads")) and os.path.isdir(os.path.join(path, "loot"))
    except Exception:
        return False


def validate_bunny_mount(path: str) -> bool:
    """Public helper - verify a path is a valid Bunny arming-mode mount."""
    return bool(path) and _bunny_signature(path)


def _find_mount_path(key: str) -> Optional[str]:
    """Try to find the mount point for mass-storage devices."""
    candidates = []

    # Common Linux mount points
    for pattern in ["/media/*/*", "/mnt/*", "/run/media/*/*"]:
        candidates.extend(glob.glob(pattern))

    # macOS Volumes
    if sys.platform == "darwin":
        candidates.extend(glob.glob("/Volumes/*"))

    # Bash Bunny: detect by filesystem signature (payloads/ + loot/) regardless of label
    if key == "bunny":
        for path in candidates:
            if _bunny_signature(path):
                return path

    name_hints = {
        "ducky": ["DUCKY", "RubberDucky"],
        "turtle": ["TURTLE", "LanTurtle"],
    }

    hints = name_hints.get(key, [])
    for path in candidates:
        basename = os.path.basename(path).upper()
        for hint in hints:
            if hint.upper() in basename:
                return path

    return None

# ── Main poll function ────────────────────────────────────────────────────────

def _enumerate_usb_ids() -> list[tuple[int, int]]:
    """Enumerate USB VID/PID pairs — sysfs + pyusb primary, lsusb on backend failure."""
    ids: list[tuple[int, int]] = []
    try:
        ids = _detect_via_sysfs()
        try:
            pyusb_ids = _detect_via_pyusb()
            ids = list({*ids, *pyusb_ids})
        except ImportError:
            pass
        except Exception:
            return _detect_via_lsusb()
    except Exception:
        return _detect_via_lsusb()
    return ids

def poll_devices() -> dict[str, DeviceStatus]:
    """
    Poll all backends and return a dict of key → DeviceStatus.
    Always returns entries for all known device types (connected or not).
    """

    # Build baseline — all disconnected
    statuses: dict[str, DeviceStatus] = {}
    seen_keys = set()

    for (vid, pid), info in KNOWN_DEVICES.items():
        key = info["key"]
        if key not in statuses:
            statuses[key] = DeviceStatus(
                key=key,
                name=info["name"],
                short=info["short"],
                color=info["color"],
                connected=False,
            )

    # Try detection backends
    connected_ids = _enumerate_usb_ids()

    # Match connected IDs against known devices
    for (vid, pid) in connected_ids:
        if (vid, pid) in KNOWN_DEVICES:
            info = KNOWN_DEVICES[(vid, pid)]
            key = info["key"]
            status = statuses[key]
            status.connected = True
            status.vid = vid
            status.pid = pid
            # Try to find mount path for mass storage devices
            if info["mount_type"] == "mass_storage":
                status.mount_path = _find_mount_path(key)

    return statuses


def format_device_bar(statuses: dict[str, DeviceStatus]) -> str:
    """Single-line device status bar."""
    order = ["ducky", "bunny", "turtle", "teensy"]
    parts = []

    for key in order:
        status = statuses.get(key)
        name = key.upper()
        if status is None:
            parts.append(f"[dim white]○ {name}[/dim white]")
            continue
        if status.connected:
            dot = f"[bold {status.color}]●[/bold {status.color}]"
            label = f"[bold {status.color}]{name}[/bold {status.color}]"
            mount = ""
            if status.mount_path:
                mnt = os.path.basename(status.mount_path)
                mount = f"[dim green] /{mnt}[/dim green]"
            parts.append(f"{dot} {label}{mount}")
        else:
            parts.append(f"[dim white]○ {name}[/dim white]")

    sep = " [dim white]·[/dim white] "
    return "[dim white]DEVICES  [/dim white]" + sep.join(parts)


if __name__ == "__main__":
    # Quick CLI test
    statuses = poll_devices()
    for key, s in statuses.items():
        state = "CONNECTED" if s.connected else "not found"
        mount = f" @ {s.mount_path}" if s.mount_path else ""
        print(f"  {s.short:10} {state}{mount}")
