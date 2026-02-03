# Almanac Startup Fix Summary

## Problem
The PM2 monitor was failing to properly start Almanac Futures, running an old version instead of the most recent one.

## Root Causes Identified

### 1. **Port Mismatch** ❌
- **Issue**: Almanac_main.py was configured to run on port **8085**
- **Monitor Expected**: Port **8072**  
- **Result**: Health checks failed, old processes kept running

### 2. **Debug Mode Enabled** ❌
- **Issue**: `debug=True` in Dash causes the reloader to spawn multiple Python processes
- **Result**: Multiple duplicate Almanac processes running simultaneously

### 3. **Process Killing Not Working** ❌  
- **Issue**: The monitor's `kill_existing_processes()` function had the logic but `psutil` wasn't being imported properly in some cases
- **Result**: Old Almanac processes were never terminated, stacking up

## Fixes Applied

### 1. **Fixed Port Configuration** ✅
**File**: `C:\Coding Projects\Almanac Futures\Almanac_main.py`
```python
# Changed from:
app.run(host='127.0.0.1', port=8085, debug=True)

# To:
app.run(host='127.0.0.1', port=8072, debug=False)
```

### 2. **Improved Process Killing** ✅
**File**: `pm2_monitor_simple.py`
- Enhanced the `kill_existing_processes()` function with:
  - Better error handling and logging
  - More specific pattern matching for Almanac (`almanac_main.py`, `almanac`)
  - Added exclusions for test scripts and monitor itself
  - Force kill if terminate fails (using `proc.kill()` after timeout)
  - Proper wait for process termination with timeout handling

### 3. **Better Logging** ✅
- Added detailed logging to track:
  - When psutil is successfully imported
  - Which processes are being terminated
  - How many processes were killed
  - Any errors during process termination

## Testing Results

After fixes:
- ✅ Almanac starts on the correct port (8072)
- ✅ Health checks pass successfully
- ✅ Old processes are properly terminated before new start
- ✅ No debug mode duplicates

## How It Works Now

1. **Monitor starts** → Calls `start_service("Almanac Futures")`
2. **Kill old processes** → `kill_existing_processes()` terminates any running Almanac instances
3. **Start fresh** → Launches `reboot_almanac.bat` in new window
4. **Batch file runs**:
   - Activates `.venv13` virtual environment
   - Runs `python Almanac_main.py`  
   - Almanac starts on port 8072 with `debug=False`
5. **Health check** → Monitor verifies port 8072 is responding

## Usage

Run the monitor as usual:
```
start_simple_monitor.bat
```

The monitor will now properly start Almanac with the latest version on the correct port.

