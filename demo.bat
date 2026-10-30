@echo off
REM AI Business OS - temporary public demo (Cloudflare Tunnel / trycloudflare.com).
REM Runs demo.ps1: backend + frontend + one tunnel each, prints the public URLs.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0demo.ps1"
