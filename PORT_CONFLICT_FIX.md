# Port Conflict Fix - Summary Engine & TWIFO Import Dropbox

**Date:** 2026-01-22  
**Issue:** Port 8001 conflict between TWIFO Import Dropbox (Streamlit) and Summary Engine backend (Docker)

---

## Problem

Both services were configured to use port 8001:
- **TWIFO Import Dropbox** (Streamlit): Port 8001
- **Summary Engine Backend** (Docker): Port 8001

This caused Summary Engine to fail to start because the port was already in use.

---

## Solution

Changed **TWIFO Import Dropbox** from port 8001 to **port 8009** to free up port 8001 for Summary Engine.

### Files Updated

1. **`Manager/launch_all_services.py`**
   - Line 132: Changed `"port": 8001` → `"port": 8009`
   - Line 133: Changed `"url": "http://localhost:8001"` → `"url": "http://localhost:8009"`
   - Line 195: Updated PORTS mapping from 8001 → 8009

2. **`HomePage/debug.py`**
   - Line 145: Updated SERVICE_PORTS mapping from 8001 → 8009
   - Line 171: Updated localhost_url from `http://127.0.0.1:8001` → `http://127.0.0.1:8009`

---

## Port Assignments (After Fix)

| Service | Port | Type |
|---------|------|------|
| **TWIFO Import Dropbox** | **8009** | Streamlit |
| **Summary Engine Backend** | **8001** | Docker (FastAPI) |
| **Summary Engine Frontend** | **3001** | Docker (Next.js) |

---

## Additional Fix: Agent Control Center Timeout

**Issue:** FastAPI app timeout was only 15 seconds, which may not be enough for apps with heavy dependencies.

**Fix:** Increased timeout from 15s to 30s for FastAPI apps in `launch_all_services.py` line 878.

---

## Verification

After restarting services:

1. **Check TWIFO Import Dropbox:**
   ```bash
   netstat -ano | findstr :8009
   # Should show Streamlit process
   ```

2. **Check Summary Engine Backend:**
   ```bash
   netstat -ano | findstr :8001
   # Should show Docker container
   ```

3. **Test URLs:**
   - TWIFO Import Dropbox: http://localhost:8009
   - Summary Engine Backend: http://localhost:8001
   - Summary Engine Frontend: http://localhost:3001

---

## Notes

- Port 8009 was chosen to maintain sequential port assignment (8001-8010 range)
- No other services were using port 8009
- All references to the old port have been updated
- Cloudflare tunnel configuration may need updating if it references the old port
