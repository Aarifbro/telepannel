#!/bin/bash
cd "/workspaces/telepannel"
source .venv/bin/activate
echo "🤖 Starting Telepannel Bot..."
echo "📅 Started at: $(date)"
echo "📁 Working directory: $(pwd)"
echo "🐍 Python version: $(python --version)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
python main.py
