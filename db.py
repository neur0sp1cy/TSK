"""
TSK built-in payload database - shared by the web server.
Placeholder payloads shown until device repos are cloned.
"""

import copy
from pathlib import Path

from config import BASE_DIR

STATIC_PAYLOADS_DIR = BASE_DIR / "web" / "static" / "payloads"

BUILTIN_DB = {
    "ducky": [
        {"cat": "CREDENTIALS", "payloads": [
            {"name": "WiFi Passwords Grab",    "file": "wifi_passwords.duck",  "path": "", "tags": ["CREDS"],          "lang": "DS1", "desc": "Dumps saved WiFi passwords via netsh on Windows 10/11."},
            {"name": "Chrome Creds Dump",      "file": "chrome_dump.duck",     "path": "", "tags": ["CREDS","EXFIL"],  "lang": "DS1", "desc": "Extracts Chrome saved credentials and posts to listener."},
            {"name": "NTLM Hash Dump",         "file": "hashdump.duck",        "path": "", "tags": ["CREDS"],          "lang": "DS1", "desc": "Dumps NTLM password hashes using Invoke-Mimikatz."},
        ]},
        {"cat": "EXFILTRATION", "payloads": [
            {"name": "PDF Exfil PowerShell",   "file": "pdf_exfil.duck",       "path": "", "tags": ["EXFIL"],          "lang": "DS1", "desc": "Finds all PDFs in user profile and sends to remote host."},
            {"name": "USB Snarfer",            "file": "usb_snarfer.duck",     "path": "", "tags": ["EXFIL"],          "lang": "DS1", "desc": "Copies documents to hidden folder on USB drive."},
        ]},
        {"cat": "PERSISTENCE", "payloads": [
            {"name": "Add Admin User",         "file": "add_admin.duck",       "path": "", "tags": ["PERSIST"],        "lang": "DS1", "desc": "Creates a hidden administrator account on the target."},
            {"name": "Scheduled Task Beacon",  "file": "sched_task.duck",      "path": "", "tags": ["PERSIST","EXEC"], "lang": "DS1", "desc": "Installs a scheduled task that beacons to C2 on login."},
        ]},
        {"cat": "RECON", "payloads": [
            {"name": "System Enum",            "file": "sys_enum.duck",        "path": "", "tags": ["RECON"],          "lang": "DS1", "desc": "Full enum: OS, users, network, AV, processes."},
            {"name": "Network Scan",           "file": "net_scan.duck",        "path": "", "tags": ["RECON","NET"],    "lang": "DS1", "desc": "Quick ARP scan of local /24 subnet via PowerShell."},
        ]},
        {"cat": "EXECUTION", "payloads": [
            {"name": "Reverse Shell PS",       "file": "revshell.duck",        "path": "", "tags": ["EXEC"],           "lang": "DS1", "desc": "Opens PowerShell reverse shell to LHOST:LPORT."},
            {"name": "Download & Execute",     "file": "dl_exec.duck",         "path": "", "tags": ["EXEC"],           "lang": "DS1", "desc": "Downloads and executes payload from HTTP server."},
        ]},
    ],
    "bunny": [
        {"cat": "NETWORK", "payloads": [
            {"name": "QuickCreds",             "file": "quickcreds/payload.txt","path":"",  "tags": ["CREDS","NET"],   "lang": "BB",  "desc": "Responder-based credential harvesting over USB ethernet."},
            {"name": "Passive Recon",          "file": "passive/payload.txt",  "path": "", "tags": ["RECON","NET"],    "lang": "BB",  "desc": "Passive network recon via tcpdump and ARP watch."},
        ]},
        {"cat": "EXFILTRATION", "payloads": [
            {"name": "SMB Snarfer",            "file": "smb/payload.txt",      "path": "", "tags": ["EXFIL","CREDS"],  "lang": "BB",  "desc": "Harvests SMB NTLMv2 hashes via Responder."},
        ]},
    ],
    "turtle": [
        {"cat": "MODULES", "payloads": [
            {"name": "AutoSSH Tunnel",         "file": "autossh",              "path": "", "tags": ["PERSIST","NET"],  "lang": "LT",  "desc": "Persistent reverse SSH tunnel to attacker server."},
            {"name": "Nmap Scanner",           "file": "nmap",                 "path": "", "tags": ["RECON","NET"],    "lang": "LT",  "desc": "Network mapper module for LAN Turtle."},
        ]},
    ],
    "teensy": [
        {"cat": "HID ATTACKS", "payloads": [
            {"name": "TSK Lab Banner",         "file": "tsk_lab_banner.ino",   "path": "", "tags": ["HID","EXEC"],     "lang": "ARD", "desc": "USB HID banner sketch (compile to .hex for Teensy 3.2 flash)."},
        ]},
    ],
    "usb": [
        {"cat": "BUILT-INS", "payloads": [
            {"name": "Lab Ping",               "file": "lab_ping.ps1",         "path": "", "tags": ["NET","EXFIL"],    "lang": "PS1", "desc": "POST hostname and user to TSK phone-home endpoint (lab connectivity test)."},
            {"name": "Env Reporter PS",        "file": "env_reporter.ps1",     "path": "", "tags": ["RECON","EXFIL"],  "lang": "PS1", "desc": "Dump whoami and environment vars to a file on the USB stick (Windows)."},
            {"name": "Env Reporter SH",        "file": "env_reporter.sh",      "path": "", "tags": ["RECON","EXFIL"],  "lang": "SH",  "desc": "Dump whoami and environment to a file on the USB stick (Linux)."},
        ]},
    ],
}

PAYLOAD_TEMPLATES = {
    "ducky":  "REM TSK | new payload\nDELAY 1000\nSTRING Hello from TSK\nENTER\n",
    "bunny":  "#!/bin/bash\n# TSK | new payload\nLED R\nATTACKMODE HID STORAGE\n",
    "turtle": "#!/bin/sh\n# TSK | new module\n echo \"TSK lab module\"\n",
    "teensy": "// TSK | new Teensy sketch\n#include <Keyboard.h>\nvoid setup() { Keyboard.begin(); }\nvoid loop() {}\n",
    "usb":    "# TSK | new USB dropper\nWrite-Host 'TSK lab payload'\n",
}

DEFAULT_EXTENSIONS = {
    "ducky": ".txt",
    "bunny": ".txt",
    "turtle": ".sh",
    "teensy": ".ino",
    "usb": ".ps1",
}


def resolve_builtin_db(device: str) -> list:
    """Return a deep copy of BUILTIN_DB with static file paths resolved."""
    raw = BUILTIN_DB.get(device, [])
    db = copy.deepcopy(raw)
    device_dir = STATIC_PAYLOADS_DIR / device
    for group in db:
        for p in group.get("payloads", []):
            fname = p.get("file", "")
            if not fname:
                continue
            static = device_dir / fname
            if static.is_file():
                p["path"] = str(static.resolve())
    return db
