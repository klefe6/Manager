@echo off
echo Starting PM2 Monitor...
echo.
echo This will restart all services every hour.
echo Press Ctrl+C to stop the monitor.
echo.

REM Install dependencies if needed
pip install -r requirements.txt

REM Start the PM2 monitor
python pm2_monitor.py

pause
