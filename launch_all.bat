@echo off
REM Comprehensive Service Launcher Wrapper
REM Launches all services including .bat, Dash, and Streamlit apps

cd /d "%~dp0"

echo.
echo ============================================================
echo   Launching ALL Services
echo ============================================================
echo.

python launch_all_services.py

pause
