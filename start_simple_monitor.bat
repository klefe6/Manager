cd /d "%~dp0"

@echo off
echo Starting Simple PM2 Monitor...
echo.
echo This will restart all services every hour.
echo Press Ctrl+C to stop the monitor.
echo.

REM Start the simple PM2 monitor
python pm2_monitor_simple.py

pause
