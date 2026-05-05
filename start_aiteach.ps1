param(
  [int]$Port = 8090
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeDir = Join-Path $ProjectRoot ".runtime_tmp"
$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$PidFile = Join-Path $RuntimeDir "web.pid"
$StdoutLog = Join-Path $RuntimeDir "web.stdout.log"
$StderrLog = Join-Path $RuntimeDir "web.stderr.log"
$RequirementsPath = Join-Path $ProjectRoot "requirements.txt"
$RequirementsHashFile = Join-Path $RuntimeDir "requirements.sha256"
$EnvLocal = Join-Path $ProjectRoot ".env.local"
$EnvExample = Join-Path $ProjectRoot ".env.example"

New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null

function Show-LogTail {
  param(
    [string]$Path,
    [string]$Title
  )

  if (-not (Test-Path $Path)) {
    return
  }

  Write-Host ""
  Write-Host $Title
  Get-Content $Path -Tail 20 -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host $_
  }
}

if (Test-Path $PidFile) {
  $ExistingPid = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
  if ($ExistingPid) {
    $ExistingProcess = Get-Process -Id $ExistingPid -ErrorAction SilentlyContinue
    if ($ExistingProcess) {
      Start-Process "http://127.0.0.1:$Port/" | Out-Null
      Write-Host "AITeach is already running. Browser opened."
      exit 0
    }
  }
  Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path $VenvPython)) {
  Write-Host "Creating Python virtual environment..."
  $BootstrapPython = Get-Command python -ErrorAction SilentlyContinue
  $UsePythonLauncher = $false
  if (-not $BootstrapPython) {
    $BootstrapPython = Get-Command py -ErrorAction SilentlyContinue
    $UsePythonLauncher = $true
  }
  if (-not $BootstrapPython) {
    throw "Python was not found. Please install Python 3.10+ or the Windows py launcher first."
  }
  if ($UsePythonLauncher) {
    & $BootstrapPython.Source -3 -m venv $VenvDir
  } else {
    & $BootstrapPython.Source -m venv $VenvDir
  }
}

if (-not (Test-Path $VenvPython)) {
  throw "python.exe was not found in .venv. Please install Python first."
}

$RequirementsHash = (Get-FileHash $RequirementsPath -Algorithm SHA256).Hash
$LastRequirementsHash = if (Test-Path $RequirementsHashFile) {
  (Get-Content $RequirementsHashFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
} else {
  ""
}
if ($RequirementsHash -ne $LastRequirementsHash) {
  Write-Host "Installing or updating dependencies..."
  & $VenvPython -m pip install -r $RequirementsPath
  $RequirementsHash | Set-Content $RequirementsHashFile -Encoding UTF8
} else {
  Write-Host "Dependencies already prepared."
}

if ((-not (Test-Path $EnvLocal)) -and (Test-Path $EnvExample)) {
  Copy-Item $EnvExample $EnvLocal
  Write-Host ".env.local created from template."
}

if (Test-Path $StdoutLog) {
  Remove-Item $StdoutLog -Force -ErrorAction SilentlyContinue
}

if (Test-Path $StderrLog) {
  Remove-Item $StderrLog -Force -ErrorAction SilentlyContinue
}

# Some Windows machines expose both Path and PATH in the process environment,
# which makes Start-Process throw before uvicorn even launches.
$ProcessPathValue = [System.Environment]::GetEnvironmentVariable("Path", "Process")
if (-not $ProcessPathValue) {
  $ProcessPathValue = [System.Environment]::GetEnvironmentVariable("PATH", "Process")
}
[System.Environment]::SetEnvironmentVariable("PATH", $null, "Process")
[System.Environment]::SetEnvironmentVariable("Path", $ProcessPathValue, "Process")

Write-Host "Starting AITeach Web..."
$Process = Start-Process `
  -FilePath $VenvPython `
  -ArgumentList @("-m", "uvicorn", "api.web_app:app", "--host", "127.0.0.1", "--port", "$Port") `
  -WorkingDirectory $ProjectRoot `
  -RedirectStandardOutput $StdoutLog `
  -RedirectStandardError $StderrLog `
  -PassThru

$Process.Id | Set-Content $PidFile -Encoding UTF8

$HealthUrl = "http://127.0.0.1:$Port/api/health"
$Started = $false

for ($Attempt = 0; $Attempt -lt 30; $Attempt++) {
  Start-Sleep -Seconds 1

  $RunningProcess = Get-Process -Id $Process.Id -ErrorAction SilentlyContinue
  if (-not $RunningProcess) {
    Write-Host "AITeach failed to start."
    Write-Host "Check logs in: $RuntimeDir"
    Show-LogTail -Path $StderrLog -Title "---- stderr (last 20 lines) ----"
    Show-LogTail -Path $StdoutLog -Title "---- stdout (last 20 lines) ----"
    exit 1
  }

  try {
    $HealthResponse = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 2
    if ($HealthResponse.StatusCode -eq 200) {
      $Started = $true
      break
    }
  } catch {
    # Keep polling until the service is ready or times out.
  }
}

if (-not $Started) {
  Write-Host "AITeach did not become ready in time."
  Write-Host "The process may still be starting, or it may have failed."
  Write-Host "Check logs in: $RuntimeDir"
  Show-LogTail -Path $StderrLog -Title "---- stderr (last 20 lines) ----"
  Show-LogTail -Path $StdoutLog -Title "---- stdout (last 20 lines) ----"
  exit 1
}

Start-Process "http://127.0.0.1:$Port/" | Out-Null

Write-Host "AITeach started."
Write-Host "URL: http://127.0.0.1:$Port/"
Write-Host "Use stop_aiteach.bat to stop the service."
