# TSK | Testing Instructions

Lab guide for validating USB Dropper workflows on Windows and Linux. Use only on systems and networks you are authorized to test.

**Policy:** [SECURITY.md](SECURITY.md)

For install steps, see [README.md](README.md).

Press **H** in the web UI for the full operator guide.

**Pre-release checklist:** [RELEASE_ROADMAP.md](RELEASE_ROADMAP.md) (timeline, polish, go-live).

**Full feature checklist:** [TESTING_CHECKLIST.md](TESTING_CHECKLIST.md) (pass/fail every feature area).

**Guided walkthrough:** [/tutorial](http://127.0.0.1:1337/tutorial) - seven missions from first login through every device workflow (print-friendly).

---

## Operator setup

1. Install and run TSK:
   ```bash
   uv sync
   uv run python server.py
   # optional HTTPS for LAN access:
   uv run python server.py --ssl
   ```
2. Register and sign in (login screen → **NEW**).
3. **CONFIG** modal (sidebar **C** or command bar): set **LHOST** to your machine's **LAN IP** (not `127.0.0.1` if the victim is another host).
4. Set **LPORT** to `1337` (default).
5. Allow inbound TCP on that port through your firewall.
6. Plug a **blank FAT32/exFAT USB stick** (not a Bunny/Ducky volume).

---

## USB Dropper workflow

```
CONFIG (LHOST / LPORT)
    ↓
SNARF → EXFIL   build PowerShell (Windows) or Bash (Linux) script
    ↓
SAVE or SAVE + FLASH   script appears in payload list under SNARFSNARF
    ↓
SNARF → LURE   optional Windows .lnk or Linux README / .desktop lure
    ↓
SAVE PACKAGE or SAVE + FLASH PACKAGE
    ↓
Victim runs lure or RUN_PAYLOAD launcher
    ↓
SNARF → CATCH   phone-home uploads appear in live feed
```

### SNARF → EXFIL

- Select exfil targets and output mode:
  - **USB root / hidden** - loot copied on the USB stick (victim-side)
  - **Phone home** - HTTP POST to `http://<LHOST>:<LPORT>/api/snarf`
- Format: PowerShell, Bash, or both.
- **SAVE + FLASH** copies the script to the operator USB stick in one step.

### SNARF → LURE

| Platform | Lure | Victim action |
|----------|------|----------------|
| Windows | LNK shortcut | Double-click (e.g. `Invoice_2026.lnk`) |
| Linux | Bash lure | `bash README.txt` from USB mount |
| Linux | Desktop entry | Open `.desktop` (may require "Trust" on GNOME) |

Payload options: saved exfil script, minimal test stub (`tsk2_lure_ok` phone-home), or custom inline command.

### SNARF → CATCH

- Endpoint: `POST http://<LHOST>:1337/api/snarf`
- Storage: `snarfed/<operator>/<timestamp>/<hostname>/` (per logged-in operator)
- UI: live feed, file tree, preview, ZIP export per session.

### Flashing (right panel)

1. **Scan** USB stick - status should show green writable.
2. **Deploy**: `root` or hidden (`.tsk/` on stick).
3. Select payload in the center list → **FLASH**, or use **SAVE + FLASH** from the SNARF modal.

`.ps1` / `.sh` payloads also get `RUN_PAYLOAD.bat` / `RUN_PAYLOAD.sh` on the stick.

---

## Test scenarios

### Scenario A: Windows lure + phone-home stub

**Goal:** Confirm lure execution and CATCH without real exfil.

1. USB Dropper → **SNARF → LURE**
2. Type: **LNK shortcut** | Preset: **Invoice_2026** | Payload: **Minimal Windows test stub**
3. **BUILD PREVIEW** → **SAVE + FLASH PACKAGE**
4. On a Windows test host: plug USB, double-click `Invoice_2026.lnk`
5. Operator: **SNARF → CATCH** - expect `tsk2_lure_ok` or stub POST in live feed

### Scenario B: Linux README lure

1. **SNARF → LURE** → **Bash lure** | **README.txt** preset | **Minimal Linux test stub**
2. **SAVE + FLASH PACKAGE**
3. On Linux test host: `bash README.txt` from USB mount path
4. Check **CATCH** on operator

### Scenario C: Phone-home exfil

1. **SNARF → EXFIL** - select targets, **PowerShell** or **Bash**, output **Phone home**
2. **SAVE + FLASH**
3. Victim: `RUN_PAYLOAD.bat` (Windows) or `RUN_PAYLOAD.sh` (Linux)
4. **SNARF → CATCH** - review uploads, export ZIP if needed

### Scenario D: Exfil to USB only (no network)

1. **SNARF → EXFIL** - output **Copy to USB root** or **hidden folder**
2. Flash to stick, run on victim
3. Loot appears in hidden folder on victim-side USB copy

---

## What to use / avoid

| OK | Avoid |
|----|--------|
| Blank FAT32/exFAT USB stick | Bash Bunny / Ducky USB volumes |
| Writable mount (green in UI) | Windows install ISO sticks (read-only) |
| Test VM or lab PC | Production systems without authorization |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Images missing in About | Restart `server.py`; hard refresh browser |
| USB stick not detected | Plain stick; click scan; `lsblk`; set `usb_mount` in CONFIG |
| USB read-only | Use blank FAT32 stick, not install media |
| Phone-home never arrives | LHOST must be LAN IP; open firewall on LPORT; same network |
| LNK built on Linux | Generation works on Linux; execution is Windows-only |
| Linux `.desktop` blocked | Use README bash lure, or mark desktop file trusted |
| Port 1337 in use | `fuser -k 1337/tcp` or change LPORT in CONFIG |
| Browser cert warning with `--ssl` | Expected for self-signed cert; Advanced → Proceed |

### Multi-operator isolation (Track 5)

1. Register two operators (e.g. `alice` and `bob`).
2. Log in as `alice`, build and run a phone-home stub; confirm catches appear in **CATCH** for alice only.
3. Log in as `bob` - SNARF **CATCH** must not show alice's files.
4. On disk: catches under `snarfed/alice/` and `snarfed/bob/` separately.

---

## Command bar reference

```
set lhost 192.168.1.50
set lport 1337
clone ducky
clone all
update all
devices
flash
help
```
