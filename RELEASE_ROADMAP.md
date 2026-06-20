# TSK | Release roadmap

Pre-launch checklist for first public release and DefCon-style demos (target: next 1-2 weeks).

- **Lab procedures:** [TESTING.md](TESTING.md) (scenario walkthroughs)
- **Full feature checklist:** [TESTING_CHECKLIST.md](TESTING_CHECKLIST.md) (pass/fail every area)
- **Install / features:** [README.md](README.md)
- **Archived TUI:** [archive/tui/README.md](archive/tui/README.md)

Use this doc as a pass/fail sheet. Mark each row **PASS**, **FAIL**, or **SKIP** (with a note).

---

## Phase 1 | Hardware and isolation testing (do first)

Use [TESTING_CHECKLIST.md](TESTING_CHECKLIST.md) sections **0-12, 17** for the full matrix. Summary below:

### 1A | Operator setup (both test accounts)

| # | Step | Pass? | Notes |
|---|------|-------|-------|
| 1 | `uv sync` && `uv run python server.py` starts clean on your demo machine | | |
| 2 | Register **alice** and **bob** (8+ char passwords) | | |
| 3 | Each operator: CONFIG → LHOST = LAN IP, LPORT = 1337 | | |
| 4 | Firewall allows inbound TCP on LPORT | | |
| 5 | Blank FAT32/exFAT stick scans green and writable in USB panel | | |

### 1B | Multi-operator CATCH isolation (Track 5)

| # | Step | Pass? | Notes |
|---|------|-------|-------|
| 1 | Log in as **alice** → SNARF → LURE → minimal Windows stub → SAVE + FLASH | | |
| 2 | Run stub on Windows victim → **CATCH** shows upload for alice | | |
| 3 | Disk: file under `snarfed/alice/` only | | |
| 4 | Log out → log in as **bob** → **CATCH** empty (no alice data) | | |
| 5 | Repeat stub as bob → catch under `snarfed/bob/` only | | |
| 6 | As bob, call `GET /api/snarf/...` or UI tree: cannot see alice sessions | | |
| 7 | CONFIG and saved payloads under `users/alice/` vs `users/bob/` stay separate | | |

### 1C | USB Dropper scenarios (from TESTING.md)

| Scenario | Platform | Pass? | Notes |
|----------|----------|-------|-------|
| **A** LNK + phone-home stub | Windows VM | | |
| **B** README bash lure | Linux VM | | |
| **C** Phone-home exfil | Win or Linux | | |
| **D** USB-only exfil (no network) | Win or Linux | | |

### 1D | Optional hardware (if you have devices)

| Device | Clone repo → browse → flash | Pass? | Notes |
|--------|------------------------------|-------|-------|
| Rubber Ducky | `clone ducky`, encoder + SD | | |
| Bash Bunny | `clone bunny`, SW1/SW2 | | |
| LAN Turtle | module push or SSH modal | | |
| Teensy | SKIP (hidden in UI; pipeline TBD) | SKIP | |

### 1E | Network modes

| # | Step | Pass? | Notes |
|---|------|-------|-------|
| 1 | `server.py --ssl` on operator box; browser accepts self-signed cert | | |
| 2 | Victim on LAN can reach UI over HTTPS | | |
| 3 | Phone-home snarf still uses **HTTP** to LHOST:LPORT (documented behavior) | | |
| 4 | Second machine on LAN opens UI and logs in as operator | | |

---

## Phase 2 | UI polish (pre-release / DefCon)

Prioritized for booth demo and first GitHub visitors. **Must-have** before go-live; **nice-to-have** if time allows.

### Must-have

| Item | Status | What to verify / do |
|------|--------|---------------------|
| Ko-fi in About | | Open **A** → banner + link to ko-fi.com/neur0sp1cy; images load from `web/static/` |
| Help + Tutorial links | | **H** modal and `/tutorial` open; Mission 1 matches current UI labels |
| LHOST hint banner | | Shows when unset; dismiss sticks; tutorial link works |
| Login / register copy | | Clear lab-only warning; password min 8 chars |
| README matches reality | | No TUI references; quick start works on fresh clone |
| `present` demo layout | | Command `present` / `present off` for projector (sidebar hidden, larger type) |
| Fresh clone smoke test | | New directory, `uv sync`, register, Scenario A in under 30 min |

### Nice-to-have (DefCon vibe)

| Item | Status | Notes |
|------|--------|-------|
| `defcon` / Konami easter egg | | Gold ticker, logo pulse, defcon.org link |
| Hack the Planet overlay | BACKLOG | Text fallback works; add `hacktheplanet.gif` when you have an asset |
| **Demo preset command** | NOT BUILT | e.g. `demo on` → present + defcon + dismiss LHOST hint (single command for booth) |
| Editor flash diff view | NOT BUILT | Side-by-side or inline diff before FLASH (VARS panel exists) |
| Edition year branding | PASS | DEF CON 34 across UI, README, and server banner |
| GitHub social preview | | README screenshot or `web/static/` hero for repo Open Graph |
| CHANGELOG.md | | v1.0.0 release notes for GitHub Release |

### Explicitly out of scope for v1.0 launch

- Textual TUI (removed; see `archive/tui/`)
- Teensy compile pipeline in UI
- Full mobile layout
- Password reset / email flows
- Operator **NEW payload** authoring per device (planned for v1.0.1 - see Phase 4)
- In-app **Ducky / Bunny command reference** (planned post-launch - see Phase 4)

---

## Phase 4 | Post v1.0.0 (after release)

**Not blockers for v1.0.0.** Ship after checklist sign-off and Git tag. Target: **v1.0.1** for payload authoring; command ref can land in the same release or a quick follow-up.

### 4A | NEW payload + MY PAYLOADS (priority)

Today: USB/Snarf can save to `users/<operator>/payloads/usb/`. Ducky, Bunny, Turtle, and Teensy are browse/edit/flash against cloned repos only. Builtin payloads open in the editor with a template but cannot be saved to the operator library (`path: ""` disables SAVE FILE; SAVE COPY only downloads locally).

| # | Feature | Notes |
|---|---------|-------|
| 1 | **+ NEW PAYLOAD** on BROWSE for each device (Ducky, Bunny, Turtle, Teensy, USB) | Name prompt → create file under `users/<operator>/payloads/<device>/` |
| 2 | **MY PAYLOADS** category in browse tree | Operator-owned files; do not lump Ducky/Bunny saves under SNARFSNARF |
| 3 | **SAVE TO LIBRARY** in editor | When no file path exists, save to MY PAYLOADS instead of download-only |
| 4 | **Repo-safe saves** | Editing a file under `repos/` should save-as to MY PAYLOADS by default (no silent overwrite of cloned libraries) |
| 5 | **API** `POST /api/payload/create` | `device`, `filename`, optional `content` or template id; validate path under user payload dir |
| 6 | **index_user_payloads** | Use cat `MY PAYLOADS` (or `OPERATOR`) for non-USB devices; keep SNARFSNARF for USB exfil scripts |

**Effort:** Medium. Backend paths largely exist (`config.payload_path`, `/api/payload/save`, `index_user_payloads`).

### 4B | Device command reference

Help (`H`) covers TSK operator workflow, not DuckyScript or Bash Bunny syntax. Booth and new operators ask for ATTACKMODE, QUACK, DELAY, etc.

| # | Feature | Notes |
|---|---------|-------|
| 1 | **DEVICE REF** section in Help modal | DuckyScript essentials: `DELAY`, `STRING`, `ENTER`, `GUI`, `REM`, `DEFAULT_DELAY`, etc. |
| 2 | **Bash Bunny** quick ref | `ATTACKMODE`, `LED`, `QUACK`, `REQUIRETOOL`, switch folders (`switch1` / `switch2`) |
| 3 | **LAN Turtle** notes | Module layout, `autossh`, SCP push pointers |
| 4 | **External links** | HAK5 official docs for full language references |
| 5 | Optional: `ref` command or **?** to open DEVICE REF | Same content as Help subsection |
| 6 | **Later:** editor insert chips | Click-to-insert common commands when `lang` is DS1 / BB |

**Effort:** Small for Help + links; Medium for editor chips.

### 4C | Suggested post-launch order

```
After v1.0.0 tag
  1   NEW payload + MY PAYLOADS (v1.0.1)
  2   DEVICE REF in Help (+ HAK5 doc links)
  3   Optional polish: editor command chips, demo on command
```

---

## Phase 3 | Go-live checklist

| # | Task | Done? |
|---|------|-------|
| 1 | All Phase 1 **must-pass** rows green (or documented SKIP) | |
| 2 | Phase 2 must-have polish done | |
| 3 | Git tag `v1.0.0` (or chosen version) on GitHub | |
| 4 | GitHub Release notes (features + lab warning + Ko-fi link) | |
| 5 | Ko-fi page mentions TSK and links to repo | |
| 6 | Demo machine: static IP or known LHOST, firewall rule, USB stick packed | |
| 7 | Booth: `present` tested on projector resolution | |

---

## Agent recommendations | ADD / CHANGE / MODIFY

Items **not** already on your list. Pick what resonates; none are blockers for launch.

### ADD (new capability)

| Idea | Why | Effort |
|------|-----|--------|
| **`demo on` / `demo off` command** | One toggle for booth: presentation mode + defcon styling + hide distractions | Small |
| **CHANGELOG.md + GitHub Release** | First public release looks intentional; users know what v2 is | Small |
| **README screenshots** (3-4 panels) | GitHub visitors understand the product in 10 seconds | Small |
| **Post-register checklist modal** | "Set LHOST → pick USB → Mission 1" reduces first-login confusion | Medium |
| **Snarf upload size / rate guard** | Soft limits on `/api/snarf` so a rogue victim cannot fill disk in shared lab | Medium |
| **`/api/health` endpoint** | `{"ok":true,"version":"2.0.0"}` for sanity checks before demo | Tiny |
| **Export operator config backup** | Download `config.json` + payload list from CONFIG tab | Medium |

### CHANGE (adjust existing behavior)

| Idea | Why | Effort |
|------|-----|--------|
| **Clarify HTTP snarf vs HTTPS UI** | CONFIG or Help: "UI may use HTTPS; phone-home URLs in generated scripts use HTTP unless you customize" | Small |
| **CATCH empty state copy** | When no catches: "Run a lure stub or exfil script; catches appear here" + link to tutorial | Small |
| **Deployment log visibility** | CONFIG already has deployments CSV; surface "last flash" in bottom bar or SNARF header | Small |
| **DefCon edition string** | Align README / login / ticker with actual con year you are targeting | Tiny |
| **Remove or gate HTP overlay until gif exists** | Avoid dead img 404 in network tab during demos | Tiny |

### MODIFY (deeper refactors - post-launch unless you have time)

| Idea | Why | Effort |
|------|-----|--------|
| **Editor diff before flash** | Operators trust FLASH more when they see substituted LHOST/LPORT | Medium |
| **Session idle timeout + re-login** | Shared demo laptop: auto-logout after N minutes | Medium |
| **Structured audit log** | Who flashed what, when (deployments.json exists; could enrich) | Medium |
| **Victim script signing / hash in UI** | Show SHA256 of generated exfil for lab reports | Medium |
| **Teensy pipeline** | Re-enable nav when compile + `.hex` path is reliable | Large |
| **Multi-user on one machine** | Concurrent operators (tabs) already work; document vs true multi-tenant server | Doc only |

### Things I would **not** add before launch

- New device types or cloud sync
- Built-in C2 beyond phone-home CATCH
- Account recovery email (scope creep for a local lab tool)
- Rebuilding the TUI

---

## Suggested order (next 7-14 days)

```
Week 1
  Day 1-2   Phase 1B + 1C (isolation + USB scenarios)
  Day 3     Phase 1E if demoing from two machines
  Day 4     Fix any FAIL rows from testing
  Day 5     Phase 2 must-have polish

Week 2
  Day 1-2   Nice-to-have polish (demo command, screenshots, CHANGELOG)
  Day 3     Phase 3 go-live + git tag v1.0.0
  Day 4-7   Buffer for hardware arrives / VM issues / booth dry run

Post v1.0.0 (Phase 4)
  Week 1    NEW payload + MY PAYLOADS (target v1.0.1)
  Week 1-2  DEVICE REF in Help modal
```

---

## Quick reference | Commands for demo dry run

```
present          # projector layout
present off
defcon           # or Konami: ↑↑↓↓←→←→BA
theme matrix     # optional visual pop
set lhost <LAN IP>
devices
help
```

Ko-fi: **A** (About) or [ko-fi.com/neur0sp1cy](https://ko-fi.com/neur0sp1cy)
