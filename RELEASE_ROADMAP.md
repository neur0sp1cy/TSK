# TSK | Release roadmap

**Status:** v1.0.0 **shipped** (2026-07-04) - public repo, GitHub Release, Ko-fi go-live post.

This doc is the long-term feature backlog when you pick the project back up. For install and features see [README.md](README.md). For lab testing see [TESTING.md](TESTING.md) and [TESTING_CHECKLIST.md](TESTING_CHECKLIST.md).

- **Release notes:** [CHANGELOG.md](CHANGELOG.md)
- **Archived TUI:** [archive/tui/README.md](archive/tui/README.md)

---

## v1.0.0 shipped | what went out

| Item | Status |
|------|--------|
| Web UI (Ducky, Bunny, Turtle, USB Dropper) | Shipped |
| SnarfSnarf EXFIL + LURE + CATCH (per-operator isolation) | Shipped |
| MY PAYLOADS / EXFILS / LURES (USB) | Shipped |
| Payload-set browse, multi-file flash, P+/F+ packages | Shipped |
| Category + package expand/collapse (persisted tree state) | Shipped |
| Editor inline find (Ctrl+F, match case, gutter highlights) | Shipped |
| Sidebar SYSTEM/DEVICES layout, full-height sidebar, no device scroll clip | Shipped |
| Seven tutorial missions, Help/About, Ko-fi links | Shipped |
| DEF CON 34 branding, six themes, `present` mode | Shipped |
| Docs audit, SECURITY attribution, pytest smoke/isolation tests | Shipped |
| Git tag `v1.0.0`, GitHub Release, Ko-fi announcement | Shipped |

**Deferred lab sign-off (operator, when hardware available):** full USB FLASH → victim → CATCH E2E, alice/bob UI isolation walkthrough, optional HAK5 device flash. Automated CATCH isolation + API smoke tests cover the code paths.

---

## Phase 3 | Go-live (complete)

| # | Task | Done? |
|---|------|-------|
| 1 | Phase 1 must-pass rows (or documented SKIP) | Partial - operator lab when ready |
| 2 | Phase 2 must-have polish | Yes |
| 3 | Git tag `v1.0.0` on GitHub | Yes (`480bc19`) |
| 4 | GitHub Release notes | Yes |
| 5 | Ko-fi page links to repo + go-live post | Yes |
| 6 | Demo machine prep | As needed for booth |
| 7 | `present` on projector | As needed for booth |

---

## Phase 4 | Post v1.0.0 (future work)

Pick up here when you reopen the project. Suggested order at bottom.

### 4A | NEW payload + MY PAYLOADS (other devices)

**USB Dropper (shipped in v1.0.0):** `+ NEW`, **MY PAYLOADS**, **EXFILS**, **LURES**, lure packages, rename/delete, binary-safe LNK preview.

**Remaining for v1.0.1+:**

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1 | **+ NEW PAYLOAD** on Ducky, Bunny, Turtle | Partial | USB done; extend browse header |
| 2 | **MY PAYLOADS** category for non-USB devices | Partial | USB done via `index_user_payloads` |
| 3 | **SAVE TO LIBRARY** in editor | Shipped (USB) | Repo paths save-as to MY PAYLOADS |
| 4 | **Repo-safe saves** | Shipped | No silent overwrite of cloned repos |
| 5 | **API** `POST /api/payload/create` | Shipped | |
| 6 | **index_user_payloads** cat names | Shipped (USB) | EXFILS / MY PAYLOADS / LURES |

**Effort:** Small-Medium for Ducky/Bunny/Turtle parity only.

### 4B | Device command reference

Help (`H`) covers TSK operator workflow, not DuckyScript or Bash Bunny syntax.

| # | Feature | Notes |
|---|---------|-------|
| 1 | **DEVICE REF** section in Help modal | DuckyScript: `DELAY`, `STRING`, `ENTER`, `GUI`, `REM`, etc. |
| 2 | **Bash Bunny** quick ref | `ATTACKMODE`, `LED`, `QUACK`, `REQUIRETOOL`, switch folders |
| 3 | **LAN Turtle** notes | Module layout, `autossh`, SCP push pointers |
| 4 | **External links** | HAK5 official docs |
| 5 | Optional: `ref` command or **?** to open DEVICE REF | Same content as Help subsection |
| 6 | **Later:** editor insert chips | Click-to-insert when `lang` is DS1 / BB |

**Effort:** Small for Help + links; Medium for editor chips.

### 4C | Boss Mode (panic / decoy screen)

When someone walks in unexpectedly, hide payloads behind something boring and plausible.

| # | Feature | Notes |
|---|---------|-------|
| 1 | **`boss` / `boss off` command** | Toggle decoy overlay; same muscle memory as `present` |
| 2 | **Global hotkey** | e.g. **`B`** or **`Ctrl+Shift+B`** when not typing in an input |
| 3 | **Decoy screen** | Fake spreadsheet, network inventory, IT dashboard (no TSK chrome) |
| 4 | **State preservation** | Restore modal, device, scroll on `boss off` |
| 5 | **Optional presets** | `boss spreadsheet` · `boss inventory` · `boss maintenance` |

**Not the same as `present`:** presentation mode is for booth/projector. Boss Mode is a **cover story** for shoulder-surfers.

**Effort:** Small-Medium (overlay + templates + hotkey; no backend).

### 4D | USB Dropper decoy / callback files (parking-lot drop)

Benign decoy files on a stick that phone home when opened (authorized physical social engineering).

| # | Feature | Notes |
|---|---------|-------|
| 1 | **Attach decoy files to flash** | PDF, DOCX, XLSX, etc. alongside lure/exfil |
| 2 | **Callback on open** | LNK / README / `.desktop` wrappers + minimal check-in stub (CATCH flow) |
| 3 | **AV-conscious templates** | Lab-only docs; detection expectations |
| 4 | **Package builder UI** | SNARF/LURES: pick decoy + callback; preview stick layout before FLASH |
| 5 | **CATCH tagging** | `decoy-open` vs exfil for client deliverables |

**Effort:** Medium.

### 4E | UI polish (on demand)

Items discussed during v1.0.0 polish - ship only if users ask.

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1 | **Compact sidebar (1080p / 14")** | Deferred | Smaller logo/tiles/cards via `@media (max-height: …)` - no nav redesign |
| 2 | **`demo on` / `demo off` command** | Not built | Single booth toggle: `present` + defcon + dismiss LHOST hint |
| 3 | **Editor flash diff view** | Not built | Side-by-side or inline diff before FLASH (VARS panel exists) |
| 4 | **GitHub social preview / README screenshots** | Not built | 3-4 panel hero for repo Open Graph |
| 5 | **Hack the Planet gif** | Backlog | Text fallback works; add asset when ready |
| 6 | **Post-register checklist modal** | Not built | "Set LHOST → pick USB → Mission 1" on first login |

### 4F | Teensy and hardware

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1 | **Teensy compile pipeline in UI** | Not built | Re-enable nav when `.hex` path is reliable |
| 2 | **Teensy payloads browse/flash** | Placeholder only | SOON badge in UI |

**Effort:** Large.

### Suggested post-launch order

```
When you reopen TSK
  1   + NEW / MY PAYLOADS for Ducky, Bunny, Turtle (v1.0.1)
  2   DEVICE REF in Help (+ HAK5 doc links)
  3   Boss Mode (decoy screen + hotkey)
  4   USB parking-lot decoy/callback files (4D)
  5   Optional polish: demo on, editor diff, compact sidebar, screenshots
  6   Teensy pipeline (4F) if hardware pipeline is ready
```

---

## Backlog | other ideas (not scheduled)

| Idea | Why | Effort |
|------|-----|--------|
| **`/api/health` endpoint** | `{"ok":true,"version":"1.0.0"}` for pre-demo sanity | Tiny |
| **Snarf upload size / rate guard** | Soft limits on `/api/snarf` in shared lab | Medium |
| **Export operator config backup** | Download config + payload list from CONFIG | Medium |
| **Session idle timeout + re-login** | Shared demo laptop auto-logout | Medium |
| **Structured audit log** | Enrich deployments.json | Medium |
| **Victim script SHA256 in UI** | Lab report artifact | Medium |
| **Deployment log in bottom bar** | Surface last flash without opening CONFIG | Small |

### Will not pursue (scope creep)

- New device types or cloud sync
- Built-in C2 beyond phone-home CATCH
- Account recovery / email flows
- Full mobile layout
- Rebuilding the Textual TUI

---

## Phase 1-2 reference (historical)

Kept for lab regression when you return. Use [TESTING_CHECKLIST.md](TESTING_CHECKLIST.md) for pass/fail rows.

**Phase 1:** Operator setup, alice/bob CATCH isolation, USB scenarios A-D, optional HAK5 flash, HTTPS mode.

**Phase 2 must-have (all shipped for v1.0.0):** Ko-fi About, Help/Tutorial, LHOST hint, login copy, README, `present`, fresh clone path, CHANGELOG.

**Phase 2 nice-to-have (partial):** `defcon`/Konami shipped; demo command, editor diff, social preview, HTP gif - see Phase 4E.

---

## Quick reference | Demo commands

```
present          # projector layout
present off
defcon           # or Konami: ↑↑↓↓←→←→BA
theme matrix
set lhost <LAN IP>
devices
help
```

Repo: [github.com/neur0sp1cy/TSK](https://github.com/neur0sp1cy/TSK)  
Ko-fi: [ko-fi.com/neur0sp1cy](https://ko-fi.com/neur0sp1cy)
