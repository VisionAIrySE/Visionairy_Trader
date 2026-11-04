@echo off
cd /d "%~dp0"
python qualify_history.py
if errorlevel 1 pause
