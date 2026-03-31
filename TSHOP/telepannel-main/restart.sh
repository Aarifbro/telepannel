#!/bin/bash
# Restart via systemd if available, otherwise kill and restart manually
if systemctl is-active --quiet telepannel 2>/dev/null; then
    systemctl restart telepannel
else
    pkill -f "python3 main.py" 2>/dev/null || pkill -f "python main.py" 2>/dev/null || true
    sleep 2
    cd /opt/telepannel
    source .venv/bin/activate
    python3 main.py
fi
