#!/usr/bin/env python3
"""
Root-level entry point for the Telepannel bot.
Changes directory to the bot source and starts main.py.
"""
import os
import sys
import runpy

BOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "TSHOP", "telepannel-main")

# Add the bot directory to the Python path and switch working directory
sys.path.insert(0, BOT_DIR)
os.chdir(BOT_DIR)

# Run main.py from the bot directory
runpy.run_path(os.path.join(BOT_DIR, "main.py"), run_name="__main__")
