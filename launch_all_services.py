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

CRITICAL FEATURES (May 2026):
1. Per service python_exe enforcement (no PATH python)
2. Preflight checks for dependencies (uvicorn, sqlalchemy, etc)
3. Stdout and stderr piped to timestamped log files
4. Health checks via port polling
5. Smart early-exit detection with grace period (handles Flask reloader,
   uvicorn --reload, and other self-detaching wrappers correctly)
6. New visible console windows spawned via Windows `start "Title" cmd /k ...`
   pattern instead of CREATE_NEW_CONSOLE — required for Flask debug-mode
   services so the wrapper does not collapse before python binds the port
7. Actual PID tracking, no wrapper PIDs
8. Visible console windows for debugging (cmd /k keeps them readable)
9. Robust kill with process tree termination
10. Within each phase, services start in parallel (ThreadPoolExecutor)
    when PARALLEL_LAUNCH_ENABLED is True
11. Per-service `health_timeout` config so slow tearsheets get more wait
"""

import json
import os
import subprocess
import sys
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import psutil  # For memory monitoring

# Import configuration and utilities
from service_config import (
    BASE_DIR,
    LOGS_DIR,
    HEALTH_CHECK_ENABLED,
    DAILY_RESTART_ENABLED,
    MEMORY_CHECK_ENABLED,
    MEMORY_THRESHOLD_GB,
    LAUNCH_PAUSE,
    PHASE_PAUSE,
    BROWSER_OPEN_DELAY,
    PARALLEL_LAUNCH_ENABLED,
    PARALLEL_MAX_WORKERS,
    BAT_SERVICES,
    DASH_APPS,
    STREAMLIT_APPS,
    FASTAPI_APPS,
    DOCKER_COMPOSE_APPS,
    NEXTJS_APPS,
    is_port_listening,
    wait_for_port,
    get_log_file,
    read_last_lines,
    run_preflight_check,
)

# Import Cloudflare Tunnel Manager
try:
    from cloudflare_tunnel_manager import get_tunnel_manager

    CLOUDFLARE_AVAILABLE = True
except ImportError:
    CLOUDFLARE_AVAILABLE = False
    print("[WARN] Cloudflare Tunnel Manager not available")


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL STATE
# ─────────────────────────────────────────────────────────────────────────────

running_processes: Dict[str, subprocess.Popen] = {}
service_logs: Dict[str, Path] = {}

# Service Dashboard (debug.py sites[]) display name -> launcher registry key(s).
# Keys: BAT:, DASH:, STREAMLIT:, FASTAPI:, DOCKER:, NEXTJS: + name in service_config.
DEBUG_SITE_LAUNCH_TARGETS: Dict[str, List[str]] = {
    "AGM Allocation": ["BAT:AGM Allocation"],
    "AGM CO": ["BAT:AGM CO"],
    "AGM Docs": ["BAT:AGM Docs"],
    "Agent Control Center": ["FASTAPI:Agent Control Center"],
    "Almanac": ["BAT:Almanac Futures"],
    "BTC Cycle Analysis": ["BAT:BTC Cycle Analysis"],
    "BTC Macro Classes": ["BAT:BTC Macro Classes"],
    "Compare Tearsheets": ["BAT:TS Generator"],
    "CTA Outreach": ["NEXTJS:CTA Outreach"],
    "CTA Outreach Backend": ["FASTAPI:CTA Outreach Backend"],
    "ES Options": ["BAT:ES Historical"],
    "Filtered Articles": ["BAT:TWIFO Sharing"],
    "Homepage": ["DASH:Home Page"],
    "Momentum Pacer Tearsheet": ["BAT:Momentum Pacer Tearsheet"],
    "Order Flow Website": [
        "NEXTJS:Order Flow Website",
        "FASTAPI:Order Flow Website Backend",
    ],
    "QuantLab Monitor": ["STREAMLIT:QuantLab Dashboard"],
    "Sector RRG": ["DASH:Sector RRG"],
    "Sector Ratio": ["BAT:Sector Ratio"],
    "SriPNL": ["DASH:SriPNL"],
    "SR3 CVOL Monitor": ["BAT:SR3 CVOL Monitor"],
    "SR3 Dashboard": ["BAT:SR3 Dashboard"],
    "Strategy Optimizer": ["DASH:Strategy Optimizer"],
    "TGM Tearsheet": ["BAT:Gold Maker"],
    "TCP Tearsheet": ["BAT:TCP Tearsheet"],
    "TKP Tearsheet": ["BAT:TKP Tearsheet"],
    "VizLab": ["NEXTJS:VizLab"],
    "Y&Q Tearsheet": ["BAT:Y&Q Tearsheet"],
}


class ExistingServiceHandle:
    """Small process-like handle for a service that is already listening."""

    def __init__(self, pid: int) -> None:
        self.pid = pid


def get_pid_for_port(port: int) -> int:
    """Return the first PID listening on a local port, or 0 if unavailable."""
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == port:
                return int(conn.pid or 0)
    except Exception:
        return 0
    return 0


def _wait_for_port_or_exit(
    name: str,
    process: subprocess.Popen,
    port: int,
    timeout: float = 30.0,
    early_exit_grace: float = 8.0,
) -> bool:
    """
    Wait for *port* to start listening, with smart early-exit handling.

    Many bat wrappers (`cmd /c call file.bat`) running Flask/uvicorn with reloader
    detach from cmd.exe quickly: the wrapper exits rc=1 in ~1s while the real
    python server is still spinning up. So we DO NOT treat wrapper exit as
    failure immediately.

    Behavior:
      - Returns True the moment the port becomes listening.
      - If the process exits AND port has not come up within *early_exit_grace*
        seconds after that exit, declare failure (the python child also died).
      - Otherwise wait the full *timeout* for the port.

    Returns True iff the port is listening before timeout.
    """
    deadline = time.time() + timeout
    process_exit_time: Optional[float] = None
    while time.time() < deadline:
        if is_port_listening("127.0.0.1", port, timeout=0.6):
            return True
        rc = process.poll() if hasattr(process, "poll") else None
        if rc is not None:
            if process_exit_time is None:
                process_exit_time = time.time()
            elapsed_since_exit = time.time() - process_exit_time
            if elapsed_since_exit >= early_exit_grace:
                if not is_port_listening("127.0.0.1", port, timeout=0.4):
                    print(
                        f"[EARLY-EXIT] {name} wrapper exited rc={rc} and port {port} "
                        f"never bound (grace {early_exit_grace:.0f}s exhausted)"
                    )
                    return False
        time.sleep(0.5)
    return False


def _launch_registry() -> Dict[str, Dict]:
    """Flat registry of all launcher configs keyed as TYPE:Name."""
    reg: Dict[str, Dict] = {}
    for name, cfg in BAT_SERVICES.items():
        reg[f"BAT:{name}"] = cfg
    for name, cfg in DASH_APPS.items():
        reg[f"DASH:{name}"] = cfg
    for name, cfg in STREAMLIT_APPS.items():
        reg[f"STREAMLIT:{name}"] = cfg
    for name, cfg in FASTAPI_APPS.items():
        reg[f"FASTAPI:{name}"] = cfg
    for name, cfg in DOCKER_COMPOSE_APPS.items():
        reg[f"DOCKER:{name}"] = cfg
    for name, cfg in NEXTJS_APPS.items():
        reg[f"NEXTJS:{name}"] = cfg
    return reg


def _config_launch_artifact(cfg: Dict) -> Optional[Path]:
    """Return the primary file this service needs to start."""
    for key in ("bat_path", "script_path", "compose_file"):
        p = cfg.get(key)
        if p is not None:
            return Path(p)
    cwd = cfg.get("cwd")
    return Path(cwd) if cwd else None


def verify_dashboard_launch_coverage() -> Tuple[List[str], List[str]]:
    """
    Compare debug.py dashboard sites to launcher registry.
    Returns (errors, warnings).
    """
    errors: List[str] = []
    warnings: List[str] = []
    reg = _launch_registry()

    for site_name, keys in DEBUG_SITE_LAUNCH_TARGETS.items():
        for key in keys:
            if key not in reg:
                errors.append(f"{site_name}: launcher key missing ({key})")
                continue
            artifact = _config_launch_artifact(reg[key])
            if artifact is None:
                errors.append(f"{site_name}: no bat/script/compose path ({key})")
            elif not artifact.exists():
                errors.append(f"{site_name}: missing file ({artifact})")

    if "DASH:Debug Page" not in reg:
        errors.append("Debug Page: launcher config missing (service dashboard)")
    else:
        dbg_art = _config_launch_artifact(reg["DASH:Debug Page"])
        if dbg_art and not dbg_art.exists():
            errors.append(f"Debug Page: missing file ({dbg_art})")

    # Launcher entries not tied to a dashboard card (informational only)
    covered_keys = {k for keys in DEBUG_SITE_LAUNCH_TARGETS.values() for k in keys}
    extra = sorted(set(reg.keys()) - covered_keys - {"DASH:Debug Page"})
    optional_extras = {
        "BAT:Import Dropbox",
        "STREAMLIT:TWIFO Import Dropbox",
        "DASH:Price Dashboard",
    }
    for key in extra:
        if key not in optional_extras:
            warnings.append(f"Launcher entry not on dashboard: {key}")

    return errors, warnings


def launch_debug_page_first(
    all_services: Dict[str, Any],
    failed_services: List[str],
) -> None:
    """Start the Service Dashboard (debug.py) before other services."""
    name = "Debug Page"
    config = DASH_APPS.get(name)
    if not config:
        failed_services.append(f"{name} (no config)")
        return

    print("[PHASE 0] Launching Debug Page (Service Dashboard) first...")
    proc = launch_python_service(name, config)
    if proc:
        all_services[name] = proc
        port = config.get("port", 8006)
        if port and is_port_listening("127.0.0.1", port, timeout=1.0):
            print(f"[OK] Debug Page ready on port {port}")
        else:
            print(f"[WARN] Debug Page may still be starting on port {port}")
    else:
        failed_services.append(name)
    print()


def _dash_apps_excluding_debug() -> Dict[str, Dict]:
    return {k: v for k, v in DASH_APPS.items() if k != "Debug Page"}


def reuse_if_already_running(name: str, port: Optional[int]) -> Optional[ExistingServiceHandle]:
    """Make repeated launcher runs idempotent by reusing occupied service ports."""
    if not port:
        return None
    if is_port_listening("127.0.0.1", port, timeout=1.0):
        pid = get_pid_for_port(port)
        pid_msg = f" (PID: {pid})" if pid else ""
        print(f"[SKIP] {name} already running on port {port}{pid_msg}; reusing existing service")
        return ExistingServiceHandle(pid)
    return None


def escape_cmd_title(title: str) -> str:
    """Escape service names for cmd.exe title commands."""
    return title.replace("&", "^&").replace('"', "'")


def _popen_new_window_bat(title: str, bat_name: str, cwd: str) -> subprocess.Popen:
    """
    Spawn a .bat in a NEW visible cmd window using the Windows `start` command.

    Why not Popen + CREATE_NEW_CONSOLE?
      - For Flask debug-mode / werkzeug reloader and similar self-detaching
        scripts, CREATE_NEW_CONSOLE causes the spawned cmd.exe wrapper to exit
        immediately rc=1 and the python child also dies (handle inheritance
        issue). The `start` shell built-in is the canonical Windows way to spawn
        a detached, visible console window that survives.
    """
    safe_title = escape_cmd_title(title)
    cmd_string = f'start "{safe_title}" cmd.exe /k "call \"{bat_name}\""'
    return subprocess.Popen(cmd_string, cwd=cwd, shell=True)


def _popen_new_window_cmdline(title: str, cmdline: str, cwd: str) -> subprocess.Popen:
    """
    Same idea as `_popen_new_window_bat` but for an arbitrary command line
    (e.g. a python service or `npx next dev -p PORT`). The new cmd window keeps
    open so the user can read output and Ctrl+C it.
    """
    safe_title = escape_cmd_title(title)
    cmd_string = f'start "{safe_title}" cmd.exe /k "{cmdline}"'
    return subprocess.Popen(cmd_string, cwd=cwd, shell=True)


# ─────────────────────────────────────────────────────────────────────────────
# SERVICE LAUNCHERS
# ─────────────────────────────────────────────────────────────────────────────


def launch_bat_service(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """Launch a .bat service in a visible console window with descriptive title."""
    bat_path = config["bat_path"]
    port = config.get("port")
    python_exe = config.get("python_exe")
    health_timeout = float(config.get("health_timeout", 60))

    if not bat_path.exists():
        error_msg = f"[ERROR] .bat not found for {name}: {bat_path}"
        print(error_msg)
        return None

    existing = reuse_if_already_running(name, port)
    if existing:
        return existing
    
    # If python_exe is specified, launch directly with Python instead of bat
    if python_exe and config.get("script_path"):
        return launch_python_service(name, config)
    
    print(f"[LAUNCH] {name} (BAT) -> {bat_path.name}")

    log_file = get_log_file(name)
    service_logs[name] = log_file

    try:
        port_info = f" - Port {port}" if port else ""
        window_title = f"SERVICE: {name}{port_info}"
        process = _popen_new_window_bat(window_title, bat_path.name, str(bat_path.parent))
        print(f"[OK] {name} launched in new window (PID: {process.pid})")

        if port:
            print(f"[HEALTH] Waiting for {name} to bind to port {port} (timeout {health_timeout:.0f}s)...")
            if _wait_for_port_or_exit(name, process, port, timeout=health_timeout):
                print(f"[OK] {name} is now listening on port {port}")
            else:
                print(f"[WARN] {name} did not start listening on port {port} within {health_timeout:.0f}s")

        return process
        
    except Exception as e:
        print(f"[ERROR] Failed to launch {name}: {e}")
        return None


def launch_python_service(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """Launch a Python service in a visible console window with descriptive title."""
    script_path = config.get("script_path")
    port = config.get("port")
    python_exe = config.get("python_exe")
    cwd = config.get("cwd", script_path.parent if script_path else BASE_DIR)
    health_timeout = float(config.get("health_timeout", 30))
    
    if not script_path or not script_path.exists():
        print(f"[ERROR] Script not found for {name}: {script_path}")
        return None
    
    if not python_exe:
        print(f"[ERROR] No python_exe specified for {name}")
        return None
    
    if not os.path.exists(python_exe):
        print(f"[ERROR] Python executable not found for {name}: {python_exe}")
        return None

    existing = reuse_if_already_running(name, port)
    if existing:
        return existing
    
    # Run preflight checks if specified
    if "preflight_checks" in config:
        success, message = run_preflight_check(name, python_exe, config["preflight_checks"])
        if not success:
            print(f"[PREFLIGHT FAILED] {name}")
            print(f"  {message}")
            return None
    
    print(f"[LAUNCH] {name} (Python) -> {script_path.name}")
    print(f"  Python: {python_exe}")
    print(f"  CWD: {cwd}")

    try:
        port_info = f" - Port {port}" if port else ""
        window_title = f"SERVICE: {name}{port_info}"
        cmdline = f'"{python_exe}" "{script_path}"'
        process = _popen_new_window_cmdline(window_title, cmdline, str(cwd))
        print(f"[OK] {name} launched in new window (PID: {process.pid})")

        if port:
            print(f"[HEALTH] Waiting for {name} to bind to port {port} (timeout {health_timeout:.0f}s)...")
            if _wait_for_port_or_exit(name, process, port, timeout=health_timeout):
                print(f"[OK] {name} is now listening on port {port}")
            else:
                print(f"[WARN] {name} did not start listening on port {port} within {health_timeout:.0f}s")

        return process

    except Exception as e:
        print(f"[ERROR] Failed to launch {name}: {e}")
        return None


def launch_streamlit_service(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """Launch a Streamlit application in a visible console window with descriptive title."""
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

    existing = reuse_if_already_running(name, port)
    if existing:
        return existing
    
    print(f"[LAUNCH] {name} (Streamlit) -> {script_path.name}")
    print(f"  Python: {python_exe}")
    print(f"  Port: {port}")
    
    rel_path = script_path.relative_to(cwd) if script_path.is_relative_to(cwd) else script_path

    try:
        window_title = f"SERVICE: {name} - Port {port}"
        cmdline = (
            f'"{python_exe}" -m streamlit run "{rel_path}" '
            f'--server.port {port} --server.headless true '
            f'--browser.gatherUsageStats false'
        )
        process = _popen_new_window_cmdline(window_title, cmdline, str(cwd))
        print(f"[OK] {name} launched in new window (PID: {process.pid})")

        print(f"[HEALTH] Waiting for {name} to bind to port {port}...")
        if _wait_for_port_or_exit(name, process, port, timeout=30):
            print(f"[OK] {name} is now listening on port {port}")
        else:
            print(f"[WARN] {name} did not start listening on port {port} within 30s")

        return process

    except Exception as e:
        print(f"[ERROR] Failed to launch {name}: {e}")
        return None


def launch_fastapi_service(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """Launch a FastAPI application in a visible console window with descriptive title."""
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

    existing = reuse_if_already_running(name, port)
    if existing:
        return existing
    
    # Run preflight checks if specified
    if "preflight_checks" in config:
        success, message = run_preflight_check(name, python_exe, config["preflight_checks"])
        if not success:
            print(f"[PREFLIGHT FAILED] {name}")
            print(f"  {message}")
            return None
    
    print(f"[LAUNCH] {name} (FastAPI) -> {uvicorn_module}")
    print(f"  Python: {python_exe}")
    print(f"  Port: {port}")

    try:
        window_title = f"SERVICE: {name} - Port {port}"
        cmdline = (
            f'"{python_exe}" -m uvicorn {uvicorn_module} '
            f'--host 0.0.0.0 --port {port} --reload'
        )
        process = _popen_new_window_cmdline(window_title, cmdline, str(cwd))
        print(f"[OK] {name} launched in new window (PID: {process.pid})")

        print(f"[HEALTH] Waiting for {name} to bind to port {port}...")
        if _wait_for_port_or_exit(name, process, port, timeout=30):
            print(f"[OK] {name} is now listening on port {port}")
        else:
            print(f"[WARN] {name} did not start listening on port {port} within 30s")

        return process

    except Exception as e:
        print(f"[ERROR] Failed to launch {name}: {e}")
        return None


def launch_nextjs_service(name: str, config: Dict) -> Optional[subprocess.Popen]:
    """Launch a Next.js application in a visible console window with descriptive title."""
    cwd = config["cwd"]
    port = config["port"]
    
    if not cwd.exists():
        print(f"[ERROR] Directory not found for {name}: {cwd}")
        return None

    existing = reuse_if_already_running(name, port)
    if existing:
        return existing
    
    print(f"[LAUNCH] {name} (Next.js) -> port {port}")

    try:
        window_title = f"SERVICE: {name} - Port {port}"
        cmdline = f"npx next dev -p {port}"
        process = _popen_new_window_cmdline(window_title, cmdline, str(cwd))
        print(f"[OK] {name} launched in new window (PID: {process.pid})")

        print(f"[HEALTH] Waiting for {name} to bind to port {port} (60s for Next.js compile)...")
        if _wait_for_port_or_exit(name, process, port, timeout=60):
            print(f"[OK] {name} is now listening on port {port}")
        else:
            print(f"[WARN] {name} did not start listening on port {port} within 60s")
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

    print(f"[LAUNCH] {name} (Docker Compose) -> {compose_file.name}")

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


def find_chrome_executable() -> Optional[str]:
    """Find Chrome on this Windows machine."""
    candidates = [
        os.path.join(os.environ.get("ProgramFiles", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LocalAppData", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def open_browser_tabs(services: Dict[str, subprocess.Popen]) -> None:
    """Open Chrome directly to the Debug Page after services have had time to bind."""
    print(f"\n[INFO] Waiting {BROWSER_OPEN_DELAY}s before opening Chrome to the Debug Page...\n")
    time.sleep(BROWSER_OPEN_DELAY)

    debug_config = DASH_APPS.get("Debug Page", {})
    debug_url = debug_config.get("url", "http://localhost:8006")
    debug_port = debug_config.get("port", 8006)

    if "Debug Page" not in services and not is_port_listening("127.0.0.1", debug_port, timeout=1.0):
        print("[WARN] Debug Page is not running; skipping Chrome launch")
        return

    chrome_path = find_chrome_executable()
    try:
        if chrome_path:
            subprocess.Popen([chrome_path, debug_url])
            print(f"[OK] Chrome opened to Debug Page: {debug_url}")
            print(f"[INFO] Chrome command: {chrome_path} {debug_url}")
        else:
            webbrowser.open(debug_url)
            print(f"[WARN] Chrome not found; opened default browser to Debug Page: {debug_url}")
    except Exception as e:
        print(f"[ERROR] Failed to open Debug Page in Chrome: {e}")


def check_system_resources() -> Tuple[bool, str]:
    """Check if system has enough resources to continue launching services."""
    try:
        mem = psutil.virtual_memory()
        available_gb = mem.available / (1024 ** 3)
        
        if available_gb < MEMORY_THRESHOLD_GB:
            return False, f"Low memory: {available_gb:.1f} GB available (need {MEMORY_THRESHOLD_GB} GB)"
        
        return True, f"Memory OK: {available_gb:.1f} GB available"
    except Exception as e:
        # If psutil fails, continue anyway
        return True, f"Memory check unavailable: {e}"


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


def _launch_phase_items(
    phase_label: str,
    items: Dict[str, Dict],
    launcher: Callable[..., Any],
    all_services: Dict[str, Any],
    failed_services: List[str],
) -> None:
    """
    Launch every entry in *items* using *launcher(name, config)*.

    When PARALLEL_LAUNCH_ENABLED: all starts in this phase run concurrently (bounded
    by PARALLEL_MAX_WORKERS). Phases still run one-after-another so Docker / Next
    do not fight with earlier waves for the same global resources until their phase.

    When disabled: original sequential behavior with LAUNCH_PAUSE between each.
    """
    if not items:
        return

    if not PARALLEL_LAUNCH_ENABLED:
        for name, config in items.items():
            proc = launcher(name, config)
            if proc:
                all_services[name] = proc
            else:
                failed_services.append(name)
            time.sleep(LAUNCH_PAUSE)
        print(f"[{phase_label}] Sequential batch complete ({len(items)} services).")
        return

    n = len(items)
    max_workers = PARALLEL_MAX_WORKERS or min(24, max(4, n))
    max_workers = max(1, min(max_workers, n))

    print(
        f"[{phase_label}] Launching {n} services in parallel "
        f"(max_workers={max_workers})..."
    )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_name = {
            executor.submit(launcher, name, config): name
            for name, config in items.items()
        }
        for fut in as_completed(future_to_name):
            name = future_to_name[fut]
            try:
                proc = fut.result()
                if proc:
                    all_services[name] = proc
                else:
                    failed_services.append(name)
            except Exception as exc:
                print(f"[ERROR] {name} launch raised: {exc}")
                failed_services.append(name)

    print(f"[{phase_label}] Parallel batch complete ({n} services).")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN LAUNCHER
# ─────────────────────────────────────────────────────────────────────────────

def launch_all_services() -> Tuple[Dict[str, subprocess.Popen], Dict[str, int]]:
    """Launch all services and return running processes and fail counts."""
    all_services: Dict[str, subprocess.Popen] = {}
    failed_services: List[str] = []

    cov_errors, cov_warnings = verify_dashboard_launch_coverage()
    if cov_errors:
        print("[COVERAGE] Dashboard sites with launcher/config problems:")
        for line in cov_errors:
            print(f"  [ERROR] {line}")
    if cov_warnings:
        print("[COVERAGE] Extra launcher entries (not on dashboard):")
        for line in cov_warnings:
            print(f"  [INFO] {line}")
    if not cov_errors:
        print(
            f"[COVERAGE] All {len(DEBUG_SITE_LAUNCH_TARGETS)} dashboard sites "
            f"mapped to launcher configs."
        )

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
    print(f"[INFO] Total: {total} services")
    print(
        f"[INFO] Parallel launch: {PARALLEL_LAUNCH_ENABLED} "
        f"(max_workers={PARALLEL_MAX_WORKERS or 'auto'})\n"
    )

    # Phase 0: Service Dashboard first (debug.py on port 8006)
    launch_debug_page_first(all_services, failed_services)

    # Phase 1: Launch .bat services
    print("[PHASE 1] Launching .bat services...")
    
    # Check memory before starting
    if MEMORY_CHECK_ENABLED:
        mem_ok, mem_msg = check_system_resources()
        print(f"[MEMORY] {mem_msg}")
        if not mem_ok:
            print(f"[WARN] Low memory detected. Consider closing other applications.")
            print(f"[WARN] Continuing with reduced launch speed...")
    
    _launch_phase_items(
        "PHASE 1", BAT_SERVICES, launch_bat_service, all_services, failed_services
    )
    print(f"[PHASE 1] Complete. Pausing {PHASE_PAUSE}s before next phase...")
    time.sleep(PHASE_PAUSE)
    print()

    # Phase 2: Launch Dash applications (Debug Page already started in Phase 0)
    print("[PHASE 2] Launching Dash applications...")
    _launch_phase_items(
        "PHASE 2",
        _dash_apps_excluding_debug(),
        launch_python_service,
        all_services,
        failed_services,
    )
    print(f"[PHASE 2] Complete. Pausing {PHASE_PAUSE}s before next phase...")
    time.sleep(PHASE_PAUSE)
    print()

    # Phase 3: Launch Streamlit applications
    print("[PHASE 3] Launching Streamlit applications...")
    _launch_phase_items(
        "PHASE 3",
        STREAMLIT_APPS,
        launch_streamlit_service,
        all_services,
        failed_services,
    )
    print(f"[PHASE 3] Complete. Pausing {PHASE_PAUSE}s before next phase...")
    time.sleep(PHASE_PAUSE)
    print()

    # Phase 4: Launch FastAPI applications
    print("[PHASE 4] Launching FastAPI applications...")
    _launch_phase_items(
        "PHASE 4", FASTAPI_APPS, launch_fastapi_service, all_services, failed_services
    )
    print(f"[PHASE 4] Complete. Pausing {PHASE_PAUSE}s before next phase...")
    time.sleep(PHASE_PAUSE)
    print()

    # Phase 5: Launch Docker Compose applications
    print("[PHASE 5] Launching Docker Compose applications...")
    if DOCKER_COMPOSE_APPS:
        docker_available, docker_info = check_docker_available()
        if docker_available:
            print(f"[OK] {docker_info}")
            _launch_phase_items(
                "PHASE 5",
                DOCKER_COMPOSE_APPS,
                launch_docker_compose_service,
                all_services,
                failed_services,
            )
        else:
            print(f"[ERROR] {docker_info}")
            print(f"[WARN] Skipping Docker Compose services")
            for name in DOCKER_COMPOSE_APPS.keys():
                failed_services.append(f"{name} (Docker not available)")
    print(f"[PHASE 5] Complete. Pausing {PHASE_PAUSE}s before next phase...")
    time.sleep(PHASE_PAUSE)
    print()

    # Phase 6: Launch Next.js applications (most resource-intensive)
    print("[PHASE 6] Launching Next.js applications...")
    _launch_phase_items(
        "PHASE 6", NEXTJS_APPS, launch_nextjs_service, all_services, failed_services
    )
    print(f"[PHASE 6] Complete. Pausing {PHASE_PAUSE}s before next phase...")
    time.sleep(PHASE_PAUSE)
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

    # Phase 8: Open Chrome to the Debug Page
    open_browser_tabs(all_services)

    # Phase 9: Save service registry
    save_service_registry(all_services)

    if tunnel_manager:
        all_services["_tunnel_manager"] = tunnel_manager

    # Print summary
    print("\n" + "=" * 70)
    print("  LAUNCH SUMMARY")
    print("=" * 70)
    launched_count = len([k for k in all_services if k != "_tunnel_manager"])
    print(f"\n[INFO] Successfully launched: {launched_count} services")
    if failed_services:
        print(f"[WARN] Failed to launch: {len(failed_services)} service(s)")
        print(f"[WARN] Failed services: {', '.join(failed_services)}")
        print(f"[INFO] Check logs in: {LOGS_DIR}")
    else:
        print(f"[OK] All launcher targets started successfully")
    if cov_errors:
        print(
            f"[WARN] {len(cov_errors)} dashboard/launcher config issue(s) were reported "
            f"before launch — fix those even if processes started."
        )
    print(f"[INFO] Chrome opened to the Debug Page when available")
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
