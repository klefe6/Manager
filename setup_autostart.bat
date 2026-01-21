@echo off
echo Setting up PM2 Monitor to start automatically on Windows startup...
echo.

REM Get the current directory
set "SCRIPT_DIR=%~dp0"
set "PYTHON_PATH=C:\Python310\python.exe"
set "SCRIPT_PATH=%SCRIPT_DIR%pm2_monitor_simple.py"

echo Creating Windows Task Scheduler entry...
echo Script directory: %SCRIPT_DIR%
echo Python path: %PYTHON_PATH%
echo Script path: %SCRIPT_PATH%
echo.

REM Create a scheduled task that runs at startup
schtasks /create /tn "PM2 Monitor" /tr "\"%PYTHON_PATH%\" \"%SCRIPT_PATH%\"" /sc onstart /ru "SYSTEM" /f

if %errorlevel% equ 0 (
    echo.
    echo SUCCESS: PM2 Monitor will now start automatically when Windows boots up!
    echo.
    echo To manage this task:
    echo - View: Task Scheduler ^> Task Scheduler Library ^> PM2 Monitor
    echo - Delete: schtasks /delete /tn "PM2 Monitor" /f
    echo.
) else (
    echo.
    echo ERROR: Failed to create scheduled task. You may need to run as Administrator.
    echo.
    echo Manual setup:
    echo 1. Open Task Scheduler
    echo 2. Create Basic Task
    echo 3. Name: PM2 Monitor
    echo 4. Trigger: When the computer starts
    echo 5. Action: Start a program
    echo 6. Program: %PYTHON_PATH%
    echo 7. Arguments: "%SCRIPT_PATH%"
    echo 8. Start in: %SCRIPT_DIR%
    echo.
)

pause

