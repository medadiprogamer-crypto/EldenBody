@echo off
title EldenBody Controller
cd /d "%~dp0"

echo Starting EldenBody Controller...
echo Press Q to quit | R to recalibrate | D to toggle debug
echo.

python main.py %*

if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)
