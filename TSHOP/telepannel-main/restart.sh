#!/bin/bash
pkill -f "python.*main.py"
sleep 2
cd /home/ubuntu/telepannel
source venv/bin/activate
python main.py
