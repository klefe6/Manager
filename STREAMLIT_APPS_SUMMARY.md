# Streamlit Applications - Complete Summary

All Streamlit applications now use **FIXED ports** - no auto-incrementing behavior.

## 📋 Complete List

### 1. QuantLab Dashboard
- **Port**: `8501` (FIXED)
- **Local URL**: http://localhost:8501
- **Cloudflare**: https://quantlab.hcresearch.ltd
- **Location**: `QuantLab/dashboard/app.py`
- **Virtual Environment**: `QuantLab/venv`
- **Description**: Research monitor dashboard for QuantLab autonomous strategy search system
- **Features**: 
  - Real-time search progress monitoring
  - Strategy approval/rejection tracking
  Research control (START/PAUSE/STOP)
  - Pipeline health monitoring
  - Approved strategies viewer

**Manual Launch:**
```powershell
cd "C:\Coding Projects\QuantLab"
.\venv\Scripts\streamlit.exe run dashboard/app.py --server.port 8501
```

---

### 2. TWIFO Import Dropbox
- **Port**: `8502` (FIXED)
- **Local URL**: http://localhost:8502
- **Cloudflare**: https://import-dropbox.hcresearch.ltd
- **Location**: `TWIFO_Sharing/import_dropbox.py`
- **Virtual Environment**: `TWIFO_Sharing/.venv13`
- **Description**: Dropbox file management interface for TWIFO sharing system
- **Features**:
  - Dropbox file browsing and filtering
  - File import management
  - Document categorization
  - Interactive file tables with AgGrid

**Manual Launch:**
```powershell
cd "C:\Coding Projects\TWIFO_Sharing"
.\.venv13\Scripts\streamlit.exe run import_dropbox.py --server.port 8502
```

**BAT File**: `TWIFO_Sharing/reboot_import_dropbox.bat` (updated to use port 8502)

---

## 🔧 Port Management

### Fixed Port Policy
- ✅ **No auto-incrementing** - Each app has a dedicated, fixed port
- ✅ **Port conflicts detected** - Launcher warns if port is in use
- ✅ **Consistent URLs** - Always know which port each app uses
- ✅ **Cloudflare integration** - Fixed ports work seamlessly with tunnels

### Reserved Port Range
Ports **8501-8510** are reserved for Streamlit applications:
- `8501`: QuantLab Dashboard ✅
- `8502`: TWIFO Import Dropbox ✅
- `8503-8510`: Available for future Streamlit apps

### Port Conflict Resolution

If you see a warning that a port is in use:

1. **Check what's using the port:**
   ```powershell
   netstat -ano | findstr :8501
   netstat -ano | findstr :8502
   ```

2. **Kill the process** (if it's an old instance):
   ```powershell
   taskkill /PID <PID> /F
   ```

3. **Or stop the conflicting service** before launching

---

## 🚀 Launching All Services

The comprehensive launcher (`launch_all_services.py`) now:
- ✅ Launches all Streamlit apps with fixed ports
- ✅ Warns if a port is already in use
- ✅ Opens browser tabs for all services
- ✅ Tracks ports in service registry

**Launch everything:**
```powershell
cd "C:\Coding Projects\Manager"
python launch_all_services.py
```

---

## 📝 Adding New Streamlit Apps

When adding a new Streamlit app:

1. **Choose next available port** (8503, 8504, etc.)

2. **Add to `STREAMLIT_APPS` in `launch_all_services.py`**:
   ```python
   "My New App": {
       "path": BASE_DIR / "MyApp" / "app.py",
       "port": 8503,  # Fixed port
       "url": "http://localhost:8503",
       "cwd": BASE_DIR / "MyApp",
       "venv": BASE_DIR / "MyApp" / "venv",
   },
   ```

3. **Add to `PORTS` dictionary** (for health checks):
   ```python
   "My New App": ("127.0.0.1", 8503),
   ```

4. **Add to Cloudflare tunnel config** (if using):
   ```yaml
   - hostname: my-new-app.hcresearch.ltd
     service: http://localhost:8503
   ```

5. **Update BAT file** (if creating one):
   ```batch
   "%STREAMLIT%" run app.py --server.port 8503
   ```

6. **Update this document** with the new app details

---

## ✅ Benefits

- **Predictable URLs** - Always know which port each app uses
- **No conflicts** - Clear port assignments prevent overlap
- **Easier debugging** - Predictable ports make troubleshooting easier
- **Cloudflare integration** - Fixed ports work better with tunnel config
- **Team collaboration** - Clear documentation for all team members
- **Service registry** - All ports tracked in `service_registry.json`

---

## 📊 Current Status

| App | Port | Status | Notes |
|-----|------|--------|------|
| QuantLab Dashboard | 8501 | ✅ Active | Main research dashboard |
| TWIFO Import Dropbox | 8502 | ✅ Active | Dropbox management UI |

---

## 🔍 Verification

After launching, verify ports are correct:

1. **Check service registry:**
   ```powershell
   Get-Content "C:\Coding Projects\Manager\service_registry.json"
   ```

2. **Test URLs:**
   - http://localhost:8501 (QuantLab)
   - http://localhost:8502 (TWIFO Dropbox)

3. **Check running processes:**
   ```powershell
   Get-Process | Where-Object {$_.ProcessName -like "*streamlit*" -or $_.ProcessName -like "*python*"}
   ```
