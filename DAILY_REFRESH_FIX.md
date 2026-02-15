# Daily Data Refresh Fix - Summary

**Date:** 2026-02-11  
**Issue:** TCP and TKP tearsheet websites were not refreshing with new data on a daily basis

## Root Cause

The tearsheet applications load their Excel data once at startup (module-level imports), and the data never refreshes unless the Python process restarts. The Manager had daily restart configured but the restart logic was incomplete - it logged restart messages but never actually killed and relaunched the services.

## Solution Implemented

### 1. Manager Service Launcher (`launch_all_services.py`)

#### Added `kill_process_tree()` function
- Uses Windows `taskkill /F /T` to kill process and all children
- Essential for clean service termination

#### Added `restart_services()` function
- Takes a list of service names to restart
- Kills existing processes gracefully
- Relaunches services using appropriate launcher (BAT, Dash, Streamlit, etc.)
- Waits for services to bind to their ports before continuing
- Resets failure counters after successful restart

#### Fixed daily restart loop
- Previously: Only logged restart message but took no action
- Now: Actually calls `restart_services()` with the configured service list
- Services restart every 24 hours (configurable via `DAILY_RESTART_INTERVAL`)

### 2. TKP Tearsheet (`tkp_ts.py`)

#### Changed layout to dynamic function
- Previously: `app.layout = html.Div([...])` with static `serve_layout()` call
- Now: `app.layout = dynamic_layout` where `dynamic_layout` is a function
- Dash calls this function on each page load/reload
- Combined with process restart, ensures fresh data on each daily cycle

### 3. TCP Tearsheet (`tcp_ts.py`)

#### Same changes as TKP
- Converted to dynamic layout function
- Ensures consistency between both tearsheet applications

## Configuration

Current settings in `launch_all_services.py`:

```python
DAILY_RESTART_ENABLED = True
DAILY_RESTART_INTERVAL = 24 * 60 * 60  # 24 hours (86400 seconds)
DAILY_RESTART_SERVICES = ["TKP Tearsheet", "TCP Tearsheet"]
```

## How It Works

1. **Manager launches services** - TKP and TCP start and load data from Excel files
2. **Services run for 24 hours** - Serving cached data loaded at startup
3. **24-hour timer triggers** - Manager detects restart interval has elapsed
4. **Services are killed** - Process tree termination ensures clean shutdown
5. **Services are relaunched** - Fresh Python process reloads all data from Excel
6. **New data is served** - Users see updated performance metrics

## Data Flow

```
Excel File (updated daily)
    ↓
Manager restarts service (every 24 hours)
    ↓
Python process reloads module
    ↓
Data loaded fresh from Excel
    ↓
Dash app serves updated tearsheet
    ↓
Users see current data
```

## Testing

A test script has been created: `Manager/test_restart_mechanism.py`

### To verify configuration:
```bash
cd "C:\Coding Projects\Manager"
python test_restart_mechanism.py
```

### To test actual restart (without waiting 24 hours):
1. Edit `launch_all_services.py`
2. Change `DAILY_RESTART_INTERVAL = 24 * 60 * 60` to `DAILY_RESTART_INTERVAL = 60`
3. Start Manager: `python launch_all_services.py`
4. Watch console - services will restart after 60 seconds
5. Verify services come back up and data is fresh
6. **Remember to change interval back to 24 hours!**

## Benefits

✅ **Automatic daily updates** - No manual intervention required  
✅ **Consistent timing** - Updates at same time every day (24 hours after Manager start)  
✅ **Clean restarts** - Process tree termination prevents zombie processes  
✅ **Health monitoring** - Waits for services to bind to ports after restart  
✅ **Configurable** - Easy to adjust restart interval if needed  
✅ **Reliable** - Both TKP and TCP use identical mechanism  

## Maintenance Notes

- **Excel files must be closed** when services restart (or they can't read them)
- **Restart interval is from Manager start** - If you want restarts at specific time (e.g., 3 AM daily), start Manager at 3 AM
- **Port conflicts** - Restart logic checks port availability before relaunching
- **Logs** - All restart activity logged to console and service logs in `Manager/logs/`

## Files Modified

1. `Manager/launch_all_services.py` - Added restart logic, fixed daily loop
2. `Tearsheet Generator/tkp_ts.py` - Dynamic layout for fresh data
3. `Tearsheet Generator/tcp_ts.py` - Dynamic layout for fresh data
4. `Manager/test_restart_mechanism.py` - New test/verification script

## Verification Checklist

- [x] restart_services() function implemented
- [x] kill_process_tree() function implemented  
- [x] Daily restart loop calls restart_services()
- [x] TKP uses dynamic layout
- [x] TCP uses dynamic layout
- [x] No linting errors
- [x] Test script created
- [x] Configuration verified (services are running on correct ports)
- [x] Documentation created
