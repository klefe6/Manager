# Ports for Offline Services (Red Rows in Dashboard)

## Services Currently Showing as Offline

### 1. Homepage
- **Dashboard URL**: `https://home.hcresearch.ltd`
- **Port**: **8005**
- **Local URL**: `http://localhost:8005`
- **Type**: Dash Application
- **File**: `HomePage/main.py`
- **Launcher Config**: ✅ In `DASH_APPS` as "Home Page"
- **Status**: Configured to launch

### 2. Database Filtering System (TWIFO Sharing)
- **Dashboard URL**: `https://filemanager.hcresearch.ltd`
- **Port**: **8065**
- **Local URL**: `http://localhost:8065`
- **Type**: Dash Application (via BAT file)
- **File**: `TWIFO_Sharing/twifo.py`
- **BAT File**: `TWIFO_Sharing/reboot_twifo.bat`
- **Launcher Config**: ✅ In `BAT_SERVICES` as "TWIFO Sharing"
- **Status**: Configured to launch

### 3. Y&Q Tearsheet
- **Dashboard URL**: `https://yq-ts.hcresearch.ltd`
- **Port**: **8071**
- **Local URL**: `http://localhost:8071`
- **Type**: Dash Application (via BAT file)
- **File**: `Tearsheet Generator/yq_ts.py`
- **BAT File**: `Tearsheet Generator/reboot_yq_ts.bat`
- **Launcher Config**: ✅ In `BAT_SERVICES` as "Y&Q Tearsheet"
- **Status**: Configured to launch

### 4. Sector RRG
- **Dashboard URL**: `https://sector.hcresearch.ltd`
- **Port**: **8003**
- **Local URL**: `http://localhost:8003`
- **Type**: Dash Application
- **File**: `Sector/app_rrg.py`
- **Launcher Config**: ✅ In `DASH_APPS` as "Sector RRG"
- **Status**: Configured to launch

### 5. ES Historical Data
- **Dashboard URL**: `https://es-historical.hcresearch.ltd`
- **Port**: **8081**
- **Local URL**: `http://localhost:8081`
- **Type**: Dash Application (via BAT file)
- **File**: `ES Historical Data/app2.py`
- **BAT File**: `ES Historical Data/reboot_es_historical_data.bat`
- **Launcher Config**: ✅ In `BAT_SERVICES` as "ES Historical"
- **Status**: Configured to launch

### 6. Strategy Optimizer
- **Dashboard URL**: `https://optimizer.hcresearch.ltd`
- **Port**: **8004**
- **Local URL**: `http://localhost:8004`
- **Type**: Dash Application
- **File**: `StrategyOptimizer/app.py`
- **Launcher Config**: ✅ In `DASH_APPS` as "Strategy Optimizer"
- **Status**: Configured to launch

## Summary

All 6 offline services are **already configured** in `launch_all_services.py`:
- ✅ 3 services in `BAT_SERVICES` (TWIFO Sharing, Y&Q Tearsheet, ES Historical)
- ✅ 3 services in `DASH_APPS` (Home Page, Sector RRG, Strategy Optimizer)

They will all start when you run `launch_all_services.py`.

## Quick Port Reference

| Service | Port | Local URL |
|---------|------|-----------|
| Homepage | 8005 | http://localhost:8005 |
| Database Filtering System | 8065 | http://localhost:8065 |
| Y&Q Tearsheet | 8071 | http://localhost:8071 |
| Sector RRG | 8003 | http://localhost:8003 |
| ES Historical Data | 8081 | http://localhost:8081 |
| Strategy Optimizer | 8004 | http://localhost:8004 |
