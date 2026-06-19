#!/usr/bin/env python3
"""
TSK setup — use this if you don't have uv.
Recommended: use uv instead (see README.md)
"""
import subprocess, sys
from pathlib import Path

VENV = Path(__file__).parent / ".venv"
DEPS = [
    "fastapi>=0.100.0",
    "uvicorn>=0.23.0",
    "websockets>=11.0",
    "bcrypt>=4.0.0",
    "paramiko>=3.0.0",
    "jinja2>=3.1.0",
    "python-multipart>=0.0.9",
    "pylnk3>=0.4.2",
]

print("\n\033[1;31m ─────────────────────────────────────\033[0m")
print("\033[1;31m  THE SKELETON KEY — Setup\033[0m")
print("\033[1;31m ─────────────────────────────────────\033[0m")
print("\n\033[1;33m TIP: uv is faster and simpler:\033[0m")
print("\033[0;37m   curl -LsSf https://astral.sh/uv/install.sh | sh\033[0m")
print("\033[0;37m   uv run python server.py\033[0m\n")

if sys.version_info < (3, 8):
    print(f"\033[1;31m✗ Python 3.8+ required\033[0m")
    sys.exit(1)
print(f"\033[1;32m✓ Python {sys.version.split()[0]}\033[0m")

print(f"\n\033[1;33m Creating venv at {VENV}...\033[0m", end=" ", flush=True)
r = subprocess.run([sys.executable, "-m", "venv", str(VENV)], capture_output=True)
if r.returncode != 0:
    print("\033[1;31m✗\033[0m")
    print("\033[1;33m Try: sudo apt install python3-venv\033[0m")
    sys.exit(1)
print("\033[1;32m✓\033[0m")

pip = VENV / "bin" / "pip"
subprocess.run([str(pip), "install", "--upgrade", "pip", "--quiet"])

for dep in DEPS:
    print(f"  → {dep}...", end=" ", flush=True)
    r = subprocess.run([str(pip), "install", dep, "--quiet"], capture_output=True)
    print("\033[1;32m✓\033[0m" if r.returncode == 0 else "\033[1;31m✗\033[0m")

print(f"""
\033[1;32m ─────────────────────────────────────\033[0m
\033[1;32m  Done! Launch the web UI:\033[0m
\033[1;37m    ./run_web.sh\033[0m
\033[1;37m    uv run python server.py\033[0m
\033[1;32m ─────────────────────────────────────\033[0m
""")
