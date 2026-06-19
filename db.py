"""
TSK built-in payload database — shared by the web server.
Placeholder payloads shown until device repos are cloned.
"""

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
            {"name": "Brutal Add Admin",       "file": "add_admin.ino",        "path": "", "tags": ["PERSIST","CREDS"],"lang": "ARD", "desc": "Screetsec Brutal — add hidden admin user."},
            {"name": "Kautilya Enum",          "file": "enum.ino",             "path": "", "tags": ["RECON","HID"],    "lang": "ARD", "desc": "SamratAshok Kautilya — full system enum."},
        ]},
    ],
    "usb": [
        {"cat": "DROPPERS", "payloads": [
            {"name": "Autorun Dropper",        "file": "autorun_dropper.py",   "path": "", "tags": ["EXEC"],           "lang": "PY",  "desc": "Autorun.inf based dropper for Windows."},
            {"name": "LNK Payload",            "file": "lnk_payload.py",       "path": "", "tags": ["EXEC"],           "lang": "PY",  "desc": "Malicious LNK file that runs payload on open."},
            {"name": "USB Snarfer",            "file": "usb_snarfer.py",       "path": "", "tags": ["EXFIL"],          "lang": "PY",  "desc": "Python USB snarfer — copies docs, creds, keys."},
        ]},
    ],
}
