$ErrorActionPreference = "Continue"

$managerDir = "C:\Coding Projects\Manager"
$launcher = Join-Path $managerDir "launch_all_services.py"
$logDir = Join-Path $managerDir "logs"
$logFile = Join-Path $logDir "startup_launch_all_services.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-StartupLog {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logFile -Value "[$timestamp] $Message"
}

Write-StartupLog "Startup launcher invoked"

if (-not (Test-Path $launcher)) {
    Write-StartupLog "ERROR: launch_all_services.py not found at $launcher"
    exit 1
}

$pythonCandidates = @(
    "C:\Python313\python.exe",
    "C:\Python310\python.exe",
    "python"
)

$pythonExe = $null
foreach ($candidate in $pythonCandidates) {
    if ($candidate -eq "python") {
        $cmd = Get-Command python -ErrorAction SilentlyContinue
        if ($cmd) {
            $pythonExe = $cmd.Source
            break
        }
    } elseif (Test-Path $candidate) {
        $pythonExe = $candidate
        break
    }
}

if (-not $pythonExe) {
    Write-StartupLog "ERROR: No Python executable found"
    exit 1
}

Write-StartupLog "Using Python: $pythonExe"
Write-StartupLog "Running launcher: $launcher"

Set-Location $managerDir
& $pythonExe $launcher *>> $logFile
$exitCode = $LASTEXITCODE
Write-StartupLog "Launcher exited with code $exitCode"
exit $exitCode
