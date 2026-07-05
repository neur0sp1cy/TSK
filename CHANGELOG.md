# Changelog

All notable changes to TSK (The Skeleton Key) are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-07-04

First public release. Web-only operator UI for authorized lab and field USB/HID payload work.

### Added

- **Web UI** - Single-page operator console at port 1337 (FastAPI + static UI)
- **Devices** - Rubber Ducky, Bash Bunny, LAN Turtle, USB Dropper browse/flash; Teensy placeholder
- **USB Dropper / SnarfSnarf** - EXFIL builder (PowerShell/Bash), LURE packages (LNK, README, `.desktop`), CATCH phone-home receiver with per-operator isolation
- **MY PAYLOADS** - Operator-owned packages on USB (P+/F+, rename, delete); multi-file Bunny/Ducky/Turtle package support
- **Payload browse** - Category and package expand/collapse with persisted tree state; EXPAND ALL
- **Editor** - Inline find bar (Ctrl+F), match case, gutter highlights, VARS panel
- **Auth** - Register/login, per-operator config and payload storage under `users/<operator>/`
- **LAN Turtle** - In-browser SSH terminal modal
- **Themes** - Six UI themes; `present` mode for projector demos
- **Tutorial** - Seven missions at `/tutorial`
- **Help / About** - In-app operator guide; Ko-fi support links
- **Docs** - README, TESTING.md, TESTING_CHECKLIST.md, RELEASE_ROADMAP.md, SECURITY.md

### Changed

- Replaced legacy Textual TUI with web UI as the sole operator surface (see `archive/tui/`)
- DEF CON 34 edition branding across UI and docs
- Sidebar layout: SYSTEM/DEVICES sections, full-height sidebar, scroll-free device list on 1080p

### Security

- CATCH uploads routed by per-operator `catch_token`; `snarfed/<operator>/` isolation
- Session auth on API routes; path confinement for repo and catch file access

### Lab use

TSK is for **authorized security testing only**. See [SECURITY.md](SECURITY.md).

[1.0.0]: https://github.com/neur0sp1cy/TSK/releases/tag/v1.0.0
