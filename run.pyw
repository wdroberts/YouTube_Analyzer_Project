#!/usr/bin/env python
"""
YouTube Analyzer Silent Launcher
Launches the app without showing a command window.
Perfect for desktop shortcuts and daily use.
"""
import os
import sys
import subprocess
from pathlib import Path

# Change to script directory
os.chdir(Path(__file__).parent)

# Launch Streamlit silently
try:
    subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py.py"],
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    )
except Exception:
    # If silent launch fails, fall back to normal run.py
    subprocess.run([sys.executable, "run.py"])

