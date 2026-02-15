# Quick Config Reference for python_exe Paths

## Almanac Futures

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

**Manual Fix if Needed:**

```bash
cd "C:\Coding Projects\Almanac Futures"
python3.12 -m venv .venv312
.venv312\Scripts\python.exe -m pip install sqlalchemy dash flask-caching pandas numpy plotly
```

## Agent Control Center

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

**Manual Fix if Needed:**

```bash
cd "C:\Coding Projects\Agent Control Center"
python3.12 -m venv .venv312
.venv312\Scripts\python.exe -m pip install uvicorn fastapi python-dotenv
```

## Key Features

1. Absolute path to python.exe in virtual environment
2. No use of python from PATH
3. No shell activate scripts
4. Preflight checks catch missing dependencies before launch
5. Remediation steps printed if check fails
6. No automatic installation, manual fix required

## Testing Commands

### Almanac Futures Preflight

```bash
"C:\Coding Projects\Almanac Futures\.venv312\Scripts\python.exe" -c "import sys; print(sys.version)"
"C:\Coding Projects\Almanac Futures\.venv312\Scripts\python.exe" -c "import sqlalchemy; print('OK')"
```

### Agent Control Center Preflight

```bash
"C:\Coding Projects\Agent Control Center\.venv312\Scripts\python.exe" -c "import sys; print(sys.executable)"
"C:\Coding Projects\Agent Control Center\.venv312\Scripts\python.exe" -c "import pkgutil; print('uvicorn' in [m.name for m in pkgutil.iter_modules()])"
"C:\Coding Projects\Agent Control Center\.venv312\Scripts\python.exe" -c "import pkgutil; print('fastapi' in [m.name for m in pkgutil.iter_modules()])"
```
