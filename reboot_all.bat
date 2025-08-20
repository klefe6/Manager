@echo off
REM ─── jump into the folder where this .bat lives ────────────────
cd /d "%~dp0"

REM ─── run the Python launcher (assumes python is on your PATH) ────
python "launch_all_services.py"

REM ─── pause so you can see any errors ────────────────────────────
pause
