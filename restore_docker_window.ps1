# Restore Docker Desktop Window
# Fixes the issue where Docker Desktop GUI is running but window is not visible

Write-Host "=== Restoring Docker Desktop Window ===" -ForegroundColor Cyan
Write-Host ""

# Find all Docker Desktop processes
$dockerProcs = Get-Process | Where-Object {
    $_.ProcessName -eq "Docker Desktop" -or 
    $_.ProcessName -like "*com.docker.backend*"
}

if (-not $dockerProcs) {
    Write-Host "[INFO] Docker Desktop is not running. Starting it..." -ForegroundColor Yellow
    $dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerExe) {
        Start-Process $dockerExe
        Write-Host "[OK] Docker Desktop started. Wait 30-60 seconds for it to initialize." -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Docker Desktop executable not found!" -ForegroundColor Red
    }
    exit
}

Write-Host "[INFO] Found $($dockerProcs.Count) Docker Desktop process(es)" -ForegroundColor Cyan

# Add Windows API functions to restore windows
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    
    [DllImport("user32.dll")]
    public static extern bool IsIconic(IntPtr hWnd);
    
    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);
    
    [DllImport("user32.dll")]
    public static extern bool BringWindowToTop(IntPtr hWnd);
    
    public const int SW_RESTORE = 9;
    public const int SW_SHOW = 5;
    public const int SW_SHOWMAXIMIZED = 3;
    public const int SW_SHOWNORMAL = 1;
}
"@

$restored = $false
foreach ($proc in $dockerProcs) {
    if ($proc.MainWindowHandle -ne [IntPtr]::Zero) {
        Write-Host "[INFO] Processing window for PID: $($proc.Id), Process: $($proc.ProcessName)" -ForegroundColor Yellow
        
        # Check if window is minimized
        if ([Win32]::IsIconic($proc.MainWindowHandle)) {
            Write-Host "  -> Window is minimized, restoring..." -ForegroundColor Yellow
            [Win32]::ShowWindow($proc.MainWindowHandle, [Win32]::SW_RESTORE)
        }
        
        # Make sure window is visible
        if (-not [Win32]::IsWindowVisible($proc.MainWindowHandle)) {
            Write-Host "  -> Window is hidden, showing..." -ForegroundColor Yellow
            [Win32]::ShowWindow($proc.MainWindowHandle, [Win32]::SW_SHOW)
        }
        
        # Bring to foreground
        [Win32]::BringWindowToTop($proc.MainWindowHandle)
        [Win32]::SetForegroundWindow($proc.MainWindowHandle)
        
        Write-Host "  -> Window restored and brought to foreground" -ForegroundColor Green
        $restored = $true
    } else {
        Write-Host "  -> PID $($proc.Id) has no visible window (background process)" -ForegroundColor Gray
    }
}

if ($restored) {
    Write-Host ""
    Write-Host "[OK] Docker Desktop window should now be visible!" -ForegroundColor Green
    Write-Host "[INFO] If you still don't see it, check your system tray (notification area) for the Docker icon." -ForegroundColor Cyan
    Write-Host "[INFO] You can also try: Right-click system tray icon -> Settings" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "[WARN] Docker Desktop processes are running but no visible windows found." -ForegroundColor Yellow
    Write-Host "[INFO] Attempting to open Docker Desktop GUI..." -ForegroundColor Cyan
    
    # Try to open Docker Desktop GUI using the protocol handler
    try {
        Start-Process "docker-desktop://" -ErrorAction Stop
        Write-Host "[OK] Sent command to open Docker Desktop GUI" -ForegroundColor Green
        Write-Host "[INFO] Wait 5-10 seconds for the window to appear..." -ForegroundColor Yellow
        Start-Sleep -Seconds 3
        
        # Check again after a moment
        $newProcs = Get-Process | Where-Object {
            $_.ProcessName -eq "Docker Desktop" -and 
            $_.MainWindowHandle -ne [IntPtr]::Zero
        }
        
        if ($newProcs) {
            Write-Host "[OK] Docker Desktop GUI window found!" -ForegroundColor Green
            foreach ($proc in $newProcs) {
                [Win32]::ShowWindow($proc.MainWindowHandle, [Win32]::SW_RESTORE)
                [Win32]::SetForegroundWindow($proc.MainWindowHandle)
            }
        } else {
            Write-Host "[INFO] If window still doesn't appear, try:" -ForegroundColor Yellow
            Write-Host "  1. Look for Docker icon in system tray (notification area)" -ForegroundColor White
            Write-Host "  2. Right-click Docker icon -> Settings or Dashboard" -ForegroundColor White
            Write-Host "  3. Or restart Docker Desktop: Right-click system tray icon -> Quit Docker Desktop, then run this script again" -ForegroundColor White
        }
    } catch {
        Write-Host "[WARN] Failed to open GUI: $_" -ForegroundColor Yellow
        Write-Host "[INFO] Manual steps:" -ForegroundColor Yellow
        Write-Host "  1. Look for Docker icon in system tray (notification area)" -ForegroundColor White
        Write-Host "  2. Right-click Docker icon -> Settings or Dashboard" -ForegroundColor White
        Write-Host "  3. Or restart Docker Desktop: Right-click system tray icon -> Quit Docker Desktop" -ForegroundColor White
    }
}

Write-Host ""
Write-Host "=== Complete ===" -ForegroundColor Cyan
