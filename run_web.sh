#!/bin/bash
# TSK Web Interface launcher
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "  TSK | The Skeleton Key  v1.0"
echo "  DEF CON 34 Edition"
echo ""

# Install deps if needed and launch directly
if command -v uv &>/dev/null; then
    cd "$SCRIPT_DIR"
    uv sync --quiet 2>/dev/null || uv sync
    exec uv run python "$SCRIPT_DIR/server.py"
fi

# Fall back to venv
VENV="$SCRIPT_DIR/.venv"
if [ ! -f "$VENV/bin/python3" ]; then
    echo "  Creating venv..."
    python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install -e "$SCRIPT_DIR" --quiet 2>/dev/null || \
"$VENV/bin/pip" install fastapi uvicorn websockets bcrypt jinja2 python-multipart pylnk3 paramiko --quiet
exec "$VENV/bin/python3" "$SCRIPT_DIR/server.py"
