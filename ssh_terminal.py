"""
Browser SSH bridge for LAN Turtle — streams OpenSSH over WebSocket.
SSH runs in a new session on a dedicated PTY so the password prompt appears
in the browser xterm, not the server's terminal.
"""

import asyncio
import fcntl
import json
import os
import pty
import shutil
import signal
import struct
import subprocess
import termios
from fastapi import WebSocket, WebSocketDisconnect

# OG LAN Turtle — match manual ssh that works on OpenSSH 9.x
TURTLE_SSH_OPTS = [
    "-o", "ConnectTimeout=15",
    "-o", "StrictHostKeyChecking=no",
    "-o", "UserKnownHostsFile=/dev/null",
    "-o", "HostKeyAlgorithms=+ssh-rsa",
    "-o", "PubkeyAcceptedAlgorithms=+ssh-rsa",
    "-o", "PubkeyAcceptedKeyTypes=+ssh-rsa",
]


def set_pty_size(fd: int, rows: int = 24, cols: int = 80) -> None:
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def turtle_ssh_argv(cfg: dict) -> list[str]:
    ip = str(cfg.get("turtle_ip", "172.16.84.1")).strip()
    user = str(cfg.get("turtle_user", "root")).strip()
    port = str(cfg.get("turtle_port", "22")).strip()
    ssh_bin = shutil.which("ssh") or "ssh"
    return [
        ssh_bin,
        "-p", port,
        *TURTLE_SSH_OPTS,
        f"{user}@{ip}",
    ]


def turtle_target_label(cfg: dict) -> str:
    user = str(cfg.get("turtle_user", "root")).strip()
    ip = str(cfg.get("turtle_ip", "172.16.84.1")).strip()
    port = str(cfg.get("turtle_port", "22")).strip()
    return f"{user}@{ip}:{port}"


def _ssh_child_setup() -> None:
    """New session + PTY as controlling tty so ssh never uses the server terminal."""
    os.setsid()
    try:
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    except OSError:
        pass


def _spawn_ssh_on_pty(argv: list[str], master_fd: int, slave_fd: int) -> subprocess.Popen:
    """Start ssh on the PTY slave in an isolated session."""
    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    proc = subprocess.Popen(
        argv,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        preexec_fn=_ssh_child_setup,
        env=env,
    )
    os.close(slave_fd)
    return proc


async def _read_pty(fd: int, ws: WebSocket) -> None:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    def on_read() -> None:
        try:
            data = os.read(fd, 4096)
            queue.put_nowait(data if data else None)
        except OSError:
            queue.put_nowait(None)

    loop.add_reader(fd, on_read)
    try:
        while True:
            data = await queue.get()
            if data is None:
                break
            await ws.send_bytes(data)
    except (WebSocketDisconnect, asyncio.CancelledError, RuntimeError):
        pass
    finally:
        try:
            loop.remove_reader(fd)
        except Exception:
            pass


async def _pump_ws_to_pty(fd: int, ws: WebSocket) -> None:
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            text = msg.get("text")
            if text:
                if text.startswith("{") and '"type"' in text:
                    try:
                        data = json.loads(text)
                        if data.get("type") == "resize":
                            set_pty_size(
                                fd,
                                int(data.get("rows", 24)),
                                int(data.get("cols", 80)),
                            )
                            continue
                    except (json.JSONDecodeError, ValueError, TypeError):
                        pass
                try:
                    os.write(fd, text.encode("utf-8", errors="replace"))
                except OSError:
                    break
            raw = msg.get("bytes")
            if raw:
                try:
                    os.write(fd, raw)
                except OSError:
                    break
    except (WebSocketDisconnect, asyncio.CancelledError, RuntimeError):
        pass


async def _wait_proc(proc: subprocess.Popen) -> int:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, proc.wait)


def _terminate_proc(proc: subprocess.Popen) -> None:
    try:
        os.kill(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


async def handle_turtle_ssh(ws: WebSocket, cfg: dict) -> None:
    """Bridge WebSocket ↔ ssh via PTY (interactive LAN Turtle shell)."""
    if not shutil.which("ssh"):
        await ws.send_json({"type": "error", "msg": "ssh not found — install OpenSSH client"})
        await ws.close()
        return

    target = turtle_target_label(cfg)
    argv = turtle_ssh_argv(cfg)

    await ws.send_json({"type": "status", "msg": f"Starting SSH → {target}"})

    try:
        master_fd, slave_fd = pty.openpty()
    except OSError as e:
        await ws.send_json({"type": "error", "msg": f"PTY open failed: {e}"})
        await ws.close()
        return

    set_pty_size(master_fd, 24, 80)

    try:
        proc = _spawn_ssh_on_pty(argv, master_fd, slave_fd)
    except OSError as e:
        os.close(master_fd)
        await ws.send_json({"type": "error", "msg": f"SSH start failed: {e}"})
        await ws.close()
        return

    await ws.send_json({
        "type": "connected",
        "target": target,
        "hint": "Password: press Enter (blank) or try hak5lan",
    })

    read_task = asyncio.create_task(_read_pty(master_fd, ws))
    write_task = asyncio.create_task(_pump_ws_to_pty(master_fd, ws))
    wait_task = asyncio.create_task(_wait_proc(proc))

    done, _pending = await asyncio.wait(
        {read_task, write_task, wait_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Stop PTY ↔ WebSocket pumps once any leg of the session ends.
    for t in (read_task, write_task):
        if not t.done():
            t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass

    if wait_task not in done:
        _terminate_proc(proc)
        try:
            await asyncio.wait_for(wait_task, timeout=2.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            try:
                os.kill(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    try:
        os.close(master_fd)
    except OSError:
        pass

    rc = 0
    if wait_task.done() and not wait_task.cancelled():
        try:
            rc = wait_task.result()
        except Exception:
            pass

    if rc != 0:
        await ws.send_json({
            "type": "error",
            "msg": "SSH session ended. If auth failed, try blank Enter or hak5lan",
        })
    else:
        await ws.send_json({"type": "status", "msg": "Session ended"})
