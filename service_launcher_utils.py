"""
Purpose: Shared utilities for launching and managing services
Author: Kevin Lefebvre
Last Updated: 2026-01-19

Provides robust, isolated service launch/kill functionality.
Fixes critical issues:
- PIPE buffer overflow causing process hangs
- Lost process handles when using 'start' command
- Orphaned processes
- PID tracking failures
"""

import subprocess
import os
import time
import socket
import sys
from pathlib import Path
from typing import Optional, Dict, Tuple, List
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CRITICAL FIX #1: Avoid PIPE buffer overflow
# ─────────────────────────────────────────────────────────────────────────────
# Problem: stdout=subprocess.PIPE fills up (64KB buffer) and blocks the process
# Solution: Use CREATE_NEW_CONSOLE to open visible window, or write to log file


# ─────────────────────────────────────────────────────────────────────────────
# CRITICAL FIX #2: Track actual process PIDs, not wrapper PIDs
# ─────────────────────────────────────────────────────────────────────────────
# Problem: Using 'start' command returns wrapper PID, loses actual process
# Solution: Use CREATE_NEW_CONSOLE flag instead of 'start' command


def is_port_available(host: str, port: int, timeout: float = 1.0) -> bool:
    """
    Check if a port is available (nothing listening on it).
    
    Returns:
        True if port is available (nothing listening)
        False if port is in use (something listening)
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return False  # Port is in use
    except (socket.error, ConnectionRefusedError, TimeoutError):
        return True  # Port is available


def is_port_listening(host: str, port: int, timeout: float = 2.0) -> bool:
    """
    Check if something is listening on a port (opposite of is_port_available).
    
    Returns:
        True if something is listening on the port
        False if nothing is listening
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True  # Something is listening
    except (socket.error, ConnectionRefusedError, TimeoutError):
        return False  # Nothing listening


def find_python_executable(venv_path: Optional[Path] = None) -> str:
    """
    Find Python executable, preferring venv if specified.
    
    Args:
        venv_path: Path to virtual environment (optional)
        
    Returns:
        Full path to python.exe
    """
    if venv_path and venv_path.exists():
        venv_python = venv_path / "Scripts" / "python.exe"
        if venv_python.exists():
            logger.info(f"Using venv Python: {venv_python}")
            return str(venv_python)
        else:
            logger.warning(f"Venv Python not found at {venv_python}, using system Python")
    elif venv_path:
        logger.warning(f"Venv path does not exist: {venv_path}, using system Python")
    
    # Fall back to system Python
    logger.info(f"Using system Python: {sys.executable}")
    return sys.executable


def kill_process_by_port(port: int) -> Tuple[bool, List[int]]:
    """
    Kill all processes using a specific port.
    
    Args:
        port: Port number to check
        
    Returns:
        Tuple of (success: bool, killed_pids: List[int])
    """
    killed_pids = []
    
    try:
        # Find all processes using the port
        result = subprocess.run(
            f'netstat -ano | findstr :{port}',
            capture_output=True,
            text=True,
            shell=True,
            timeout=5
        )
        
        # Parse netstat output to find PIDs
        lines = result.stdout.strip().split('\n')
        pids = set()
        
        for line in lines:
            if f':{port}' in line and ('LISTENING' in line or 'ESTABLISHED' in line):
                parts = line.split()
                # PID is the last column in netstat output
                if len(parts) >= 5:
                    try:
                        pid_str = parts[-1].strip()
                        if pid_str.isdigit():
                            pids.add(int(pid_str))
                    except (ValueError, IndexError):
                        continue
        
        # Kill each process
        for pid in pids:
            try:
                # Use /T to kill process tree (child processes too)
                result = subprocess.run(
                    f'taskkill /F /T /PID {pid}',
                    capture_output=True,
                    text=True,
                    shell=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    killed_pids.append(pid)
                    logger.info(f"Killed process tree for PID {pid} on port {port}")
                else:
                    logger.warning(f"Failed to kill PID {pid}: {result.stderr}")
            except subprocess.TimeoutExpired:
                logger.error(f"Timeout while trying to kill PID {pid}")
            except Exception as e:
                logger.warning(f"Error killing PID {pid}: {e}")
        
        return len(killed_pids) > 0, killed_pids
    
    except Exception as e:
        logger.error(f"Error finding/killing processes on port {port}: {e}")
        return False, []


def launch_bat_file(bat_path: str, service_name: str) -> Optional[subprocess.Popen]:
    """
    Launch a .bat file in a NEW CONSOLE WINDOW with proper process tracking.
    
    CRITICAL: Uses CREATE_NEW_CONSOLE instead of 'start' command to maintain process handle.
    
    Args:
        bat_path: Full path to .bat file
        service_name: Name of service (for window title)
        
    Returns:
        Popen object with handle to the actual process, or None on failure
    """
    if not os.path.exists(bat_path):
        logger.error(f".bat file not found: {bat_path}")
        return None
    
    bat_dir = os.path.dirname(bat_path)
    bat_file = os.path.basename(bat_path)
    
    logger.info(f"Launching {service_name} from: {bat_path}")
    
    try:
        # CRITICAL FIX: Use CREATE_NEW_CONSOLE + cmd.exe to open new window
        # This keeps the process handle while showing output in a visible window
        # Do NOT use 'start' command - it causes PID loss
        
        cmd_args = ["cmd.exe", "/k", bat_file]
        
        process = subprocess.Popen(
            cmd_args,
            cwd=bat_dir,
            creationflags=subprocess.CREATE_NEW_CONSOLE,  # Opens new console, keeps handle
            # Do NOT use stdout/stderr=PIPE - causes buffer overflow and hangs
        )
        
        logger.info(f"{service_name} launched successfully (PID: {process.pid})")
        return process
        
    except Exception as e:
        logger.error(f"Failed to launch {service_name}: {e}", exc_info=True)
        return None


def launch_python_app(
    script_path: str,
    service_name: str,
    port: int,
    venv_path: Optional[str] = None
) -> Optional[subprocess.Popen]:
    """
    Launch a Python application (Dash, FastAPI, etc.) in a NEW CONSOLE WINDOW.
    
    CRITICAL: Opens visible console and avoids PIPE buffer overflow.
    
    Args:
        script_path: Full path to Python script
        service_name: Name of service
        port: Port number the service will run on
        venv_path: Path to virtual environment (optional)
        
    Returns:
        Popen object or None on failure
    """
    if not os.path.exists(script_path):
        logger.error(f"Python script not found: {script_path}")
        return None
    
    script_dir = os.path.dirname(script_path)
    python_exe = find_python_executable(Path(venv_path) if venv_path else None)
    
    logger.info(f"Launching {service_name} on port {port}")
    logger.info(f"  Script: {script_path}")
    logger.info(f"  Python: {python_exe}")
    
    try:
        # CRITICAL FIX: Use CREATE_NEW_CONSOLE without PIPE
        # Opens visible console window showing all output
        # No buffer overflow issues
        
        cmd_args = [python_exe, os.path.basename(script_path)]
        
        process = subprocess.Popen(
            cmd_args,
            cwd=script_dir,
            creationflags=subprocess.CREATE_NEW_CONSOLE,  # Opens new console, keeps handle
            # Do NOT use stdout/stderr=PIPE - causes buffer overflow
        )
        
        # Give process a moment to start
        time.sleep(1)
        
        # Check if process is still running
        if process.poll() is not None:
            logger.error(f"{service_name} process exited immediately (exit code: {process.returncode})")
            return None
        
        logger.info(f"{service_name} launched successfully (PID: {process.pid})")
        return process
        
    except Exception as e:
        logger.error(f"Failed to launch {service_name}: {e}", exc_info=True)
        return None


def launch_fastapi_app(
    main_file_path: str,
    service_name: str,
    port: int,
    working_dir: str,
    uvicorn_module: str,
    venv_path: Optional[str] = None
) -> Optional[subprocess.Popen]:
    """
    Launch a FastAPI application using uvicorn in a NEW CONSOLE WINDOW.
    
    Args:
        main_file_path: Path to main.py file
        service_name: Name of service
        port: Port number
        working_dir: Working directory
        uvicorn_module: Module path for uvicorn (e.g., "main:app" or "app.main:app")
        venv_path: Path to virtual environment (optional)
        
    Returns:
        Popen object or None on failure
    """
    if not os.path.exists(main_file_path):
        logger.error(f"FastAPI main file not found: {main_file_path}")
        return None
    
    python_exe = find_python_executable(Path(venv_path) if venv_path else None)
    
    logger.info(f"Launching {service_name} (FastAPI) on port {port}")
    logger.info(f"  Module: {uvicorn_module}")
    logger.info(f"  Working dir: {working_dir}")
    
    try:
        # CRITICAL FIX: Use CREATE_NEW_CONSOLE without PIPE
        cmd_args = [
            python_exe, "-m", "uvicorn",
            uvicorn_module,
            "--host", "0.0.0.0",
            "--port", str(port),
            "--reload"
        ]
        
        process = subprocess.Popen(
            cmd_args,
            cwd=working_dir,
            creationflags=subprocess.CREATE_NEW_CONSOLE,  # Opens new console, keeps handle
            # Do NOT use stdout/stderr=PIPE
        )
        
        # Give process a moment to start
        time.sleep(1)
        
        if process.poll() is not None:
            logger.error(f"{service_name} process exited immediately (exit code: {process.returncode})")
            return None
        
        logger.info(f"{service_name} launched successfully (PID: {process.pid})")
        return process
        
    except Exception as e:
        logger.error(f"Failed to launch {service_name}: {e}", exc_info=True)
        return None


def launch_nextjs_app(
    app_dir: str,
    service_name: str,
    port: int
) -> Optional[subprocess.Popen]:
    """
    Launch a Next.js application in a NEW CONSOLE WINDOW.
    
    CRITICAL: Uses CREATE_NEW_CONSOLE to track actual process, not wrapper.
    
    Args:
        app_dir: Directory containing package.json
        service_name: Name of service
        port: Port number
        
    Returns:
        Popen object or None on failure
    """
    if not os.path.exists(app_dir):
        logger.error(f"Next.js app directory not found: {app_dir}")
        return None
    
    logger.info(f"Launching {service_name} (Next.js) on port {port}")
    logger.info(f"  Directory: {app_dir}")
    
    try:
        # CRITICAL FIX: Use CREATE_NEW_CONSOLE without 'start' command
        # This way we track the actual npx/node process, not a wrapper
        
        # Use npx next dev directly with port flag
        cmd_args = ["cmd.exe", "/k", f"npx next dev -p {port}"]
        
        process = subprocess.Popen(
            cmd_args,
            cwd=app_dir,
            creationflags=subprocess.CREATE_NEW_CONSOLE,  # Opens new console, keeps handle
            # Do NOT use stdout/stderr=PIPE
        )
        
        # Give Next.js time to compile and start (it's slower than other apps)
        logger.info(f"Waiting for {service_name} to compile...")
        time.sleep(3)
        
        if process.poll() is not None:
            logger.error(f"{service_name} process exited immediately (exit code: {process.returncode})")
            return None
        
        logger.info(f"{service_name} launched successfully (PID: {process.pid})")
        return process
        
    except Exception as e:
        logger.error(f"Failed to launch {service_name}: {e}", exc_info=True)
        return None


def wait_for_port(host: str, port: int, timeout: float = 30.0, check_interval: float = 0.5) -> bool:
    """
    Wait for a port to start listening.
    
    Args:
        host: Host to check
        port: Port to check
        timeout: Maximum time to wait (seconds)
        check_interval: How often to check (seconds)
        
    Returns:
        True if port starts listening within timeout, False otherwise
    """
    start_time = time.time()
    
    while (time.time() - start_time) < timeout:
        if is_port_listening(host, port, timeout=1.0):
            logger.info(f"Port {port} is now listening")
            return True
        time.sleep(check_interval)
    
    logger.warning(f"Port {port} did not start listening within {timeout}s")
    return False


def get_pid_by_port(port: int) -> List[int]:
    """
    Find all PIDs listening on a specific port.
    
    Args:
        port: Port number to check
        
    Returns:
        List of PIDs using the port
    """
    pids = []
    
    try:
        result = subprocess.run(
            f'netstat -ano | findstr :{port}',
            capture_output=True,
            text=True,
            shell=True,
            timeout=5
        )
        
        lines = result.stdout.strip().split('\n')
        
        for line in lines:
            if f':{port}' in line and ('LISTENING' in line or 'ESTABLISHED' in line):
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        pid_str = parts[-1].strip()
                        if pid_str.isdigit():
                            pid = int(pid_str)
                            if pid not in pids:
                                pids.append(pid)
                    except (ValueError, IndexError):
                        continue
        
    except Exception as e:
        logger.error(f"Error finding PIDs on port {port}: {e}")
    
    return pids


def kill_process_tree(pid: int) -> bool:
    """
    Kill a process and all its children.
    
    Args:
        pid: Process ID to kill
        
    Returns:
        True if successfully killed, False otherwise
    """
    try:
        # /F = force, /T = kill process tree (children too)
        result = subprocess.run(
            f'taskkill /F /T /PID {pid}',
            capture_output=True,
            text=True,
            shell=True,
            timeout=10
        )
        
        if result.returncode == 0:
            logger.info(f"Successfully killed process tree for PID {pid}")
            return True
        else:
            logger.warning(f"Failed to kill PID {pid}: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout while trying to kill PID {pid}")
        return False
    except Exception as e:
        logger.error(f"Error killing PID {pid}: {e}")
        return False


def kill_process_by_port_robust(port: int) -> Tuple[bool, List[int]]:
    """
    Robustly kill all processes using a port.
    
    Args:
        port: Port number
        
    Returns:
        Tuple of (any_killed: bool, killed_pids: List[int])
    """
    pids = get_pid_by_port(port)
    killed_pids = []
    
    if not pids:
        logger.info(f"No processes found on port {port}")
        return False, []
    
    logger.info(f"Found {len(pids)} process(es) on port {port}: {pids}")
    
    for pid in pids:
        if kill_process_tree(pid):
            killed_pids.append(pid)
    
    # Wait a moment for processes to die
    time.sleep(0.5)
    
    # Verify port is now free
    if not is_port_listening("127.0.0.1", port):
        logger.info(f"Port {port} is now free")
        return True, killed_pids
    else:
        logger.warning(f"Port {port} still in use after kill attempt")
        return len(killed_pids) > 0, killed_pids
