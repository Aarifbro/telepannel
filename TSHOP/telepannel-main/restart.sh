#!/bin/bash
pkill -f "python.*main.py"
sleep 2
cd /workspaces/telepannel/TSHOP/telepannel-main
source venv/bin/activate
python main.py
