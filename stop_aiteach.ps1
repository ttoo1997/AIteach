Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $ProjectRoot ".runtime_tmp\web.pid"

if (-not (Test-Path $PidFile)) {
  Write-Host "No running AITeach process record was found."
  exit 0
}

$PidText = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
if (-not $PidText) {
  Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
  Write-Host "PID file was empty and has been cleaned."
  exit 0
}

$Process = Get-Process -Id $PidText -ErrorAction SilentlyContinue
if ($Process) {
  Stop-Process -Id $PidText -Force
  Write-Host "AITeach stopped."
} else {
  Write-Host "Recorded process was not found. PID file cleaned."
}

Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
