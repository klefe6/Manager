#!/usr/bin/env python3
"""
PM2-like Monitor for Windows Batch Files

This script monitors and restarts Windows batch files every hour, similar to PM2.
It tracks running processes, kills existing instances before restarting, and provides
comprehensive logging and monitoring.

Features:
- Hourly restart of all configured services
- Process tracking and cleanup
- Comprehensive logging
- Health monitoring
- Graceful shutdown handling
"""

import subprocess
import os
import time
import socket
import sys
import psutil
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import signal
import threading

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

# Core settings
HOURLY_RESTART_ENABLED = True      # Enable hourly restarts
HEALTH_CHECK_ENABLED   = True      # Enable health monitoring
RESTART_INTERVAL       = 60 * 60   # 1 hour in seconds
HEALTH_CHECK_INTERVAL  = 30        # 30 seconds between health checks
LAUNCH_PAUSE           = 5         # seconds pause between launching each .bat
GRACEFUL_SHUTDOWN_TIME = 10        # seconds to wait for graceful shutdown

# Process tracking
PROCESS_TIMEOUT        = 30        # seconds to wait for process to start
MAX_RESTART_ATTEMPTS   = 3         # max restart attempts before giving up

# Logging
LOG_LEVEL = logging.INFO
LOG_FILE  = "pm2_monitor.log"

# ─── Service Configuration ───────────────────────────────────────────────────
SERVICES = {
    "TWIFO Sharing":    r"C:\Program Files\Coding Projects\TWIFO_Sharing\reboot_twifo.bat",
    "Import Dropbox":   r"C:\Program Files\Coding Projects\TWIFO_Sharing\reboot_import_dropbox.bat",
    "TS Generator":     r"C:\Program Files\Coding Projects\Tearsheet Generator\run_tsgen.bat",
    "TKP Tearsheet":    r"C:\Program Files\Coding Projects\Tearsheet Generator\reboot_tkp_ts.bat",
    "Y&Q Tearsheet":    r"C:\Program Files\Coding Projects\Tearsheet Generator\reboot_yq_ts.bat",
    "Gold Maker":       r"C:\Program Files\Coding Projects\Tearsheet Generator\reboot_gold_maker.bat",
    "Price Dashboard":  r"C:\Program Files\Coding Projects\Price Dashboard\reboot_dashboard.bat",
    "Strategy Opt":     r"C:\Program Files\Coding Projects\StrategyOptimizer\reboot_strategy_optimizer.bat",
    "Home Page":        r"C:\Program Files\Coding Projects\HomePage\reboot_homepage.bat",
    "Debug Page":       r"C:\Program Files\Coding Projects\HomePage\reboot_debug.bat",
    "Sector Ratio":     r"C:\Program Files\Coding Projects\GSR\reboot_gsr.bat",
    "ES Historical":    r"C:\Program Files\Coding Projects\ES Historical Data\reboot_es_historical_data.bat",
    "Almanac Futures":  r"C:\Program Files\Coding Projects\Almanac Futures\reboot_almanac.bat",
}

# Health check ports
PORTS = {
    "TWIFO Sharing":   ("127.0.0.1", 8065),
    "Import Dropbox":  ("127.0.0.1", 8501),
    "TS Generator":    ("127.0.0.1", 8077),
    "TKP Tearsheet":   ("127.0.0.1", 8076),
    "Y&Q Tearsheet":   ("127.0.0.1", 8071),
    "Gold Maker":      ("127.0.0.1", 8075),
    "Price Dashboard": ("127.0.0.1", 3000),
    "Strategy Opt":    ("127.0.0.1", 8080),
    "Home Page":       ("127.0.0.1", 8050),
    "Debug Page":      ("127.0.0.1", 8060),
    "Sector Ratio":    ("127.0.0.1", 8080),
    "ES Historical":   ("127.0.0.1", 8081),
    "Almanac Futures": ("127.0.0.1", 8072),
}

# ─── Process name patterns for better process detection ───────────────────────
PROCESS_PATTERNS = {
    "TWIFO Sharing":    ["twifo", "sharing", "node"],
    "Import Dropbox":   ["import", "dropbox", "node"],
    "TS Generator":     ["tsgen", "generator", "node"],
    "TKP Tearsheet":    ["tkp", "tearsheet", "node"],
    "Y&Q Tearsheet":    ["yq", "tearsheet", "node"],
    "Gold Maker":       ["gold", "maker", "node"],
    "Price Dashboard":  ["price", "dashboard", "app.py"],
    "Strategy Opt":     ["strategy", "optimizer", "node"],
    "Home Page":        ["homepage", "home", "node"],
    "Debug Page":       ["debug", "node"],
    "Sector Ratio":     ["gsr", "node"],
    "ES Historical":    ["es", "historical", "node"],
    "Almanac Futures":  ["almanac", "futures", "node"],
}

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL STATE
# ─────────────────────────────────────────────────────────────────────────────

# Track running processes
running_processes: Dict[str, subprocess.Popen] = {}
process_start_times: Dict[str, datetime] = {}
restart_counts: Dict[str, int] = {}
shutdown_requested = False

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────────────────────────────────────

def setup_logging():
    """Configure logging with both file and console output."""
    logging.basicConfig(
        level=LOG_LEVEL,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ─────────────────────────────────────────────────────────────────────────────
# PROCESS MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def find_processes_by_name(process_name: str) -> List[psutil.Process]:
    """Find all running processes that match the given name."""
    matching_processes = []
    try:
        # Get process patterns for better matching
        patterns = PROCESS_PATTERNS.get(process_name, [process_name.lower()])
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'exe']):
            try:
                proc_name = proc.info['name'].lower() if proc.info['name'] else ""
                cmdline = ' '.join(proc.info['cmdline']).lower() if proc.info['cmdline'] else ""
                exe_path = proc.info['exe'].lower() if proc.info['exe'] else ""
                
                # Check if any pattern matches
                for pattern in patterns:
                    if (pattern in proc_name or 
                        pattern in cmdline or 
                        pattern in exe_path):
                        matching_processes.append(proc)
                        break
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        logger.warning(f"Error finding processes for {process_name}: {e}")
    return matching_processes

def kill_service_processes(service_name: str) -> bool:
    """Kill all processes related to a service."""
    logger.info(f"Stopping processes for {service_name}")
    
    # First, try to terminate gracefully
    killed_any = False
    for proc in find_processes_by_name(service_name):
        try:
            if proc.is_running():
                logger.info(f"Terminating process {proc.pid} for {service_name}")
                proc.terminate()
                killed_any = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    # Wait for graceful shutdown
    if killed_any:
        time.sleep(GRACEFUL_SHUTDOWN_TIME)
        
        # Force kill if still running
        for proc in find_processes_by_name(service_name):
            try:
                if proc.is_running():
                    logger.warning(f"Force killing process {proc.pid} for {service_name}")
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    
    return killed_any

def is_service_healthy(host: str, port: int) -> bool:
    """Check if a service is healthy by attempting a TCP connection."""
    try:
        with socket.create_connection((host, port), timeout=5):
            return True
    except Exception:
        return False

def start_service(service_name: str) -> bool:
    """Start a service and track its process."""
    bat_path = SERVICES.get(service_name)
    if not bat_path or not os.path.isfile(bat_path):
        logger.error(f"Batch file not found for {service_name}: {bat_path}")
        return False
    
    try:
        # Kill existing processes first
        kill_service_processes(service_name)
        
        # Start new process
        cwd = os.path.dirname(bat_path)
        logger.info(f"Starting {service_name} from {bat_path}")
        
        process = subprocess.Popen(
            f'start "" "{bat_path}"',
            cwd=cwd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        running_processes[service_name] = process
        process_start_times[service_name] = datetime.now()
        
        # Wait longer for the process to start and stabilize
        time.sleep(LAUNCH_PAUSE + 2)  # Extra 2 seconds for stability
        
        # Verify the process is still running
        if process.poll() is not None:
            logger.warning(f"Process for {service_name} exited immediately")
            return False
        
        logger.info(f"Successfully started {service_name} (PID: {process.pid})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to start {service_name}: {e}")
        return False

def restart_service(service_name: str) -> bool:
    """Restart a service (stop + start)."""
    logger.info(f"Restarting {service_name}")
    
    # Stop the service
    if service_name in running_processes:
        try:
            running_processes[service_name].terminate()
        except Exception as e:
            logger.warning(f"Error terminating {service_name}: {e}")
        finally:
            del running_processes[service_name]
            if service_name in process_start_times:
                del process_start_times[service_name]
    
    # Kill any remaining processes
    kill_service_processes(service_name)
    
    # Start the service
    return start_service(service_name)

def restart_all_services() -> Dict[str, bool]:
    """Restart all configured services."""
    logger.info("=" * 60)
    logger.info("RESTARTING ALL SERVICES")
    logger.info("=" * 60)
    
    results = {}
    for service_name in SERVICES.keys():
        logger.info(f"Restarting {service_name}...")
        success = restart_service(service_name)
        results[service_name] = success
        
        if success:
            restart_counts[service_name] = restart_counts.get(service_name, 0) + 1
            logger.info(f"[SUCCESS] {service_name} restarted successfully (restart #{restart_counts[service_name]})")
        else:
            logger.error(f"[FAILED] Failed to restart {service_name}")
        
        time.sleep(LAUNCH_PAUSE)
    
    return results

# ─────────────────────────────────────────────────────────────────────────────
# HEALTH MONITORING
# ─────────────────────────────────────────────────────────────────────────────

def check_all_services_health() -> Dict[str, bool]:
    """Check health of all services."""
    health_status = {}
    
    for service_name, (host, port) in PORTS.items():
        healthy = is_service_healthy(host, port)
        health_status[service_name] = healthy
        
        status = "[HEALTHY]" if healthy else "[UNHEALTHY]"
        logger.debug(f"{service_name}: {status} (port {port})")
    
    return health_status

def health_monitor_worker():
    """Background worker for health monitoring."""
    while not shutdown_requested:
        try:
            if HEALTH_CHECK_ENABLED:
                health_status = check_all_services_health()
                unhealthy_services = [name for name, healthy in health_status.items() if not healthy]
                
                if unhealthy_services:
                    logger.warning(f"Unhealthy services detected: {', '.join(unhealthy_services)}")
                    # Give services more time to start up before reporting as unhealthy
                    time.sleep(30)  # Wait 30 seconds before next check
                else:
                    logger.debug("All services are healthy")
            
            time.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in health monitor: {e}")
            time.sleep(HEALTH_CHECK_INTERVAL)

# ─────────────────────────────────────────────────────────────────────────────
# MAIN SCHEDULER
# ─────────────────────────────────────────────────────────────────────────────

def main_scheduler():
    """Main scheduler that handles hourly restarts."""
    global shutdown_requested
    
    logger.info("PM2 Monitor started")
    logger.info(f"Hourly restart enabled: {HOURLY_RESTART_ENABLED}")
    logger.info(f"Health check enabled: {HEALTH_CHECK_ENABLED}")
    logger.info(f"Restart interval: {RESTART_INTERVAL} seconds")
    logger.info(f"Services to monitor: {len(SERVICES)}")
    
    # Initial startup
    logger.info("Performing initial startup of all services...")
    restart_all_services()
    
    # Wait for services to fully initialize before starting health checks
    logger.info("Waiting for services to initialize...")
    time.sleep(60)  # Give services 1 minute to start up
    
    # Start health monitoring in background
    if HEALTH_CHECK_ENABLED:
        health_thread = threading.Thread(target=health_monitor_worker, daemon=True)
        health_thread.start()
        logger.info("Health monitoring started")
    
    # Main loop
    last_restart = datetime.now()
    
    try:
        while not shutdown_requested:
            current_time = datetime.now()
            
            if HOURLY_RESTART_ENABLED:
                time_since_restart = (current_time - last_restart).total_seconds()
                
                if time_since_restart >= RESTART_INTERVAL:
                    logger.info(f"Hourly restart triggered (last restart: {time_since_restart:.0f}s ago)")
                    restart_all_services()
                    last_restart = current_time
                else:
                    remaining = RESTART_INTERVAL - time_since_restart
                    logger.info(f"Next restart in {remaining:.0f} seconds")
            
            # Sleep for a short interval
            time.sleep(60)  # Check every minute
            
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
        shutdown_requested = True
    except Exception as e:
        logger.error(f"Unexpected error in main scheduler: {e}")
        shutdown_requested = True
    finally:
        logger.info("Shutting down PM2 Monitor...")
        cleanup()

def cleanup():
    """Clean up running processes on shutdown."""
    logger.info("Cleaning up running processes...")
    
    for service_name, process in running_processes.items():
        try:
            if process.poll() is None:  # Process is still running
                logger.info(f"Terminating {service_name} (PID: {process.pid})")
                process.terminate()
                process.wait(timeout=GRACEFUL_SHUTDOWN_TIME)
        except Exception as e:
            logger.warning(f"Error terminating {service_name}: {e}")
    
    logger.info("Cleanup completed")

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, initiating shutdown...")
    shutdown_requested = True

# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """Main entry point."""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        main_scheduler()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
