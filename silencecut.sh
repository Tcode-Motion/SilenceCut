#!/bin/sh
# SilenceCut launcher for macOS and Linux
cd "$(dirname "$0")"
PY=$(command -v python3 || command -v python)
if [ $# -gt 0 ]; then
  exec $PY silencecut.py "$@"
fi
exec $PY silencecut_web.py
