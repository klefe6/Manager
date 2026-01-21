# Port Mapping - Logical Sequential Assignment

All services now use logical sequential ports starting from 8001.

## Main Services (8001-8006)

| Service | Port | Local URL | Cloudflare Domain | Type |
|---------|------|-----------|-------------------|------|
| **TWIFO Import Dropbox** | **8001** | http://localhost:8001 | https://import-dropbox.hcresearch.ltd | Streamlit |
| **Price Dashboard** | **8002** | http://localhost:8002 | https://price-dashboard.hcresearch.ltd | Dash |
| **Sector RRG** | **8003** | http://localhost:8003 | https://sector-rrg.hcresearch.ltd | Dash |
| **Strategy Optimizer** | **8004** | http://localhost:8004 | https://strategy-optimizer.hcresearch.ltd | Dash |
| **Home Page** | **8005** | http://localhost:8005 | https://homepage.hcresearch.ltd | Dash |
| **Debug Page / Service Dashboard** | **8006** | http://localhost:8006 | https://debug.hcresearch.ltd | Flask |

## Other Services (Existing Ports)

| Service | Port | Local URL | Cloudflare Domain | Type |
|---------|------|-----------|-------------------|------|
| **QuantLab Dashboard** | **8501** | http://localhost:8501 | https://quantlab.hcresearch.ltd | Streamlit |
| **TWIFO Sharing** | **8065** | http://localhost:8065 | https://twifo.hcresearch.ltd | Dash |
| **TKP Tearsheet** | **8076** | http://localhost:8076 | https://tkp-ts.hcresearch.ltd | Dash |
| **Y&Q Tearsheet** | **8071** | http://localhost:8071 | https://yq-ts.hcresearch.ltd | Dash |
| **Gold Maker** | **8075** | http://localhost:8075 | https://gold.hcresearch.ltd | Dash |
| **Sector Ratio** | **8080** | http://localhost:8080 | https://secratio.hcresearch.ltd | Dash |
| **ES Historical Data** | **8081** | http://localhost:8081 | https://es-historical.hcresearch.ltd | Dash |
| **Almanac Futures** | **8072** | http://localhost:8072 | https://almanac.hcresearch.ltd | Dash |
| **TS Generator** | **8077** | http://localhost:8077 | https://ts-generator.hcresearch.ltd | Dash |

## Port Changes Summary

### Changed Ports
- **TWIFO Import Dropbox**: 8502 → **8001** ✅
- **Price Dashboard**: 3000 → **8002** ✅
- **Sector RRG**: 8059 → **8003** ✅
- **Strategy Optimizer**: 8070 → **8004** ✅
- **Home Page**: 8055 → **8005** ✅
- **Debug Page**: 8056 → **8006** ✅

### Unchanged Ports
- **QuantLab Dashboard**: 8501 (kept separate)
- All other services: Kept on existing ports

## Files Updated

1. ✅ `Manager/launch_all_services.py` - Updated DASH_APPS, STREAMLIT_APPS, PORTS
2. ✅ `Price Dashboard/app.py` - Changed port from 3000 to 8002
3. ✅ `Sector/app_rrg.py` - Changed port from 8059 to 8003
4. ✅ `StrategyOptimizer/app.py` - Changed port from 8070 to 8004
5. ✅ `HomePage/main.py` - Changed port from 8055 to 8005
6. ✅ `HomePage/debug.py` - Changed port from 8056 to 8006
7. ✅ `TWIFO_Sharing/reboot_import_dropbox.bat` - Changed port from 8502 to 8001
8. ✅ `Manager/cloudflare_tunnel_config.yaml` - Updated all port mappings

## Benefits

✅ **Logical numbering** - Sequential ports 8001-8006 for main services  
✅ **Easy to remember** - Simple pattern: 8001, 8002, 8003...  
✅ **No conflicts** - Clear separation from other services  
✅ **Consistent** - All main services in one range  

## Quick Reference

```powershell
# Main services
http://localhost:8001  # Dropbox filtering
http://localhost:8002  # Price Dashboard
http://localhost:8003  # Sector RRG
http://localhost:8004  # Strategy Optimizer
http://localhost:8005  # Homepage
http://localhost:8006  # Service Dashboard
```
