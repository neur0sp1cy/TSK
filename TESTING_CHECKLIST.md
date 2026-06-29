# TSK | Full testing checklist

Follow this document to verify **every major feature** before calling TSK ready for mainstream release.

**Authorized lab use only** - see [SECURITY.md](SECURITY.md). Do not test against systems without permission.

**Strategy and timeline:** [RELEASE_ROADMAP.md](RELEASE_ROADMAP.md)  
**Scenario walkthroughs:** [TESTING.md](TESTING.md)  
**Operator guide:** press **H** in the web UI

---

## How to use this doc

1. Copy the **Session log** table below or print this file.
2. Mark each row: **PASS** | **FAIL** | **SKIP** | **N/A**
3. Add **Notes** for every FAIL (steps to reproduce).
4. Do not ship until all **Blocker** rows pass (or are SKIP with written reason).

### Session log

| Field | Value |
|-------|-------|
| Tester | |
| Date | |
| Machine / OS | |
| TSK commit or tag | |
| Python version | |
| LHOST used | |
| Victim VMs | |

---

## Readiness gate | "Mainstream ready"

TSK is **READY** when all of the following are true:

| # | Criterion | Met? |
|---|-----------|------|
| 1 | Fresh clone → `uv sync` → `server.py` → register → login works | |
| 2 | Multi-operator CATCH isolation verified (alice cannot see bob) | |
| 3 | At least one USB Dropper end-to-end path works (lure or exfil + CATCH) | |
| 4 | README + TESTING + tutorial links match the live UI | |
| 5 | No open **Blocker** FAIL rows in this checklist | |
| 6 | Help modal and About (Ko-fi) render correctly | |

Optional for v1.0.0 but recommended: one HAK5 device flash (Bunny, Ducky, or Turtle) if hardware available.

---

## 0 | Environment prep

| # | Test | Blocker? | Result | Notes |
|---|------|----------|--------|-------|
| 0.1 | `uv sync` completes without errors | Yes | | |
| 0.2 | `uv run python server.py` binds port 1337 | Yes | | |
| 0.3 | Browser opens `http://127.0.0.1:1337` | Yes | | |
| 0.4 | Favicon and login branding load (no 404 in devtools Network) | No | | |
| 0.5 | Plain FAT32/exFAT USB stick available | Yes* | | *Required for USB sections |
| 0.6 | Windows test VM on same LAN (or host-only net) | No | | |
| 0.7 | Linux test VM on same LAN | No | | |
| 0.8 | Firewall allows inbound TCP on LPORT (default 1337) | Yes | | |

---

## 1 | Authentication and operators

| # | Test | Blocker? | Result | Notes |
|---|------|----------|--------|-------|
| 1.1 | Register new operator (password ≥ 8 chars) | Yes | | |
| 1.2 | Reject weak password (< 8 chars) | Yes | | |
| 1.3 | Login with correct credentials | Yes | | |
| 1.4 | Login fails with wrong password | Yes | | |
| 1.5 | Logout works; protected routes require login | Yes | | |
| 1.6 | Register second operator (for isolation tests) | Yes | | |
| 1.7 | Change password (CONFIG or auth UI) | No | | |
| 1.8 | `users/<operator>/` directory created on register | No | | |
| 1.9 | Delete operator → login screen only (app hidden, no stale modals) | Yes | | |
| 1.10 | Register new operator after delete → Operator modal shows new name + correct `users/<op>/` paths | Yes | | |
| 1.11 | Rename operator → modal and CONFIG paths update | No | | |

---

## 2 | Config and network

| # | Test | Blocker? | Result | Notes |
|---|------|----------|--------|-------|
| 2.1 | CONFIG modal shows current settings | Yes | | |
| 2.2 | Set LHOST via UI saves to `users/<op>/config.json` | Yes | | |
| 2.3 | LAN IP helper returns sensible address | No | | |
| 2.4 | Set LPORT; persists after refresh | Yes | | |
| 2.5 | LHOST hint banner shows when LHOST unset | No | | |
| 2.6 | Dismiss LHOST hint; stays dismissed (localStorage) | No | | |
| 2.7 | Command bar: `set lhost <ip>` updates config | Yes | | |
| 2.8 | Command bar: `set lport <port>` updates config | No | | |
| 2.9 | Deployment log lists flashes after a flash | No | | |
| 2.10 | Export deployments CSV downloads | No | | |

---

## 3 | Navigation, UI, and themes

| # | Test | Blocker? | Result | Notes |
|---|------|----------|--------|-------|
| 3.1 | Device nav: Ducky, Bunny, Turtle, USB (Teensy hidden) | Yes | | |
| 3.2 | Keyboard shortcuts R/B/L/U jump devices | No | | |
| 3.3 | Center: payload list always visible; CONFIG/REPOS/OPERATOR open as modals | Yes | | |
| 3.4 | USB → SNARF button in PAYLOADS header opens SNARF modal | Yes | | |
| 3.5 | Theme picker: all 6 themes apply | No | | |
| 3.6 | Command `theme <name>` works | No | | |
| 3.7 | Device status dots reflect plug/unplug (if hardware) | No | | |
| 3.8 | `devices` command refreshes status | No | | |
| 3.9 | `present` / `present off` presentation layout | No | | |
| 3.10 | Bottom command bar accepts input and runs commands | Yes | | |

---

## 4 | Payload browse and repos

| # | Test | Blocker? | Result | Notes |
|---|------|----------|--------|-------|
| 4.1 | Payload list shows built-in payloads per device | Yes | | |
| 4.2 | Select payload → preview panel updates | Yes | | |
| 4.3 | Payload search filters list | No | | |
| 4.4 | REPOS modal shows clone status | Yes | | |
| 4.5 | `clone ducky` (or bunny/turtle) succeeds | No | | |
| 4.6 | After clone, payload list shows repo payloads | No | | |
| 4.7 | `update all` pulls without error | No | | |
| 4.8 | Saved operator payloads appear under SNARFSNARF / USER | No | | |

---

## 5 | Editor and flash (generic)

| # | Test | Blocker? | Result | Notes |
|---|------|----------|--------|-------|
| 5.1 | EDIT opens editor modal with payload content | Yes | | |
| 5.2 | VARS panel toggles (Ctrl+D); shows LHOST/LPORT subs | No | | |
| 5.3 | Save edited payload to operator storage | No | | |
| 5.4 | Flash preview shows substituted vars before flash | No | | |
| 5.5 | FLASH completes for USB stick payload | Yes* | | *If testing USB |
| 5.6 | DOWNLOAD saves payload file locally | No | | |

---

## 6 | USB Dropper | SNARF EXFIL

| # | Test | Blocker? | Result | Notes |
|---|------|----------|--------|-------|
| 6.1 | USB device → SNARF button visible in PAYLOADS header | Yes | | |
| 6.2 | EXFIL builder: select targets, PowerShell format | Yes | | |
| 6.3 | EXFIL builder: Bash format | No | | |
| 6.4 | BUILD PREVIEW shows script in SNARF modal (LHOST/LPORT) | Yes | | |
| 6.5 | SAVE writes to `users/<op>/payloads/usb/` | Yes | | |
| 6.6 | SAVE appears in payload list → SNARFSNARF | Yes | | |
| 6.7 | Phone-home output mode in generated script | Yes | | |
| 6.8 | USB root / hidden deploy modes in builder | No | | |
| 6.9 | SAVE + FLASH copies to stick | Yes | | |
| 6.10 | RUN_PAYLOAD.bat / .sh on stick after flash | No | | |

---

## 7 | USB Dropper | SNARF LURE

| # | Test | Blocker? | Result | Notes |
|---|------|----------|--------|-------|
| 7.1 | SNARF modal → LURE: Windows LNK options | Yes | | |
| 7.2 | LURE: Linux README bash lure | No | | |
| 7.3 | LURE: Linux .desktop entry | No | | |
| 7.4 | Attach saved exfil or minimal test stub | Yes | | |
| 7.5 | BUILD PREVIEW for lure package | Yes | | |
| 7.6 | SAVE PACKAGE to operator storage | Yes | | |
| 7.7 | SAVE + FLASH PACKAGE to USB stick | Yes | | |
| 7.8 | **Scenario A:** Windows VM double-click LNK → phone-home | Yes | | |
| 7.9 | **Scenario B:** Linux VM `bash README.txt` → phone-home | No | | |

---

## 8 | CATCH (phone-home receiver)

| # | Test | Blocker? | Result | Notes |
|---|------|----------|--------|-------|
| 8.1 | SNARF modal → CATCH shows live feed | Yes | | |
| 8.2 | Upload appears after victim runs stub/exfil | Yes | | |
| 8.3 | File tree lists session / hostname folders | Yes | | |
| 8.4 | Preview file contents in UI | Yes | | |
| 8.5 | Delete single file | No | | |
| 8.6 | Delete whole session | No | | |
| 8.7 | Export session ZIP | No | | |
| 8.8 | On disk: `snarfed/<operator>/<timestamp>/...` | Yes | | |

---

## 9 | Multi-operator isolation

| # | Test | Blocker? | Result | Notes |
|---|------|----------|--------|-------|
| 9.1 | alice catch **not** visible when logged in as bob | Yes | | |
| 9.2 | bob catch **not** visible when logged in as alice | Yes | | |
| 9.3 | Separate `snarfed/alice/` and `snarfed/bob/` on disk | Yes | | |
| 9.4 | Separate `users/alice/config.json` vs bob | Yes | | |
| 9.5 | Separate saved payloads per operator | No | | |
| 9.6 | API calls without token rejected (401) | Yes | | |

---

## 10 | USB stick panel

| # | Test | Blocker? | Result | Notes |
|---|------|----------|--------|-------|
| 10.1 | SCAN detects writable stick (green) | Yes | | |
| 10.2 | Deploy: USB root vs hidden `.tsk/` | No | | |
| 10.3 | Stick select dropdown when multiple mounts | No | | |
| 10.4 | Read-only stick shows warning (no flash) | No | | |

---

## 11 | HAK5 hardware (SKIP if unavailable)

| Device | Clone | Browse | Flash | ARMED / mount | Result | Notes |
|--------|-------|--------|-------|---------------|--------|-------|
| Bash Bunny | | | SW1 / SW2 | | | |
| Rubber Ducky | | | encode + SD | | | |
| LAN Turtle | | | SCP / push | | | |
| Teensy | N/A | N/A | Hidden in UI | N/A | SKIP | |

### LAN Turtle SSH (browser)

| # | Test | Blocker? | Result | Notes |
|---|------|----------|--------|-------|
| 11.1 | SSH button appears on Turtle device | No | | |
| 11.2 | SSH modal connects (or shows clear error) | No | | |
| 11.3 | Turtle CONFIG: IP, user, port | No | | |

---

## 12 | HTTPS mode

| # | Test | Blocker? | Result | Notes |
|---|------|----------|--------|-------|
| 12.1 | `uv run python server.py --ssl` starts | No | | |
| 12.2 | Browser accepts self-signed cert | No | | |
| 12.3 | UI fully functional over HTTPS | No | | |
| 12.4 | Phone-home scripts still POST to `http://LHOST:LPORT` | No | | Document if expected |

---

## 13 | Tutorial missions (`/tutorial`)

| Mission | Topic | UI labels still match? | Pass? | Notes |
|---------|-------|------------------------|-------|-------|
| 01 | Initial setup | | | |
| 02 | USB exfil build & flash | | | |
| 03 | CATCH & review | | | |
| 04 | Lure package | | | |
| 05 | Bash Bunny | | | |
| 06 | LAN Turtle | | | |
| 07 | Rubber Ducky | | | |

| # | Test | Blocker? | Result | Notes |
|---|------|----------|--------|-------|
| 13.1 | Link from Help modal opens tutorial | No | | |
| 13.2 | LHOST hint links to Mission 1 | No | | |
| 13.3 | Print-friendly layout readable | No | | |

---

## 14 | Help, About, and support

| # | Test | Blocker? | Result | Notes |
|---|------|----------|--------|-------|
| 14.1 | **H** opens Help modal; scroll works | Yes | | |
| 14.2 | Help lists SNARF flow, commands, per-operator paths | Yes | | |
| 14.3 | **A** opens About modal | Yes | | |
| 14.4 | Ko-fi banner image loads | No | | |
| 14.5 | Ko-fi link opens ko-fi.com/neur0sp1cy | No | | |
| 14.6 | README Ko-fi link matches | No | | |
| 14.7 | GitHub link in About/help works | No | | |

---

## 15 | Easter eggs and demo (optional)

| # | Test | Blocker? | Result | Notes |
|---|------|----------|--------|-------|
| 15.1 | `quote` / `joke` in command bar | No | | |
| 15.2 | `hack the planet` (text fallback if no gif) | No | | |
| 15.3 | `defcon` or Konami code | No | | |
| 15.4 | Music: drop file in `web/static/music/`, `play` | No | | |
| 15.5 | Matrix theme + rain burst (if applicable) | No | | |

---

## 16 | Documentation audit

| Doc | Accurate? | Looks good? | Result | Notes |
|-----|-----------|-------------|--------|-------|
| README.md install + features | | | | |
| TESTING.md scenarios | | | | |
| TESTING_CHECKLIST.md (this file) | | | | |
| RELEASE_ROADMAP.md | | | | |
| `/tutorial` all 7 missions | | | | |
| Help modal (`H`) vs live UI | | | | |
| No references to removed TUI | | | | |

---

## 17 | End-to-end scenarios (quick path)

Minimum lab path if time is short:

| Scenario | Description | Pass? | Notes |
|----------|-------------|-------|-------|
| **A** | Windows LNK + minimal stub → CATCH | | TESTING.md |
| **B** | Linux README lure → CATCH | | |
| **C** | Phone-home exfil → CATCH + ZIP export | | |
| **D** | USB-only exfil (no network) | | |
| **ISO** | Two operators, isolation (Section 9) | | |

---

## Summary scorecard

| Section | Total tests | PASS | FAIL | SKIP |
|---------|-------------|------|------|------|
| 0 Prep | | | | |
| 1 Auth | | | | |
| 2 Config | | | | |
| 3 UI | | | | |
| 4 Browse/Repos | | | | |
| 5 Editor/Flash | | | | |
| 6 EXFIL | | | | |
| 7 LURE | | | | |
| 8 CATCH | | | | |
| 9 Isolation | | | | |
| 10 USB panel | | | | |
| 11 Hardware | | | | |
| 12 HTTPS | | | | |
| 13 Tutorial | | | | |
| 14 Help/About | | | | |
| 15 Easter eggs | | | | |
| 16 Docs | | | | |
| 17 Scenarios | | | | |

### Sign-off

| | |
|---|---|
| **All blockers PASS?** | Yes / No |
| **Known FAILs (ship blockers?)** | |
| **Ready for mainstream release?** | Yes / No |
| **Signed** | |

---

## After testing

1. Log FAILs in GitHub Issues or your notes.
2. Run polish pass on anything in [RELEASE_ROADMAP.md](RELEASE_ROADMAP.md) Phase 2.
3. Tag `v1.0.0` and publish GitHub Release when sign-off is **Yes**.
