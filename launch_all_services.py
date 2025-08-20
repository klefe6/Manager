#!/usr/bin/env python3
"""
launch_and_watch.py

- Always launches all services once on start.
- If HEALTH_CHECK_ENABLED = True, monitors each service every CHECK_INTERVAL seconds
  and restarts any that fail more than FAIL_THRESHOLD consecutive checks.
- If DAILY_RESTART_ENABLED = True, restarts the TKP Tearsheet service every 24 hours.
"""

import subprocess
import os
import time
import socket
import sys

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
HEALTH_CHECK_ENABLED   = False      # monitor & auto‑restart unhealthy services
DAILY_RESTART_ENABLED  = True      # restart TKP Tearsheet every 24 hours

FAIL_THRESHOLD         = 2         # consecutive failures before restart
CHECK_INTERVAL         = 15        # seconds between health checks
LAUNCH_PAUSE           = 3         # seconds pause between launching each .bat
DAILY_RESTART_INTERVAL = 24 * 60 * 60  # 24 hours in seconds

TKP_SERVICE_NAME       = "TKP Tearsheet"  # key in SERVICES dict to restart daily

# ─── Map each service name → full path to its .bat ───────────────────────────
SERVICES = {
    "TWIFO Sharing":    r"C:\Program Files\Coding Projects\TWIFO_Sharing\reboot_twifo.bat",
    "Import Dropbox":   r"C:\Program Files\Coding Projects\TWIFO_Sharing\reboot_import_dropbox.bat",
    "TS Generator":     r"C:\Program Files\Coding Projects\Tearsheet Generator\run_tsgen.bat",
    "TKP Tearsheet":    r"C:\Program Files\Coding Projects\Tearsheet Generator\reboot_tkp_ts.bat",
    "Gold Maker":       r"C:\Program Files\Coding Projects\Tearsheet Generator\reboot_gold_maker.bat",
    "Strategy Opt":     r"C:\Program Files\Coding Projects\StrategyOptimizer\reboot_strategy_optimizer.bat",
    "Home Page":        r"C:\Program Files\Coding Projects\HomePage\reboot_homepage.bat",
    "Debug Page":       r"C:\Program Files\Coding Projects\HomePage\reboot_debug.bat",
    "GSR Service":      r"C:\Program Files\Coding Projects\GSR\reboot_gsr.bat",
    "ES Historical":    r"C:\Program Files\Coding Projects\ES Historical Data\reboot_es_historical_data.bat",
    "Almanac Futures":  r"C:\Program Files\Coding Projects\Almanac Futures\reboot_almanac.bat",
}

# ─── Map each service name → (host, port) used for TCP health checks ─────────
PORTS = {
    "TWIFO Sharing":   ("127.0.0.1", 8065),
    "Import Dropbox":  ("127.0.0.1", 8055),
    "TS Generator":    ("127.0.0.1", 8077),
    "TKP Tearsheet":   ("127.0.0.1", 8076),
    "Gold Maker":      ("127.0.0.1", 8075),
    "Strategy Opt":    ("127.0.0.1", 8080),
    "Home Page":       ("127.0.0.1", 8050),
    "Debug Page":      ("127.0.0.1", 8060),
    "GSR Service":     ("127.0.0.1", 8070),
    "ES Historical":   ("127.0.0.1", 8071),
    "Almanac Futures": ("127.0.0.1", 8072),
}


def is_service_healthy(host: str, port: int) -> bool:
    """
    Return True if we can open a TCP connection to host:port, else False.
    """
    try:
        with socket.create_connection((host, port), timeout=5):
            return True
    except Exception:
        return False


def launch_services(names, fail_counts):
    """
    For each service name in `names`, launch its .bat (in a new window),
    reset its fail count, and pause briefly between launches.
    """
    for name in names:
        bat = SERVICES.get(name)
        if not bat or not os.path.isfile(bat):
            print(f"[ERROR] .bat not found for {name}: {bat}")
            continue

        cwd = os.path.dirname(bat)
        print(f"[LAUNCH] {name} → {bat}")
        subprocess.Popen(f'start "" "{bat}"', cwd=cwd, shell=True)
        fail_counts[name] = 0
        time.sleep(LAUNCH_PAUSE)


def check_health(fail_counts):
    """
    Check each service in PORTS. Increment fail_counts on failure,
    reset on success, and collect any that exceed FAIL_THRESHOLD.
    Returns a list of names to restart.
    """
    to_restart = []
    for name, (host, port) in PORTS.items():
        healthy = is_service_healthy(host, port)
        if healthy:
            fail_counts[name] = 0
            print(f"[OK]   {name} (port {port})")
        else:
            fail_counts[name] += 1
            print(f"[FAIL] {name} (port {port}) [{fail_counts[name]}/{FAIL_THRESHOLD}]")
            if fail_counts[name] >= FAIL_THRESHOLD:
                to_restart.append(name)
    return to_restart


def main():
    # initialize failure counters for every service
    fail_counts = {name: 0 for name in SERVICES}

    print(f"\n[INFO] HEALTH_CHECK_ENABLED  = {HEALTH_CHECK_ENABLED}")
    print(f"[INFO] DAILY_RESTART_ENABLED = {DAILY_RESTART_ENABLED}\n")

    print("[INFO] Initial launch of all services\n")
    launch_services(SERVICES.keys(), fail_counts)

    # track last daily restart time
    last_daily_restart = time.time()

    # if neither feature is on, exit immediately
    if not HEALTH_CHECK_ENABLED and not DAILY_RESTART_ENABLED:
        print("[INFO] No monitoring or daily restart enabled; exiting.\n")
        return

    try:
        while True:
            # Sleep once per health‑check interval
            time.sleep(CHECK_INTERVAL)

            # 1) Health‑check loop
            if HEALTH_CHECK_ENABLED:
                to_restart = check_health(fail_counts)
                if to_restart:
                    print(f"\n[WARN] Restarting failed services: {', '.join(to_restart)}\n")
                    launch_services(to_restart, fail_counts)
                else:
                    # any services in warning state?
                    warnings = [n for n, c in fail_counts.items() if 0 < c < FAIL_THRESHOLD]
                    if warnings:
                        print(f"\n[WARN] Services warning (not yet restarted): {', '.join(warnings)}\n")
                    else:
                        print("\n[OK] All services healthy — continuing to monitor.\n")

            # 2) Daily restart check
            if DAILY_RESTART_ENABLED:
                now = time.time()
                if now - last_daily_restart >= DAILY_RESTART_INTERVAL:
                    print(f"\n[INFO] 24h elapsed — restarting {TKP_SERVICE_NAME}\n")
                    launch_services([TKP_SERVICE_NAME], fail_counts)
                    last_daily_restart = now

    except KeyboardInterrupt:
        print("\n[INFO] Shutdown requested by user. Exiting.\n")


if __name__ == "__main__":
    main()
