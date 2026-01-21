#!/usr/bin/env python3
"""
Simple PM2 Monitor for Windows Batch Files

A simplified version that starts all services once and exits.
This version removes all looping mechanisms, performance monitoring,
and automatic restarting functionality.
"""

import subprocess
import os
import time
import socket
import sys
import logging
from datetime import datetime
from typing import Dict, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

# Core settings - Optimized for maximum stability and minimal resource usage
LAUNCH_PAUSE           = 1         # seconds pause between launching each .bat (minimal delay)
STARTUP_DELAY          = 0         # seconds to wait after startup before health checks (0 = skip wait entirely)
SKIP_HEALTH_CHECK      = True      # Skip health checks entirely (fastest, prevents hanging)
KILL_EXISTING_PROCESSES = False    # Skip process killing to reduce system load (disabled by default)
CHECK_HEALTH_BEFORE_KILL = False   # Skip health check before starting (faster launches)
ALLOW_CONSOLE_WINDOWS  = True      # Set False to run services in background (prevents window spam)

# Diagnostic mode - launches services sequentially and records resource usage deltas
DIAGNOSTIC_MODE        = True      # Enable sequential start + profiling to isolate problem services
DIAG_PAUSE_BETWEEN     = 5         # seconds to wait after starting each service during diagnostics
DIAG_VERIFY_TIMEOUT    = 10        # seconds max to probe health for the just-started service
STOP_ON_SUSPECT        = True      # Stop diagnostic run if a suspicious spike/failure is detected

# Logging - Optimized for stability (INFO for important messages, DEBUG for verbose)
LOG_LEVEL = logging.INFO  # Keep INFO for important startup messages, but minimize debug spam
LOG_FILE  = "pm2_monitor_simple.log"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB max log size (rotate if needed)

# ─── Service Configuration ───────────────────────────────────────────────────
# Note: Services are ordered by priority - Debug Page starts first
# TODO: "Database Filtering System" (filemanager.hcresearch.ltd) is missing from this list
#       Need to identify the service folder, batch file, and port to add it
SERVICES = {
    "Debug Page":       r"C:\Program Files\Coding Projects\HomePage\reboot_debug.bat",
    "TWIFO Sharing":    r"C:\Program Files\Coding Projects\TWIFO_Sharing\reboot_twifo.bat",
    "Import Dropbox":   r"C:\Program Files\Coding Projects\TWIFO_Sharing\reboot_import_dropbox.bat",
    "TS Generator":     r"C:\Program Files\Coding Projects\Tearsheet Generator\run_tsgen.bat",
    "TKP Tearsheet":    r"C:\Program Files\Coding Projects\Tearsheet Generator\reboot_tkp_ts.bat",
    "Y&Q Tearsheet":    r"C:\Program Files\Coding Projects\Tearsheet Generator\reboot_yq_ts.bat",
    "Gold Maker":       r"C:\Program Files\Coding Projects\Tearsheet Generator\reboot_gold_maker.bat",
    "Price Dashboard":  r"C:\Program Files\Coding Projects\Price Dashboard\reboot_dashboard.bat",
    "Strategy Opt":     r"C:\Program Files\Coding Projects\StrategyOptimizer\reboot_strategy_optimizer.bat",
    "Home Page":        r"C:\Program Files\Coding Projects\HomePage\reboot_homepage.bat",
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

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL STATE
# ─────────────────────────────────────────────────────────────────────────────

restart_counts = {}

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────────────────────────────────────

def setup_logging():
    """Configure logging with both file and console output - optimized for performance."""
    import logging.handlers
    
    # Use RotatingFileHandler to prevent log files from growing too large
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, 
        encoding='utf-8',
        maxBytes=MAX_LOG_SIZE,
        backupCount=1  # Keep only 1 backup file
    )
    
    # Console handler with reduced output
    console_handler = logging.StreamHandler(sys.stdout)
    
    # Set format
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Configure logger
    logger = logging.getLogger(__name__)
    logger.setLevel(LOG_LEVEL)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Prevent duplicate logs
    logger.propagate = False
    
    return logger

logger = setup_logging()

# ─────────────────────────────────────────────────────────────────────────────
# SERVICE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def is_service_healthy(host: str, port: int) -> bool:
    """Check if a service is healthy by attempting a TCP connection."""
    try:
        with socket.create_connection((host, port), timeout=1):  # Reduced timeout from 3 to 1 second
            return True
    except Exception:
        return False

def start_service(service_name: str) -> bool:
    """Start a service - optimized for speed and minimal resource usage."""
    bat_path = SERVICES.get(service_name)
    if not bat_path or not os.path.isfile(bat_path):
        logger.error(f"Batch file not found for {service_name}: {bat_path}")
        return False
    
    try:
        cwd = os.path.dirname(bat_path)
        
        # Check if service is already healthy before doing anything (only if enabled)
        if CHECK_HEALTH_BEFORE_KILL and service_name in PORTS:
            try:
                host, port = PORTS[service_name]
                if is_service_healthy(host, port):
                    logger.info(f"{service_name} is already healthy on port {port}, skipping start")
                    return True
            except Exception as health_check_error:
                # If health check fails, just proceed to start anyway
                logger.debug(f"Health check failed for {service_name}, proceeding: {health_check_error}")
        
        logger.info(f"Starting {service_name} from {bat_path}")
        
        # Kill any existing processes for this service first (only if enabled)
        if KILL_EXISTING_PROCESSES:
            try:
                kill_existing_processes(service_name)
            except Exception as kill_error:
                # If process killing fails, just proceed to start anyway
                logger.debug(f"Process killing failed for {service_name}, proceeding: {kill_error}")
        
        # Start the batch file in a new window with a unique title (or background)
        # Use close_fds and detach to prevent resource leaks
        try:
            if ALLOW_CONSOLE_WINDOWS:
                window_title = f"PM2-{service_name}"
                # Use start command to open in new window
                proc = subprocess.Popen(
                    f'start "{window_title}" "{bat_path}"',
                    cwd=cwd,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True  # Close file descriptors to prevent resource leaks
                )
                # Don't wait for process - let it run independently
                proc.poll()  # Check if started (non-blocking)
            else:
                # Run in background without opening window
                proc = subprocess.Popen(
                    [bat_path],
                    cwd=cwd,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                proc.poll()  # Check if started (non-blocking)
        except Exception as launch_error:
            logger.warning(f"Failed to launch {service_name}: {launch_error}")
            return False
        
        logger.info(f"Successfully started {service_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to start {service_name}: {e}")
        return False

def kill_existing_processes(service_name: str):
    """Kill existing processes for a service to prevent terminal stacking.
    Optimized to reduce system load by using more specific matching and caching.
    """
    try:
        import psutil
        
        # More specific patterns - avoid generic terms like "node" that match too many processes
        # Only match processes that are clearly related to our service
        patterns = {
            "Debug Page": ["reboot_debug", "debug.py"],
            "TWIFO Sharing": ["reboot_twifo", "twifo.py"],
            "Import Dropbox": ["reboot_import_dropbox", "import_dropbox.py"],
            "TS Generator": ["run_tsgen", "tsgen"],
            "TKP Tearsheet": ["reboot_tkp_ts", "tkp"],
            "Y&Q Tearsheet": ["reboot_yq_ts", "yq"],
            "Gold Maker": ["reboot_gold_maker", "gold_maker"],
            "Price Dashboard": ["reboot_dashboard", "app.py", "price"],
            "Strategy Opt": ["reboot_strategy_optimizer", "strategy_optimizer"],
            "Home Page": ["reboot_homepage", "homepage"],
            "Sector Ratio": ["reboot_gsr", "gsr.py"],
            "ES Historical": ["reboot_es_historical_data", "es_historical"],
            "Almanac Futures": ["reboot_almanac", "almanac"],
        }
        
        service_patterns = patterns.get(service_name, [])
        if not service_patterns:
            logger.debug(f"No specific patterns for {service_name}, skipping process kill")
            return
        
        # Get the service's working directory for more precise matching
        bat_path = SERVICES.get(service_name)
        if bat_path:
            service_dir = os.path.dirname(bat_path).lower()
        else:
            service_dir = ""
        
        killed_count = 0
        # Cache process list to avoid multiple iterations (with timeout protection)
        try:
            # Limit process scan time to prevent hanging
            processes = list(psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']))
        except Exception as scan_error:
            logger.warning(f"Failed to scan processes: {scan_error}")
            return
        
        for proc in processes:
            try:
                # Quick check - skip if process already dead
                if not proc.is_running():
                    continue
                    
                proc_name = proc.info['name'].lower() if proc.info['name'] else ""
                cmdline = ' '.join(proc.info['cmdline']).lower() if proc.info['cmdline'] else ""
                
                # Try to get cwd, but don't fail if we can't
                try:
                    proc_cwd = proc.info['cwd'].lower() if proc.info.get('cwd') else ""
                except (psutil.AccessDenied, AttributeError):
                    proc_cwd = ""
                
                # More specific matching: must match pattern AND be in service directory
                matches_pattern = any(pattern in cmdline for pattern in service_patterns)
                matches_dir = service_dir and service_dir in proc_cwd
                
                if matches_pattern and (matches_dir or not service_dir):
                    logger.debug(f"Terminating existing process for {service_name}: PID {proc.pid}")
                    proc.terminate()
                    killed_count += 1
                    # Reduced sleep time - only wait if we actually killed something
                    if killed_count == 1:
                        time.sleep(0.5)  # Reduced further to prevent delays
                            
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception as e:
                logger.debug(f"Error checking process {proc.pid}: {e}")
                continue
        
        if killed_count > 0:
            logger.info(f"Killed {killed_count} existing process(es) for {service_name}")
        else:
            logger.debug(f"No existing processes found for {service_name}")
                
    except ImportError:
        logger.warning("psutil not available - cannot kill existing processes")
    except Exception as e:
        logger.warning(f"Error killing existing processes for {service_name}: {e}")


def restart_all_services() -> Dict[str, bool]:
    """Restart all configured services - optimized for speed."""
    logger.info("=" * 60)
    logger.info("RESTARTING ALL SERVICES")
    logger.info("=" * 60)
    
    results = {}
    for service_name in SERVICES.keys():
        try:
            logger.info(f"Starting {service_name}...")
            success = start_service(service_name)
            results[service_name] = success
            
            if success:
                restart_counts[service_name] = restart_counts.get(service_name, 0) + 1
                logger.info(f"[SUCCESS] {service_name} started (restart #{restart_counts[service_name]})")
            else:
                logger.warning(f"[WARNING] {service_name} may have failed to start")
            
            # Only pause if configured (allows for instant launches if LAUNCH_PAUSE=0)
            if LAUNCH_PAUSE > 0:
                time.sleep(LAUNCH_PAUSE)
        except Exception as service_error:
            logger.error(f"[ERROR] Exception starting {service_name}: {service_error}")
            results[service_name] = False
            # Continue with next service even if one fails
            continue
    
    return results

def check_all_services_health() -> Dict[str, bool]:
    """Check health of all services - optimized with timeout protection."""
    health_status = {}
    
    for service_name, (host, port) in PORTS.items():
        try:
            healthy = is_service_healthy(host, port)
            health_status[service_name] = healthy
            status = "[HEALTHY]" if healthy else "[UNHEALTHY]"
            logger.debug(f"{service_name}: {status} (port {port})")
        except Exception as health_error:
            # If health check fails, mark as unhealthy but don't crash
            logger.debug(f"Health check error for {service_name}: {health_error}")
            health_status[service_name] = False
    
    return health_status

# ─────────────────────────────────────────────────────────────────────────────
# DIAGNOSTICS
# ─────────────────────────────────────────────────────────────────────────────

def _resource_snapshot() -> Dict[str, float]:
    """Return a lightweight CPU/memory snapshot. Falls back gracefully without psutil."""
    snapshot = {"cpu_percent": -1.0, "mem_percent": -1.0}
    try:
        import psutil  # type: ignore
        # Non-blocking, low-cost probes
        snapshot["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        snapshot["mem_percent"] = psutil.virtual_memory().percent
    except Exception:
        # psutil missing or restricted; keep defaults
        pass
    return snapshot

def _log_snapshot(prefix: str):
    snap = _resource_snapshot()
    logger.info(f"{prefix} cpu={snap['cpu_percent']:.1f}% mem={snap['mem_percent']:.1f}%")

def run_diagnostic_sequence():
    """Sequentially start services, pausing in between, and log resource deltas.

    Goal: identify the most recent service started before Cursor/system instability.
    """
    logger.info("===== DIAGNOSTIC MODE: sequential launch + profiling =====")
    services = list(SERVICES.keys())
    total = len(services)

    base_snap = _resource_snapshot()
    logger.info(
        f"Baseline resources cpu={base_snap['cpu_percent']:.1f}% mem={base_snap['mem_percent']:.1f}%"
    )

    for idx, service_name in enumerate(services, start=1):
        logger.info(f"[DIAG {idx}/{total}] Starting: {service_name}")
        pre = _resource_snapshot()

        ok = start_service(service_name)
        if not ok:
            logger.warning(f"[DIAG] Start reported failure for {service_name}")

        # Gentle settle pause to surface issues without blocking long
        time.sleep(max(0, DIAG_PAUSE_BETWEEN))

        # Optional quick health probe for just-started service
        healthy = True
        if service_name in PORTS and DIAG_VERIFY_TIMEOUT > 0 and not SKIP_HEALTH_CHECK:
            host, port = PORTS[service_name]
            deadline = time.time() + DIAG_VERIFY_TIMEOUT
            healthy = False
            while time.time() < deadline:
                if is_service_healthy(host, port):
                    healthy = True
                    break
                time.sleep(0.5)

        post = _resource_snapshot()
        cpu_delta = post["cpu_percent"] - pre["cpu_percent"] if pre["cpu_percent"] >= 0 else -1.0
        mem_delta = post["mem_percent"] - pre["mem_percent"] if pre["mem_percent"] >= 0 else -1.0

        logger.info(
            f"[DIAG] {service_name} healthy={healthy} cpuΔ={cpu_delta:.1f}pp memΔ={mem_delta:.1f}pp"
        )

        # Heuristic: if health probe failed OR memory jumped > 10pp, mark as suspect
        suspect = (not healthy) or (mem_delta >= 10.0)
        if suspect:
            logger.warning(f"[DIAG] SUSPECT service: {service_name}")
            if STOP_ON_SUSPECT:
                logger.warning("[DIAG] Stopping diagnostic run at first suspect by config")
                break

    logger.info("===== DIAGNOSTIC MODE COMPLETE =====")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN SCHEDULER
# ─────────────────────────────────────────────────────────────────────────────

def start_services_once():
    """Start all services once and exit - optimized for speed and stability."""
    logger.info("PM2 Monitor started - Single Run Mode (Optimized)")
    logger.info(f"Services to start: {len(SERVICES)}")
    
    # Initial startup
    try:
        logger.info("Starting all services...")
        restart_all_services()
    except Exception as startup_error:
        logger.error(f"Error during service startup: {startup_error}")
        # Continue anyway - some services may have started
    
    # Wait for services to initialize (only if configured)
    if not SKIP_HEALTH_CHECK and STARTUP_DELAY > 0:
        logger.info(f"Waiting {STARTUP_DELAY} seconds for services to initialize...")
        try:
            # Break wait into smaller chunks to prevent Cursor from thinking it's hung
            chunks = max(1, STARTUP_DELAY // 10)  # Update every 10 seconds
            for i in range(chunks):
                time.sleep(10)
                remaining = STARTUP_DELAY - ((i + 1) * 10)
                if remaining > 0:
                    logger.debug(f"Still waiting... {remaining} seconds remaining")
            
            # Check initial health (with timeout protection)
            logger.info("Checking service health...")
            try:
                health_status = check_all_services_health()
                healthy_count = sum(1 for healthy in health_status.values() if healthy)
                total_count = len(health_status)
                logger.info(f"Health check complete: {healthy_count}/{total_count} services healthy")
            except Exception as health_error:
                logger.warning(f"Health check failed: {health_error}")
        except KeyboardInterrupt:
            logger.info("Health check interrupted by user")
    elif SKIP_HEALTH_CHECK:
        logger.info("Health check skipped (SKIP_HEALTH_CHECK=True) - Fast mode")
    else:
        logger.info("Health check skipped (STARTUP_DELAY=0) - Instant mode")
    
    logger.info("PM2 Monitor completed - All services started")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """Main entry point."""
    try:
        if DIAGNOSTIC_MODE:
            run_diagnostic_sequence()
        else:
            start_services_once()
    except KeyboardInterrupt:
        logger.info("Interrupted by user (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Ensure logging is flushed
        try:
            logging.shutdown()
        except Exception:
            pass

if __name__ == "__main__":
    main()
