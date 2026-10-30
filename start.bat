@echo off
REM AI Business OS - double-click launcher.
REM Runs start.ps1 (backend + frontend, each in its own window).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
