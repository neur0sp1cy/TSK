"""
Non-interactive SSH/SFTP to LAN Turtle for flash operations.
Uses OpenSSH + sshpass (legacy ssh-rsa host keys). Paramiko 5+ cannot negotiate
OG LAN Turtle host keys without a legacy Transport shim.
"""

import os
import shutil
import subprocess

from ssh_terminal import TURTLE_SSH_OPTS

# Extra opts for batch sshpass/scp (fail fast, no interactive prompts)
TURTLE_BATCH_OPTS = [
    *TURTLE_SSH_OPTS,
    "-o", "NumberOfPasswordPrompts=1",
    "-o", "PreferredAuthentications=password",
    "-o", "ServerAliveInterval=5",
    "-o", "ServerAliveCountMax=2",
]

try:
    import paramiko
    from paramiko.ssh_exception import IncompatiblePeer
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False
    IncompatiblePeer = Exception  # type: ignore


class TurtleSSHError(Exception):
    pass


# OG LAN Turtle only offers ssh-rsa — Paramiko 5 removed it from defaults.
if HAS_PARAMIKO:
    class TurtleTransport(paramiko.Transport):
        _preferred_keys = ("ssh-rsa",)
        _preferred_pubkeys = ("ssh-rsa",)


def _cfg_connection(cfg: dict) -> tuple[str, str, int, str]:
    ip = str(cfg.get("turtle_ip", "172.16.84.1")).strip()
    user = str(cfg.get("turtle_user", "root")).strip()
    port = int(str(cfg.get("turtle_port", "22")).strip() or "22")
    password = cfg.get("turtle_password", "")
    if password is None:
        password = ""
    return ip, user, port, password


def _has_sshpass() -> bool:
    return shutil.which("sshpass") is not None


def _has_ssh() -> bool:
    return shutil.which("ssh") is not None


def _run_with_sshpass(
    argv: list[str],
    password: str,
    timeout: int,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["SSHPASS"] = password
    return subprocess.run(
        ["sshpass", "-e", *argv],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _ssh_argv(cfg: dict, remote_cmd: str) -> list[str]:
    ip, user, port, _ = _cfg_connection(cfg)
    return [
        "ssh",
        "-p", str(port),
        *TURTLE_BATCH_OPTS,
        f"{user}@{ip}",
        remote_cmd,
    ]


def _scp_argv(cfg: dict, local_path: str, remote_path: str) -> list[str]:
    ip, user, port, _ = _cfg_connection(cfg)
    return [
        "scp",
        "-P", str(port),
        *TURTLE_BATCH_OPTS,
        local_path,
        f"{user}@{ip}:{remote_path}",
    ]


def _connect_openssh(cfg: dict, remote_cmd: str = "echo OK", timeout: int = 20) -> tuple[bool, str]:
    if not _has_ssh():
        return False, "OpenSSH client (ssh) not found"

    _, _, _, password = _cfg_connection(cfg)
    argv = _ssh_argv(cfg, remote_cmd)

    try:
        if _has_sshpass():
            result = _run_with_sshpass(argv, password, timeout)
        else:
            ip, user, port, _ = _cfg_connection(cfg)
            batch = [
                "ssh",
                "-p", str(port),
                *TURTLE_BATCH_OPTS,
                "-o", "BatchMode=yes",
                f"{user}@{ip}",
                remote_cmd,
            ]
            result = subprocess.run(batch, capture_output=True, text=True, timeout=timeout)

        if result.returncode == 0 and "OK" in result.stdout:
            return True, "Connected"
        err = (result.stderr or result.stdout or "").strip()
        if not _has_sshpass():
            return False, (
                "Install sshpass for password auth: sudo apt install sshpass"
            )
        return False, err or f"ssh failed (exit {result.returncode})"
    except subprocess.TimeoutExpired:
        return False, "SSH timed out — is the Turtle plugged in and booted?"
    except Exception as e:
        return False, str(e)


def _connect_paramiko(cfg: dict) -> "paramiko.SSHClient":
    if not HAS_PARAMIKO:
        raise TurtleSSHError("paramiko not installed")

    ip, user, port, password = _cfg_connection(cfg)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=ip,
            port=port,
            username=user,
            password=password,
            allow_agent=False,
            look_for_keys=False,
            timeout=15,
            banner_timeout=15,
            auth_timeout=15,
            transport_factory=TurtleTransport,
            disabled_algorithms={
                "pubkeys": ["rsa-sha2-256", "rsa-sha2-512"],
            },
        )
    except IncompatiblePeer as e:
        raise TurtleSSHError(
            f"SSH algorithm mismatch: {e}. Install sshpass and use OpenSSH."
        )
    except paramiko.AuthenticationException:
        raise TurtleSSHError(
            "SSH authentication failed — check LAN TURTLE PASSWORD in CONFIG."
        )
    except (paramiko.SSHException, OSError, TimeoutError) as e:
        raise TurtleSSHError(f"SSH connect failed: {e}")
    return client


def turtle_test_connection(cfg: dict) -> tuple[bool, str]:
    """Return (ok, message). Prefer OpenSSH+sshpass (legacy ssh-rsa)."""
    ok, msg = _connect_openssh(cfg)
    if ok:
        return True, msg

    if _has_sshpass() or not HAS_PARAMIKO:
        return False, msg

    try:
        client = _connect_paramiko(cfg)
        _, stdout, _ = client.exec_command("echo OK", timeout=10)
        out = stdout.read().decode(errors="replace").strip()
        client.close()
        if "OK" in out:
            return True, "Connected"
        return False, f"Unexpected response: {out!r}"
    except TurtleSSHError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


def turtle_upload_file(
    cfg: dict,
    local_path: str,
    remote_path: str,
    chmod_mode: int = 0o755,
) -> None:
    """Upload a module file to the Turtle."""
    _, _, _, password = _cfg_connection(cfg)

    if _has_ssh() and _has_sshpass():
        scp_argv = _scp_argv(cfg, local_path, remote_path)
        try:
            result = _run_with_sshpass(scp_argv, password, 60)
        except subprocess.TimeoutExpired:
            raise TurtleSSHError("SCP timed out")
        if result.returncode != 0:
            raise TurtleSSHError((result.stderr or result.stdout or "SCP failed").strip())

        chmod_argv = _ssh_argv(cfg, f"chmod {format(chmod_mode, 'o')} {remote_path}")
        try:
            chmod_res = _run_with_sshpass(chmod_argv, password, 15)
        except subprocess.TimeoutExpired:
            raise TurtleSSHError("chmod timed out")
        if chmod_res.returncode != 0:
            raise TurtleSSHError(
                (chmod_res.stderr or chmod_res.stdout or "chmod failed").strip()
            )
        return

    if HAS_PARAMIKO:
        client = _connect_paramiko(cfg)
        try:
            sftp = client.open_sftp()
            sftp.put(local_path, remote_path)
            sftp.chmod(remote_path, chmod_mode)
            sftp.close()
        finally:
            client.close()
        return

    raise TurtleSSHError(
        "Cannot upload — install sshpass: sudo apt install sshpass"
    )


def turtle_run_remote(cfg: dict, remote_cmd: str, timeout: int = 30) -> tuple[int, str, str]:
    """Run a remote command; return (exit_code, stdout, stderr)."""
    _, _, _, password = _cfg_connection(cfg)

    if _has_ssh() and _has_sshpass():
        argv = _ssh_argv(cfg, remote_cmd)
        try:
            result = _run_with_sshpass(argv, password, timeout)
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            raise TurtleSSHError("Remote command timed out")

    if HAS_PARAMIKO:
        client = _connect_paramiko(cfg)
        try:
            _, stdout, stderr = client.exec_command(remote_cmd, timeout=timeout)
            out = stdout.read().decode(errors="replace")
            err = stderr.read().decode(errors="replace")
            code = stdout.channel.recv_exit_status()
            return code, out, err
        finally:
            client.close()

    raise TurtleSSHError("Install sshpass for remote commands")
