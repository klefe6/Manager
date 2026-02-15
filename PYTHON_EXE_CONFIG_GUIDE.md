# Configuration Guide for Virtual Environment Paths

## Per Service python_exe Configuration

Each service that requires a specific Python interpreter must define an absolute path to the virtual environment python.exe.

### Example Configurations

#### Almanac Futures

Uses Python 3.12 virtual environment to avoid SQLAlchemy compatibility issues with Python 3.13.

```python
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
```

**Manual Setup Steps:**

```bash
cd "C:\Coding Projects\Almanac Futures"

# Create virtual environment with Python 3.12
python3.12 -m venv .venv312

# Activate and install dependencies
.venv312\Scripts\activate
pip install dash flask-caching pandas numpy plotly sqlalchemy

# Verify installation
python -c "import sqlalchemy; print('SQLAlchemy OK')"
```

---

#### Agent Control Center

Uses Python 3.12 virtual environment with uvicorn and fastapi.

```python
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
```

**Manual Setup Steps:**

```bash
cd "C:\Coding Projects\Agent Control Center"

# Create virtual environment with Python 3.12
python3.12 -m venv .venv312

# Activate and install dependencies
.venv312\Scripts\activate
pip install uvicorn fastapi python-dotenv

# Verify installation
python -c "import uvicorn, fastapi; print('uvicorn and fastapi OK')"
```

---

### Other Services with Virtual Environments

#### Strategy Optimizer

```python
"Strategy Optimizer": {
    "script_path": BASE_DIR / "StrategyOptimizer" / "app.py",
    "port": 8004,
    "url": "http://localhost:8004",
    "cwd": BASE_DIR / "StrategyOptimizer",
    "python_exe": BASE_DIR / "StrategyOptimizer" / ".venv13" / "Scripts" / "python.exe",
},
```

#### Home Page and Debug Page

```python
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
```

#### TWIFO Import Dropbox

```python
"TWIFO Import Dropbox": {
    "script_path": BASE_DIR / "TWIFO_Sharing" / "import_dropbox.py",
    "port": 8009,
    "url": "http://localhost:8009",
    "cwd": BASE_DIR / "TWIFO_Sharing",
    "python_exe": BASE_DIR / "TWIFO_Sharing" / ".venv13" / "Scripts" / "python.exe",
},
```

---

## Services Using System Python

Some services use system Python C:\Python313\python.exe:

```python
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
```

---

## Preflight Check System

### How It Works

1. Before launching a service, run specified Python commands using the configured python_exe
2. Check command output against expected values
3. If check fails, print remediation steps and abort launch
4. If all checks pass, proceed with service launch

### Example Preflight Check

```python
"preflight_checks": [
    {
        "command": "import sys; print(sys.version)",
        "description": "Python version check",
    },
    {
        "command": "import uvicorn; print('OK')",
        "expected": "OK",
        "description": "uvicorn import check",
        "remediation": "Install uvicorn: .venv312\\Scripts\\python.exe -m pip install uvicorn"
    },
]
```

### Output Example

```
[PREFLIGHT] Agent Control Center using C:\Coding Projects\Agent Control Center\.venv312\Scripts\python.exe
  Check: Python executable path
    Output: C:\Coding Projects\Agent Control Center\.venv312\Scripts\python.exe
  Check: uvicorn module check
    Output: True
  Check: fastapi module check
    Output: True
[PREFLIGHT] Agent Control Center passed all checks
```

---

## Health Check System

### Port Polling

After launching a service, the launcher polls the configured port for up to 20 seconds (configurable):

```python
if port:
    print(f"[HEALTH] Waiting for {name} to bind to port {port}...")
    if wait_for_port("127.0.0.1", port, timeout=20):
        print(f"[OK] {name} is now listening on port {port}")
    else:
        print(f"[WARN] {name} did not start listening on port {port} within 20s")
```

### Early Exit Detection

If a process exits within 2 seconds of launch, the last 50 lines of the log are printed:

```python
time.sleep(2)

if process.poll() is not None:
    print(f"[ERROR] {name} terminated immediately (exit code: {process.returncode})")
    print(f"[ERROR] Last 50 lines from log:")
    print(read_last_lines(log_file, 50))
    return None
```

---

## Log File System

### Location

All service logs are stored in:
```
C:\Coding Projects\Manager\logs\
```

### Naming Convention

```
{service_name}_{timestamp}.log
```

Example:
```
Agent_Control_Center_20260214_143022.log
Almanac_Futures_20260214_143025.log
```

### Log Format

```
=== Agent Control Center Launch Log ===
Timestamp: 2026-02-14T14:30:22.123456
Python: C:\Coding Projects\Agent Control Center\.venv312\Scripts\python.exe
Module: main:app
Port: 8007
CWD: C:\Coding Projects\Agent Control Center
======================================================================

[Uvicorn output follows...]
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8007
```

---

## Troubleshooting

### Almanac Futures SQLAlchemy Error

**Symptom:** Service fails preflight check with SQLAlchemy import error

**Fix:**
```bash
cd "C:\Coding Projects\Almanac Futures"

# Create fresh venv with Python 3.12
python3.12 -m venv .venv312

# Install dependencies
.venv312\Scripts\python.exe -m pip install sqlalchemy dash flask-caching pandas numpy plotly

# Verify
.venv312\Scripts\python.exe -c "import sqlalchemy; print('OK')"
```

### Agent Control Center Uvicorn Missing

**Symptom:** Service fails preflight check with uvicorn not found

**Fix:**
```bash
cd "C:\Coding Projects\Agent Control Center"

# Create fresh venv with Python 3.12
python3.12 -m venv .venv312

# Install dependencies
.venv312\Scripts\python.exe -m pip install uvicorn fastapi python-dotenv

# Verify
.venv312\Scripts\python.exe -c "import uvicorn, fastapi; print('OK')"
```

### Service Port Not Binding

**Symptom:** Health check shows port not listening after 20 seconds

**Steps:**
1. Check service log file in C:\Coding Projects\Manager\logs\
2. Look for import errors, database connection errors, or port already in use
3. Verify python_exe path exists and is correct
4. Verify all dependencies are installed in that venv
5. Try running service manually with that python_exe

### Process Exits Immediately

**Symptom:** ERROR message shows process terminated immediately

**Steps:**
1. Check the last 50 lines of log (automatically printed)
2. Look for syntax errors, import errors, or missing modules
3. Run preflight checks manually to verify all dependencies
4. Try running service manually to see full error output

---

## Key Changes from Previous Version

1. **Explicit python_exe paths**: No more relying on PATH or activate scripts
2. **Preflight checks**: Catch missing dependencies before launch
3. **Comprehensive logging**: All stdout and stderr captured with timestamps
4. **Health checks**: Verify port binding before marking success
5. **Early exit detection**: Print last 50 lines of log if process crashes
6. **No silent failures**: Every error is logged and printed

---

## Production Checklist

Before running launch_all_services.py:

1. Verify all python_exe paths exist
2. For Almanac Futures, ensure .venv312 uses Python 3.11 or 3.12
3. For Agent Control Center, ensure .venv312 has uvicorn and fastapi installed
4. Check that Docker Desktop is running (for Summary Engine and Trading Video Library)
5. Verify no port conflicts (run netstat to check ports 8001 through 8080)
6. Clear old log files if needed (logs directory can grow large)

After running:

1. Check console output for any ERROR or WARN messages
2. Open http://localhost:8006 (Debug Page) to verify all services show green
3. Check log files for any services that failed health checks
4. If a service is red in Debug Page, check its log file for errors
5. Run preflight checks manually if needed to diagnose dependency issues
