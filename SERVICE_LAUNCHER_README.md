# Comprehensive Service Launcher

## Overview

The `launch_all_services.py` script launches **ALL** your services in one go:

- ✅ **.bat services** (existing batch file services)
- ✅ **Dash applications** (Price Dashboard, Sector RRG, Strategy Optimizer, Home Page, Debug Page)
- ✅ **Streamlit applications** (QuantLab Dashboard)

## Features

### Automatic Browser Opening
- Opens browser tabs for all web services automatically
- Waits 5 seconds for services to start before opening
- Handles port conflicts gracefully

### Port Management
- **Dash apps**: Fixed ports (3000, 8055, 8056, 8059, 8070)
- **Streamlit apps**: Auto-increments if port in use (8501 → 8502 → 8503...)
- Port availability checking before launch

### Virtual Environment Support
- Automatically detects and uses venv Python when available
- Falls back to system Python if venv not found
- HomePage uses `.venv13`
- QuantLab uses `venv`

### Service Registry
- Saves service information to `service_registry.json`
- Tracks PIDs, ports, URLs, and service types
- Useful for monitoring and debugging

## Services Launched

### .BAT Services (9 services)
1. TWIFO Sharing (port 8065)
2. Import Dropbox (port 8501 - may conflict with Streamlit)
3. TS Generator (port 8077)
4. TKP Tearsheet (port 8076)
5. Y&Q Tearsheet (port 8071)
6. Gold Maker (port 8075)
7. Sector Ratio (port 8080)
8. ES Historical Data (port 8081)
9. Almanac Futures (port 8072)

### Dash Applications (5 apps)
1. **Price Dashboard** - `Price Dashboard/app.py` (port 3000)
2. **Sector RRG** - `Sector/app_rrg.py` (port 8059)
3. **Strategy Optimizer** - `StrategyOptimizer/app.py` (port 8070)
4. **Home Page** - `HomePage/main.py` (port 8055, uses .venv13)
5. **Debug Page** - `HomePage/debug.py` (port 8056, uses .venv13)

### Streamlit Applications (1 app)
1. **QuantLab Dashboard** - `QuantLab/dashboard/app.py` (port 8501, auto-increments)

**Total: 15 services**

## Usage

### Quick Start
```powershell
cd "C:\Program Files\Coding Projects\Manager"
python launch_all_services.py
```

Or double-click:
```
launch_all.bat
```

### What Happens

1. **Phase 1**: Launches all .bat services (each in new window)
2. **Phase 2**: Launches all Dash applications (background processes)
3. **Phase 3**: Launches all Streamlit applications (background processes)
4. **Phase 4**: Waits 5 seconds, then opens browser tabs for all web services
5. **Phase 5**: Saves service registry to `service_registry.json`

### Browser Tabs Opened

The launcher automatically opens:
- http://localhost:3000 - Price Dashboard
- http://localhost:8055 - Home Page
- http://localhost:8056 - Debug Page
- http://localhost:8059 - Sector RRG
- http://localhost:8070 - Strategy Optimizer
- http://localhost:8501 (or 8502, 8503...) - QuantLab Dashboard

## Configuration

Edit `launch_all_services.py` to:
- Add/remove services
- Change ports
- Adjust launch delays
- Enable health monitoring

### Adding a New Service

**Dash App:**
```python
DASH_APPS["My New App"] = {
    "path": BASE_DIR / "MyApp" / "app.py",
    "port": 8082,
    "url": "http://localhost:8082",
    "cwd": BASE_DIR / "MyApp",
    "venv": None,  # or Path to venv
}
```

**Streamlit App:**
```python
STREAMLIT_APPS["My Streamlit App"] = {
    "path": BASE_DIR / "MyApp" / "app.py",
    "base_port": 8503,
    "cwd": BASE_DIR / "MyApp",
    "venv": BASE_DIR / "MyApp" / "venv",
}
```

## Service Registry

After launch, check `service_registry.json`:

```json
{
  "launched_at": "2026-01-18T14:30:00",
  "services": {
    "Price Dashboard": {
      "name": "Price Dashboard",
      "pid": 12345,
      "type": "dash",
      "port": 3000,
      "url": "http://localhost:3000"
    },
    "QuantLab Dashboard": {
      "name": "QuantLab Dashboard",
      "pid": 12346,
      "type": "streamlit",
      "port": 8501,
      "url": "http://localhost:8501"
    }
  }
}
```

## Troubleshooting

### Port Already in Use
- The launcher checks port availability
- Streamlit auto-increments (8501 → 8502 → 8503...)
- Dash apps will show a warning but attempt to start anyway
- Check `service_registry.json` for actual ports used

### Service Not Starting
- Check if Python executable is correct
- Verify venv exists (if specified)
- Check service logs in their respective directories
- Verify file paths are correct

### Browser Not Opening
- Services need ~5 seconds to start
- Check if browser is set as default
- Manually open URLs from `service_registry.json`

### Streamlit Port Detection
- Streamlit may use a different port than specified
- Check Streamlit output in terminal
- Or check `service_registry.json` for actual port

## Stopping Services

**Option 1: Close Windows**
- Close .bat service windows
- Close Python terminal windows

**Option 2: Task Manager**
- Find Python processes
- End process by PID (from `service_registry.json`)

**Option 3: PowerShell**
```powershell
# Stop all Python processes (CAREFUL - stops ALL Python)
Get-Process python* | Stop-Process

# Or stop by specific port
netstat -ano | findstr :3000
taskkill /PID <PID> /F
```

## Notes

- Services run in background (detached from launcher)
- Launcher can be closed after launch (services continue)
- Health monitoring is disabled by default
- Daily restart is enabled (restarts TKP Tearsheet every 24h)
- All paths are Windows-native (backslashes, no WSL)

## Success Criteria

After running `launch_all_services.py`:
- ✅ All 15 services launched
- ✅ Browser tabs opened for web services
- ✅ `service_registry.json` created
- ✅ All services accessible via their URLs
- ✅ No port conflicts (or handled gracefully)
