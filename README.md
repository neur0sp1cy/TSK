<p align="center">
  <img src="web/static/TSK-Header.png" alt="TSK | The Skeleton Key" width="100%">
</p>

<div align="center">
<table>
<tr>
<td valign="middle"><img src="web/static/tsk-avatar-ui.png" width="96" height="96" alt="TSK | The Skeleton Key"></td>
<td valign="middle">
<h1 style="margin:0;padding:0;border:none">TSK | The Skeleton Key</h1>
<p style="margin:0"><strong>DEF CON 34 Edition</strong></p>
</td>
</tr>
</table>
</div>

A free, open source platform for building and deploying USB / HID payloads. Includes a web UI for payload browsing, device flashing, SnarfSnarf exfil generation, lure building, and phone-home catch.

Modern web rebuild of **The Skeleton Key** (2018 TUI lineage). GitHub repo: **[neur0sp1cy/TSK2](https://github.com/neur0sp1cy/TSK2)**.

**By [Neur0Sp1cy](https://github.com/neur0sp1cy)**

Special thanks to **derv82** for helping inspire the original TSK vision.

**Contact:** [neur0sp1cy@proton.me](mailto:neur0sp1cy@proton.me) - questions, concerns, and comments.

---

## Legal and authorized use

TSK is for **authorized security testing only** - private labs, VMs you control, or environments where you have **written permission** to deploy payloads and run assessments.

**Do not** use this project against systems you do not own or lack authorization to test. Misuse, harassment, and illegal activity are not supported and are solely your responsibility.

Full policy: **[SECURITY.md](SECURITY.md)** (authorized use, vulnerability reporting, disclaimer).

---

## Features

- **Web UI** - Browse HAK5 payload repos, preview, edit, and flash to supported devices
- **USB Dropper** - Build exfil scripts (PowerShell / Bash), lure packages (LNK, README, `.desktop`), flash to a plain USB stick
- **SnarfSnarf** - Visual exfil builder with phone-home or on-stick output
- **CATCH** - Live receiver for phone-home uploads with preview and ZIP export
- **LAN Turtle** - SSH terminal in the browser
- **Themes** - Six UI themes (default through flat); `theme <name>` in command bar
- **Tutorial** - In-app missions at `/tutorial`

See [TESTING.md](TESTING.md) for lab setup and step-by-step USB test scenarios.

**Pre-release checklist:** [RELEASE_ROADMAP.md](RELEASE_ROADMAP.md) (timeline, polish, go-live).

**Full feature checklist:** [TESTING_CHECKLIST.md](TESTING_CHECKLIST.md) (pass/fail every feature before release).

**In-app tutorial:** open [/tutorial](http://127.0.0.1:1337/tutorial) (or `http://<your-host>:1337/tutorial`) for seven guided missions covering every device workflow. Also linked from the Help modal (`H`).

---

## Requirements

| Requirement | Notes |
|-------------|--------|
| Python 3.8+ | 3.10+ recommended |
| [uv](https://docs.astral.sh/uv/) | Recommended for dependency install |
| Plain USB flash drive | FAT32 or exFAT, writable (not a Bunny/Ducky volume) |
| Same LAN | Required for phone-home; victim must reach `LHOST:LPORT` (default **1337**) |
| java | Rubber Ducky encoding only |
| ssh | LAN Turtle operations only |

Dependencies install automatically via `uv sync` (FastAPI, uvicorn, bcrypt, jinja2, pylnk3, paramiko).

---

## Quick start

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

git clone https://github.com/neur0sp1cy/TSK2
cd TSK2
uv sync
uv run python server.py
```

Open **http://127.0.0.1:1337** in your browser (or run `./run_web.sh` on Linux).

**Fun commands** (command bar): `quote` · `joke` · `hack the planet` · `defcon` · `play`/`pause`/`next` (drop tracks in `web/static/music/`) · `present` for demo layout. Press **H** for the full list.

To enable HTTPS (recommended when accessing from other LAN machines):

```bash
uv run python server.py --ssl
```

A self-signed cert is generated once at `ssl/tsk.crt` and reused on every restart. Your browser will show a security warning on first visit - click **Advanced** then **Proceed** to accept it. Phone-home snarf scripts use plain HTTP and are unaffected.

### Windows

```powershell
git clone https://github.com/neur0sp1cy/TSK2
cd TSK2
uv sync
uv run python server.py
# or: uv run python server.py --ssl
```

### First login

1. Click **NEW** on the login screen and register an operator (password min 8 characters).
2. Open **CONFIG** and set **LHOST** to your LAN IP (use the LAN IP helper).
3. Set **LPORT** to `1337` unless you changed the server port.
4. Optional: open **/tutorial** for Mission 1 walkthrough, or press **H** and click **OPEN TUTORIAL**.

Per-operator config: `users/<operator>/config.json`  
Saved USB payloads: `users/<operator>/payloads/usb/`  
Cloned repos: `repos/`  
Phone-home uploads: `snarfed/<operator>/` (isolated per operator)

Session auth: register/login required; API uses `X-TSK-Token` header. Password min 8 characters.

---

## Web UI

| Area | Purpose |
|------|---------|
| Left nav | Ducky, Bunny, Turtle, Teensy, USB Dropper |
| Center tabs | BROWSE, SNARF (USB), REPOS, CONFIG |
| Right panel | Preview, USB stick scan, FLASH / EDIT / SAVE |
| Bottom bar | Command line (`set lhost`, `clone ducky`, `devices`, …) |
| **H** | Help modal (operator guide) |
| **A** | About modal |

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `R` `B` `T` `U` `L` | Jump to device |
| `C` / `P` / `A` / `H` | Config, Repos, About, Help |
| `1`-`4` | Browse, Snarf, Config, Repos tabs |
| `f` / `Ctrl+Enter` | Flash |
| `e` | Edit payload |
| `Esc` | Close modals |

---

## Supported devices

| Device | Flash method |
|--------|----------------|
| USB Dropper | Web UI: scripts and lure packages to a plain USB stick |
| Rubber Ducky (OG) | `encoder.jar` → SD card |
| Bash Bunny (OG) | Mass storage → switch1 / switch2 |
| LAN Turtle (OG) | SSH/SCP push |
| Teensy 3.2 / 4.0 | `teensy_loader_cli` with pre-compiled `.hex` (compile pipeline in progress - hidden from UI for now) |

Clone HAK5 libraries from the REPOS tab: `clone ducky`, `clone bunny`, `clone turtle`, `clone all`.

---

## Project structure

```
TSK2/
├── server.py           # Web server (start here)
├── web/index.html      # Web UI
├── web/tutorial.html   # In-app tutorial missions
├── web/static/         # Icons, branding, music drop folder
├── dropper/            # SnarfSnarf, lure builder, receiver
├── flash.py            # Flash engine
├── config.py           # Auth and per-operator config
├── repos.py            # Repo clone and indexing
├── users/              # Operator data
├── repos/              # Cloned payload libraries
├── snarfed/            # Phone-home catches (per-operator subdirs)
├── TESTING.md          # Lab testing guide
├── TESTING_CHECKLIST.md
├── RELEASE_ROADMAP.md
├── SECURITY.md         # Authorized use and disclosure
├── archive/tui/        # Archived TUI notes (removed; web UI only)
└── pyproject.toml
```

---

## Support TSK

TSK is free and open source. If it helps in the field, a coffee keeps the lights on in Night City.

☕ [Buy me a coffee on Ko-fi](https://ko-fi.com/neur0sp1cy)

Every donation goes back into hardware and development. No paywalls, ever.

### Bug reports and support

- **Bugs:** [GitHub Issues](https://github.com/neur0sp1cy/TSK2/issues) (use the bug report template)
- **Repro help:** [TESTING_CHECKLIST.md](TESTING_CHECKLIST.md) - cite the section you are on
- **Security issues in TSK:** see [SECURITY.md](SECURITY.md) (responsible disclosure, not public issues for exploit details)
- **Questions / concerns:** [neur0sp1cy@proton.me](mailto:neur0sp1cy@proton.me)
- **Expectations:** best-effort support; be constructive - we squash bugs, not tolerate abuse

**Enable Issues:** On GitHub, open **neur0sp1cy/TSK2** → **Settings** → **General** → **Features** → enable **Issues** → **Save**. New issues will use the bug report template in `.github/ISSUE_TEMPLATE/`.

---

*Dreamed up under the wet hot neon lights of Las Vegas.*
