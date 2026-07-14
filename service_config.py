#!/usr/bin/env python3
"""
Service Configuration and Utilities
Part of the Comprehensive Service Launcher system.

Contains:
- Configuration constants
- Service definitions
- Utility functions
"""

import os
import subprocess
import socket
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from tearsheet_fleet_runtime import (
    DirtyRuntimeRootError,
    apply_fleet_bat_overrides,
    get_runtime_root,
)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

# Feature flags
HEALTH_CHECK_ENABLED = False  # Monitor and auto restart unhealthy services
DAILY_RESTART_ENABLED = True  # Restart TKP/TCP Tearsheet every 24 hours
MEMORY_CHECK_ENABLED = True  # Check available memory before launching services
MEMORY_THRESHOLD_GB = 4  # Minimum GB of available RAM required to continue

# Timing configuration
FAIL_THRESHOLD = 2  # Consecutive failures before restart
CHECK_INTERVAL = 15  # Seconds between health checks
LAUNCH_PAUSE = 3  # Seconds pause between launching each service when PARALLEL_LAUNCH_ENABLED is False
PHASE_PAUSE = 5  # Seconds pause between phases (new)

# Parallel launch (within each phase all services start concurrently; phases still run in order)
PARALLEL_LAUNCH_ENABLED = True
# Cap concurrent spawns per phase (Dash/Streamlit/FastAPI/bat/Next/Docker); lower if the machine struggles
PARALLEL_MAX_WORKERS = 12
DAILY_RESTART_INTERVAL = 24 * 60 * 60  # 24 hours in seconds
BROWSER_OPEN_DELAY = 5  # Seconds to wait before opening browser (increased)

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
        "port": 8401,
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
        "port": 8301,
        "python_exe": None,
        # TKP loads ~768 rows of Excel + yfinance + quantstats; first boot ~60s
        "health_timeout": 120,
    },
    "TCP Tearsheet": {
        "bat_path": BASE_DIR / "Tearsheet Generator" / "reboot_tcp_ts.bat",
        "port": 8302,
        "python_exe": None,
        "health_timeout": 120,
    },
    "Y&Q Tearsheet": {
        "bat_path": BASE_DIR / "Tearsheet Generator" / "reboot_yq_ts.bat",
        "port": 8303,
        "python_exe": None,
        "health_timeout": 90,
    },
    "Momentum Pacer Tearsheet": {
        "bat_path": BASE_DIR / "Tearsheet Generator" / "reboot_mp_ts.bat",
        "port": 8304,
        "python_exe": None,
        "health_timeout": 60,
        # AGM died silently at the 2026-07-14 crash-reboot; keep its output on disk.
        "capture_output": True,
    },
    "Glenn Uploader": {
        # Full local stack: FastAPI backend on 8091 + Vite frontend on 5173.
        # The bat kills both ports, then starts backend before frontend.
        "bat_path": BASE_DIR / "Tearsheet Generator" / "reboot_glenn_uploader.bat",
        "port": 5173,
        "ports": [8091, 5173],
        "python_exe": None,
        "health_timeout": 150,
        "capture_output": True,
    },
    "Gold Maker": {
        "bat_path": BASE_DIR / "Tearsheet Generator" / "reboot_gold_maker.bat",
        "port": 8075,
        "python_exe": None,
        "health_timeout": 90,
    },
    "Sector Ratio": {
        "bat_path": BASE_DIR / "GSR" / "reboot_gsr.bat",
        "port": 8104,
        "python_exe": None,
    },
    "ES Historical": {
        "bat_path": BASE_DIR / "ES Historical Data" / "reboot_es_historical_data.bat",
        "port": 8081,
        "python_exe": None,
    },
    "Almanac Futures": {
        "bat_path": BASE_DIR / "Almanac Futures" / "reboot_almanac.bat",
        "port": 8105,
        # Launched via reboot_almanac.bat only (.venv13\Scripts\python.exe, port 8105). Avoid
        # launch_python_service here: paths contain spaces and .venv312 is not used for this app.
        "python_exe": None,
    },
    "AGM Allocation": {
        "bat_path": BASE_DIR / "AGM_Allocation" / "reboot_agm_allocation.bat",
        "port": 8511,
        "python_exe": None,
    },
    "AGM CO": {
        "bat_path": BASE_DIR / "AGM CO" / "reboot_agm_co.bat",
        "port": 8512,
        "python_exe": None,
    },
    "AGM Docs": {
        "bat_path": BASE_DIR / "AGM Docs" / "reboot_agm_docs.bat",
        "port": 8513,
        "python_exe": None,
    },
    # CTA Outreach: started via FASTAPI_APPS + NEXTJS_APPS below (not bat, to avoid duplicate launch)
    "BTC Cycle Analysis": {
        "bat_path": BASE_DIR / "BTCAnalysis" / "start_btc_analysis.bat",
        "port": 8801,
        "python_exe": None,
    },
    "BTC Macro Classes": {
        "bat_path": BASE_DIR / "BTCClasses" / "start_btc_classes.bat",
        "port": 8802,
        "python_exe": None,
    },
    "SR3 CVOL Monitor": {
        "bat_path": BASE_DIR / "sr3_claude" / "start_sr3_claude.bat",
        "port": 8701,
        "python_exe": None,
    },
    "SR3 Dashboard": {
        "bat_path": BASE_DIR / "CME-CVOL-IV-Rank-Monitor" / "start_sr3_dashboard.bat",
        "port": 8702,
        "python_exe": None,
    },
}

# Point TKP/TCP/AGM client launchers at the canonical live-deploy runtime.
# Raises DirtyRuntimeRootError if the configured runtime root is the dirty checkout.
try:
    _TEARSHEET_RUNTIME_ROOT = get_runtime_root()
    apply_fleet_bat_overrides(BAT_SERVICES)
except DirtyRuntimeRootError:
    raise
except Exception as _tearsheet_runtime_exc:  # noqa: BLE001 — fail closed for fleet path
    raise RuntimeError(
        f"Failed to resolve tearsheet fleet runtime root: {_tearsheet_runtime_exc}"
    ) from _tearsheet_runtime_exc

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
        "port": 8103,
        "url": "http://localhost:8103",
        "cwd": BASE_DIR / "QuantLab",
        "python_exe": r"C:\Python313\python.exe",
    },
}

# FastAPI Applications
FASTAPI_APPS: Dict[str, Dict] = {
    "Agent Control Center": {
        "script_path": BASE_DIR / "Agent Control Center" / "main.py",
        "port": 8601,
        "url": "http://localhost:8601",
        "cwd": BASE_DIR / "Agent Control Center",
        "python_exe": r"C:\Python310\python.exe",
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
                "remediation": "Install uvicorn and fastapi:\n  C:\\Python310\\python.exe -m pip install uvicorn fastapi"
            },
            {
                "command": "import pkgutil; print('fastapi' in [m.name for m in pkgutil.iter_modules()])",
                "expected": "True",
                "description": "fastapi module check",
                "remediation": "Install fastapi:\n  C:\\Python310\\python.exe -m pip install fastapi"
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
        "port": 8902,
        "url": "http://localhost:8902",
        "cwd": BASE_DIR / "CTA" / "backend",
        "python_exe": r"C:\Python310\python.exe",
        "uvicorn_module": "app.main:app",
    },
}

# Docker Compose Applications
DOCKER_COMPOSE_APPS: Dict[str, Dict] = {
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
        "port": 8110,
        "url": "http://localhost:8110",
    },
    "Order Flow Website": {
        "cwd": BASE_DIR / "Order Flow Website" / "frontend",
        "port": 8012,
        "url": "http://localhost:8012",
    },
    "CTA Outreach": {
        "cwd": BASE_DIR / "CTA" / "frontend",
        "port": 8901,
        "url": "http://localhost:8901",
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
    "TWIFO Sharing": "articles.hcresearch.ltd",
    "TKP Tearsheet": "tkp-ts.hcresearch.ltd",
    "TCP Tearsheet": "tcp-ts.hcresearch.ltd",
    "Y&Q Tearsheet": "yq-ts.hcresearch.ltd",
    "Momentum Pacer Tearsheet": "agm-ts.hcresearch.ltd",
    "Gold Maker": "tgm-ts.hcresearch.ltd",
    "Sector Ratio": "secratio.hcresearch.ltd",
    "ES Historical": "es-historical.hcresearch.ltd",
    "Almanac Futures": "almanac.hcresearch.ltd",
    "AGM Allocation": "agm-allocation.hcresearch.ltd",
    "AGM Docs": "agmdocs.hcresearch.ltd",
    "TS Generator": "ts-generator.hcresearch.ltd",
    "Agent Control Center": "agent-control.hcresearch.ltd",
    "Summary Engine": "summary.hcresearch.ltd",
    "VizLab": "vizlab.hcresearch.ltd",
    "SriPNL": "amf.hcresearch.ltd",
    "CTA Outreach": "ctaout.hcresearch.ltd",
    "CTA Outreach Backend": "ctabackend.hcresearch.ltd",
    "SR3 CVOL Monitor": "sr3-v1.hcresearch.ltd",
    "SR3 Dashboard": "sr3-v2.hcresearch.ltd",
}

# Services to skip opening browser tabs
SKIP_BROWSER_OPEN = {"Summary Engine Backend"}
SKIP_PORTS = {8000, 8001}

