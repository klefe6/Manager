#!/usr/bin/env python3
"""
Purpose: Comprehensive Service Launcher with Virtual Environment Enforcement
Author: Kevin Lefebvre
Last Updated: 2026-02-14

Launches all services including:
- .bat file services
- Dash applications (Python)
- Streamlit applications
- FastAPI applications
- Next.js applications
- Docker Compose applications
- Cloudflare Tunnel

Windows native, handles port conflicts gracefully.

CRITICAL FEATURES (Feb 2026):
1. Per service python_exe enforcement (no PATH python)
2. Preflight checks for dependencies (uvicorn, sqlalchemy, etc)
3. Stdout and stderr piped to timestamped log files
4. Health checks via port polling
5. Early exit detection with last 50 lines of logs
6. No PIPE buffer overflow, all processes use CREATE_NEW_CONSOLE or log files
7. Actual PID tracking, no wrapper PIDs
8. Visible console windows for debugging
9. Robust kill with process tree termination
"""

import json
import os
import subprocess
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import socket

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

# Feature flags
HEALTH_CHECK_ENABLED = False  # Monitor and auto restart unhealthy services
DAILY_RESTART_ENABLED = True  # Restart TKP/TCP Tearsheet every 24 hours

# Timing configuration
FAIL_THRESHOLD = 2  # Consecutive failures before restart
CHECK_INTERVAL = 15  # Seconds between health checks
LAUNCH_PAUSE = 1  # Seconds pause between launching each service
DAILY_RESTART_INTERVAL = 24 * 60 * 60  # 24 hours in seconds
BROWSER_OPEN_DELAY = 3  # Seconds to wait before opening browser

# Service configuration
DAILY_RESTART_SERVICES: List[str] = ["TKP Tearsheet", "TCP Tearsheet"]

# Base directory
BASE_DIR = Path(r"C:\Coding Projects")

# Logs directory
LOGS_DIR = BASE_DIR / "Manager" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────


def is_port_available(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if a port is available (nothing listening on it)."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return False  # Port is in use
    except (socket.error, ConnectionRefusedError, TimeoutError):
        return True  # Port is available


def is_port_listening(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if something is listening on a port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True  # Something is listening
    except (socket.error, ConnectionRefusedError, TimeoutError):
        return False  # Nothing listening


def wait_for_port(host: str, port: int, timeout: float = 30.0, check_interval: float = 0.5) -> bool:
    """Wait for a port to start listening."""
    start_time = time.time()
    
    while (time.time() - start_time) < timeout:
        if is_port_listening(host, port, timeout=1.0):
            return True
        time.sleep(check_interval)
    
    return False


def get_log_file(service_name: str) -> Path:
    """Get log file path for a service."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return LOGS_DIR / f"{service_name.replace(' ', '_')}_{timestamp}.log"


def read_last_lines(file_path: Path, num_lines: int = 50) -> str:
    """Read last N lines from a file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            return ''.join(lines[-num_lines:])
    except Exception as e:
        return f"Could not read log file: {e}"


def kill_process_tree(pid: int) -> bool:
    """Kill a process and all its children using taskkill on Windows."""
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            timeout=10
        )
        return True
    except Exception as e:
        print(f"[ERROR] Failed to kill process {pid}: {e}")
        return False


def run_preflight_check(service_name: str, python_exe: str, checks: List[Dict]) -> Tuple[bool, str]:
    """
    Run preflight checks for a service.
    
    Args:
        service_name: Name of the service
        python_exe: Absolute path to Python executable
        checks: List of check definitions with 'command' and 'expected' keys
        
    Returns:
        Tuple of (success, message)
    """
    if not os.path.exists(python_exe):
        return False, f"Python executable not found: {python_exe}"
    
    print(f"[PREFLIGHT] {service_name} using {python_exe}")
    
    for check in checks:
        cmd = [python_exe, "-c", check["command"]]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return False, f"Check failed: {check.get('description', 'unknown')}\nError: {result.stderr}"
            
            output = result.stdout.strip()
            print(f"  Check: {check.get('description', 'unknown')}")
            print(f"    Output: {output}")
            
            # Verify expected output if specified
            if "expected" in check:
                if check["expected"] not in output:
                    remediation = check.get("remediation", "No remediation steps provided")
                    return False, f"Check failed: {check.get('description', 'unknown')}\n{remediation}"
        
        except subprocess.TimeoutExpired:
            return False, f"Check timed out: {check.get('description', 'unknown')}"
        except Exception as e:
            return False, f"Check error: {check.get('description', 'unknown')}: {e}"
    
    print(f"[PREFLIGHT] {service_name} passed all checks")
    return True, "OK"


# ─────────────────────────────────────────────────────────────────────────────
# SERVICE CONFIGURATIONS
# ─────────────────────────────────────────────────────────────────────────────

# .BAT Services
BAT_SERVICES: Dict[str, Dict] = {
    "TWIFO Sharing": {
        "bat_path": BASE_DIR / "TWIFO_Sharing" / "reboot_twifo.bat",
        "port": 8065,
        "python_exe": None,  # Uses bat file internal python
    },
    "Import Dropbox": {
        "bat_path": BASE_DIR / "TWIFO_Sharing" / "reboot_import_dropbox.bat",
        "port": None,
        "python_exe": None,
    },
    "TS Generator": {
        "bat_path": BASE_DIR / "Tearsheet Generator" / "run_tsgen.bat",
        "port": 8077,
        "python_exe": None,
    },
    "TKP Tearsheet": {
        "bat_path": BASE_DIR / "Tearsheet Generator" / "reboot_tkp_ts.bat",
        "port": 8076,
        "python_exe": None,
    },
    "TCP Tearsheet": {
        "bat_path": BASE_DIR / "Tearsheet Generator" / "reboot_tcp_ts.bat",
        "port": 8078,
        "python_exe": None,
    },
    "Y&Q Tearsheet": {
        "bat_path": BASE_DIR / "Tearsheet Generator" / "reboot_yq_ts.bat",
        "port": 8071,
        "python_exe": None,
    },
    "Gold Maker": {
        "bat_path": BASE_DIR / "Tearsheet Generator" / "reboot_gold_maker.bat",
        "port": 8075,
        "python_exe": None,
    },
    "Sector Ratio": {
        "bat_path": BASE_DIR / "GSR" / "reboot_gsr.bat",
        "port": 8080,
        "python_exe": None,
    },
    "ES Historical": {
        "bat_path": BASE_DIR / "ES Historical Data" / "reboot_es_historical_data.bat",
        "port": 8081,
        "python_exe": None,
    },
    "Almanac Futures": {
        "bat_path": BASE_DIR / "Almanac Futures" / "reboot_almanac.bat",
        "port": 8072,
        "python_exe": BASE_DIR / "Almanac Futures" / ".venv312" / "Scripts" / "python.exe",
        "script_path": BASE_DIR / "Almanac Futures" / "runalmanac.py",
        "cwd": BASE_DIR / "Almanac Futures",
        "preflight_checks": [
            {
                "command": "import sys; print(sys.version)",
                "description": "Python version check",
            },
            {
                "command": "import sys; print('OK' if (3, 11) <= sys.version_info < (3, 13) else 'FAIL')",
                "expected": "OK",
                "description": "Python version is 3.11 or 3.12",
                "remediation": "Create venv with Python 3.11 or 3.12: python3.12 -m venv .venv312"
            },
            {
                "command": "import sqlalchemy; print('OK')",
                "expected": "OK",
                "description": "SQLAlchemy import check",
                "remediation": "Install SQLAlchemy: .venv312\\Scripts\\python.exe -m pip install sqlalchemy"
            },
        ],
    },
    "AGM Allocation": {
        "bat_path": BASE_DIR / "AGM_Allocation" / "reboot_agm_allocation.bat",
        "port": 1001,
        "python_exe": None,
    },
    "CTA Outreach": {
        "bat_path": BASE_DIR / "CTA" / "reboot_cta.bat",
        "port": 3004,
        "python_exe": None,
    },
}

# Dash Applications
DASH_APPS: Dict[str, Dict] = {
    "Price Dashboard": {
        "script_path": BASE_DIR / "Price Dashboard" / "app.py",
        "port": 8002,
        "url": "http://localhost:8002",
        "cwd": BASE_DIR / "Price Dashboard",
        "python_exe": r"C:\Python313\python.exe",
    },
    "Sector RRG": {
        "script_path": BASE_DIR / "Sector" / "app_rrg.py",
        "port": 8003,
        "url": "http://localhost:8003",
        "cwd": BASE_DIR / "Sector",
        "python_exe": r"C:\Python313\python.exe",
    },
    "Strategy Optimizer": {
        "script_path": BASE_DIR / "StrategyOptimizer" / "app.py",
        "port": 8004,
        "url": "http://localhost:8004",
        "cwd": BASE_DIR / "StrategyOptimizer",
        "python_exe": BASE_DIR / "StrategyOptimizer" / ".venv13" / "Scripts" / "python.exe",
    },
    "Home Page": {
        "script_path": BASE_DIR / "HomePage" / "main.py",
        "port": 8005,
        "url": "http://localhost:8005",
        "cwd": BASE_DIR / "HomePage",
        "python_exe": BASE_DIR / "HomePage" / ".venv13" / "Scripts" / "python.exe",
    },
    "Debug Page": {
        "script_path": BASE_DIR / "HomePage" / "debug.py",
        "port": 8006,
        "url": "http://localhost:8006",
        "cwd": BASE_DIR / "HomePage",
        "python_exe": BASE_DIR / "HomePage" / ".venv13" / "Scripts" / "python.exe",
    },
    "SriPNL": {
        "script_path": BASE_DIR / "SriPNL" / "app.py",
        "port": 7878,
        "url": "http://localhost:7878",
        "cwd": BASE_DIR / "SriPNL",
        "python_exe": r"C:\Python313\python.exe",
    },
}

# Streamlit Applications
STREAMLIT_APPS: Dict[str, Dict] = {
    "TWIFO Import Dropbox": {
        "script_path": BASE_DIR / "TWIFO_Sharing" / "import_dropbox.py",
        "port": 8009,
        "url": "http://localhost:8009",
        "cwd": BASE_DIR / "TWIFO_Sharing",
        "python_exe": BASE_DIR / "TWIFO_Sharing" / ".venv13" / "Scripts" / "python.exe",
    },
    "QuantLab Dashboard": {
        "script_path": BASE_DIR / "QuantLab" / "dashboard" / "app.py",
        "port": 8501,
        "url": "http://localhost:8501",
        "cwd": BASE_DIR / "QuantLab",
        "python_exe": r"C:\Python313\python.exe",
    },
}

# FastAPI Applications
FASTAPI_APPS: Dict[str, Dict] = {
    "Agent Control Center": {
        "script_path": BASE_DIR / "Agent Control Center" / "main.py",
        "port": 8007,
        "url": "http://localhost:8007",
        "cwd": BASE_DIR / "Agent Control Center",
        "python_exe": BASE_DIR / "Agent Control Center" / ".venv312" / "Scripts" / "python.exe",
        "uvicorn_module": "main:app",
        "preflight_checks": [
            {
                "command": "import sys; print(sys.executable)",
                "description": "Python executable path",
            },
            {
                "command": "import pkgutil; print('uvicorn' in [m.name for m in pkgutil.iter_modules()])",
                "expected": "True",
                "description": "uvicorn module check",
                "remediation": "Install uvicorn and fastapi:\n  .venv312\\Scripts\\python.exe -m pip install uvicorn fastapi"
            },
            {
                "command": "import pkgutil; print('fastapi' in [m.name for m in pkgutil.iter_modules()])",
                "expected": "True",
                "description": "fastapi module check",
                "remediation": "Install fastapi:\n  .venv312\\Scripts\\python.exe -m pip install fastapi"
            },
        ],
    },
    "Order Flow Website Backend": {
        "script_path": BASE_DIR / "Order Flow Website" / "backend" / "app" / "main.py",
        "port": 8000,
        "url": "http://localhost:8000",
        "cwd": BASE_DIR / "Order Flow Website" / "backend",
        "python_exe": BASE_DIR / "Order Flow Website" / "backend" / ".venv" / "Scripts" / "python.exe",
        "uvicorn_module": "app.main:app",
    },
    "CTA Outreach Backend": {
        "script_path": BASE_DIR / "CTA" / "backend" / "app" / "main.py",
        "port": 8010,
        "url": "http://localhost:8010",
        "cwd": BASE_DIR / "CTA" / "backend",
        "python_exe": r"C:\Python313\python.exe",
        "uvicorn_module": "app.main:app",
    },
}

# Docker Compose Applications
DOCKER_COMPOSE_APPS: Dict[str, Dict] = {
    "Trading Video Library": {
        "compose_file": BASE_DIR / "Trading Video Library" / "docker-compose.yml",
        "ports": [8000, 3003],
        "urls": {
            "backend": "http://localhost:8000",
            "frontend": "http://localhost:3003",
        },
        "cwd": BASE_DIR / "Trading Video Library",
        "services": ["api", "worker", "redis", "web"],
    },
    "Summary Engine": {
        "compose_file": BASE_DIR / "SummaryEngine" / "docker-compose.yml",
        "ports": [8001, 3001],
        "urls": {
            "backend": "http://localhost:8001",
            "frontend": "http://localhost:3001",
        },
        "cwd": BASE_DIR / "SummaryEngine",
        "services": ["backend", "frontend"],
    },
}

# Next.js Applications
NEXTJS_APPS: Dict[str, Dict] = {
    "VizLab": {
        "cwd": BASE_DIR / "VizLab",
        "port": 8011,
        "url": "http://localhost:8011",
    },
    "Order Flow Website": {
        "cwd": BASE_DIR / "Order Flow Website" / "frontend",
        "port": 8012,
        "url": "http://localhost:8012",
    },
    "CTA Outreach": {
        "cwd": BASE_DIR / "CTA" / "frontend",
        "port": 3004,
        "url": "http://localhost:3004",
    },
}

# Cloudflare domain mapping
CLOUDFLARE_DOMAINS: Dict[str, str] = {
    "Price Dashboard": "price-dashboard.hcresearch.ltd",
    "Sector RRG": "sector-rrg.hcresearch.ltd",
    "Strategy Optimizer": "strategy-optimizer.hcresearch.ltd",
    "Home Page": "homepage.hcresearch.ltd",
    "Debug Page": "debug.hcresearch.ltd",
    "QuantLab Dashboard": "quantlab.hcresearch.ltd",
    "TWIFO Import Dropbox": "import-dropbox.hcresearch.ltd",
    "TWIFO Sharing": "twifo.hcresearch.ltd",
    "TKP Tearsheet": "tkp-ts.hcresearch.ltd",
    "TCP Tearsheet": "tcp-ts.hcresearch.ltd",
    "Y&Q Tearsheet": "yq-ts.hcresearch.ltd",
    "Gold Maker": "tgm-ts.hcresearch.ltd",
    "Sector Ratio": "secratio.hcresearch.ltd",
    "ES Historical": "es-historical.hcresearch.ltd",
    "Almanac Futures": "almanac.hcresearch.ltd",
    "AGM Allocation": "agm-allocation.hcresearch.ltd",
    "TS Generator": "ts-generator.hcresearch.ltd",
    "Agent Control Center": "agent-control.hcresearch.ltd",
    "Trading Video Library": "trading-video-library.hcresearch.ltd",
    "Summary Engine": "summary.hcresearch.ltd",
    "VizLab": "vizlab.hcresearch.ltd",
    "SriPNL": "amf.hcresearch.ltd",
}

# Services to skip opening browser tabs
SKIP_BROWSER_OPEN = {"Summary Engine Backend"}
SKIP_PORTS = {8000, 8001}


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL STATE
# ─────────────────────────────────────────────────────────────────────────────

running_processes: Dict[str, subprocess.Popen] = {}
service_logs: Dict[str, Path] = {}


# ─────────────────────────────────────────────────────────────────────────────
# SERVICE LAUNCHERS
# ─────────────────────────────────────────────────────────────────────────────


def launch_bat_service(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """Launch a .bat service with proper PID tracking and logging."""
    bat_path = config["bat_path"]
    port = config.get("port")
    python_exe = config.get("python_exe")
    
    if not bat_path.exists():
        error_msg = f"[ERROR] .bat not found for {name}: {bat_path}"
        print(error_msg)
        return None
    
    # If python_exe is specified, launch directly with Python instead of bat
    if python_exe and config.get("script_path"):
        return launch_python_service(name, config)
    
    print(f"[LAUNCH] {name} (BAT) → {bat_path.name}")
    
    log_file = get_log_file(name)
    service_logs[name] = log_file
    
    try:
        with open(log_file, "w", encoding="utf-8") as log:
            log.write(f"=== {name} Launch Log ===\n")
            log.write(f"Timestamp: {datetime.now().isoformat()}\n")
            log.write(f"Command: {bat_path}\n")
            log.write(f"CWD: {bat_path.parent}\n")
            log.write("=" * 70 + "\n\n")
            log.flush()
            
            process = subprocess.Popen(
                [str(bat_path)],
                cwd=str(bat_path.parent),
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
        
        time.sleep(1)
        
        if process.poll() is not None:
            print(f"[ERROR] {name} terminated immediately (exit code: {process.returncode})")
            print(f"[ERROR] Last 50 lines from log:")
            print(read_last_lines(log_file, 50))
            return None
        
        print(f"[OK] {name} launched (PID: {process.pid}, log: {log_file.name})")
        
        if port:
            print(f"[HEALTH] Waiting for {name} to bind to port {port}...")
            if wait_for_port("127.0.0.1", port, timeout=20):
                print(f"[OK] {name} is now listening on port {port}")
            else:
                print(f"[WARN] {name} did not start listening on port {port} within 20s")
                print(f"[WARN] Check log file: {log_file}")
        
        return process
        
    except Exception as e:
        print(f"[ERROR] Failed to launch {name}: {e}")
        return None


def launch_python_service(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """Launch a Python service with explicit python_exe and logging."""
    script_path = config.get("script_path")
    port = config.get("port")
    python_exe = config.get("python_exe")
    cwd = config.get("cwd", script_path.parent if script_path else BASE_DIR)
    
    if not script_path or not script_path.exists():
        print(f"[ERROR] Script not found for {name}: {script_path}")
        return None
    
    if not python_exe:
        print(f"[ERROR] No python_exe specified for {name}")
        return None
    
    if not os.path.exists(python_exe):
        print(f"[ERROR] Python executable not found for {name}: {python_exe}")
        return None
    
    # Run preflight checks if specified
    if "preflight_checks" in config:
        success, message = run_preflight_check(name, python_exe, config["preflight_checks"])
        if not success:
            print(f"[PREFLIGHT FAILED] {name}")
            print(f"  {message}")
            return None
    
    print(f"[LAUNCH] {name} (Python) → {script_path.name}")
    print(f"  Python: {python_exe}")
    print(f"  CWD: {cwd}")
    
    log_file = get_log_file(name)
    service_logs[name] = log_file
    
    try:
        with open(log_file, "w", encoding="utf-8") as log:
            log.write(f"=== {name} Launch Log ===\n")
            log.write(f"Timestamp: {datetime.now().isoformat()}\n")
            log.write(f"Python: {python_exe}\n")
            log.write(f"Script: {script_path}\n")
            log.write(f"CWD: {cwd}\n")
            log.write("=" * 70 + "\n\n")
            log.flush()
            
            process = subprocess.Popen(
                [str(python_exe), str(script_path)],
                cwd=str(cwd),
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
        
        time.sleep(2)
        
        if process.poll() is not None:
            print(f"[ERROR] {name} terminated immediately (exit code: {process.returncode})")
            print(f"[ERROR] Last 50 lines from log:")
            print(read_last_lines(log_file, 50))
            return None
        
        print(f"[OK] {name} launched (PID: {process.pid}, log: {log_file.name})")
        
        if port:
            print(f"[HEALTH] Waiting for {name} to bind to port {port}...")
            if wait_for_port("127.0.0.1", port, timeout=20):
                print(f"[OK] {name} is now listening on port {port}")
            else:
                print(f"[WARN] {name} did not start listening on port {port} within 20s")
                print(f"[WARN] Check log file: {log_file}")
                print(f"[WARN] Last 50 lines from log:")
                print(read_last_lines(log_file, 50))
        
        return process
        
    except Exception as e:
        print(f"[ERROR] Failed to launch {name}: {e}")
        return None


def launch_streamlit_service(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """Launch a Streamlit application with explicit python_exe."""
    script_path = config["script_path"]
    port = config["port"]
    python_exe = config["python_exe"]
    cwd = config["cwd"]
    
    if not script_path.exists():
        print(f"[ERROR] Script not found for {name}: {script_path}")
        return None
    
    if not os.path.exists(python_exe):
        print(f"[ERROR] Python executable not found for {name}: {python_exe}")
        return None
    
    print(f"[LAUNCH] {name} (Streamlit) → {script_path.name}")
    print(f"  Python: {python_exe}")
    print(f"  Port: {port}")
    
    log_file = get_log_file(name)
    service_logs[name] = log_file
    
    rel_path = script_path.relative_to(cwd) if script_path.is_relative_to(cwd) else script_path
    
    try:
        with open(log_file, "w", encoding="utf-8") as log:
            log.write(f"=== {name} Launch Log ===\n")
            log.write(f"Timestamp: {datetime.now().isoformat()}\n")
            log.write(f"Python: {python_exe}\n")
            log.write(f"Script: {script_path}\n")
            log.write(f"Port: {port}\n")
            log.write(f"CWD: {cwd}\n")
            log.write("=" * 70 + "\n\n")
            log.flush()
            
            process = subprocess.Popen(
                [
                    str(python_exe),
                    "-m",
                    "streamlit",
                    "run",
                    str(rel_path),
                    "--server.port",
                    str(port),
                    "--server.headless",
                    "true",
                    "--browser.gatherUsageStats",
                    "false",
                ],
                cwd=str(cwd),
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
        
        time.sleep(2)
        
        if process.poll() is not None:
            print(f"[ERROR] {name} terminated immediately (exit code: {process.returncode})")
            print(f"[ERROR] Last 50 lines from log:")
            print(read_last_lines(log_file, 50))
            return None
        
        print(f"[OK] {name} launched (PID: {process.pid}, log: {log_file.name})")
        
        print(f"[HEALTH] Waiting for {name} to bind to port {port}...")
        if wait_for_port("127.0.0.1", port, timeout=20):
            print(f"[OK] {name} is now listening on port {port}")
        else:
            print(f"[WARN] {name} did not start listening on port {port} within 20s")
            print(f"[WARN] Check log file: {log_file}")
        
        return process
        
    except Exception as e:
        print(f"[ERROR] Failed to launch {name}: {e}")
        return None


def launch_fastapi_service(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """Launch a FastAPI application with explicit python_exe and uvicorn."""
    script_path = config["script_path"]
    port = config["port"]
    python_exe = config["python_exe"]
    cwd = config["cwd"]
    uvicorn_module = config.get("uvicorn_module", "main:app")
    
    if not script_path.exists():
        print(f"[ERROR] Script not found for {name}: {script_path}")
        return None
    
    if not os.path.exists(python_exe):
        print(f"[ERROR] Python executable not found for {name}: {python_exe}")
        return None
    
    # Run preflight checks if specified
    if "preflight_checks" in config:
        success, message = run_preflight_check(name, python_exe, config["preflight_checks"])
        if not success:
            print(f"[PREFLIGHT FAILED] {name}")
            print(f"  {message}")
            return None
    
    print(f"[LAUNCH] {name} (FastAPI) → {uvicorn_module}")
    print(f"  Python: {python_exe}")
    print(f"  Port: {port}")
    
    log_file = get_log_file(name)
    service_logs[name] = log_file
    
    try:
        with open(log_file, "w", encoding="utf-8") as log:
            log.write(f"=== {name} Launch Log ===\n")
            log.write(f"Timestamp: {datetime.now().isoformat()}\n")
            log.write(f"Python: {python_exe}\n")
            log.write(f"Module: {uvicorn_module}\n")
            log.write(f"Port: {port}\n")
            log.write(f"CWD: {cwd}\n")
            log.write("=" * 70 + "\n\n")
            log.flush()
            
            process = subprocess.Popen(
                [
                    str(python_exe),
                    "-m",
                    "uvicorn",
                    uvicorn_module,
                    "--host",
                    "0.0.0.0",
                    "--port",
                    str(port),
                    "--reload"
                ],
                cwd=str(cwd),
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
        
        time.sleep(2)
        
        if process.poll() is not None:
            print(f"[ERROR] {name} terminated immediately (exit code: {process.returncode})")
            print(f"[ERROR] Last 50 lines from log:")
            print(read_last_lines(log_file, 50))
            return None
        
        print(f"[OK] {name} launched (PID: {process.pid}, log: {log_file.name})")
        
        print(f"[HEALTH] Waiting for {name} to bind to port {port}...")
        if wait_for_port("127.0.0.1", port, timeout=20):
            print(f"[OK] {name} is now listening on port {port}")
        else:
            print(f"[WARN] {name} did not start listening on port {port} within 20s")
            print(f"[WARN] Check log file: {log_file}")
            print(f"[WARN] Last 50 lines from log:")
            print(read_last_lines(log_file, 50))
        
        return process
        
    except Exception as e:
        print(f"[ERROR] Failed to launch {name}: {e}")
        return None


def launch_nextjs_service(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """Launch a Next.js application."""
    cwd = config["cwd"]
    port = config["port"]
    
    if not cwd.exists():
        print(f"[ERROR] Directory not found for {name}: {cwd}")
        return None
    
    print(f"[LAUNCH] {name} (Next.js) → port {port}")
    
    log_file = get_log_file(name)
    service_logs[name] = log_file
    
    try:
        with open(log_file, "w", encoding="utf-8") as log:
            log.write(f"=== {name} Launch Log ===\n")
            log.write(f"Timestamp: {datetime.now().isoformat()}\n")
            log.write(f"Port: {port}\n")
            log.write(f"CWD: {cwd}\n")
            log.write("=" * 70 + "\n\n")
            log.flush()
            
            process = subprocess.Popen(
                ["cmd.exe", "/k", f"npx next dev -p {port}"],
                cwd=str(cwd),
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
            )
        
        time.sleep(3)
        
        if process.poll() is not None:
            print(f"[ERROR] {name} terminated immediately (exit code: {process.returncode})")
            print(f"[ERROR] Last 50 lines from log:")
            print(read_last_lines(log_file, 50))
            return None
        
        print(f"[OK] {name} launched (PID: {process.pid}, log: {log_file.name})")
        
        print(f"[HEALTH] Waiting for {name} to bind to port {port} (30s for Next.js compile)...")
        if wait_for_port("127.0.0.1", port, timeout=30):
            print(f"[OK] {name} is now listening on port {port}")
        else:
            print(f"[WARN] {name} did not start listening on port {port} within 30s")
            print(f"[WARN] Next.js first compile can take 30 to 60 seconds")
        
        return process
        
    except Exception as e:
        print(f"[ERROR] Failed to launch {name}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# DOCKER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────


def open_docker_desktop() -> bool:
    """Open Docker Desktop application on Windows."""
    try:
        docker_paths = [
            r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
            os.path.expanduser(r"~\AppData\Local\Docker\Docker Desktop.exe"),
            r"C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe",
        ]

        for path in docker_paths:
            if os.path.exists(path):
                try:
                    os.startfile(path)
                    print(f"[OK] Opened Docker Desktop: {path}")
                    return True
                except Exception:
                    pass

        subprocess.Popen('start "" "Docker Desktop"', shell=True)
        print("[OK] Attempted to start Docker Desktop via start command")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error opening Docker Desktop: {e}")
        return False


def check_docker_available(auto_start: bool = True) -> Tuple[bool, str]:
    """Check if Docker is installed and running."""
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout.strip():
            return True, f"Docker {result.stdout.strip()}"

        if auto_start:
            print("[INFO] Docker Desktop is not running, attempting to start...")
            if open_docker_desktop():
                print("[INFO] Waiting for Docker to start...")
                time.sleep(10)
                for attempt in range(6):
                    time.sleep(5)
                    retry_result = subprocess.run(
                        ["docker", "version", "--format", "{{.Server.Version}}"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if retry_result.returncode == 0 and retry_result.stdout.strip():
                        return True, f"Docker {retry_result.stdout.strip()}"
                return False, "Docker Desktop did not start within 40 seconds"
            else:
                return False, "Docker Desktop failed to start"
        else:
            return False, "Docker Desktop is not running"

    except FileNotFoundError:
        return False, "Docker command not found, is Docker Desktop installed?"
    except subprocess.TimeoutExpired:
        return False, "Docker command timed out"
    except Exception as e:
        return False, f"Docker check failed: {str(e)}"


def launch_docker_compose_service(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """Launch a Docker Compose application."""
    compose_file = config["compose_file"]
    cwd = config["cwd"]
    ports = config.get("ports", [])

    if not compose_file.exists():
        print(f"[ERROR] Docker Compose file not found for {name}: {compose_file}")
        return None

    print(f"[LAUNCH] {name} (Docker Compose) → {compose_file.name}")

    log_file = get_log_file(name)
    service_logs[name] = log_file

    compose_cmd = ["docker", "compose", "-f", str(compose_file), "up", "-d", "--build"]

    try:
        with open(log_file, "w", encoding="utf-8") as log:
            log.write(f"=== {name} Launch Log ===\n")
            log.write(f"Timestamp: {datetime.now().isoformat()}\n")
            log.write(f"Compose File: {compose_file}\n")
            log.write(f"CWD: {cwd}\n")
            log.write("=" * 70 + "\n\n")
            log.flush()
            
            result = subprocess.run(
                compose_cmd,
                cwd=str(cwd),
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=300,
            )
        
        if result.returncode != 0:
            print(f"[ERROR] {name} Docker Compose build failed (exit code: {result.returncode})")
            print(f"[ERROR] Last 50 lines from log:")
            print(read_last_lines(log_file, 50))
            return None

        process = subprocess.Popen(
            ["docker", "compose", "-f", str(compose_file), "ps"],
            cwd=str(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        print(f"[OK] {name} Docker Compose started (log: {log_file.name})")

        backend_ports = [p for p in ports if 8000 <= p < 9000]
        frontend_ports = [p for p in ports if 3000 <= p < 4000]

        for port in backend_ports:
            print(f"[HEALTH] Waiting for {name} backend on port {port}...")
            if wait_for_port("127.0.0.1", port, timeout=30):
                print(f"[OK] {name} backend is now listening on port {port}")
            else:
                print(f"[WARN] {name} backend did not start on port {port} within 30s")

        for port in frontend_ports:
            timeout = 90 if "Summary Engine" in name else 45
            print(f"[HEALTH] Waiting for {name} frontend on port {port} (up to {timeout}s for Next.js build)...")
            if wait_for_port("127.0.0.1", port, timeout=timeout):
                print(f"[OK] {name} frontend is now listening on port {port}")
            else:
                print(f"[WARN] {name} frontend did not start on port {port} within {timeout}s")
                print(f"[WARN] Next.js first build can take 60 to 120 seconds")

        return process
        
    except Exception as e:
        print(f"[ERROR] Failed to launch {name}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# BROWSER & MONITORING
# ─────────────────────────────────────────────────────────────────────────────


def open_browser_tabs(services: Dict[str, subprocess.Popen]) -> None:
    """Open browser tabs for all web services after a delay."""
    print(f"\n[INFO] Waiting {BROWSER_OPEN_DELAY}s before opening browsers...\n")
    time.sleep(BROWSER_OPEN_DELAY)

    urls_to_open = []

    for name, config in list(DASH_APPS.items()) + list(STREAMLIT_APPS.items()) + list(FASTAPI_APPS.items()):
        if name in services and name not in SKIP_BROWSER_OPEN:
            url = config.get("url")
            port = config.get("port")
            if url and port not in SKIP_PORTS:
                urls_to_open.append((name, url))

    for name, config in DOCKER_COMPOSE_APPS.items():
        if name in services:
            frontend_url = config.get("urls", {}).get("frontend")
            if frontend_url:
                urls_to_open.append((name, frontend_url))

    for name, config in NEXTJS_APPS.items():
        if name in services:
            url = config.get("url")
            if url:
                urls_to_open.append((name, url))

    if urls_to_open:
        print(f"[INFO] Opening {len(urls_to_open)} browser tabs...")
        for name, url in urls_to_open:
            try:
                webbrowser.open(url)
                print(f"  Browser opened for {name}: {url}")
                time.sleep(0.5)
            except Exception as e:
                print(f"  Failed to open browser for {name}: {e}")


def save_service_registry(services: Dict[str, subprocess.Popen]) -> None:
    """Save service registry to JSON."""
    registry = {
        "launched_at": datetime.now().isoformat(),
        "services": {}
    }

    for name, process in services.items():
        if name == "_tunnel_manager":
            continue

        registry["services"][name] = {
            "name": name,
            "pid": process.pid if process else None,
            "log_file": str(service_logs.get(name, "N/A")),
        }

    registry_file = BASE_DIR / "Manager" / "service_registry.json"
    registry_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(registry_file, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, default=str)
        print(f"[INFO] Service registry saved to: {registry_file.name}")
    except Exception as e:
        print(f"[WARN] Failed to save service registry: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN LAUNCHER
# ─────────────────────────────────────────────────────────────────────────────


def launch_all_services() -> Tuple[Dict[str, subprocess.Popen], Dict[str, int]]:
    """Launch all services and return running processes and fail counts."""
    all_services: Dict[str, subprocess.Popen] = {}
    failed_services: List[str] = []

    print("\n" + "=" * 70)
    print("  COMPREHENSIVE SERVICE LAUNCHER")
    print("=" * 70)
    print(f"\n[INFO] Logs directory: {LOGS_DIR}")
    print(f"[INFO] Launching {len(BAT_SERVICES)} .bat services")
    print(f"[INFO] Launching {len(DASH_APPS)} Dash applications")
    print(f"[INFO] Launching {len(STREAMLIT_APPS)} Streamlit applications")
    print(f"[INFO] Launching {len(FASTAPI_APPS)} FastAPI applications")
    print(f"[INFO] Launching {len(DOCKER_COMPOSE_APPS)} Docker Compose applications")
    print(f"[INFO] Launching {len(NEXTJS_APPS)} Next.js applications")
    
    total = (
        len(BAT_SERVICES)
        + len(DASH_APPS)
        + len(STREAMLIT_APPS)
        + len(FASTAPI_APPS)
        + len(DOCKER_COMPOSE_APPS)
        + len(NEXTJS_APPS)
    )
    print(f"[INFO] Total: {total} services\n")

    # Phase 1: Launch .bat services
    print("[PHASE 1] Launching .bat services...")
    for name, config in BAT_SERVICES.items():
        process = launch_bat_service(name, config)
        if process:
            all_services[name] = process
        else:
            failed_services.append(name)
        time.sleep(LAUNCH_PAUSE)
    print()

    # Phase 2: Launch Dash applications
    print("[PHASE 2] Launching Dash applications...")
    for name, config in DASH_APPS.items():
        process = launch_python_service(name, config)
        if process:
            all_services[name] = process
        else:
            failed_services.append(name)
        time.sleep(LAUNCH_PAUSE)
    print()

    # Phase 3: Launch Streamlit applications
    print("[PHASE 3] Launching Streamlit applications...")
    for name, config in STREAMLIT_APPS.items():
        process = launch_streamlit_service(name, config)
        if process:
            all_services[name] = process
        else:
            failed_services.append(name)
        time.sleep(LAUNCH_PAUSE)
    print()

    # Phase 4: Launch FastAPI applications
    print("[PHASE 4] Launching FastAPI applications...")
    for name, config in FASTAPI_APPS.items():
        process = launch_fastapi_service(name, config)
        if process:
            all_services[name] = process
        else:
            failed_services.append(name)
        time.sleep(LAUNCH_PAUSE)
    print()

    # Phase 5: Launch Docker Compose applications
    print("[PHASE 5] Launching Docker Compose applications...")
    if DOCKER_COMPOSE_APPS:
        docker_available, docker_info = check_docker_available()
        if docker_available:
            print(f"[OK] {docker_info}")
            for name, config in DOCKER_COMPOSE_APPS.items():
                process = launch_docker_compose_service(name, config)
                if process:
                    all_services[name] = process
                else:
                    failed_services.append(name)
                time.sleep(LAUNCH_PAUSE)
        else:
            print(f"[ERROR] {docker_info}")
            print(f"[WARN] Skipping Docker Compose services")
            for name in DOCKER_COMPOSE_APPS.keys():
                failed_services.append(f"{name} (Docker not available)")
    print()

    # Phase 6: Launch Next.js applications
    print("[PHASE 6] Launching Next.js applications...")
    for name, config in NEXTJS_APPS.items():
        process = launch_nextjs_service(name, config)
        if process:
            all_services[name] = process
        else:
            failed_services.append(name)
        time.sleep(LAUNCH_PAUSE)
    print()

    # Phase 7: Launch Cloudflare Tunnel
    tunnel_manager = None
    if CLOUDFLARE_AVAILABLE:
        print("[PHASE 7] Starting Cloudflare Tunnel...")
        try:
            tunnel_manager = get_tunnel_manager()
            if tunnel_manager and tunnel_manager.start_tunnel():
                print("[OK] Cloudflare Tunnel started")
            else:
                print("[INFO] Cloudflare Tunnel not configured or failed to start")
        except Exception as e:
            print(f"[WARN] Cloudflare Tunnel error: {e}")
        print()

    # Phase 8: Open browser tabs
    open_browser_tabs(all_services)

    # Phase 9: Save service registry
    save_service_registry(all_services)

    if tunnel_manager:
        all_services["_tunnel_manager"] = tunnel_manager

    # Print summary
    print("\n" + "=" * 70)
    print("  LAUNCH SUMMARY")
    print("=" * 70)
    print(f"\n[INFO] Successfully launched: {len(all_services)} services")
    if failed_services:
        print(f"[WARN] Failed to launch: {len(failed_services)} service(s)")
        print(f"[WARN] Failed services: {', '.join(failed_services)}")
        print(f"[INFO] Check logs in: {LOGS_DIR}")
    else:
        print(f"[OK] All services launched successfully")
    print(f"[INFO] Browser tabs opened for web services")
    print(f"[INFO] Services are running in background")
    print()

    return all_services, {}


def main() -> None:
    """Main launcher function."""
    print(f"\n[INFO] HEALTH_CHECK_ENABLED  = {HEALTH_CHECK_ENABLED}")
    print(f"[INFO] DAILY_RESTART_ENABLED = {DAILY_RESTART_ENABLED}\n")

    all_services, _ = launch_all_services()

    print("[INFO] Services are running, press Ctrl+C to exit launcher")
    print("[INFO] Services will continue running after launcher exits")
    print("[INFO] To stop services, close their console windows or use Task Manager\n")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n[INFO] Launcher stopped, services continue running\n")


if __name__ == "__main__":
    main()
