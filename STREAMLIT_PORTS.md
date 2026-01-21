# Streamlit Applications - Fixed Port Assignments

All Streamlit applications now use **FIXED ports** - no auto-incrementing. This ensures consistent URLs and prevents port conflicts.

## Port Assignments

| Application | Port | Local URL | Cloudflare Domain | Location |
|------------|------|-----------|-------------------|----------|
| **QuantLab Dashboard** | **8501** | http://localhost:8501 | https://quantlab.hcresearch.ltd | `QuantLab/dashboard/app.py` |
| **TWIFO Import Dropbox** | **8502** | http://localhost:8502 | https://import-dropbox.hcresearch.ltd | `TWIFO_Sharing/import_dropbox.py` |

## Details

### 1. QuantLab Dashboard
- **Port**: 8501 (FIXED)
- **Path**: `QuantLab/dashboard/app.py`
- **Virtual Environment**: `QuantLab/venv`
- **Description**: Research monitor dashboard for QuantLab strategy search system
- **Run manually**: 
  ```powershell
  cd "C:\Program Files\Coding Projects\QuantLab"
  .\venv\Scripts\streamlit.exe run dashboard/app.py --server.port 8501
  ```

### 2. TWIFO Import Dropbox
- **Port**: 8502 (FIXED)
- **Path**: `TWIFO_Sharing/import_dropbox.py`
- **Virtual Environment**: `TWIFO_Sharing/.venv13`
- **Description**: Dropbox file management interface for TWIFO sharing system
- **Run manually**: 
  ```powershell
  cd "C:\Program Files\Coding Projects\TWIFO_Sharing"
  .\.venv13\Scripts\streamlit.exe run import_dropbox.py --server.port 8502
  ```

## Port Conflict Prevention

If a port is already in use:
1. **Check what's using it**:
   ```powershell
   netstat -ano | findstr :8501
   netstat -ano | findstr :8502
   ```

2. **Kill the process** (if needed):
   ```powershell
   taskkill /PID <PID> /F
   ```

3. **Or stop the conflicting service** before launching

## Updating BAT Files

The BAT files that launch Streamlit apps should also use fixed ports:

### `TWIFO_Sharing/reboot_import_dropbox.bat`
Update to include port:
```batch
"%STREAMLIT%" run import_dropbox.py --server.port 8502
```

## Adding New Streamlit Apps

When adding a new Streamlit app:

1. **Choose an unused port** (8503, 8504, etc.)
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

3. **Add to Cloudflare tunnel config** (if using):
   ```yaml
   - hostname: my-new-app.hcresearch.ltd
     service: http://localhost:8503
   ```

4. **Update this document** with the new app

## Benefits of Fixed Ports

✅ **Consistent URLs** - Always know which port each app uses  
✅ **No conflicts** - Clear port assignments prevent overlap  
✅ **Easier debugging** - Predictable ports make troubleshooting easier  
✅ **Cloudflare integration** - Fixed ports work better with tunnel config  
✅ **Documentation** - Clear port assignments for team members  

## Reserved Ports

Ports 8501-8510 are reserved for Streamlit applications:
- 8501: QuantLab Dashboard
- 8502: TWIFO Import Dropbox
- 8503-8510: Available for future Streamlit apps
