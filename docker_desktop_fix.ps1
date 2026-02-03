# Docker Desktop GUI Fix Script
# Purpose: Diagnose and fix Docker Desktop GUI not opening issues

Write-Host "=== Docker Desktop Diagnostic & Fix ===" -ForegroundColor Cyan
Write-Host ""

# Check if Docker Desktop executable exists
$dockerPaths = @(
    "C:\Program Files\Docker\Docker\Docker Desktop.exe",
    "$env:LOCALAPPDATA\Docker\Docker Desktop.exe",
    "C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe"
)

$dockerExe = $null
foreach ($path in $dockerPaths) {
    if (Test-Path $path) {
        $dockerExe = $path
        Write-Host "[OK] Found Docker Desktop at: $path" -ForegroundColor Green
        break
    }
}

if (-not $dockerExe) {
    Write-Host "[ERROR] Docker Desktop executable not found!" -ForegroundColor Red
    Write-Host "Please reinstall Docker Desktop from: https://www.docker.com/products/docker-desktop"
    exit 1
}

# Check if Docker daemon is running
Write-Host ""
Write-Host "Checking Docker daemon status..." -ForegroundColor Yellow
try {
    $dockerVersion = docker version --format "{{.Server.Version}}" 2>&1
    if ($LASTEXITCODE -eq 0 -and $dockerVersion) {
        Write-Host "[OK] Docker daemon is running (Version: $dockerVersion)" -ForegroundColor Green
        $daemonRunning = $true
    } else {
        Write-Host "[WARN] Docker daemon is not responding" -ForegroundColor Yellow
        $daemonRunning = $false
    }
} catch {
    Write-Host "[WARN] Docker daemon check failed: $_" -ForegroundColor Yellow
    $daemonRunning = $false
}

# Check for existing Docker Desktop processes
Write-Host ""
Write-Host "Checking for existing Docker Desktop processes..." -ForegroundColor Yellow
$dockerProcesses = Get-Process | Where-Object {
    $_.ProcessName -eq "Docker Desktop" -or 
    $_.ProcessName -like "*com.docker*" -or
    $_.MainWindowTitle -like "*Docker*"
}

if ($dockerProcesses) {
    Write-Host "[INFO] Found Docker Desktop processes:" -ForegroundColor Cyan
    $dockerProcesses | Format-Table Id, ProcessName, MainWindowTitle, Responding -AutoSize
    
    # Try to bring window to foreground
    Write-Host ""
    Write-Host "Attempting to bring Docker Desktop window to foreground..." -ForegroundColor Yellow
    foreach ($proc in $dockerProcesses) {
        if ($proc.MainWindowHandle -ne [IntPtr]::Zero) {
            Add-Type -TypeDefinition @"
                using System;
                using System.Runtime.InteropServices;
                public class Win32 {
                    [DllImport("user32.dll")]
                    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
                    [DllImport("user32.dll")]
                    public static extern bool SetForegroundWindow(IntPtr hWnd);
                    public const int SW_RESTORE = 9;
                }
"@
            [Win32]::ShowWindow($proc.MainWindowHandle, [Win32]::SW_RESTORE)
            [Win32]::SetForegroundWindow($proc.MainWindowHandle)
            Write-Host "[OK] Brought window to foreground for PID: $($proc.Id)" -ForegroundColor Green
        }
    }
    
    Write-Host ""
    Write-Host "[INFO] Docker Desktop is already running. Check your system tray (notification area) for the Docker icon." -ForegroundColor Cyan
    Write-Host "If the window is still not visible, try:" -ForegroundColor Yellow
    Write-Host "  1. Right-click the Docker icon in system tray -> Settings" -ForegroundColor White
    Write-Host "  2. Or restart Docker Desktop: Right-click system tray icon -> Quit Docker Desktop, then run this script again" -ForegroundColor White
} else {
    Write-Host "[INFO] No Docker Desktop GUI process found" -ForegroundColor Yellow
    
    if ($daemonRunning) {
        Write-Host "[INFO] Docker daemon is running but GUI is not. Starting GUI..." -ForegroundColor Yellow
    } else {
        Write-Host "[INFO] Starting Docker Desktop (this may take 30-60 seconds)..." -ForegroundColor Yellow
    }
    
    # Try multiple methods to start Docker Desktop
    $started = $false
    
    # Method 1: Direct executable
    try {
        Start-Process -FilePath $dockerExe -ErrorAction Stop
        Write-Host "[OK] Started Docker Desktop using direct path" -ForegroundColor Green
        $started = $true
    } catch {
        Write-Host "[WARN] Direct start failed: $_" -ForegroundColor Yellow
    }
    
    # Method 2: Protocol handler (if direct start didn't work)
    if (-not $started) {
        try {
            Start-Process "docker-desktop://" -ErrorAction Stop
            Write-Host "[OK] Started Docker Desktop using protocol handler" -ForegroundColor Green
            $started = $true
        } catch {
            Write-Host "[WARN] Protocol handler failed: $_" -ForegroundColor Yellow
        }
    }
    
    if ($started) {
        Write-Host ""
        Write-Host "[INFO] Waiting for Docker Desktop to initialize..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
        
        # Wait up to 30 seconds for the process to appear
        $timeout = 30
        $elapsed = 0
        while ($elapsed -lt $timeout) {
            $proc = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "[OK] Docker Desktop process started (PID: $($proc.Id))" -ForegroundColor Green
                break
            }
            Start-Sleep -Seconds 2
            $elapsed += 2
            Write-Host "." -NoNewline
        }
        Write-Host ""
    } else {
        Write-Host ""
        Write-Host "[ERROR] Failed to start Docker Desktop. Try:" -ForegroundColor Red
        Write-Host "  1. Run PowerShell as Administrator and try again" -ForegroundColor White
        Write-Host "  2. Check Windows Event Viewer for errors" -ForegroundColor White
        Write-Host "  3. Repair Docker Desktop installation from Settings -> Apps" -ForegroundColor White
        Write-Host "  4. Reinstall Docker Desktop if issues persist" -ForegroundColor White
    }
}

Write-Host ""
Write-Host "=== Diagnostic Complete ===" -ForegroundColor Cyan
