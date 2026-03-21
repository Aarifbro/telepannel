#!/bin/bash
cd "$(dirname "$0")"
# Support both .venv (VPS deployment) and venv (local dev)
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "ERROR: No virtual environment found (.venv or venv). Run vps_setup.sh first." >&2
    exit 1
fi
python3 main.py
