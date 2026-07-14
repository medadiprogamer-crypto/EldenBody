@echo off
title EldenBody Controller - Install
echo ============================================
echo   EldenBody Controller - Installation
echo ============================================
echo.

cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

echo [1/3] Checking Python version...
python --version

echo.
echo [2/3] Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Verifying ViGEm and imports...
python -c "import vgamepad; import mediapipe; import cv2; import hid; print('All core modules OK')"

if errorlevel 1 (
    echo.
    echo WARNING: Some modules failed to import. Check errors above.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Installation complete!
echo.
echo   IMPORTANT:
echo   - ViGEmBus driver must be installed
echo   - Connect PS4 controller via USB for gyro
echo   - Run run.bat to start EldenBody
echo ============================================
echo.
pause
