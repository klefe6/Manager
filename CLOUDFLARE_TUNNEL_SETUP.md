# Cloudflare Tunnel Setup Guide

## Overview

Cloudflare Tunnel (cloudflared) creates secure tunnels from your local services to Cloudflare's network, allowing you to:
- Access local services via custom domain names (e.g., `price-dashboard.hcresearch.ltd`)
- No need to open ports on your router
- Automatic HTTPS/SSL certificates
- Access from anywhere (if you want)

## Quick Start

### 1. Install cloudflared

**Option A: Download**
1. Go to https://github.com/cloudflare/cloudflared/releases
2. Download `cloudflared-windows-amd64.exe`
3. Rename to `cloudflared.exe` and add to PATH, or place in a folder

**Option B: Using winget (Windows 11)**
```powershell
winget install --id Cloudflare.cloudflared
```

**Option C: Using Chocolatey**
```powershell
choco install cloudflared
```

### 2. Authenticate with Cloudflare

```powershell
cloudflared tunnel login
```

This will:
- Open your browser
- Ask you to log in to Cloudflare
- Authorize cloudflared to manage tunnels
- Save credentials to `%USERPROFILE%\.cloudflared\cert.pem`

### 3. Create a Tunnel

```powershell
cloudflared tunnel create local-services
```

This creates a tunnel named "local-services" and gives you a tunnel ID (looks like: `abc12345-6789-...`)

### 4. Configure the Tunnel

**Option A: Use the Setup Script (Recommended)**
```powershell
cd "C:\Coding Projects\Manager"
.\setup_cloudflare_tunnel.ps1
```

This interactive script will:
- Check if cloudflared is installed
- Guide you through login
- Create the tunnel
- Update the config file
- Create DNS routes

**Option B: Manual Configuration**

1. Edit `cloudflare_tunnel_config.yaml`:
   - Replace `<YOUR_TUNNEL_ID>` with your actual tunnel ID
   - Update `credentials-file` path if needed

2. Create DNS routes for each subdomain:
```powershell
cloudflared tunnel route dns local-services price-dashboard.hcresearch.ltd
cloudflared tunnel route dns local-services sector-rrg.hcresearch.ltd
cloudflared tunnel route dns local-services strategy-optimizer.hcresearch.ltd
# ... etc for all subdomains
```

### 5. Start the Tunnel

**Option A: Automatic (via launcher)**
```powershell
python launch_all_services.py
```

The launcher will automatically start the tunnel if configured.

**Option B: Manual**
```powershell
cloudflared tunnel --config "C:\Coding Projects\Manager\cloudflare_tunnel_config.yaml" run
```

**Option C: Using the manager script**
```powershell
python cloudflare_tunnel_manager.py start
```

## Domain Mapping

The following services are mapped to subdomains:

| Service | Local Port | Domain |
|---------|-----------|--------|
| Price Dashboard | 3000 | `price-dashboard.hcresearch.ltd` |
| Sector RRG | 8059 | `sector-rrg.hcresearch.ltd` |
| Strategy Optimizer | 8070 | `strategy-optimizer.hcresearch.ltd` |
| Home Page | 8055 | `homepage.hcresearch.ltd` |
| Debug Page | 8056 | `debug.hcresearch.ltd` |
| QuantLab Dashboard | 8501 | `quantlab.hcresearch.ltd` |
| TWIFO Sharing | 8065 | `twifo.hcresearch.ltd` |
| TKP Tearsheet | 8076 | `tkp-ts.hcresearch.ltd` |
| Y&Q Tearsheet | 8071 | `yq-ts.hcresearch.ltd` |
| Gold Maker | 8075 | `gold.hcresearch.ltd` |
| Sector Ratio | 8080 | `secratio.hcresearch.ltd` |
| ES Historical Data | 8081 | `es-historical.hcresearch.ltd` |
| Almanac Futures | 8072 | `almanac.hcresearch.ltd` |
| TS Generator | 8077 | `ts-generator.hcresearch.ltd` |
| Import Dropbox | 8501 | `import-dropbox.hcresearch.ltd` |

## Configuration File

The configuration file is at:
```
C:\Coding Projects\Manager\cloudflare_tunnel_config.yaml
```

Example structure:
```yaml
tunnel: abc12345-6789-...
credentials-file: C:\Users\YourName\.cloudflared\abc12345-6789-....json

ingress:
  - hostname: price-dashboard.hcresearch.ltd
    service: http://localhost:3000
  - hostname: sector-rrg.hcresearch.ltd
    service: http://localhost:8059
  # ... more routes
  - service: http_status:404  # Catch-all (must be last)
```

## Managing the Tunnel

### Start
```powershell
python cloudflare_tunnel_manager.py start
```

### Stop
```powershell
python cloudflare_tunnel_manager.py stop
```

### Status
```powershell
python cloudflare_tunnel_manager.py status
```

### View Logs
Logs are saved to:
```
C:\Coding Projects\Manager\logs\cloudflare_tunnel_*.log
```

## Troubleshooting

### Tunnel won't start

1. **Check if cloudflared is installed:**
   ```powershell
   cloudflared --version
   ```

2. **Check if you're logged in:**
   ```powershell
   cloudflared tunnel list
   ```

3. **Verify tunnel ID in config:**
   - Open `cloudflare_tunnel_config.yaml`
   - Make sure `<YOUR_TUNNEL_ID>` is replaced with actual ID

4. **Check credentials file:**
   - Should be at: `%USERPROFILE%\.cloudflared\<tunnel-id>.json`
   - Or path specified in config file

### DNS routes not working

1. **Verify DNS routes exist:**
   ```powershell
   cloudflared tunnel route dns list
   ```

2. **Check DNS propagation:**
   ```powershell
   nslookup price-dashboard.hcresearch.ltd
   ```
   Should return a CNAME pointing to your tunnel.

3. **Create missing routes:**
   ```powershell
   cloudflared tunnel route dns <tunnel-name> <subdomain>.<domain>
   ```

### Services not accessible via domain

1. **Check if local service is running:**
   ```powershell
   curl http://localhost:3000
   ```

2. **Check tunnel logs:**
   - Look in `Manager\logs\cloudflare_tunnel_*.log`
   - Check for connection errors

3. **Verify ingress rules:**
   - Make sure hostname matches exactly
   - Check port numbers are correct
   - Ensure catch-all rule is last

### Port conflicts

If a service is on a different port than expected:
1. Update `cloudflare_tunnel_config.yaml` with correct port
2. Restart the tunnel

## Advanced: Using Cloudflare API

If you want to manage tunnels programmatically, you can use the Cloudflare API:

```python
import requests

# Get API token from Cloudflare Dashboard
# https://dash.cloudflare.com/profile/api-tokens

API_TOKEN = "your-api-token"
ZONE_ID = "your-zone-id"
ACCOUNT_ID = "your-account-id"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# List tunnels
response = requests.get(
    f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel",
    headers=headers
)
```

## Security Notes

- **Tunnel is secure**: Traffic is encrypted between your machine and Cloudflare
- **Access control**: By default, anyone with the domain can access (if DNS is public)
- **Private networks**: You can restrict access using Cloudflare Access (paid feature)
- **Localhost only**: Services must be accessible on localhost (127.0.0.1)

## Integration with Launcher

The `launch_all_services.py` script automatically:
1. Checks if Cloudflare Tunnel is configured
2. Starts the tunnel after all services are launched
3. Stops the tunnel on Ctrl+C (if you want)

To disable automatic tunnel startup, comment out the tunnel manager import in `launch_all_services.py`.

## Next Steps

1. ✅ Install cloudflared
2. ✅ Run setup script
3. ✅ Test access via domain names
4. ✅ Integrate with service launcher
5. ✅ (Optional) Set up Cloudflare Access for private access

## Resources

- Cloudflare Tunnel Docs: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/
- cloudflared GitHub: https://github.com/cloudflare/cloudflared
- Cloudflare Dashboard: https://dash.cloudflare.com/
