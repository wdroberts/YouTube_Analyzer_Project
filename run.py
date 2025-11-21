#!/usr/bin/env python
"""
YouTube Analyzer Launcher
Enhanced launcher with validation and helpful error messages.
"""
import os
import sys
import subprocess
from pathlib import Path


def check_env_file():
    """Check if .env file exists."""
    env_path = Path(".env")
    if not env_path.exists():
        print("=" * 60)
        print("[ERROR] .env file not found!")
        print("=" * 60)
        print("\nQuick Fix:")
        print("1. Copy env.template to .env")
        print("2. Add your OpenAI API key")
        print("3. Run this again\n")
        print("Commands:")
        print("  Windows: copy env.template .env")
        print("  Mac/Linux: cp env.template .env")
        print("=" * 60)
        input("\nPress Enter to exit...")
        return False
    return True


def check_virtual_env():
    """Check if running in virtual environment."""
    venv_path = Path(".venv")
    if not venv_path.exists():
        print("=" * 60)
        print("[WARNING] Virtual environment not found")
        print("=" * 60)
        print("\nRecommended: Create a virtual environment")
        print("  python -m venv .venv")
        print("\nContinuing anyway...")
        print("=" * 60)
        return True
    return True


def check_dependencies():
    """Check if key dependencies are installed."""
    try:
        import streamlit
        return True
    except ImportError:
        print("=" * 60)
        print("[*] Installing dependencies...")
        print("=" * 60)
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            print("\n[OK] Dependencies installed successfully!")
            return True
        except subprocess.CalledProcessError:
            print("\n[ERROR] Failed to install dependencies")
            print("Try manually: pip install -r requirements.txt")
            input("\nPress Enter to exit...")
            return False


def main():
    """Main launcher function."""
    # Change to script directory
    os.chdir(Path(__file__).parent)
    
    # Configure stdout for Windows
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass
    
    print("=" * 60)
    print("YouTube Analyzer Launcher")
    print("=" * 60)
    print()
    
    # Run checks
    print("[*] Running startup checks...")
    
    if not check_env_file():
        return 1
    print("  [OK] Configuration (.env) found")
    
    check_virtual_env()
    
    if not check_dependencies():
        return 1
    print("  [OK] Dependencies OK")
    
    print("\n[*] Starting application...")
    print("=" * 60)
    print()
    
    # Launch Streamlit
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py.py"])
        return 0
    except KeyboardInterrupt:
        print("\n\n[*] Application stopped by user")
        return 0
    except Exception as e:
        print(f"\n[ERROR] Error launching application: {e}")
        input("\nPress Enter to exit...")
        return 1


if __name__ == "__main__":
    sys.exit(main())

