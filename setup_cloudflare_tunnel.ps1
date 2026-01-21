# Cloudflare Tunnel Setup Script
# This script helps you set up Cloudflare Tunnel for your local services

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Cloudflare Tunnel Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if cloudflared is installed
$cloudflaredPath = Get-Command cloudflared -ErrorAction SilentlyContinue

if (-not $cloudflaredPath) {
    Write-Host "[ERROR] cloudflared is not installed!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install cloudflared:" -ForegroundColor Yellow
    Write-Host "1. Download from: https://github.com/cloudflare/cloudflared/releases" -ForegroundColor Yellow
    Write-Host "2. Or use winget: winget install --id Cloudflare.cloudflared" -ForegroundColor Yellow
    Write-Host "3. Or use chocolatey: choco install cloudflared" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host "[OK] cloudflared is installed" -ForegroundColor Green
Write-Host ""

# Step 1: Login to Cloudflare
Write-Host "Step 1: Login to Cloudflare" -ForegroundColor Cyan
Write-Host "This will open a browser window for authentication..." -ForegroundColor Yellow
$login = Read-Host "Press Enter to continue (or 'skip' to skip)"
if ($login -ne "skip") {
    cloudflared tunnel login
    Write-Host ""
}

# Step 2: Create tunnel
Write-Host "Step 2: Create a tunnel" -ForegroundColor Cyan
$tunnelName = Read-Host "Enter tunnel name (e.g., 'local-services')"
if ($tunnelName) {
    Write-Host "Creating tunnel: $tunnelName" -ForegroundColor Yellow
    cloudflared tunnel create $tunnelName
    Write-Host ""
}

# Step 3: Get tunnel ID
Write-Host "Step 3: Get tunnel ID" -ForegroundColor Cyan
Write-Host "Listing tunnels..." -ForegroundColor Yellow
cloudflared tunnel list
Write-Host ""
$tunnelId = Read-Host "Enter your tunnel ID (from the list above)"

if (-not $tunnelId) {
    Write-Host "[ERROR] Tunnel ID is required!" -ForegroundColor Red
    exit 1
}

# Step 4: Update config file
Write-Host ""
Write-Host "Step 4: Updating configuration file..." -ForegroundColor Cyan
$configFile = "C:\Program Files\Coding Projects\Manager\cloudflare_tunnel_config.yaml"
$configContent = Get-Content $configFile -Raw

# Replace tunnel ID
$configContent = $configContent -replace '<YOUR_TUNNEL_ID>', $tunnelId

# Update credentials file path
$credentialsPath = "$env:USERPROFILE\.cloudflared\$tunnelId.json"
$configContent = $configContent -replace 'C:\\Program Files\\Coding Projects\\Manager\\.cloudflared\\<YOUR_TUNNEL_ID>\.json', $credentialsPath

Set-Content -Path $configFile -Value $configContent
Write-Host "[OK] Configuration file updated" -ForegroundColor Green
Write-Host ""

# Step 5: Create DNS routes
Write-Host "Step 5: Create DNS routes" -ForegroundColor Cyan
$domain = Read-Host "Enter your domain (e.g., hcresearch.ltd)"

if ($domain) {
    Write-Host ""
    Write-Host "Creating DNS routes for subdomains..." -ForegroundColor Yellow
    Write-Host "You can create these manually in Cloudflare Dashboard or run:" -ForegroundColor Yellow
    Write-Host ""
    
    $subdomains = @(
        "price-dashboard",
        "sector-rrg",
        "strategy-optimizer",
        "homepage",
        "debug",
        "quantlab",
        "twifo",
        "tkp-ts",
        "yq-ts",
        "gold",
        "secratio",
        "es-historical",
        "almanac",
        "ts-generator",
        "import-dropbox"
    )
    
    foreach ($subdomain in $subdomains) {
        Write-Host "  cloudflared tunnel route dns $tunnelName $subdomain.$domain" -ForegroundColor Gray
    }
    
    Write-Host ""
    $createRoutes = Read-Host "Create all DNS routes automatically? (y/n)"
    
    if ($createRoutes -eq "y") {
        foreach ($subdomain in $subdomains) {
            Write-Host "Creating route: $subdomain.$domain" -ForegroundColor Yellow
            cloudflared tunnel route dns $tunnelName "$subdomain.$domain"
        }
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To start the tunnel, run:" -ForegroundColor Yellow
Write-Host "  cloudflared tunnel run $tunnelName" -ForegroundColor White
Write-Host ""
Write-Host "Or use the launcher script which will start it automatically." -ForegroundColor Yellow
Write-Host ""
