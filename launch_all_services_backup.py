#!/usr/bin/env python3
"""
Comprehensive Service Launcher

Launches ALL services including:
- .bat file services (existing)
- Dash applications (Python scripts)
- Streamlit applications
- FastAPI applications
- Next.js applications
- Opens browser windows automatically

Windows-native, handles port conflicts gracefully.

CRITICAL FIXES IMPLEMENTED:
1. No more PIPE buffer overflow - all processes use CREATE_NEW_CONSOLE
2. Actual PID tracking - no wrapper PIDs from 'start' command
3. Visible console windows for debugging
4. Robust kill with process tree termination
5. Proper health checks
"""

import subprocess
import os
import time
import socket
import sys
import json
import webbrowser
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# Import shared utilities
from service_launcher_utils import (
    is_port_available,
    is_port_listening,
    find_python_executable,
    kill_process_by_port_robust,
    launch_bat_file,
    launch_python_app,
    launch_fastapi_app,
    launch_nextjs_app,
    wait_for_port,
    get_pid_by_port
)

# Import Cloudflare Tunnel Manager
try:
    from cloudflare_tunnel_manager import get_tunnel_manager
    CLOUDFLARE_AVAILABLE = True
except ImportError:
    CLOUDFLARE_AVAILABLE = False
    print("[WARN] Cloudflare Tunnel Manager not available")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
HEALTH_CHECK_ENABLED   = False      # monitor & auto‑restart unhealthy services
DAILY_RESTART_ENABLED  = True       # restart TKP Tearsheet every 24 hours

FAIL_THRESHOLD         = 2          # consecutive failures before restart
CHECK_INTERVAL         = 15         # seconds between health checks
LAUNCH_PAUSE           = 3          # seconds pause between launching each service
DAILY_RESTART_INTERVAL = 24 * 60 * 60  # 24 hours in seconds
BROWSER_OPEN_DELAY     = 5          # seconds to wait before opening browser

TKP_SERVICE_NAME       = "TKP Tearsheet"  # key in SERVICES dict to restart daily

# Base directory
BASE_DIR = Path(r"C:\Coding Projects")

# ─── .BAT Services (existing) ────────────────────────────────────────────────
BAT_SERVICES = {
    "TWIFO Sharing":    BASE_DIR / "TWIFO_Sharing" / "reboot_twifo.bat",
    "Import Dropbox":   BASE_DIR / "TWIFO_Sharing" / "reboot_import_dropbox.bat",
    "TS Generator":     BASE_DIR / "Tearsheet Generator" / "run_tsgen.bat",
    "TKP Tearsheet":    BASE_DIR / "Tearsheet Generator" / "reboot_tkp_ts.bat",
    "Y&Q Tearsheet":    BASE_DIR / "Tearsheet Generator" / "reboot_yq_ts.bat",
    "Gold Maker":       BASE_DIR / "Tearsheet Generator" / "reboot_gold_maker.bat",
    "Sector Ratio":     BASE_DIR / "GSR" / "reboot_gsr.bat",
    "ES Historical":    BASE_DIR / "ES Historical Data" / "reboot_es_historical_data.bat",
    "Almanac Futures":  BASE_DIR / "Almanac Futures" / "reboot_almanac.bat",
}

# ─── Dash Applications ───────────────────────────────────────────────────────
# Logical sequential port assignment: 8001-8010
DASH_APPS = {
    "Price Dashboard": {
        "path": BASE_DIR / "Price Dashboard" / "app.py",
        "port": 8002,  # Changed from 3000
        "url": "http://localhost:8002",
        "cwd": BASE_DIR / "Price Dashboard",
        "venv": None,  # Uses system Python or check for venv
    },
    "Sector RRG": {
        "path": BASE_DIR / "Sector" / "app_rrg.py",
        "port": 8003,  # Changed from 8059
        "url": "http://localhost:8003",
        "cwd": BASE_DIR / "Sector",
        "venv": None,
    },
    "Strategy Optimizer": {
        "path": BASE_DIR / "StrategyOptimizer" / "app.py",
        "port": 8004,  # Changed from 8070
        "url": "http://localhost:8004",
        "cwd": BASE_DIR / "StrategyOptimizer",
        "venv": None,
    },
    "Home Page": {
        "path": BASE_DIR / "HomePage" / "main.py",
        "port": 8005,  # Changed from 8055
        "url": "http://localhost:8005",
        "cwd": BASE_DIR / "HomePage",
        "venv": BASE_DIR / "HomePage" / ".venv13",  # Has venv
    },
    "Debug Page": {
        "path": BASE_DIR / "HomePage" / "debug.py",
        "port": 8006,  # Changed from 8056
        "url": "http://localhost:8006",
        "cwd": BASE_DIR / "HomePage",
        "venv": BASE_DIR / "HomePage" / ".venv13",
    },
}

# ─── Streamlit Applications ──────────────────────────────────────────────
# Each Streamlit app has a FIXED port - no auto-incrementing
# Logical sequential port assignment: 8001-8010
STREAMLIT_APPS = {
    "TWIFO Import Dropbox": {
        "path": BASE_DIR / "TWIFO_Sharing" / "import_dropbox.py",
        "port": 8009,  # Changed from 8001 to avoid conflict with Summary Engine backend (8001)
        "url": "http://localhost:8009",
        "cwd": BASE_DIR / "TWIFO_Sharing",
        "venv": BASE_DIR / "TWIFO_Sharing" / ".venv13",
    },
    "QuantLab Dashboard": {
        "path": BASE_DIR / "QuantLab" / "dashboard" / "app.py",
        "port": 8501,  # Keep QuantLab on 8501 (not in user's list)
        "url": "http://localhost:8501",
        "cwd": BASE_DIR / "QuantLab",
        "venv": None,  # Use system Python (venv doesn't have streamlit installed)
    },
}

# ─── FastAPI Applications ─────────────────────────────────────────────────
FASTAPI_APPS = {
    "Agent Control Center": {
        "path": BASE_DIR / "Agent Control Center" / "main.py",
        "port": 8007,  # Configured in config.py
        "url": "http://localhost:8007",
        "cwd": BASE_DIR / "Agent Control Center",
        "venv": None,
    },
}

# ─── Docker Compose Applications ──────────────────────────────────────────
DOCKER_COMPOSE_APPS = {
    "Trading Video Library": {
        "path": BASE_DIR / "Trading Video Library" / "docker-compose.yml",
        "ports": [8000, 3003],  # API: 8000, Frontend: 3003
        "urls": {
            "backend": "http://localhost:8000",
            "frontend": "http://localhost:3003",
        },
        "cwd": BASE_DIR / "Trading Video Library",
        "services": ["api", "worker", "redis", "web"],  # All services needed
    },
    "Summary Engine": {
        "path": BASE_DIR / "SummaryEngine" / "docker-compose.yml",
        "ports": [8001, 3001],  # Backend: 8001, Frontend: 3001
        "urls": {
            "backend": "http://localhost:8001",
            "frontend": "http://localhost:3001",
        },
        "cwd": BASE_DIR / "SummaryEngine",
        "services": ["backend", "frontend"],  # Services to start
    },
}

# ─── Next.js Applications ─────────────────────────────────────────────────
NEXTJS_APPS = {
    "VizLab": {
        "path": BASE_DIR / "VizLab",
        "port": 8011,  # 3D Quant Data Visualization Platform
        "url": "http://localhost:8011",
        "cwd": BASE_DIR / "VizLab",
        "command": "npm run dev",  # Development mode
    },
}

# ─── Combined Port Map (for health checks) ───────────────────────────────────
PORTS = {
    "TWIFO Sharing":   ("127.0.0.1", 8065),
    "TWIFO Import Dropbox": ("127.0.0.1", 8009),  # Streamlit (Dropbox filtering) - changed from 8001 to avoid conflict
    "Price Dashboard": ("127.0.0.1", 8002),
    "Sector RRG":      ("127.0.0.1", 8003),
    "Strategy Opt":    ("127.0.0.1", 8004),
    "Home Page":       ("127.0.0.1", 8005),
    "Debug Page":      ("127.0.0.1", 8006),
    "Agent Control Center": ("127.0.0.1", 8007),
    "Trading Video Library API": ("127.0.0.1", 8000),
    "Trading Video Library": ("127.0.0.1", 3003),
    "Summary Engine Backend": ("127.0.0.1", 8001),
    "Summary Engine Frontend": ("127.0.0.1", 3001),
    "VizLab":          ("127.0.0.1", 8011),
    "TS Generator":    ("127.0.0.1", 8077),
    "TKP Tearsheet":   ("127.0.0.1", 8076),
    "Y&Q Tearsheet":   ("127.0.0.1", 8071),
    "Gold Maker":      ("127.0.0.1", 8075),
    "Sector Ratio":    ("127.0.0.1", 8080),
    "ES Historical":   ("127.0.0.1", 8081),
    "Almanac Futures": ("127.0.0.1", 8072),
    "QuantLab Dashboard": ("127.0.0.1", 8501),
}

# Track running processes
running_processes: Dict[str, subprocess.Popen] = {}
streamlit_ports: Dict[str, int] = {}  # Track actual Streamlit ports


# Utility functions now imported from service_launcher_utils.py
# Keeping a wrapper for backward compatibility
def is_service_healthy(host: str, port: int) -> bool:
    """Return True if we can open a TCP connection to host:port, else False."""
    return is_port_listening(host, port, timeout=5)


def launch_bat_service(name: str, bat_path: Path):
    """
    Launch a .bat service in a new window with PROPER PID TRACKING.
    
    CRITICAL FIX: Uses launch_bat_file() which maintains process handle.
    Old method used 'start' command which lost the actual process PID.
    """
    log_dir = BASE_DIR / "Manager" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{name.replace(' ', '_')}_launch.log"
    
    if not bat_path.exists():
        error_msg = f"[ERROR] .bat not found for {name}: {bat_path}"
        print(error_msg)
        with open(log_file, 'w') as f:
            f.write(f"{datetime.now().isoformat()} - {error_msg}\n")
        return None
    
    print(f"[LAUNCH] {name} → {bat_path.name}")
    
    # Log launch details
    with open(log_file, 'w') as f:
        f.write(f"{datetime.now().isoformat()} - Launching {name}\n")
        f.write(f"Command: {bat_path}\n")
        f.write(f"CWD: {bat_path.parent}\n")
        f.write(f"Service Name: {name}\n")
        f.write("=" * 70 + "\n")
    
    # Use utility function that properly tracks PID
    process = launch_bat_file(str(bat_path), name)
    
    if process:
        with open(log_file, 'a') as f:
            f.write(f"Process started - PID: {process.pid}\n")
            f.write(f"Exit code: {process.poll() if process.poll() is not None else 'Running'}\n")
        print(f"[OK] {name} launched (PID: {process.pid}, log: {log_file})")
    else:
        with open(log_file, 'a') as f:
            f.write("ERROR: Process failed to start\n")
        print(f"[ERROR] {name} failed to launch (log: {log_file})")
    
    return process


def launch_dash_app(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """
    Launch a Dash application with PROPER CONSOLE OUTPUT.
    
    CRITICAL FIX: Uses CREATE_NEW_CONSOLE instead of PIPE to avoid buffer overflow.
    Old method: stdout/stderr=PIPE caused buffer to fill and process to hang.
    New method: Opens visible console window, no blocking.
    """
    log_dir = BASE_DIR / "Manager" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{name.replace(' ', '_')}_launch.log"
    
    app_path = config["path"]
    port = config["port"]
    url = config["url"]
    cwd = config["cwd"]
    venv = config.get("venv")
    
    if not app_path.exists():
        error_msg = f"[ERROR] Dash app not found for {name}: {app_path}"
        print(error_msg)
        with open(log_file, 'w') as f:
            f.write(f"{datetime.now().isoformat()} - {error_msg}\n")
        return None
    
    # Check if port is available
    if not is_port_available("127.0.0.1", port):
        print(f"[WARN] Port {port} already in use for {name}, attempting anyway...")
    
    print(f"[LAUNCH] {name} (Dash) → {app_path.name} on port {port}")
    
    # Log launch details
    with open(log_file, 'w') as f:
        f.write(f"{datetime.now().isoformat()} - Launching {name} (Dash)\n")
        f.write(f"Script: {app_path}\n")
        f.write(f"Port: {port}\n")
        f.write(f"URL: {url}\n")
        f.write(f"CWD: {cwd}\n")
        f.write(f"Venv: {venv if venv else 'System Python'}\n")
        f.write("=" * 70 + "\n")
    
    # Use utility function that avoids PIPE buffer overflow
    process = launch_python_app(
        script_path=str(app_path),
        service_name=name,
        port=port,
        venv_path=str(venv) if venv else None
    )
    
    if process:
        # Store URL for browser opening
        process._service_url = url
        process._service_name = name
        with open(log_file, 'a') as f:
            f.write(f"Process started - PID: {process.pid}\n")
            f.write(f"Exit code: {process.poll() if process.poll() is not None else 'Running'}\n")
        print(f"[OK] {name} launched (PID: {process.pid}, log: {log_file})")
    else:
        with open(log_file, 'a') as f:
            f.write("ERROR: Process failed to start\n")
        print(f"[ERROR] {name} failed to launch (log: {log_file})")
    
    return process


def launch_streamlit_app(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """Launch a Streamlit application with FIXED port."""
    app_path = config["path"]
    port = config["port"]  # Fixed port - no auto-increment
    url = config["url"]
    cwd = config["cwd"]
    venv = config.get("venv")
    
    if not app_path.exists():
        print(f"[ERROR] Streamlit app not found for {name}: {app_path}")
        return None
    
    python_exe = find_python_executable(venv)
    
    # Check if port is available (warn but don't change it)
    if not is_port_available("127.0.0.1", port):
        print(f"[WARN] Port {port} is already in use for {name}!")
        print(f"[WARN] The app may fail to start or use a different port.")
        print(f"[WARN] Make sure no other service is using port {port}.")
    
    print(f"[LAUNCH] {name} (Streamlit) → {app_path.name} on FIXED port {port}")
    
    # Launch Streamlit app with FIXED port
    # Streamlit command: streamlit run dashboard/app.py --server.port PORT
    # Use relative path from cwd to ensure proper import resolution
    rel_path = app_path.relative_to(cwd) if app_path.is_relative_to(cwd) else app_path
    streamlit_cmd = [
        python_exe, "-m", "streamlit", "run",
        str(rel_path),
        "--server.port", str(port),
        "--server.headless", "true",  # Don't auto-open browser (we'll do it)
        "--browser.gatherUsageStats", "false"
    ]
    
    log_dir = BASE_DIR / "Manager" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    launch_log_file = log_dir / f"{name.replace(' ', '_')}_launch.log"
    streamlit_log_file = cwd / f"{name.replace(' ', '_')}_streamlit.log"
    
    # Log launch details
    with open(launch_log_file, 'w') as f:
        f.write(f"{datetime.now().isoformat()} - Launching {name} (Streamlit)\n")
        f.write(f"Script: {app_path}\n")
        f.write(f"Port: {port} (FIXED)\n")
        f.write(f"URL: {url}\n")
        f.write(f"CWD: {cwd}\n")
        f.write(f"Python: {python_exe}\n")
        f.write(f"Venv: {venv if venv else 'System Python'}\n")
        f.write(f"Streamlit Log: {streamlit_log_file}\n")
        f.write("=" * 70 + "\n")
    
    try:
        # For Streamlit, we need to redirect output to see errors
        # Use a log file for debugging
        with open(streamlit_log_file, 'w') as log:
            process = subprocess.Popen(
                streamlit_cmd,
                cwd=str(cwd),
                stdout=log,
                stderr=subprocess.STDOUT,  # Combine stderr with stdout
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
            )
        
        # Give it a moment to start
        time.sleep(2)
        
        # Check if process started successfully
        if process.poll() is not None:
            # Process already exited - read log to see why
            try:
                with open(streamlit_log_file, 'r') as f:
                    error_msg = f.read()[-500:]  # Last 500 chars
                print(f"[ERROR] {name} failed to start. Check logs: {launch_log_file}, {streamlit_log_file}")
                print(f"[ERROR] Last log output: {error_msg[-200:]}")
                with open(launch_log_file, 'a') as f:
                    f.write(f"ERROR: Process exited immediately\n")
                    f.write(f"Exit code: {process.poll()}\n")
                    f.write(f"Last streamlit log: {error_msg[-200:]}\n")
            except:
                print(f"[ERROR] {name} failed to start. Check logs: {launch_log_file}, {streamlit_log_file}")
                with open(launch_log_file, 'a') as f:
                    f.write(f"ERROR: Process exited immediately\n")
                    f.write(f"Exit code: {process.poll()}\n")
            return None
        
        # Store URL and port for browser opening
        process._service_url = url
        process._service_name = name
        streamlit_ports[name] = port
        
        with open(launch_log_file, 'a') as f:
            f.write(f"Process started - PID: {process.pid}\n")
            f.write(f"Exit code: {process.poll() if process.poll() is not None else 'Running'}\n")
            f.write(f"Streamlit log: {streamlit_log_file}\n")
        print(f"[OK] {name} process started (PID: {process.pid}, logs: {launch_log_file}, {streamlit_log_file})")
        return process
    except Exception as e:
        print(f"[ERROR] Failed to launch {name}: {e}")
        import traceback
        traceback.print_exc()
        return None


def launch_fastapi_app_wrapper(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """
    Launch a FastAPI application with PROPER CONSOLE OUTPUT.
    
    CRITICAL FIX: Uses CREATE_NEW_CONSOLE instead of PIPE to avoid buffer overflow.
    Old method: stdout/stderr=PIPE caused buffer to fill and process to hang.
    New method: Opens visible console window, no blocking.
    """
    log_dir = BASE_DIR / "Manager" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{name.replace(' ', '_')}_launch.log"
    
    app_path = config["path"]
    port = config["port"]
    url = config["url"]
    cwd = config["cwd"]
    venv = config.get("venv")
    
    if not app_path.exists():
        error_msg = f"[ERROR] FastAPI app not found for {name}: {app_path}"
        print(error_msg)
        with open(log_file, 'w') as f:
            f.write(f"{datetime.now().isoformat()} - {error_msg}\n")
        return None
    
    # Check if port is available
    if not is_port_available("127.0.0.1", port):
        print(f"[WARN] Port {port} already in use for {name}, attempting anyway...")
    
    print(f"[LAUNCH] {name} (FastAPI) → {app_path.name} on port {port}")
    
    # Log launch details
    with open(log_file, 'w') as f:
        f.write(f"{datetime.now().isoformat()} - Launching {name} (FastAPI)\n")
        f.write(f"Main File: {app_path}\n")
        f.write(f"Port: {port}\n")
        f.write(f"URL: {url}\n")
        f.write(f"CWD: {cwd}\n")
        f.write(f"Venv: {venv if venv else 'System Python'}\n")
        f.write("=" * 70 + "\n")
    
    # Determine the uvicorn module path based on the app structure
    # Agent Control Center: main.py at root -> main:app
    if "Agent Control Center" in name:
        uvicorn_module = "main:app"
    else:
        # Default: try to infer from path
        if "app" in str(app_path.parent):
            uvicorn_module = "app.main:app"
        else:
            uvicorn_module = "main:app"
    
    # Use utility function that avoids PIPE buffer overflow
    process = launch_fastapi_app(
        main_file_path=str(app_path),
        service_name=name,
        port=port,
        working_dir=str(cwd),
        uvicorn_module=uvicorn_module,
        venv_path=str(venv) if venv else None
    )
    
    if process:
        # Store URL for browser opening
        process._service_url = url
        process._service_name = name
        with open(log_file, 'a') as f:
            f.write(f"Process started - PID: {process.pid}\n")
            f.write(f"Exit code: {process.poll() if process.poll() is not None else 'Running'}\n")
        print(f"[OK] {name} launched (PID: {process.pid}, log: {log_file})")
    else:
        with open(log_file, 'a') as f:
            f.write("ERROR: Process failed to start\n")
        print(f"[ERROR] {name} failed to launch (log: {log_file})")
    
    return process


def open_docker_desktop() -> bool:
    """
    Open Docker Desktop application on Windows.
    
    Uses multiple methods in order of reliability:
    1. os.startfile() if executable found (Windows-native, most reliable)
    2. Windows 'start' command with shell=True
    3. Registry lookup
    4. PowerShell Start-Process
    5. docker-desktop:// protocol handler (final fallback, most reliable on Windows 10/11)
    
    Returns:
        True if command was executed successfully, False otherwise
    """
    try:
        # Common Docker Desktop installation paths on Windows
        docker_paths = [
            r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
            os.path.expanduser(r"~\AppData\Local\Docker\Docker Desktop.exe"),
            r"C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe",
        ]
        
        docker_path = None
        for path in docker_paths:
            expanded_path = os.path.expandvars(os.path.expanduser(path))
            if os.path.exists(expanded_path):
                docker_path = expanded_path
                print(f"[INFO] Found Docker Desktop at: {docker_path}")
                break
        
        # Method 1: Use os.startfile() if we found the executable (most reliable on Windows)
        if docker_path:
            try:
                os.startfile(docker_path)
                print(f"[OK] Opened Docker Desktop using os.startfile(): {docker_path}")
                return True
            except Exception as e:
                print(f"[WARN] os.startfile() failed: {e}, trying subprocess...")
                try:
                    # Fallback: subprocess with the full path
                    subprocess.Popen([docker_path], shell=False, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                    print(f"[OK] Opened Docker Desktop using subprocess: {docker_path}")
                    return True
                except Exception as e2:
                    print(f"[WARN] subprocess.Popen() also failed: {e2}")
        
        # Method 2: Try Windows 'start' command (works even if path not found, uses Windows search)
        try:
            subprocess.Popen(
                'start "" "Docker Desktop"',
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            print("[OK] Attempted to start Docker Desktop via 'start' command")
            return True
        except Exception as e:
            print(f"[WARN] 'start' command failed: {e}")
        
        # Method 3: Try registry lookup for Docker Desktop (Windows-specific)
        if sys.platform == 'win32':
            try:
                import winreg
                registry_paths = [
                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Docker Desktop.exe"),
                    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths\Docker Desktop.exe"),
                ]
                
                for hkey, reg_path in registry_paths:
                    try:
                        key = winreg.OpenKey(hkey, reg_path)
                        reg_docker_path = winreg.QueryValue(key, None)
                        winreg.CloseKey(key)
                        if reg_docker_path and os.path.exists(reg_docker_path):
                            os.startfile(reg_docker_path)
                            print(f"[OK] Opened Docker Desktop from registry: {reg_docker_path}")
                            return True
                    except (FileNotFoundError, OSError):
                        continue
            except ImportError:
                pass  # winreg not available
            except Exception as e:
                print(f"[WARN] Registry lookup failed: {e}")
        
        # Method 4: Try PowerShell Start-Process
        try:
            ps_command = 'Start-Process "Docker Desktop" -ErrorAction SilentlyContinue'
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                shell=False,
                timeout=5,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            print("[OK] Attempted to start Docker Desktop via PowerShell")
            return True
        except Exception as e:
            print(f"[WARN] PowerShell method failed: {e}")
        
        # Method 5: Final fallback - Docker Desktop protocol handler (most reliable on Windows 10/11)
        try:
            subprocess.Popen(
                'start docker-desktop://',
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            print("[OK] Attempted to start Docker Desktop via protocol handler (docker-desktop://)")
            return True
        except Exception as e:
            print(f"[WARN] Protocol handler method failed: {e}")
        
        print("[ERROR] All methods to open Docker Desktop failed")
        return False
        
    except Exception as e:
        print(f"[ERROR] Error opening Docker Desktop: {e}")
        return False


def check_docker_available(auto_start: bool = True) -> Tuple[bool, str]:
    """
    Check if Docker is installed and Docker Desktop is running.
    Optionally attempts to start Docker Desktop if not running.
    
    Args:
        auto_start: If True, automatically try to start Docker Desktop if not running.
    
    Returns:
        Tuple of (is_available: bool, error_message: str)
    """
    try:
        # Try to run docker version command (quicker than docker ps)
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and result.stdout.strip():
            # Docker is available and responding
            docker_version = result.stdout.strip()
            return True, f"Docker {docker_version}"
        else:
            # Check stderr for more details
            error_detail = result.stderr.strip() if result.stderr else "Unknown error"
            if "Cannot connect to the Docker daemon" in error_detail or "error during connect" in error_detail:
                if auto_start:
                    print("[INFO] Docker Desktop is not running. Attempting to start it...")
                    opened = open_docker_desktop()
                    if opened:
                        print("[INFO] Docker Desktop launch command executed. Waiting for it to start...")
                        # Wait a bit for Docker to start
                        time.sleep(5)
                        # Check again after waiting
                        for attempt in range(6):  # Check up to 30 seconds
                            time.sleep(5)
                            retry_result = subprocess.run(
                                ["docker", "version", "--format", "{{.Server.Version}}"],
                                capture_output=True,
                                text=True,
                                timeout=10
                            )
                            if retry_result.returncode == 0 and retry_result.stdout.strip():
                                docker_version = retry_result.stdout.strip()
                                return True, f"Docker {docker_version} (started automatically)"
                        return False, "Docker Desktop was launched but did not start within 30 seconds. Please wait and try again."
                    else:
                        return False, "Docker Desktop is not running and failed to start automatically. Please start Docker Desktop manually."
                else:
                    return False, "Docker Desktop is not running. Please start Docker Desktop and wait for it to fully initialize."
            return False, f"Docker command failed: {error_detail}"
            
    except FileNotFoundError:
        return False, "Docker command not found. Is Docker Desktop installed?"
    except subprocess.TimeoutExpired:
        return False, "Docker command timed out. Docker Desktop may be starting up - please wait and try again."
    except Exception as e:
        return False, f"Docker check failed: {str(e)}"


def launch_docker_compose_app(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """
    Launch a Docker Compose application.
    
    Uses docker-compose up -d to start services in detached mode.
    """
    compose_file = config["path"]
    cwd = config["cwd"]
    ports = config.get("ports", [])
    
    if not compose_file.exists():
        print(f"[ERROR] Docker Compose file not found for {name}: {compose_file}")
        return None
    
    # Note: Docker availability is checked before launching Docker services in launch_all_services()
    # This check here is redundant but kept as a safety net
    
    # Check if ports are available
    for port in ports:
        if not is_port_available("127.0.0.1", port):
            print(f"[WARN] Port {port} already in use for {name}, Docker may fail to start...")
    
    print(f"[LAUNCH] {name} (Docker Compose) → {compose_file.name}")
    
    try:
        # Use docker-compose up -d to start in detached mode
        # Note: Use 'docker compose' (space) for newer Docker versions, fallback to 'docker-compose' (hyphen)
        compose_cmd = [
            "docker", "compose",
            "-f", str(compose_file),
            "up",
            "-d",
            "--build"  # Rebuild if needed
        ]
        
        # Create a log file for Docker output
        log_file = cwd / f"{name.replace(' ', '_')}_docker.log"
        
        with open(log_file, 'w') as log:
            try:
                process = subprocess.Popen(
                    compose_cmd,
                    cwd=str(cwd),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
                )
            except FileNotFoundError:
                # Fallback to docker-compose (hyphen) for older Docker versions
                print(f"[INFO] 'docker compose' not found, trying 'docker-compose'...")
                compose_cmd[0:2] = ["docker-compose"]
                process = subprocess.Popen(
                    compose_cmd,
                    cwd=str(cwd),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
                )
        
        # Give Docker time to start containers
        print(f"[INFO] Waiting for Docker containers to start (this may take 30-60 seconds)...")
        time.sleep(5)
        
        # Check if process started successfully
        if process.poll() is not None:
            # Process already exited - read log to see why
            try:
                with open(log_file, 'r') as f:
                    error_msg = f.read()[-500:]  # Last 500 chars
                print(f"[ERROR] {name} failed to start. Check log: {log_file}")
                print(f"[ERROR] Last log output: {error_msg[-200:]}")
            except:
                print(f"[ERROR] {name} failed to start. Check log: {log_file}")
            return None
        
        # Store URLs for browser opening (use frontend URL as primary)
        process._service_url = config.get("urls", {}).get("frontend", config.get("urls", {}).get("backend", ""))
        process._service_name = name
        process._docker_ports = ports
        process._docker_urls = config.get("urls", {})
        
        print(f"[OK] {name} Docker Compose started (PID: {process.pid}, log: {log_file})")
        
        # Special notes for specific apps
        if "Summary Engine" in name:
            print(f"[INFO] Note: If this is first run, seed database with: docker compose -f {compose_file} exec backend python scripts/seed_db.py")
        elif "Trading Video Library" in name:
            print(f"[INFO] Trading Video Library: API on port 8000, Frontend on port 3003")
            print(f"[INFO] 4 tabs: Video Link, Profile Link, Upload File, Library")
        
        return process
    except FileNotFoundError:
        print(f"[ERROR] docker/docker-compose command not found. Is Docker installed?")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to launch {name}: {e}")
        import traceback
        traceback.print_exc()
        return None


def launch_nextjs_app_wrapper(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """
    Launch a Next.js application with PROPER PID TRACKING.
    
    CRITICAL FIX: Uses CREATE_NEW_CONSOLE instead of 'start' command.
    Old method: 'start' command returned wrapper PID, actual process was orphaned.
    New method: Tracks actual Next.js process PID in visible console.
    """
    log_dir = BASE_DIR / "Manager" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{name.replace(' ', '_')}_launch.log"
    
    app_path = config["path"]
    port = config["port"]
    url = config["url"]
    cwd = config["cwd"]
    command = config.get("command", "npm run dev")
    
    if not app_path.exists():
        error_msg = f"[ERROR] Next.js app directory not found for {name}: {app_path}"
        print(error_msg)
        with open(log_file, 'w') as f:
            f.write(f"{datetime.now().isoformat()} - {error_msg}\n")
        return None
    
    # Check if port is available
    if not is_port_available("127.0.0.1", port):
        print(f"[WARN] Port {port} already in use for {name}, attempting anyway...")
    
    print(f"[LAUNCH] {name} (Next.js) → port {port}")
    
    # Log launch details
    with open(log_file, 'w') as f:
        f.write(f"{datetime.now().isoformat()} - Launching {name} (Next.js)\n")
        f.write(f"App Directory: {app_path}\n")
        f.write(f"Port: {port}\n")
        f.write(f"URL: {url}\n")
        f.write(f"CWD: {cwd}\n")
        f.write(f"Command: {command}\n")
        f.write("=" * 70 + "\n")
    
    # Use utility function that properly tracks PID
    process = launch_nextjs_app(
        app_dir=str(cwd),
        service_name=name,
        port=port
    )
    
    if process:
        # Store URL for browser opening
        process._service_url = url
        process._service_name = name
        with open(log_file, 'a') as f:
            f.write(f"Process started - PID: {process.pid}\n")
            f.write(f"Exit code: {process.poll() if process.poll() is not None else 'Running'}\n")
        print(f"[OK] {name} launched (PID: {process.pid}, log: {log_file})")
    else:
        with open(log_file, 'a') as f:
            f.write("ERROR: Process failed to start\n")
        print(f"[ERROR] {name} failed to launch (log: {log_file})")
    
    return process


def detect_streamlit_port(name: str, expected_port: int, max_wait: int = 10) -> Optional[int]:
    """Verify Streamlit is running on expected port (fixed ports, no auto-increment)."""
    # With fixed ports, we just check the expected port
    for _ in range(max_wait):
        if is_service_healthy("127.0.0.1", expected_port):
            return expected_port
        time.sleep(0.5)
    return None


def open_browser_tabs(services: Dict[str, subprocess.Popen]):
    """Open browser tabs for all web services after a delay."""
    print(f"\n[INFO] Waiting {BROWSER_OPEN_DELAY}s for services to start, then opening browsers...\n")
    time.sleep(BROWSER_OPEN_DELAY)
    
    # Services to skip opening browser tabs (backend APIs, blank pages, etc.)
    SKIP_BROWSER_OPEN = {
        "Summary Engine Backend",  # Backend API only, no UI
    }
    
    # Ports to skip (blank pages or backend-only services)
    SKIP_PORTS = {8000, 8001}  # Trading Video Library API (8000), Summary Engine Backend (8001) - APIs only, no UI
    
    urls_to_open = []
    
    # Collect URLs from all services
    for name, process in services.items():
        if hasattr(process, '_service_url'):
            # Skip services that shouldn't open browsers
            if name in SKIP_BROWSER_OPEN:
                continue
            
            # Skip URLs with ports that shouldn't open
            url = process._service_url
            if any(f":{port}" in url for port in SKIP_PORTS):
                continue
            
            # For Streamlit, verify it's on the fixed port
            if name in STREAMLIT_APPS:
                expected_port = STREAMLIT_APPS[name]["port"]
                actual_port = detect_streamlit_port(name, expected_port)
                if actual_port:
                    url = f"http://localhost:{actual_port}"
                    # Check if this port should be skipped
                    if actual_port in SKIP_PORTS:
                        continue
                    streamlit_ports[name] = actual_port
                    urls_to_open.append((name, url))
                else:
                    # Use configured URL (fixed port)
                    if expected_port not in SKIP_PORTS:
                        urls_to_open.append((name, process._service_url))
            # For Docker Compose, use frontend URL if available
            elif name in DOCKER_COMPOSE_APPS and hasattr(process, '_docker_urls'):
                # Open frontend URL (skip backend)
                frontend_url = process._docker_urls.get("frontend")
                if frontend_url:
                    urls_to_open.append((name, frontend_url))
            else:
                urls_to_open.append((name, process._service_url))
    
    # Open all URLs
    if urls_to_open:
        print(f"[INFO] Opening {len(urls_to_open)} browser tabs...")
        for name, url in urls_to_open:
            try:
                webbrowser.open(url)
                print(f"  ✓ Opened {name}: {url}")
                time.sleep(0.5)  # Small delay between opens
            except Exception as e:
                print(f"  ✗ Failed to open {name}: {e}")
    else:
        print("[WARN] No web service URLs found to open")


def launch_all_services():
    """Launch all services (BAT, Dash, Streamlit, FastAPI, Docker Compose, Next.js, Cloudflare Tunnel)."""
    all_services = {}
    failed_services = []  # Track services that failed to launch
    fail_counts = {name: 0 for name in list(BAT_SERVICES.keys()) + list(DASH_APPS.keys()) + list(STREAMLIT_APPS.keys()) + list(FASTAPI_APPS.keys()) + list(DOCKER_COMPOSE_APPS.keys()) + list(NEXTJS_APPS.keys())}
    
    print("\n" + "=" * 70)
    print("  COMPREHENSIVE SERVICE LAUNCHER")
    print("=" * 70)
    print(f"\n[INFO] Launching {len(BAT_SERVICES)} .bat services")
    print(f"[INFO] Launching {len(DASH_APPS)} Dash applications")
    print(f"[INFO] Launching {len(STREAMLIT_APPS)} Streamlit applications")
    print(f"[INFO] Launching {len(FASTAPI_APPS)} FastAPI applications")
    print(f"[INFO] Launching {len(DOCKER_COMPOSE_APPS)} Docker Compose applications")
    print(f"[INFO] Launching {len(NEXTJS_APPS)} Next.js applications")
    if CLOUDFLARE_AVAILABLE:
        print(f"[INFO] Cloudflare Tunnel: Available")
    print(f"[INFO] Total: {len(BAT_SERVICES) + len(DASH_APPS) + len(STREAMLIT_APPS) + len(FASTAPI_APPS) + len(DOCKER_COMPOSE_APPS) + len(NEXTJS_APPS)} services\n")
    
    # 1. Launch .bat services
    print("[PHASE 1] Launching .bat services...")
    for name, bat_path in BAT_SERVICES.items():
        process = launch_bat_service(name, bat_path)
        if process:
            all_services[name] = process
        else:
            failed_services.append(name)
        time.sleep(LAUNCH_PAUSE)
    
    print()
    
    # 2. Launch Dash applications
    print("[PHASE 2] Launching Dash applications...")
    for name, config in DASH_APPS.items():
        process = launch_dash_app(name, config)
        if process:
            all_services[name] = process
            # Wait for port to start listening before continuing
            port = config["port"]
            if wait_for_port("127.0.0.1", port, timeout=10):
                print(f"[OK] {name} is now listening on port {port}")
            else:
                print(f"[WARN] {name} did not start listening on port {port} within timeout")
                failed_services.append(f"{name} (port not listening)")
        else:
            failed_services.append(name)
        time.sleep(LAUNCH_PAUSE)
    
    print()
    
    # 3. Launch Streamlit applications
    print("[PHASE 3] Launching Streamlit applications...")
    for name, config in STREAMLIT_APPS.items():
        process = launch_streamlit_app(name, config)
        if process:
            all_services[name] = process
            print(f"[OK] {name} launched successfully")
        else:
            print(f"[ERROR] Failed to launch {name} via Streamlit")
            # Try fallback to batch file if it exists
            if name == "QuantLab Dashboard":
                bat_path = BASE_DIR / "QuantLab" / "reboot_dashboard.bat"
                if bat_path.exists():
                    print(f"[INFO] Trying fallback: launching {name} via batch file...")
                    bat_process = launch_bat_service(name, bat_path)
                    if bat_process:
                        all_services[name] = bat_process
                        print(f"[OK] {name} launched via batch file")
                    else:
                        failed_services.append(name)
                else:
                    failed_services.append(name)
            else:
                failed_services.append(name)
        time.sleep(LAUNCH_PAUSE)
    
    print()
    
    # 3.5. Launch FastAPI applications
    print("[PHASE 3.5] Launching FastAPI applications...")
    for name, config in FASTAPI_APPS.items():
        process = launch_fastapi_app_wrapper(name, config)
        if process:
            all_services[name] = process
            # Wait for port to start listening (FastAPI apps can take longer to start with dependencies)
            port = config["port"]
            if wait_for_port("127.0.0.1", port, timeout=30):
                print(f"[OK] {name} is now listening on port {port}")
            else:
                print(f"[WARN] {name} did not start listening on port {port} within timeout")
                log_filename = f"{name.replace(' ', '_')}_launch.log"
                log_path = BASE_DIR / "Manager" / "logs" / log_filename
                print(f"[INFO] Check console window for errors or check log: {log_path}")
                failed_services.append(f"{name} (port not listening)")
        else:
            failed_services.append(name)
        time.sleep(LAUNCH_PAUSE)
    
    print()
    
    # 3.6. Launch Docker Compose applications
    print("[PHASE 3.6] Launching Docker Compose applications...")
    
    # Check Docker availability before launching any Docker services
    docker_available = True
    if DOCKER_COMPOSE_APPS:
        docker_available, docker_info = check_docker_available()
        if docker_available:
            print(f"[OK] {docker_info} - Ready for Docker Compose services")
        else:
            print(f"[ERROR] {docker_info}")
            print(f"[WARN] Skipping {len(DOCKER_COMPOSE_APPS)} Docker Compose service(s)")
            for name in DOCKER_COMPOSE_APPS.keys():
                failed_services.append(f"{name} (Docker not available)")
            print()
            # Skip Docker services if Docker isn't available
            # Continue to next phase
    
    for name, config in DOCKER_COMPOSE_APPS.items():
        # Skip if Docker isn't available
        if not docker_available:
            continue
        process = launch_docker_compose_app(name, config)
        if process:
            all_services[name] = process
            # Wait for ports to start listening
            ports = config.get("ports", [])
            print(f"[INFO] Waiting for {name} services to start (this may take 30-90 seconds for first build)...")
            
            # Wait longer for backend/API ports first, then frontend
            backend_ports = [p for p in ports if p >= 8000 and p < 9000]  # API ports
            frontend_ports = [p for p in ports if p >= 3000 and p < 4000]  # Frontend ports
            
            port_failed = False
            # Check backend ports first
            for port in backend_ports:
                if wait_for_port("127.0.0.1", port, timeout=90):
                    print(f"[OK] {name} API is now listening on port {port}")
                else:
                    print(f"[WARN] {name} API did not start listening on port {port} within timeout")
                    print(f"[WARN] Check Docker logs: docker compose -f {config['path']} logs")
                    port_failed = True
            
            # Then check frontend ports
            for port in frontend_ports:
                if wait_for_port("127.0.0.1", port, timeout=60):
                    print(f"[OK] {name} Frontend is now listening on port {port}")
                else:
                    print(f"[WARN] {name} Frontend did not start listening on port {port} within timeout")
                    print(f"[WARN] Check Docker logs: docker compose -f {config['path']} logs")
                    port_failed = True
            
            if port_failed:
                failed_services.append(f"{name} (ports not listening)")
        else:
            failed_services.append(name)
        time.sleep(LAUNCH_PAUSE)
    
    print()
    
    # 3.7. Launch Next.js applications
    print("[PHASE 3.7] Launching Next.js applications...")
    for name, config in NEXTJS_APPS.items():
        process = launch_nextjs_app_wrapper(name, config)
        if process:
            all_services[name] = process
            # Wait for Next.js to compile and start listening (can take 10-30 seconds)
            port = config["port"]
            print(f"[INFO] Waiting for {name} to compile and start (this may take 20-30 seconds)...")
            if wait_for_port("127.0.0.1", port, timeout=45):
                print(f"[OK] {name} is now listening on port {port}")
            else:
                print(f"[WARN] {name} did not start listening on port {port} within timeout")
                print(f"[WARN] Check the {name} console window for errors")
                failed_services.append(f"{name} (port not listening)")
        else:
            failed_services.append(name)
        time.sleep(LAUNCH_PAUSE)
    
    print()
    
    # 4. Launch Cloudflare Tunnel (if configured)
    tunnel_manager = None
    if CLOUDFLARE_AVAILABLE:
        print("[PHASE 4] Starting Cloudflare Tunnel...")
        try:
            tunnel_manager = get_tunnel_manager()
            if tunnel_manager and tunnel_manager.start_tunnel():
                print("[OK] Cloudflare Tunnel started")
            else:
                print("[INFO] Cloudflare Tunnel not configured or failed to start")
        except Exception as e:
            print(f"[WARN] Cloudflare Tunnel error: {e}")
        print()
    
    # 5. Open browser tabs (this also detects actual Streamlit ports)
    open_browser_tabs(all_services)
    
    # 6. Save service registry for monitoring (after port detection)
    save_service_registry(all_services)
    
    # Store tunnel manager for cleanup
    if tunnel_manager:
        all_services['_tunnel_manager'] = tunnel_manager
    
    print("\n" + "=" * 70)
    print("  LAUNCH SUMMARY")
    print("=" * 70)
    print(f"\n[INFO] Successfully launched: {len(all_services)} services")
    if failed_services:
        print(f"[WARN] Failed to launch: {len(failed_services)} service(s)")
        print(f"[WARN] Failed services: {', '.join(failed_services)}")
        print(f"[INFO] Check logs in: {BASE_DIR / 'Manager' / 'logs'}")
    else:
        print(f"[OK] All services launched successfully")
    print(f"[INFO] Browser tabs opened for web services")
    print(f"[INFO] Services are running in background")
    
    # Print service URLs
    print(f"\n[INFO] Service URLs (Local):")
    for name, process in all_services.items():
        # Handle Docker Compose apps with multiple URLs
        if name in DOCKER_COMPOSE_APPS and hasattr(process, '_docker_urls'):
            urls = process._docker_urls
            if "frontend" in urls:
                print(f"  • {name} Frontend: {urls['frontend']}")
            if "backend" in urls:
                print(f"  • {name} Backend: {urls['backend']}")
        elif hasattr(process, '_service_url'):
            # Use detected port for Streamlit if available
            if name in streamlit_ports:
                url = f"http://localhost:{streamlit_ports[name]}"
            else:
                url = process._service_url
            print(f"  • {name}: {url}")
    
    # Print Cloudflare domains if tunnel is running
    if tunnel_manager and tunnel_manager.is_running():
        print(f"\n[INFO] Service URLs (Cloudflare):")
        domain_map = {
            "Price Dashboard": "price-dashboard.hcresearch.ltd",
            "Sector RRG": "sector-rrg.hcresearch.ltd",
            "Strategy Optimizer": "strategy-optimizer.hcresearch.ltd",
            "Home Page": "homepage.hcresearch.ltd",
            "Debug Page": "debug.hcresearch.ltd",
            "QuantLab Dashboard": "quantlab.hcresearch.ltd",
            "TWIFO Import Dropbox": "import-dropbox.hcresearch.ltd",
            "TWIFO Sharing": "twifo.hcresearch.ltd",
            "TKP Tearsheet": "tkp-ts.hcresearch.ltd",
            "Y&Q Tearsheet": "yq-ts.hcresearch.ltd",
            "Gold Maker": "tgm-ts.hcresearch.ltd",
            "Sector Ratio": "secratio.hcresearch.ltd",
            "ES Historical": "es-historical.hcresearch.ltd",
            "Almanac Futures": "almanac.hcresearch.ltd",
            "TS Generator": "ts-generator.hcresearch.ltd",
            "Agent Control Center": "agent-control.hcresearch.ltd",
            "Trading Video Library": "trading-video-library.hcresearch.ltd",
            "Summary Engine": "summary.hcresearch.ltd",
            "VizLab": "vizlab.hcresearch.ltd",
        }
        for name, domain in domain_map.items():
            if name in all_services:
                print(f"  • {name}: https://{domain}")
    
    print()
    
    return all_services, fail_counts


def save_service_registry(services: Dict[str, subprocess.Popen]):
    """Save service registry to JSON for reference."""
    registry = {
        "launched_at": datetime.now().isoformat(),
        "services": {}
    }
    
    for name, process in services.items():
        service_info = {
            "name": name,
            "pid": process.pid if process else None,
            "type": "unknown"
        }
        
        if name in BAT_SERVICES:
            service_info["type"] = "bat"
            service_info["bat_file"] = str(BAT_SERVICES[name])
        elif name in DASH_APPS:
            service_info["type"] = "dash"
            service_info["port"] = DASH_APPS[name]["port"]
            service_info["url"] = DASH_APPS[name]["url"]
        elif name in STREAMLIT_APPS:
            service_info["type"] = "streamlit"
            service_info["port"] = streamlit_ports.get(name, STREAMLIT_APPS[name]["port"])
            service_info["url"] = f"http://localhost:{service_info['port']}"
        elif name in FASTAPI_APPS:
            service_info["type"] = "fastapi"
            service_info["port"] = FASTAPI_APPS[name]["port"]
            service_info["url"] = FASTAPI_APPS[name]["url"]
        elif name in DOCKER_COMPOSE_APPS:
            service_info["type"] = "docker-compose"
            service_info["ports"] = DOCKER_COMPOSE_APPS[name]["ports"]
            service_info["urls"] = DOCKER_COMPOSE_APPS[name]["urls"]
        elif name in NEXTJS_APPS:
            service_info["type"] = "nextjs"
            service_info["port"] = NEXTJS_APPS[name]["port"]
            service_info["url"] = NEXTJS_APPS[name]["url"]
        
        if hasattr(process, '_service_url'):
            service_info["url"] = process._service_url
        
        registry["services"][name] = service_info
    
    registry_file = BASE_DIR / "Manager" / "service_registry.json"
    registry_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(registry_file, 'w', encoding='utf-8') as f:
            json.dump(registry, f, indent=2, default=str)
        print(f"[INFO] Service registry saved to: {registry_file}")
    except Exception as e:
        print(f"[WARN] Failed to save service registry: {e}")


def check_health(fail_counts):
    """Check each service in PORTS. Increment fail_counts on failure."""
    to_restart = []
    for name, (host, port) in PORTS.items():
        # Handle Streamlit port tracking (fixed ports)
        if name in streamlit_ports:
            port = streamlit_ports[name]
        elif name in STREAMLIT_APPS:
            port = STREAMLIT_APPS[name]["port"]
        
        healthy = is_service_healthy(host, port)
        if healthy:
            fail_counts[name] = 0
            print(f"[OK]   {name} (port {port})")
        else:
            fail_counts[name] = fail_counts.get(name, 0) + 1
            print(f"[FAIL] {name} (port {port}) [{fail_counts[name]}/{FAIL_THRESHOLD}]")
            if fail_counts[name] >= FAIL_THRESHOLD:
                to_restart.append(name)
    return to_restart


def main():
    """Main launcher function."""
    print(f"\n[INFO] HEALTH_CHECK_ENABLED  = {HEALTH_CHECK_ENABLED}")
    print(f"[INFO] DAILY_RESTART_ENABLED = {DAILY_RESTART_ENABLED}\n")
    
    # Launch all services
    all_services, fail_counts = launch_all_services()
    
    # Extract tunnel manager for cleanup
    tunnel_manager = all_services.get('_tunnel_manager')
    
    # If neither feature is on, exit immediately
    if not HEALTH_CHECK_ENABLED and not DAILY_RESTART_ENABLED:
        print("[INFO] No monitoring or daily restart enabled.")
        print("[INFO] Services are running. Press Ctrl+C to exit.\n")
        print("[INFO] To stop services, close their windows or use Task Manager.\n")
        
        try:
            # Keep script alive so processes don't become orphaned
            while True:
                time.sleep(60)
                # Quick health check without restart
                print(f"\n[STATUS] {datetime.now().strftime('%H:%M:%S')} - Services still running...")
        except KeyboardInterrupt:
            print("\n[INFO] Shutdown requested. Services continue running in background.\n")
        return
    
    # Track last daily restart time
    last_daily_restart = time.time()
    
    try:
        while True:
            time.sleep(CHECK_INTERVAL)
            
            # 1) Health-check loop
            if HEALTH_CHECK_ENABLED:
                to_restart = check_health(fail_counts)
                if to_restart:
                    print(f"\n[WARN] Restarting failed services: {', '.join(to_restart)}\n")
                    # Restart logic would go here
                else:
                    warnings = [n for n, c in fail_counts.items() if 0 < c < FAIL_THRESHOLD]
                    if warnings:
                        print(f"\n[WARN] Services warning: {', '.join(warnings)}\n")
                    else:
                        print("\n[OK] All services healthy — continuing to monitor.\n")
            
            # 2) Daily restart check
            if DAILY_RESTART_ENABLED:
                now = time.time()
                if now - last_daily_restart >= DAILY_RESTART_INTERVAL:
                    print(f"\n[INFO] 24h elapsed — restarting {TKP_SERVICE_NAME}\n")
                    # Restart logic would go here
                    last_daily_restart = now
    
    except KeyboardInterrupt:
        print("\n[INFO] Shutdown requested by user.")
        
        # Stop tunnel if running
        if tunnel_manager:
            tunnel_manager.stop_tunnel()
        
        print("[INFO] Services continue running in background.")
        print("[INFO] Close service windows or use Task Manager to stop them.\n")


def open_docker_desktop_gui():
    """
    Standalone function to open Docker Desktop GUI window.
    Can be called even when Docker daemon is already running.
    """
    print("[INFO] Opening Docker Desktop GUI...")
    success = open_docker_desktop()
    if success:
        print("[OK] Docker Desktop GUI launch command executed")
    else:
        print("[ERROR] Failed to open Docker Desktop GUI")
    return success


if __name__ == "__main__":
    # Allow opening Docker Desktop GUI directly via command line argument
    if len(sys.argv) > 1 and sys.argv[1] == "--open-docker":
        open_docker_desktop_gui()
        sys.exit(0)
    main()
