#!/usr/bin/env python3
"""
Purpose: Comprehensive Service Launcher
Author: Kevin Lefebvre
Last Updated: 2026-02-10

Launches all services including:
- .bat file services
- Dash applications (Python)
- Streamlit applications
- FastAPI applications
- Next.js applications
- Docker Compose applications
- Cloudflare Tunnel

Windows-native, handles port conflicts gracefully.

CRITICAL FIXES:
1. No PIPE buffer overflow - all processes use CREATE_NEW_CONSOLE
2. Actual PID tracking - no wrapper PIDs from 'start' command
3. Visible console windows for debugging
4. Robust kill with process tree termination
5. Proper health checks
6. Optimized timeouts to prevent slow launches (Feb 2026)
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

# Import shared utilities
from service_launcher_utils import (
    find_python_executable,
    is_port_available,
    is_port_listening,
    launch_bat_file,
    launch_fastapi_app,
    launch_nextjs_app,
    launch_python_app,
    wait_for_port,
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

# Feature flags
HEALTH_CHECK_ENABLED = False  # Monitor & auto-restart unhealthy services
DAILY_RESTART_ENABLED = True  # Restart TKP/TCP Tearsheet every 24 hours

# Timing configuration
FAIL_THRESHOLD = 2  # Consecutive failures before restart
CHECK_INTERVAL = 15  # Seconds between health checks
LAUNCH_PAUSE = 1  # Seconds pause between launching each service (reduced for speed)
DAILY_RESTART_INTERVAL = 24 * 60 * 60  # 24 hours in seconds (86400) - adjustable as needed
BROWSER_OPEN_DELAY = 3  # Seconds to wait before opening browser (reduced for speed)

# Service configuration
# Services to include in the daily 24h restart loop (same update mechanism for both)
DAILY_RESTART_SERVICES: List[str] = ["TKP Tearsheet", "TCP Tearsheet"]

# Base directory
BASE_DIR = Path(r"C:\Coding Projects")

# ─────────────────────────────────────────────────────────────────────────────
# SERVICE CONFIGURATIONS
# ─────────────────────────────────────────────────────────────────────────────
# Key services (must be started):
#   - TCP Tearsheet (port 8078) — BAT_SERVICES
#   - Summary website (port 3001) — DOCKER_COMPOSE_APPS["Summary Engine"] frontend
#   - Filtered articles (port 8065) — BAT_SERVICES["TWIFO Sharing"]

# .BAT Services
BAT_SERVICES: Dict[str, Path] = {
    "TWIFO Sharing": BASE_DIR / "TWIFO_Sharing" / "reboot_twifo.bat",
    "Import Dropbox": BASE_DIR / "TWIFO_Sharing" / "reboot_import_dropbox.bat",
    "TS Generator": BASE_DIR / "Tearsheet Generator" / "run_tsgen.bat",
    "TKP Tearsheet": BASE_DIR / "Tearsheet Generator" / "reboot_tkp_ts.bat",
    "TCP Tearsheet": BASE_DIR / "Tearsheet Generator" / "reboot_tcp_ts.bat",
    "Y&Q Tearsheet": BASE_DIR / "Tearsheet Generator" / "reboot_yq_ts.bat",
    "Gold Maker": BASE_DIR / "Tearsheet Generator" / "reboot_gold_maker.bat",
    "Sector Ratio": BASE_DIR / "GSR" / "reboot_gsr.bat",
    "ES Historical": BASE_DIR / "ES Historical Data" / "reboot_es_historical_data.bat",
    "Almanac Futures": BASE_DIR / "Almanac Futures" / "reboot_almanac.bat",
    "AGM Allocation": BASE_DIR / "AGM_Allocation" / "reboot_agm_allocation.bat",
    "CTA Outreach": BASE_DIR / "CTA" / "reboot_cta.bat",
}

# Dash Applications (ports 8002-8006)
DASH_APPS: Dict[str, Dict] = {
    "Price Dashboard": {
        "path": BASE_DIR / "Price Dashboard" / "app.py",
        "port": 8002,
        "url": "http://localhost:8002",
        "cwd": BASE_DIR / "Price Dashboard",
        "venv": None,
    },
    "Sector RRG": {
        "path": BASE_DIR / "Sector" / "app_rrg.py",
        "port": 8003,
        "url": "http://localhost:8003",
        "cwd": BASE_DIR / "Sector",
        "venv": None,
    },
    "Strategy Optimizer": {
        "path": BASE_DIR / "StrategyOptimizer" / "app.py",
        "port": 8004,
        "url": "http://localhost:8004",
        "cwd": BASE_DIR / "StrategyOptimizer",
        "venv": None,
    },
    "Home Page": {
        "path": BASE_DIR / "HomePage" / "main.py",
        "port": 8005,
        "url": "http://localhost:8005",
        "cwd": BASE_DIR / "HomePage",
        "venv": BASE_DIR / "HomePage" / ".venv13",
    },
    "Debug Page": {
        "path": BASE_DIR / "HomePage" / "debug.py",
        "port": 8006,
        "url": "http://localhost:8006",
        "cwd": BASE_DIR / "HomePage",
        "venv": BASE_DIR / "HomePage" / ".venv13",
    },
    "SriPNL": {
        "path": BASE_DIR / "SriPNL" / "app.py",
        "port": 7878,
        "url": "http://localhost:7878",
        "cwd": BASE_DIR / "SriPNL",
        "venv": None,
    },
}

# Streamlit Applications (fixed ports)
STREAMLIT_APPS: Dict[str, Dict] = {
    "TWIFO Import Dropbox": {
        "path": BASE_DIR / "TWIFO_Sharing" / "import_dropbox.py",
        "port": 8009,
        "url": "http://localhost:8009",
        "cwd": BASE_DIR / "TWIFO_Sharing",
        "venv": BASE_DIR / "TWIFO_Sharing" / ".venv13",
    },
    "QuantLab Dashboard": {
        "path": BASE_DIR / "QuantLab" / "dashboard" / "app.py",
        "port": 8501,
        "url": "http://localhost:8501",
        "cwd": BASE_DIR / "QuantLab",
        "venv": None,
    },
}

# FastAPI Applications
FASTAPI_APPS: Dict[str, Dict] = {
    "Agent Control Center": {
        "path": BASE_DIR / "Agent Control Center" / "main.py",
        "port": 8007,
        "url": "http://localhost:8007",
        "cwd": BASE_DIR / "Agent Control Center",
        "venv": None,
    },
    "Order Flow Website Backend": {
        "path": BASE_DIR / "Order Flow Website" / "backend" / "app" / "main.py",
        "port": 8000,
        "url": "http://localhost:8000",
        "cwd": BASE_DIR / "Order Flow Website" / "backend",
        "venv": BASE_DIR / "Order Flow Website" / "backend" / ".venv",
    },
    "CTA Outreach Backend": {
        "path": BASE_DIR / "CTA" / "backend" / "app" / "main.py",
        "port": 8010,
        "url": "http://localhost:8010",
        "cwd": BASE_DIR / "CTA" / "backend",
        "venv": None,
    },
}

# Docker Compose Applications
DOCKER_COMPOSE_APPS: Dict[str, Dict] = {
    "Trading Video Library": {
        "path": BASE_DIR / "Trading Video Library" / "docker-compose.yml",
        "ports": [8000, 3003],
        "urls": {
            "backend": "http://localhost:8000",
            "frontend": "http://localhost:3003",
        },
        "cwd": BASE_DIR / "Trading Video Library",
        "services": ["api", "worker", "redis", "web"],
    },
    "Summary Engine": {
        "path": BASE_DIR / "SummaryEngine" / "docker-compose.yml",
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
        "path": BASE_DIR / "VizLab",
        "port": 8011,
        "url": "http://localhost:8011",
        "cwd": BASE_DIR / "VizLab",
        "command": "npm run dev",
    },
    "Order Flow Website": {
        "path": BASE_DIR / "Order Flow Website" / "frontend",
        "port": 8012,
        "url": "http://localhost:8012",
        "cwd": BASE_DIR / "Order Flow Website" / "frontend",
        "command": "npm run dev",
    },
    "CTA Outreach": {
        "path": BASE_DIR / "CTA" / "frontend",
        "port": 3004,
        "url": "http://localhost:3004",
        "cwd": BASE_DIR / "CTA" / "frontend",
        "command": "npm run dev",
    },
}

# Combined Port Map (for health checks)
PORTS: Dict[str, Tuple[str, int]] = {
    "TWIFO Sharing": ("127.0.0.1", 8065),
    "TWIFO Import Dropbox": ("127.0.0.1", 8009),
    "Price Dashboard": ("127.0.0.1", 8002),
    "Sector RRG": ("127.0.0.1", 8003),
    "Strategy Optimizer": ("127.0.0.1", 8004),
    "Home Page": ("127.0.0.1", 8005),
    "Debug Page": ("127.0.0.1", 8006),
    "Agent Control Center": ("127.0.0.1", 8007),
    "Trading Video Library API": ("127.0.0.1", 8000),
    "Trading Video Library": ("127.0.0.1", 3003),
    "Summary Engine": ("127.0.0.1", 3001),
    "Summary Engine Backend": ("127.0.0.1", 8001),
    "Summary Engine Frontend": ("127.0.0.1", 3001),
    "VizLab": ("127.0.0.1", 8011),
    "Order Flow Website Backend": ("127.0.0.1", 8000),
    "Order Flow Website": ("127.0.0.1", 8012),
    "CTA Outreach Backend": ("127.0.0.1", 8010),
    "CTA Outreach": ("127.0.0.1", 3004),
    "TS Generator": ("127.0.0.1", 8077),
    "TKP Tearsheet": ("127.0.0.1", 8076),
    "TCP Tearsheet": ("127.0.0.1", 8078),
    "Y&Q Tearsheet": ("127.0.0.1", 8071),
    "Gold Maker": ("127.0.0.1", 8075),
    "Sector Ratio": ("127.0.0.1", 8080),
    "ES Historical": ("127.0.0.1", 8081),
    "Almanac Futures": ("127.0.0.1", 8072),
    "AGM Allocation": ("127.0.0.1", 1001),
    "QuantLab Dashboard": ("127.0.0.1", 8501),
    "SriPNL": ("127.0.0.1", 7878),
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
SKIP_PORTS = {8000, 8001}  # Backend APIs only, no UI


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL STATE
# ─────────────────────────────────────────────────────────────────────────────

running_processes: Dict[str, subprocess.Popen] = {}
streamlit_ports: Dict[str, int] = {}


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────


def get_log_file(service_name: str) -> Path:
    """Get log file path for a service."""
    log_dir = BASE_DIR / "Manager" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"{service_name.replace(' ', '_')}_launch.log"


def write_launch_log(log_file: Path, service_name: str, details: Dict) -> None:
    """Write launch details to log file."""
    with open(log_file, "w") as f:
        f.write(f"{datetime.now().isoformat()} - Launching {service_name}\n")
        for key, value in details.items():
            f.write(f"{key}: {value}\n")
        f.write("=" * 70 + "\n")


def is_service_healthy(host: str, port: int) -> bool:
    """Check if service is healthy (port is listening)."""
    return is_port_listening(host, port, timeout=5)


# ─────────────────────────────────────────────────────────────────────────────
# SERVICE LAUNCHERS
# ─────────────────────────────────────────────────────────────────────────────


def launch_bat_service(
    name: str, bat_path: Path, diag: bool = False
) -> Optional[subprocess.Popen]:
    """Launch a .bat service with proper PID tracking. diag=True runs with output to log."""
    log_file = get_log_file(name)

    if not bat_path.exists():
        error_msg = f"[ERROR] .bat not found for {name}: {bat_path}"
        print(error_msg)
        with open(log_file, "w") as f:
            f.write(f"{datetime.now().isoformat()} - {error_msg}\n")
        return None

    print(f"[LAUNCH] {name} → {bat_path.name}" + (" (diag mode)" if diag else ""))

    write_launch_log(
        log_file,
        name,
        {
            "Command": str(bat_path),
            "CWD": str(bat_path.parent),
            "Service Name": name,
        },
    )

    process = launch_bat_file(
        str(bat_path), name, diag=diag, diag_log_path=str(log_file) if diag else None
    )

    if process:
        if diag:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"Diag exit code: {process.returncode}\n")
            print(f"[OK] {name} diag finished (exit code: {process.returncode}). Check log: {log_file}")
            return process
        time.sleep(1)
        if process.poll() is not None:
            with open(log_file, "a") as f:
                f.write(f"ERROR: Process terminated immediately (exit code: {process.poll()})\n")
            print(f"[ERROR] {name} terminated immediately (exit code: {process.poll()})")
            print(f"[INFO] Check the console window for {name} for error details")
            return None

        with open(log_file, "a") as f:
            f.write(f"Process started - PID: {process.pid}\n")
            f.write(
                f"Exit code: {process.poll() if process.poll() is not None else 'Running'}\n"
            )
        print(f"[OK] {name} launched (PID: {process.pid}, log: {log_file})")
    else:
        with open(log_file, "a") as f:
            f.write("ERROR: Process failed to start\n")
        print(f"[ERROR] {name} failed to launch (log: {log_file})")

    return process


def launch_dash_app(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """Launch a Dash application with proper console output."""
    log_file = get_log_file(name)

    app_path = config["path"]
    port = config["port"]
    url = config["url"]
    cwd = config["cwd"]
    venv = config.get("venv")

    if not app_path.exists():
        error_msg = f"[ERROR] Dash app not found for {name}: {app_path}"
        print(error_msg)
        with open(log_file, "w") as f:
            f.write(f"{datetime.now().isoformat()} - {error_msg}\n")
        return None

    if not is_port_available("127.0.0.1", port):
        print(f"[WARN] Port {port} already in use for {name}, attempting anyway...")

    print(f"[LAUNCH] {name} (Dash) → {app_path.name} on port {port}")

    write_launch_log(
        log_file,
        f"{name} (Dash)",
        {
            "Script": str(app_path),
            "Port": port,
            "URL": url,
            "CWD": str(cwd),
            "Venv": str(venv) if venv else "System Python",
        },
    )

    process = launch_python_app(
        script_path=str(app_path),
        service_name=name,
        port=port,
        venv_path=str(venv) if venv else None,
    )

    if process:
        process._service_url = url
        process._service_name = name
        with open(log_file, "a") as f:
            f.write(f"Process started - PID: {process.pid}\n")
            f.write(
                f"Exit code: {process.poll() if process.poll() is not None else 'Running'}\n"
            )
        print(f"[OK] {name} launched (PID: {process.pid}, log: {log_file})")
    else:
        with open(log_file, "a") as f:
            f.write("ERROR: Process failed to start\n")
        print(f"[ERROR] {name} failed to launch (log: {log_file})")

    return process


def launch_streamlit_app(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """Launch a Streamlit application with fixed port."""
    app_path = config["path"]
    port = config["port"]
    url = config["url"]
    cwd = config["cwd"]
    venv = config.get("venv")

    if not app_path.exists():
        print(f"[ERROR] Streamlit app not found for {name}: {app_path}")
        return None

    python_exe = find_python_executable(venv)

    if not is_port_available("127.0.0.1", port):
        print(f"[WARN] Port {port} is already in use for {name}!")
        print(f"[WARN] The app may fail to start or use a different port.")

    print(f"[LAUNCH] {name} (Streamlit) → {app_path.name} on FIXED port {port}")

    rel_path = (
        app_path.relative_to(cwd) if app_path.is_relative_to(cwd) else app_path
    )
    streamlit_cmd = [
        python_exe,
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
    ]

    launch_log_file = get_log_file(name)
    streamlit_log_file = cwd / f"{name.replace(' ', '_')}_streamlit.log"

    write_launch_log(
        launch_log_file,
        f"{name} (Streamlit)",
        {
            "Script": str(app_path),
            "Port": f"{port} (FIXED)",
            "URL": url,
            "CWD": str(cwd),
            "Python": python_exe,
            "Venv": str(venv) if venv else "System Python",
            "Streamlit Log": str(streamlit_log_file),
        },
    )

    try:
        with open(streamlit_log_file, "w") as log:
            process = subprocess.Popen(
                streamlit_cmd,
                cwd=str(cwd),
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                if sys.platform == "win32"
                else 0,
            )

        time.sleep(2)

        if process.poll() is not None:
            try:
                with open(streamlit_log_file, "r") as f:
                    error_msg = f.read()[-500:]
                print(
                    f"[ERROR] {name} failed to start. Check logs: {launch_log_file}, {streamlit_log_file}"
                )
                print(f"[ERROR] Last log output: {error_msg[-200:]}")
                with open(launch_log_file, "a") as f:
                    f.write(f"ERROR: Process exited immediately\n")
                    f.write(f"Exit code: {process.poll()}\n")
                    f.write(f"Last streamlit log: {error_msg[-200:]}\n")
            except Exception:
                print(
                    f"[ERROR] {name} failed to start. Check logs: {launch_log_file}, {streamlit_log_file}"
                )
                with open(launch_log_file, "a") as f:
                    f.write(f"ERROR: Process exited immediately\n")
                    f.write(f"Exit code: {process.poll()}\n")
            return None

        process._service_url = url
        process._service_name = name
        streamlit_ports[name] = port

        with open(launch_log_file, "a") as f:
            f.write(f"Process started - PID: {process.pid}\n")
            f.write(
                f"Exit code: {process.poll() if process.poll() is not None else 'Running'}\n"
            )
            f.write(f"Streamlit log: {streamlit_log_file}\n")
        print(
            f"[OK] {name} process started (PID: {process.pid}, logs: {launch_log_file}, {streamlit_log_file})"
        )
        return process
    except Exception as e:
        print(f"[ERROR] Failed to launch {name}: {e}")
        import traceback

        traceback.print_exc()
        return None


def launch_fastapi_app_wrapper(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """Launch a FastAPI application with proper console output."""
    log_file = get_log_file(name)

    app_path = config["path"]
    port = config["port"]
    url = config["url"]
    cwd = config["cwd"]
    venv = config.get("venv")

    if not app_path.exists():
        error_msg = f"[ERROR] FastAPI app not found for {name}: {app_path}"
        print(error_msg)
        with open(log_file, "w") as f:
            f.write(f"{datetime.now().isoformat()} - {error_msg}\n")
        return None

    if not is_port_available("127.0.0.1", port):
        print(f"[WARN] Port {port} already in use for {name}, attempting anyway...")

    print(f"[LAUNCH] {name} (FastAPI) → {app_path.name} on port {port}")

    write_launch_log(
        log_file,
        f"{name} (FastAPI)",
        {
            "Main File": str(app_path),
            "Port": port,
            "URL": url,
            "CWD": str(cwd),
            "Venv": str(venv) if venv else "System Python",
        },
    )

    # Determine uvicorn module path
    if "Agent Control Center" in name:
        uvicorn_module = "main:app"
    else:
        uvicorn_module = "app.main:app" if "app" in str(app_path.parent) else "main:app"

    process = launch_fastapi_app(
        main_file_path=str(app_path),
        service_name=name,
        port=port,
        working_dir=str(cwd),
        uvicorn_module=uvicorn_module,
        venv_path=str(venv) if venv else None,
    )

    if process:
        process._service_url = url
        process._service_name = name
        with open(log_file, "a") as f:
            f.write(f"Process started - PID: {process.pid}\n")
            f.write(
                f"Exit code: {process.poll() if process.poll() is not None else 'Running'}\n"
            )
        print(f"[OK] {name} launched (PID: {process.pid}, log: {log_file})")
    else:
        with open(log_file, "a") as f:
            f.write("ERROR: Process failed to start\n")
        print(f"[ERROR] {name} failed to launch (log: {log_file})")

    return process


def launch_nextjs_app_wrapper(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """Launch a Next.js application with proper PID tracking."""
    log_file = get_log_file(name)

    app_path = config["path"]
    port = config["port"]
    url = config["url"]
    cwd = config["cwd"]

    if not app_path.exists():
        error_msg = f"[ERROR] Next.js app directory not found for {name}: {app_path}"
        print(error_msg)
        with open(log_file, "w") as f:
            f.write(f"{datetime.now().isoformat()} - {error_msg}\n")
        return None

    if not is_port_available("127.0.0.1", port):
        print(f"[WARN] Port {port} already in use for {name}, attempting anyway...")

    print(f"[LAUNCH] {name} (Next.js) → port {port}")

    write_launch_log(
        log_file,
        f"{name} (Next.js)",
        {
            "App Directory": str(app_path),
            "Port": port,
            "URL": url,
            "CWD": str(cwd),
            "Command": config.get("command", "npm run dev"),
        },
    )

    process = launch_nextjs_app(app_dir=str(cwd), service_name=name, port=port)

    if process:
        process._service_url = url
        process._service_name = name
        with open(log_file, "a") as f:
            f.write(f"Process started - PID: {process.pid}\n")
            f.write(
                f"Exit code: {process.poll() if process.poll() is not None else 'Running'}\n"
            )
        print(f"[OK] {name} launched (PID: {process.pid}, log: {log_file})")
    else:
        with open(log_file, "a") as f:
            f.write("ERROR: Process failed to start\n")
        print(f"[ERROR] {name} failed to launch (log: {log_file})")

    return process


# ─────────────────────────────────────────────────────────────────────────────
# DOCKER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────


def open_docker_desktop() -> bool:
    """Open Docker Desktop application on Windows using multiple fallback methods."""
    try:
        docker_paths = [
            r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
            os.path.expanduser(r"~\AppData\Local\Docker\Docker Desktop.exe"),
            r"C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe",
        ]

        for path in docker_paths:
            expanded_path = os.path.expandvars(os.path.expanduser(path))
            if os.path.exists(expanded_path):
                try:
                    os.startfile(expanded_path)
                    print(f"[OK] Opened Docker Desktop: {expanded_path}")
                    return True
                except Exception as e:
                    print(f"[WARN] os.startfile() failed: {e}")

        # Fallback methods
        for method_name, method_func in [
            ("start command", lambda: subprocess.Popen(
                'start "" "Docker Desktop"', shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )),
            ("PowerShell", lambda: subprocess.run(
                ["powershell", "-Command", 'Start-Process "Docker Desktop" -ErrorAction SilentlyContinue'],
                timeout=5, capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )),
            ("protocol handler", lambda: subprocess.Popen(
                'start docker-desktop://', shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )),
        ]:
            try:
                method_func()
                print(f"[OK] Attempted to start Docker Desktop via {method_name}")
                return True
            except Exception:
                continue

        print("[ERROR] All methods to open Docker Desktop failed")
        return False
    except Exception as e:
        print(f"[ERROR] Error opening Docker Desktop: {e}")
        return False


def check_docker_available(auto_start: bool = True) -> Tuple[bool, str]:
    """Check if Docker is installed and running. Optionally start Docker Desktop."""
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout.strip():
            return True, f"Docker {result.stdout.strip()}"

        error_detail = result.stderr.strip() if result.stderr else "Unknown error"
        if "Cannot connect" in error_detail or "error during connect" in error_detail:
            if auto_start:
                print("[INFO] Docker Desktop is not running. Attempting to start it...")
                if open_docker_desktop():
                    print("[INFO] Docker Desktop launch command executed. Waiting...")
                    time.sleep(5)
                    for attempt in range(6):
                        time.sleep(5)
                        retry_result = subprocess.run(
                            ["docker", "version", "--format", "{{.Server.Version}}"],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        if retry_result.returncode == 0 and retry_result.stdout.strip():
                            return True, f"Docker {retry_result.stdout.strip()} (started automatically)"
                    return False, "Docker Desktop did not start within 30 seconds"
                else:
                    return False, "Docker Desktop failed to start automatically"
            else:
                return False, "Docker Desktop is not running"

        return False, f"Docker command failed: {error_detail}"

    except FileNotFoundError:
        return False, "Docker command not found. Is Docker Desktop installed?"
    except subprocess.TimeoutExpired:
        return False, "Docker command timed out"
    except Exception as e:
        return False, f"Docker check failed: {str(e)}"


def launch_docker_compose_app(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """Launch a Docker Compose application."""
    compose_file = config["path"]
    cwd = config["cwd"]
    ports = config.get("ports", [])

    if not compose_file.exists():
        print(f"[ERROR] Docker Compose file not found for {name}: {compose_file}")
        return None

    for port in ports:
        if not is_port_available("127.0.0.1", port):
            print(f"[WARN] Port {port} already in use for {name}")

    print(f"[LAUNCH] {name} (Docker Compose) → {compose_file.name}")

    compose_cmd = ["docker", "compose", "-f", str(compose_file), "up", "-d", "--build"]
    log_file = cwd / f"{name.replace(' ', '_')}_docker.log"

    try:
        # Use subprocess.run to capture exit code (fail fast)
        try:
            result = subprocess.run(
                compose_cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
        except FileNotFoundError:
            print("[INFO] 'docker compose' not found, trying 'docker-compose'...")
            compose_cmd[0:2] = ["docker-compose"]
            result = subprocess.run(
                compose_cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            print(f"[ERROR] {name} Docker Compose build timed out after 5 minutes")
            print(f"[ERROR] Check Docker logs and network connectivity")
            return None

        # Write output to log file
        with open(log_file, "w") as log:
            log.write(result.stdout)
            if result.stderr:
                log.write("\n--- STDERR ---\n")
                log.write(result.stderr)

        # Check exit code - fail fast if build failed
        if result.returncode != 0:
            print(f"[ERROR] {name} Docker Compose build failed (exit code: {result.returncode})")
            print(f"[ERROR] Check log: {log_file}")
            
            # Show last 500 chars of output for quick diagnosis
            error_output = (result.stdout + result.stderr)[-500:]
            if error_output:
                print(f"[ERROR] Last output:\n{error_output}")
            
            # Provide recovery instructions for common TLS timeout error
            if "TLS handshake timeout" in result.stdout or "TLS handshake timeout" in result.stderr:
                print(f"\n[RECOVERY] TLS handshake timeout detected. Try these commands:")
                print(f"  cd {cwd}")
                print(f"  docker compose -f {compose_file.name} pull web")
                print(f"  docker compose -f {compose_file.name} build --no-cache web")
                print(f"  docker compose -f {compose_file.name} up -d web")
                print(f"\n[INFO] Alternative: Use Docker Desktop registry mirror settings")
                print(f"  or set DOCKERHUB_MIRROR environment variable")
            
            return None

        # Build succeeded - start detached process for monitoring
        process = subprocess.Popen(
            ["docker", "compose", "-f", str(compose_file), "ps"],
            cwd=str(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        process._service_url = config.get("urls", {}).get(
            "frontend", config.get("urls", {}).get("backend", "")
        )
        process._service_name = name
        process._docker_ports = ports
        process._docker_urls = config.get("urls", {})

        print(f"[OK] {name} Docker Compose started successfully (log: {log_file})")

        if "Summary Engine" in name:
            print(
                f"[INFO] Note: If first run, seed database with: docker compose -f {compose_file} exec backend python scripts/seed_db.py"
            )
        elif "Trading Video Library" in name:
            print(f"[INFO] Trading Video Library: API on port 8000, Frontend on port 3003")

        return process
    except FileNotFoundError:
        print(f"[ERROR] docker/docker-compose command not found. Is Docker installed?")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to launch {name}: {e}")
        import traceback

        traceback.print_exc()
        return None


# ─────────────────────────────────────────────────────────────────────────────
# BROWSER & MONITORING
# ─────────────────────────────────────────────────────────────────────────────


def detect_streamlit_port(name: str, expected_port: int, max_wait: int = 10) -> Optional[int]:
    """Verify Streamlit is running on expected port."""
    for _ in range(max_wait):
        if is_service_healthy("127.0.0.1", expected_port):
            return expected_port
        time.sleep(0.5)
    return None


def open_browser_tabs(services: Dict[str, subprocess.Popen]) -> None:
    """Open browser tabs for all web services after a delay."""
    print(f"\n[INFO] Waiting {BROWSER_OPEN_DELAY}s for services to start, then opening browsers...\n")
    time.sleep(BROWSER_OPEN_DELAY)

    urls_to_open = []

    for name, process in services.items():
        if not hasattr(process, "_service_url"):
            continue

        if name in SKIP_BROWSER_OPEN:
            continue

        url = process._service_url
        if any(f":{port}" in url for port in SKIP_PORTS):
            continue

        if name in STREAMLIT_APPS:
            expected_port = STREAMLIT_APPS[name]["port"]
            actual_port = detect_streamlit_port(name, expected_port)
            if actual_port:
                url = f"http://localhost:{actual_port}"
                if actual_port not in SKIP_PORTS:
                    urls_to_open.append((name, url))
                    streamlit_ports[name] = actual_port
            elif expected_port not in SKIP_PORTS:
                urls_to_open.append((name, process._service_url))
        elif name in DOCKER_COMPOSE_APPS and hasattr(process, "_docker_urls"):
            frontend_url = process._docker_urls.get("frontend")
            if frontend_url:
                urls_to_open.append((name, frontend_url))
        else:
            urls_to_open.append((name, process._service_url))

    if urls_to_open:
        print(f"[INFO] Opening {len(urls_to_open)} browser tabs...")
        for name, url in urls_to_open:
            try:
                webbrowser.open(url)
                print(f"  ✓ Opened {name}: {url}")
                time.sleep(0.5)
            except Exception as e:
                print(f"  ✗ Failed to open {name}: {e}")
    else:
        print("[WARN] No web service URLs found to open")


def save_service_registry(services: Dict[str, subprocess.Popen]) -> None:
    """Save service registry to JSON for reference."""
    registry = {"launched_at": datetime.now().isoformat(), "services": {}}

    for name, process in services.items():
        if name == "_tunnel_manager":
            continue

        service_info = {
            "name": name,
            "pid": process.pid if process else None,
            "type": "unknown",
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

        if hasattr(process, "_service_url"):
            service_info["url"] = process._service_url

        registry["services"][name] = service_info

    registry_file = BASE_DIR / "Manager" / "service_registry.json"
    registry_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(registry_file, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, default=str)
        print(f"[INFO] Service registry saved to: {registry_file}")
    except Exception as e:
        print(f"[WARN] Failed to save service registry: {e}")


def check_health(fail_counts: Dict[str, int]) -> List[str]:
    """Check each service health. Return list of services to restart."""
    to_restart = []
    for name, (host, port) in PORTS.items():
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


def restart_services(
    service_names: List[str],
    all_services: Dict[str, subprocess.Popen],
    fail_counts: Dict[str, int]
) -> None:
    """Restart specified services by killing and relaunching them."""
    for name in service_names:
        print(f"[INFO] Restarting {name}...")
        
        # Kill the existing process if it exists
        if name in all_services:
            process = all_services[name]
            if process and process.poll() is None:  # Process is still running
                print(f"[INFO] Killing {name} (PID: {process.pid})...")
                if kill_process_tree(process.pid):
                    print(f"[OK] Killed {name}")
                    time.sleep(2)  # Wait for cleanup
                else:
                    print(f"[WARN] Failed to kill {name}, proceeding anyway...")
            
            # Remove from services dict
            del all_services[name]
        
        # Reset fail count
        if name in fail_counts:
            fail_counts[name] = 0
        
        # Relaunch the service
        if name in BAT_SERVICES:
            bat_path = BAT_SERVICES[name]
            process = launch_bat_service(name, bat_path)
            if process:
                all_services[name] = process
                print(f"[OK] Relaunched {name} (PID: {process.pid})")
                
                # Wait for service to start if it has a known port
                if name in PORTS:
                    host, port = PORTS[name]
                    print(f"[INFO] Waiting for {name} to bind to port {port}...")
                    if wait_for_port(host, port, timeout=15):
                        print(f"[OK] {name} is now listening on port {port}")
                    else:
                        print(f"[WARN] {name} did not start listening on port {port} within 15s")
            else:
                print(f"[ERROR] Failed to relaunch {name}")
        
        elif name in DASH_APPS:
            config = DASH_APPS[name]
            process = launch_dash_app(name, config)
            if process:
                all_services[name] = process
                port = config["port"]
                print(f"[OK] Relaunched {name} (PID: {process.pid})")
                print(f"[INFO] Waiting for {name} to bind to port {port}...")
                if wait_for_port("127.0.0.1", port, timeout=15):
                    print(f"[OK] {name} is now listening on port {port}")
                else:
                    print(f"[WARN] {name} did not start listening on port {port} within 15s")
            else:
                print(f"[ERROR] Failed to relaunch {name}")
        
        elif name in STREAMLIT_APPS:
            config = STREAMLIT_APPS[name]
            process = launch_streamlit_app(name, config)
            if process:
                all_services[name] = process
                port = config["port"]
                print(f"[OK] Relaunched {name} (PID: {process.pid})")
            else:
                print(f"[ERROR] Failed to relaunch {name}")
        
        else:
            print(f"[WARN] Unknown service type for {name}, cannot restart")
        
        time.sleep(LAUNCH_PAUSE)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN LAUNCHER
# ─────────────────────────────────────────────────────────────────────────────


def launch_all_services() -> Tuple[Dict[str, subprocess.Popen], Dict[str, int]]:
    """Launch all services and return running processes and fail counts."""
    all_services: Dict[str, subprocess.Popen] = {}
    failed_services: List[str] = []
    fail_counts = {
        name: 0
        for name in list(BAT_SERVICES.keys())
        + list(DASH_APPS.keys())
        + list(STREAMLIT_APPS.keys())
        + list(FASTAPI_APPS.keys())
        + list(DOCKER_COMPOSE_APPS.keys())
        + list(NEXTJS_APPS.keys())
    }

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
    
    # Define critical services that MUST bind to ports (wait for these)
    CRITICAL_BAT_SERVICES = {"TWIFO Sharing", "TS Generator"}
    
    for name, bat_path in BAT_SERVICES.items():
        process = launch_bat_service(name, bat_path)
        if process:
            all_services[name] = process
            # Only wait for critical services with known ports
            if name in CRITICAL_BAT_SERVICES and name in PORTS:
                host, port = PORTS[name]
                print(f"[INFO] Waiting for {name} to bind to port {port}...")
                if wait_for_port(host, port, timeout=15):
                    print(f"[OK] {name} is now listening on port {port}")
                else:
                    print(f"[WARN] {name} did not start listening on port {port} within 15s")
                    failed_services.append(f"{name} (port not listening)")
            elif name in PORTS:
                # Non-critical services: just check once after a brief delay
                host, port = PORTS[name]
                time.sleep(2)
                if is_port_listening(host, port, timeout=1.0):
                    print(f"[OK] {name} is listening on port {port}")
                else:
                    print(f"[INFO] {name} may still be starting on port {port} (not waiting)")
        else:
            failed_services.append(name)
        time.sleep(LAUNCH_PAUSE)

    print()

    # Phase 2: Launch Dash applications
    print("[PHASE 2] Launching Dash applications...")
    for name, config in DASH_APPS.items():
        process = launch_dash_app(name, config)
        if process:
            all_services[name] = process
            port = config["port"]
            # Dash apps typically start quickly
            if wait_for_port("127.0.0.1", port, timeout=8):
                print(f"[OK] {name} is now listening on port {port}")
            else:
                print(f"[WARN] {name} did not start listening on port {port} within 8s")
                print(f"[INFO] Check console window for {name} for errors")
                # Don't mark as failed - service may still start
        else:
            failed_services.append(name)
        time.sleep(LAUNCH_PAUSE)

    print()

    # Phase 3: Launch Streamlit applications
    print("[PHASE 3] Launching Streamlit applications...")
    for name, config in STREAMLIT_APPS.items():
        process = launch_streamlit_app(name, config)
        if process:
            all_services[name] = process
            print(f"[OK] {name} launched successfully")
        else:
            print(f"[ERROR] Failed to launch {name} via Streamlit")
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

    # Phase 3.5: Launch FastAPI applications
    print("[PHASE 3.5] Launching FastAPI applications...")
    for name, config in FASTAPI_APPS.items():
        process = launch_fastapi_app_wrapper(name, config)
        if process:
            all_services[name] = process
            port = config["port"]
            # FastAPI/Uvicorn starts quickly
            if wait_for_port("127.0.0.1", port, timeout=10):
                print(f"[OK] {name} is now listening on port {port}")
            else:
                print(f"[WARN] {name} did not start listening on port {port} within 10s")
                log_path = BASE_DIR / "Manager" / "logs" / f"{name.replace(' ', '_')}_launch.log"
                print(f"[INFO] Check console window for errors or check log: {log_path}")
                # Don't mark as failed - service may still be starting
        else:
            failed_services.append(name)
        time.sleep(LAUNCH_PAUSE)

    print()

    # Phase 3.6: Launch Docker Compose applications
    print("[PHASE 3.6] Launching Docker Compose applications...")
    docker_available = True
    if DOCKER_COMPOSE_APPS:
        docker_available, docker_info = check_docker_available()
        if docker_available:
            print(f"[OK] {docker_info} - Ready for Docker Compose services")
        else:
            print(f"[ERROR] {docker_info}")
            print(
                f"[WARN] Skipping {len(DOCKER_COMPOSE_APPS)} Docker Compose service(s). "
                "Summary Engine and Trading Video Library require Docker Desktop to be running."
            )
            for name in DOCKER_COMPOSE_APPS.keys():
                failed_services.append(f"{name} (Docker not available)")
            print()

    for name, config in DOCKER_COMPOSE_APPS.items():
        if not docker_available:
            continue
        process = launch_docker_compose_app(name, config)
        if process:
            all_services[name] = process
            ports = config.get("ports", [])
            print(f"[INFO] Waiting for {name} services to start (15-45 seconds for first build)...")
            # Give containers time to bind after docker compose up -d
            time.sleep(5)

            backend_ports = [p for p in ports if 8000 <= p < 9000]
            frontend_ports = [p for p in ports if 3000 <= p < 4000]

            port_failed = False
            # Reduced timeout for backend (API typically starts fast)
            for port in backend_ports:
                if wait_for_port("127.0.0.1", port, timeout=30):
                    print(f"[OK] {name} API is now listening on port {port}")
                else:
                    print(f"[WARN] {name} API did not start listening on port {port} within 30s")
                    print(f"[INFO] Check Docker logs: docker compose -f {config['path']} logs")
                    # Don't mark as failed immediately

            # Frontend needs more time for build
            for port in frontend_ports:
                if wait_for_port("127.0.0.1", port, timeout=45):
                    print(f"[OK] {name} Frontend is now listening on port {port}")
                else:
                    print(f"[WARN] {name} Frontend did not start listening on port {port} within 45s")
                    print(f"[INFO] Check Docker logs: docker compose -f {config['path']} logs web")
                    # Don't mark as failed - may still be building
        else:
            failed_services.append(name)
        time.sleep(LAUNCH_PAUSE)

    print()

    # Phase 3.7: Launch Next.js applications
    print("[PHASE 3.7] Launching Next.js applications...")
    for name, config in NEXTJS_APPS.items():
        process = launch_nextjs_app_wrapper(name, config)
        if process:
            all_services[name] = process
            port = config["port"]
            print(f"[INFO] Waiting for {name} to compile and start (15-30 seconds)...")
            # Next.js dev server with hot reload
            if wait_for_port("127.0.0.1", port, timeout=30):
                print(f"[OK] {name} is now listening on port {port}")
            else:
                print(f"[WARN] {name} did not start listening on port {port} within 30s")
                print(f"[INFO] Check the {name} console window - may still be compiling")
                # Don't mark as failed
        else:
            failed_services.append(name)
        time.sleep(LAUNCH_PAUSE)

    print()

    # Phase 4: Launch Cloudflare Tunnel
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

    # Phase 5: Open browser tabs
    open_browser_tabs(all_services)

    # Phase 6: Save service registry
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
        print(f"[INFO] Check logs in: {BASE_DIR / 'Manager' / 'logs'}")
        print(f"[INFO] Check console windows for real-time error messages")
    else:
        print(f"[OK] All services launched successfully")
    print(f"[INFO] Browser tabs opened for web services")
    print(f"[INFO] Services are running in background")
    
    # Verify which services are actually listening
    print(f"\n[INFO] Verifying service ports...")
    listening_services = []
    not_listening_services = []
    
    for name in all_services.keys():
        if name == "_tunnel_manager":
            continue
        if name in PORTS:
            host, port = PORTS[name]
            if is_port_listening(host, port, timeout=1.0):
                listening_services.append((name, port))
            else:
                not_listening_services.append((name, port))
    
    if listening_services:
        print(f"[OK] {len(listening_services)} service(s) confirmed listening:")
        for name, port in listening_services:
            print(f"  ✓ {name} (port {port})")
    
    if not_listening_services:
        print(f"\n[WARN] {len(not_listening_services)} service(s) not yet listening:")
        for name, port in not_listening_services:
            print(f"  ✗ {name} (port {port}) - check console window for errors")

    # Print service URLs
    print(f"\n[INFO] Service URLs (Local):")
    for name, process in all_services.items():
        if name == "_tunnel_manager":
            continue
        if name in DOCKER_COMPOSE_APPS and hasattr(process, "_docker_urls"):
            urls = process._docker_urls
            if "frontend" in urls:
                print(f"  • {name} Frontend: {urls['frontend']}")
            if "backend" in urls:
                print(f"  • {name} Backend: {urls['backend']}")
        elif hasattr(process, "_service_url"):
            url = (
                f"http://localhost:{streamlit_ports[name]}"
                if name in streamlit_ports
                else process._service_url
            )
            print(f"  • {name}: {url}")

    # Print Cloudflare domains
    if tunnel_manager and tunnel_manager.is_running():
        print(f"\n[INFO] Service URLs (Cloudflare):")
        for name, domain in CLOUDFLARE_DOMAINS.items():
            if name in all_services:
                print(f"  • {name}: https://{domain}")

    print()

    return all_services, fail_counts


def main() -> None:
    """Main launcher function."""
    print(f"\n[INFO] HEALTH_CHECK_ENABLED  = {HEALTH_CHECK_ENABLED}")
    print(f"[INFO] DAILY_RESTART_ENABLED = {DAILY_RESTART_ENABLED}\n")

    all_services, fail_counts = launch_all_services()

    tunnel_manager = all_services.get("_tunnel_manager")

    if not HEALTH_CHECK_ENABLED and not DAILY_RESTART_ENABLED:
        print("[INFO] No monitoring or daily restart enabled.")
        print("[INFO] Services are running. Press Ctrl+C to exit.\n")
        print("[INFO] To stop services, close their windows or use Task Manager.\n")

        try:
            while True:
                time.sleep(60)
                print(f"\n[STATUS] {datetime.now().strftime('%H:%M:%S')} - Services still running...")
        except KeyboardInterrupt:
            print("\n[INFO] Shutdown requested. Services continue running in background.\n")
        return

    last_daily_restart = time.time()

    try:
        while True:
            time.sleep(CHECK_INTERVAL)

            if HEALTH_CHECK_ENABLED:
                to_restart = check_health(fail_counts)
                if to_restart:
                    print(f"\n[WARN] Restarting failed services: {', '.join(to_restart)}\n")
                    restart_services(to_restart, all_services, fail_counts)
                else:
                    warnings = [n for n, c in fail_counts.items() if 0 < c < FAIL_THRESHOLD]
                    if warnings:
                        print(f"\n[WARN] Services warning: {', '.join(warnings)}\n")
                    else:
                        print("\n[OK] All services healthy — continuing to monitor.\n")

            if DAILY_RESTART_ENABLED:
                now = time.time()
                if now - last_daily_restart >= DAILY_RESTART_INTERVAL:
                    print(f"\n[INFO] 24h elapsed — restarting: {', '.join(DAILY_RESTART_SERVICES)}\n")
                    restart_services(DAILY_RESTART_SERVICES, all_services, fail_counts)
                    last_daily_restart = now

    except KeyboardInterrupt:
        print("\n[INFO] Shutdown requested by user.")

        if tunnel_manager:
            tunnel_manager.stop_tunnel()

        print("[INFO] Services continue running in background.")
        print("[INFO] Close service windows or use Task Manager to stop them.\n")


def open_docker_desktop_gui() -> bool:
    """Standalone function to open Docker Desktop GUI window."""
    print("[INFO] Opening Docker Desktop GUI...")
    success = open_docker_desktop()
    if success:
        print("[OK] Docker Desktop GUI launch command executed")
    else:
        print("[ERROR] Failed to open Docker Desktop GUI")
    return success


def launch_only_bat(service_name: str, diag: bool = False) -> None:
    """Launch a single BAT service by name (for quick testing). diag=True redirects to *_launch.log."""
    if service_name not in BAT_SERVICES:
        print(f"[ERROR] Unknown BAT service: {service_name}")
        print(f"[INFO] Available: {', '.join(BAT_SERVICES.keys())}")
        sys.exit(1)

    bat_path = BAT_SERVICES[service_name]
    print(f"\n[INFO] --only mode: launching '{service_name}' only" + (" (diag)" if diag else "") + "\n")
    process = launch_bat_service(service_name, bat_path, diag=diag)
    if process:
        if diag:
            log_file = get_log_file(service_name)
            print(f"[INFO] Check log for CWD/dir/RUNNING/EXITCODE: {log_file}")
            return
        print(f"\n[OK] {service_name} launched (PID: {process.pid})")
        if service_name in PORTS:
            host, port = PORTS[service_name]
            print(f"[INFO] Waiting for {service_name} to bind to port {port}...")
            if wait_for_port(host, port, timeout=15):
                print(f"[OK] {service_name} is listening on port {port}")
            else:
                print(f"[WARN] {service_name} not listening on port {port} within 15s")
    else:
        print(f"\n[ERROR] {service_name} failed to launch")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--open-docker":
        open_docker_desktop_gui()
        sys.exit(0)
    if len(sys.argv) > 2 and sys.argv[1] == "--only":
        diag = "--diag" in sys.argv
        launch_only_bat(sys.argv[2], diag=diag)
        sys.exit(0)
    main()
