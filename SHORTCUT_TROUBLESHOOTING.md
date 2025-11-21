# Desktop Shortcut - Troubleshooting Guide

## Issue Resolution Summary

### Problem
Desktop shortcut launched the console window but browser did not auto-open.

### Root Cause
Streamlit configuration had `headless = true` in `.streamlit/config.toml`, which prevents automatic browser opening.

### Solution
Changed `.streamlit/config.toml`:
```toml
[server]
headless = false  # Changed from true
```

### Additional Fixes Applied
1. **Console Window Visibility**: Changed shortcut `WindowStyle` from 7 (minimized) to 1 (normal)
2. **Improved Launcher Messages**: Enhanced `run.py` with clearer startup progress messages
3. **Cleaned Up Orphaned Processes**: Multiple Python instances were running from testing

---

## Current Working Configuration

### Desktop Shortcut Properties
- **Target**: `C:\Users\wdrob\PycharmProjects\YouTube_Analyzer_Project\.venv\Scripts\python.exe`
- **Arguments**: `"C:\Users\wdrob\PycharmProjects\YouTube_Analyzer_Project\run.py"`
- **Working Directory**: `C:\Users\wdrob\PycharmProjects\YouTube_Analyzer_Project`
- **Icon**: `C:\Users\wdrob\PycharmProjects\YouTube_Analyzer_Project\icon.ico`
- **Window Style**: 1 (Normal)

### Expected Behavior
1. Double-click desktop icon
2. Console window opens with startup messages
3. Browser automatically opens to `http://localhost:8501`
4. App loads with dark theme

---

## Common Issues & Solutions

### Issue: "Console opens but nothing happens"
**Cause**: Streamlit in headless mode  
**Fix**: Set `headless = false` in `.streamlit/config.toml`

### Issue: "Icon does nothing when clicked"
**Causes**:
- Missing dependencies (chardet, streamlit, etc.)
- Virtual environment not set up
- Multiple instances already running

**Fix**:
1. Install dependencies: `.\.venv\Scripts\pip.exe install -r requirements.txt`
2. Stop all instances: `Stop-Process -Name python, pythonw -Force`
3. Try again

### Issue: "Console window immediately closes"
**Cause**: Error in `run.py` startup checks  
**Fix**: 
- Check if `.env` file exists
- Verify virtual environment at `.venv/`
- Run manually to see error: `.\.venv\Scripts\python.exe run.py`

### Issue: "Browser opens to wrong port"
**Cause**: Multiple Streamlit instances running  
**Fix**: 
```powershell
Stop-Process -Name python, pythonw, streamlit -Force
```
Then relaunch the shortcut.

---

## Manual Launch Methods

### Method 1: Desktop Shortcut (Recommended)
Double-click "YouTube Analyzer" icon on desktop

### Method 2: PowerShell
```powershell
cd C:\Users\wdrob\PycharmProjects\YouTube_Analyzer_Project
.\.venv\Scripts\python.exe run.py
```

### Method 3: Direct Streamlit
```powershell
cd C:\Users\wdrob\PycharmProjects\YouTube_Analyzer_Project
.\.venv\Scripts\streamlit.exe run app.py.py
```

---

## Verification Commands

### Check if app is running
```powershell
Get-Process -Name python, pythonw | Select-Object ProcessName, Id, StartTime
```

### Check Streamlit ports
```powershell
netstat -ano | findstr "850"
```

### View app logs
```powershell
Get-Content app.log -Tail 20
```

### Stop all instances
```powershell
Stop-Process -Name python, pythonw, streamlit -Force
```

---

## Files Involved

- `run.py` - Main launcher script with startup checks
- `run.pyw` - Silent launcher (no console window)
- `icon.ico` - Custom YouTube-themed icon
- `setup_shortcut.ps1` - Automated shortcut creation
- `.streamlit/config.toml` - Streamlit configuration (headless setting)
- Desktop shortcut: `%USERPROFILE%\Desktop\YouTube Analyzer.lnk`

---

## Success Checklist

- [x] Desktop icon visible with custom icon
- [x] Double-click opens console window
- [x] Startup checks pass (config, dependencies)
- [x] Browser opens automatically
- [x] App loads at http://localhost:8501
- [x] Dark theme applies
- [x] Console window stays open (can be minimized)

---

## Notes

- Keep the console window open while using the app
- Press Ctrl+C in console to stop the app
- Close browser tab when done, then close console
- Can pin shortcut to taskbar for easier access

Last Updated: 2025-11-21

