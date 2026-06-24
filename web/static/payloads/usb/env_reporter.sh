#!/bin/bash
# TSK built-in | Env Reporter (Linux)
# Writes whoami and environment snapshot next to this script on the USB stick.
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/tsk_env_report.txt"
{
  echo "TSK Env Reporter"
  echo "================"
  echo "whoami: $(whoami 2>&1)"
  echo "date:   $(date -Is 2>/dev/null || date)"
  echo ""
  echo "--- environment ---"
  env | sort
} > "$OUT"
