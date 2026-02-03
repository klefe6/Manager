# Service Launch Testing Guide
**Date:** 2026-01-19

## Quick Test - Verify Fixes Work

### 1. Test Launch All Services

```powershell
cd "C:\Coding Projects\Manager"
python launch_all_services.py
```

**Expected behavior:**
- Multiple console windows open (one per service)
- Each window shows service output
- No hangs or freezes
- Services start listening on their ports
- Browser tabs open automatically

**Check these three critical services:**

#### Price Dashboard (Port 8002)
- ✅ Console window titled "Price Dashboard" or similar
- ✅ Shows "Running on http://0.0.0.0:8002"
- ✅ No error messages
- ✅ Browser opens to http://localhost:8002
- ✅ Page loads successfully

#### AI Professor (Port 3000)
- ✅ Console window titled "AI Professor - Next.js"
- ✅ Shows "compiled successfully" or compilation progress
- ✅ Shows "ready on http://localhost:3000"
- ✅ Browser opens to http://localhost:3000
- ✅ Page loads successfully

#### VizLab (Port 8011)
- ✅ Console window titled "VizLab - Next.js"
- ✅ Shows "compiled successfully" or compilation progress
- ✅ Shows "ready on http://localhost:8011"
- ✅ Browser opens to http://localhost:8011
- ✅ Page loads successfully

### 2. Test Service Dashboard

```powershell
# Navigate to Service Dashboard
http://localhost:8006
```

**Expected behavior:**
- All services shown in table
- Status column shows Online/Offline
- PID column shows process IDs (or "-" if offline)
- Kill and Start buttons present for each service

### 3. Test Kill Functionality

**Steps:**
1. Find a running service (green row)
2. Hover over row - PID column should update
3. Click "Kill" button
4. Confirm the kill
5. Wait 2 seconds

**Expected behavior:**
- ✅ Alert shows "Killed <service> on port <port>" with PIDs
- ✅ Service console window closes
- ✅ Status changes to "Offline" (red)
- ✅ PID column shows "-"
- ✅ Can visit service URL → connection refused

### 4. Test Start Functionality

**Steps:**
1. Find an offline service (red row)
2. Click "Start" button
3. Wait for alert

**Expected behavior:**
- ✅ Alert shows "Started <service>" with PID
- ✅ New console window opens for the service
- ✅ Service starts running (output visible in window)
- ✅ After 5-10 seconds, status changes to "Online" (green)
- ✅ PID column shows process ID
- ✅ Can visit service URL → page loads

### 5. Test Process Tree Kill

**Test that child processes are killed:**

1. Start AI Professor (has Redis + Worker + Next.js)
2. Check Task Manager → should see multiple node.exe processes
3. Kill AI Professor via dashboard
4. Check Task Manager → all related processes should be gone

**Expected:**
- ✅ Kills parent process
- ✅ Kills Redis process
- ✅ Kills Worker process
- ✅ Kills Next.js process
- ✅ Port is freed

### 6. Test Rapid Kill/Start Cycles

1. Kill a service
2. Immediately start it again
3. Kill it again
4. Start it again

**Expected:**
- ✅ No "port already in use" errors
- ✅ Each cycle works cleanly
- ✅ No orphaned processes
- ✅ PID updates correctly each time

---

## Debugging Failed Services

### If a service shows "Offline" after starting:

1. **Check the console window** - it should still be open
   - Look for error messages
   - Check if it's stuck waiting for input
   - Check if port binding failed

2. **Check port is actually listening:**
   ```powershell
   netstat -ano | findstr :<port>
   ```
   - Should show LISTENING state
   - Note the PID

3. **Check PID in dashboard** - hover over service row
   - Should match netstat PID
   - If "-", process isn't running

4. **Check for orphaned processes:**
   ```powershell
   # Check all Python processes
   tasklist /FI "IMAGENAME eq python.exe"
   
   # Check all Node processes
   tasklist /FI "IMAGENAME eq node.exe"
   ```

5. **Check service-specific requirements:**
   - **AI Professor:** Requires Redis, Prisma client generated, node_modules installed
   - **Summary Engine:** Requires backend running on 8008
   - **VizLab:** Requires node_modules installed

---

## Common Issues & Solutions

### "Port already in use"
**Cause:** Previous process not killed properly
**Solution:** 
```powershell
netstat -ano | findstr :<port>
taskkill /F /T /PID <pid>
```

### "Service won't start"
**Cause:** Dependencies missing
**Solution:**
- Check console window for errors
- Install dependencies manually:
  ```powershell
  # For Next.js apps
  cd "<service folder>"
  npm install
  
  # For Python apps
  pip install -r requirements.txt
  ```

### "Console window closes immediately"
**Cause:** Script error or missing files
**Solution:**
- Run .bat file manually to see error
- Check paths in .bat file
- Check Python/Node is in PATH

### "Process hangs (no output)"
**OLD ISSUE:** PIPE buffer overflow
**STATUS:** Should be fixed with new launcher
**If still happens:** Report as bug - should not occur with CREATE_NEW_CONSOLE

---

## Performance Benchmarks

### Startup Times (from launch to port listening):

| Service | Old (broken) | New (fixed) | Notes |
|---------|--------------|-------------|-------|
| Price Dashboard | Hangs | ~3-5s | Dash compilation |
| AI Professor | Lost PID | ~20-30s | Next.js compilation + Prisma |
| VizLab | Lost PID | ~15-25s | Next.js compilation |
| Agent Control Center | ~3s | ~3-5s | FastAPI startup |
| Sector RRG | Hangs | ~3-5s | Dash compilation |

### Health Check Times:

| Check Type | Time | Notes |
|------------|------|-------|
| Port listening | <1s | TCP connection attempt |
| HTTP GET | 1-5s | Full HTTP request |
| PID lookup | <1s | netstat query |

---

## Rollback Instructions

If new launcher causes issues:

1. **Backup files are NOT created** - use git to revert:
   ```powershell
   cd "C:\Coding Projects"
   git checkout Manager/launch_all_services.py
   git checkout Manager/service_launcher_utils.py
   git checkout HomePage/debug.py
   git checkout HomePage/templates/index.html
   ```

2. **Or restore specific functions:**
   - Change `CREATE_NEW_CONSOLE` back to `CREATE_NEW_PROCESS_GROUP`
   - Change `stdout/stderr` from None to `subprocess.PIPE`
   - Remove call to `wait_for_port()`

---

## Support

For issues contact: Kevin Lefebvre

**Log Locations:**
- Service Dashboard: `HomePage/logs/web_app.log`
- Service-specific: Check console window output
- System events: Windows Event Viewer
