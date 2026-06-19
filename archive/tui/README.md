# TUI (archived)

TSK shipped an optional Textual terminal UI (`TSK.py`) in early v2 development. It was removed in favor of the **web UI as the single operator surface**.

## Why it was dropped

- The web UI is feature-complete: SNARF, lure, CATCH, editor, themes, tutorial, SSH modal, and device workflows.
- Maintaining two UIs duplicated effort with no clear operator benefit.
- Real workflows already assume `server.py` is running; `http://127.0.0.1:1337` is simpler than a 120×36 terminal app.

## If you need the old code

Check git history before the TUI removal commit for:

- `TSK.py` - Textual application
- `TSK.tcss` - Stylesheet
- `tui_themes.py` - Theme palettes
- `run.sh` - TUI launcher

## Revisiting later

If there is demand for terminal-only operation (SSH-only host, no browser), prefer a thin wrapper (print URL, health check) over rebuilding a full second UI. Any revival should share `config.py`, `repos.py`, and `flash.py` with the web app, not fork them.
