# ============================================================================
# YouTube Analyzer - Automatic Shortcut Setup
# ============================================================================
# This script creates a desktop shortcut with custom icon automatically
# Run this ONCE to set up your launcher
# ============================================================================

$ErrorActionPreference = "Stop"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host " YouTube Analyzer - Shortcut Setup" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory (project root)
$ProjectDir = $PSScriptRoot
$LauncherScript = Join-Path $ProjectDir "run.pyw"
$IconFile = Join-Path $ProjectDir "icon.ico"

# Check if launcher exists
if (-not (Test-Path $LauncherScript)) {
    Write-Host "[ERROR] Launcher script not found: $LauncherScript" -ForegroundColor Red
    Write-Host "Make sure run.pyw exists in the project directory" -ForegroundColor Yellow
    pause
    exit 1
}

# Check if icon exists
if (-not (Test-Path $IconFile)) {
    Write-Host "[WARNING] Icon file not found. Creating..." -ForegroundColor Yellow
    try {
        py create_icon.py
        Write-Host "[OK] Icon created successfully" -ForegroundColor Green
    } catch {
        Write-Host "[WARNING] Could not create icon. Will use default Python icon." -ForegroundColor Yellow
        $IconFile = $null
    }
}

# Create desktop shortcut
Write-Host "[1/4] Creating desktop shortcut..." -ForegroundColor Yellow
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopPath "YouTube Analyzer.lnk"

# Create WScript Shell object
$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut($ShortcutPath)

# Get pythonw.exe path (for silent execution)
$PythonwPath = (Get-Command pythonw -ErrorAction SilentlyContinue).Path
if (-not $PythonwPath) {
    # Fallback to py launcher with -w flag
    $PythonwPath = "pythonw"
}

# Configure shortcut
$Shortcut.TargetPath = $PythonwPath
$Shortcut.Arguments = "`"$LauncherScript`""
$Shortcut.WorkingDirectory = $ProjectDir
$Shortcut.Description = "Launch YouTube Analyzer - Transcribe and analyze videos"
$Shortcut.WindowStyle = 7  # Minimized

# Set icon if available
if ($IconFile -and (Test-Path $IconFile)) {
    $Shortcut.IconLocation = $IconFile
    Write-Host "   [OK] Custom icon assigned" -ForegroundColor Green
} else {
    Write-Host "   [OK] Using default icon" -ForegroundColor Green
}

# Save shortcut
$Shortcut.Save()
Write-Host "   [OK] Desktop shortcut created" -ForegroundColor Green

# Offer to pin to taskbar
Write-Host ""
Write-Host "[2/4] Desktop shortcut created at:" -ForegroundColor Yellow
Write-Host "   $ShortcutPath" -ForegroundColor Cyan
Write-Host ""

# Create Start Menu shortcut
Write-Host "[3/4] Creating Start Menu shortcut..." -ForegroundColor Yellow
$StartMenuPath = [Environment]::GetFolderPath("Programs")
$StartMenuShortcut = Join-Path $StartMenuPath "YouTube Analyzer.lnk"

try {
    $StartShortcut = $WScriptShell.CreateShortcut($StartMenuShortcut)
    $StartShortcut.TargetPath = $PythonwPath
    $StartShortcut.Arguments = "`"$LauncherScript`""
    $StartShortcut.WorkingDirectory = $ProjectDir
    $StartShortcut.Description = "Launch YouTube Analyzer - Transcribe and analyze videos"
    $StartShortcut.WindowStyle = 7
    if ($IconFile -and (Test-Path $IconFile)) {
        $StartShortcut.IconLocation = $IconFile
    }
    $StartShortcut.Save()
    Write-Host "   [OK] Start Menu shortcut created" -ForegroundColor Green
} catch {
    Write-Host "   [WARNING] Could not create Start Menu shortcut" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[4/4] Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host " What's Next?" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Look on your desktop for 'YouTube Analyzer' shortcut" -ForegroundColor White
Write-Host "2. Double-click to launch the app" -ForegroundColor White
Write-Host "3. (Optional) Right-click shortcut -> Pin to Taskbar" -ForegroundColor White
Write-Host ""
Write-Host "The shortcut will:" -ForegroundColor Yellow
Write-Host "   - Launch silently (no command window)" -ForegroundColor Gray
Write-Host "   - Open your browser automatically" -ForegroundColor Gray
Write-Host "   - Use the custom icon you see" -ForegroundColor Gray
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Ask if user wants to launch now
$Launch = Read-Host "Would you like to launch YouTube Analyzer now? (y/n)"
if ($Launch -eq 'y' -or $Launch -eq 'Y') {
    Write-Host ""
    Write-Host "Launching YouTube Analyzer..." -ForegroundColor Green
    Start-Process -FilePath $PythonwPath -ArgumentList "`"$LauncherScript`"" -WorkingDirectory $ProjectDir
    Write-Host "App should open in your browser shortly..." -ForegroundColor Green
}

Write-Host ""
Write-Host "Setup complete! Enjoy YouTube Analyzer!" -ForegroundColor Cyan
Write-Host ""
pause

