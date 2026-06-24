#!/usr/bin/env bash
# Build Teensy lab banner hex (Teensy 3.2 / mk20dx256) when arduino-cli + Teensyduino are installed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKETCH="$ROOT/web/static/payloads/teensy/tsk_lab_banner.ino"
OUT_DIR="$ROOT/web/static/payloads/teensy"
FQBN="${FQBN:-teensy:avr:teensy31}"

if ! command -v arduino-cli >/dev/null 2>&1; then
  echo "arduino-cli not found. Install from https://arduino.github.io/arduino-cli/"
  echo "Then install Teensyduino board package and run this script again."
  exit 1
fi

arduino-cli compile --fqbn "$FQBN" --output-dir "$OUT_DIR" "$SKETCH"
echo "Built: $OUT_DIR/tsk_lab_banner.hex"
