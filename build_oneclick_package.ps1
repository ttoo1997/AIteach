Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BundleDir = Join-Path $ProjectRoot "AITeach_OneClick_Package"

$DirectoriesToCopy = @(
  "api",
  "data",
  "knowledge_base",
  "matlab",
  "schemas",
  "services",
  "simulation",
  "storage",
  "web_frontend"
)

$FilesToCopy = @(
  ".env.example",
  "app.py",
  "app_config.py",
  "README.md",
  "requirements.txt",
  "runtime_env.py",
  "start_aiteach.ps1",
  "start_aiteach.bat",
  "stop_aiteach.ps1",
  "stop_aiteach.bat"
)

New-Item -ItemType Directory -Path $BundleDir -Force | Out-Null

foreach ($directory in $DirectoriesToCopy) {
  $source = Join-Path $ProjectRoot $directory
  $target = Join-Path $BundleDir $directory
  if (Test-Path $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
  }
  Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
}

foreach ($file in $FilesToCopy) {
  $source = Join-Path $ProjectRoot $file
  $target = Join-Path $BundleDir $file
  if (Test-Path $target) {
    Remove-Item -LiteralPath $target -Force
  }
  Copy-Item -LiteralPath $source -Destination $target -Force
}

$TransientPaths = @(
  ".env.local",
  ".runtime_tmp",
  ".venv",
  ".kb_cache",
  "wrong_questions_runtime.db"
)

foreach ($relativePath in $TransientPaths) {
  $target = Join-Path $BundleDir $relativePath
  if (Test-Path $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
  }
}

$StartLauncher = @'
@echo off
setlocal
call "%~dp0start_aiteach.bat"
endlocal
'@

$StopLauncher = @'
@echo off
setlocal
call "%~dp0stop_aiteach.bat"
endlocal
'@

$ConfigLauncher = @'
@echo off
setlocal
if not exist "%~dp0.env.local" copy "%~dp0.env.example" "%~dp0.env.local" >nul
notepad "%~dp0.env.local"
endlocal
'@

$PackageReadme = @(
  "# AITeach Classmate Package",
  "",
  "This folder is ready to zip and send to classmates.",
  "",
  "## First-time setup",
  "",
  "1. Make sure Python 3.10+ is installed.",
  "2. Double-click Edit_API_Key.bat.",
  "3. Fill in DASHSCOPE_API_KEY inside .env.local.",
  "4. Save the file and close Notepad.",
  "",
  "## Start the project",
  "",
  "1. Double-click Launch_AITeach.bat.",
  "2. The first launch will create .venv and install dependencies.",
  "3. Your browser will open http://127.0.0.1:8090/ automatically.",
  "",
  "## Stop the project",
  "",
  "1. Double-click Stop_AITeach.bat.",
  "",
  "## Notes",
  "",
  "- This is a local web application, not a native desktop app.",
  "- Simulation works without MATLAB by default.",
  "- If MATLAB is installed locally, the CLI path can be configured inside the app.",
  "- Wrong-question data is stored in data/wrong_questions.db.",
  "",
  "## When sharing with classmates",
  "",
  "- Zip the whole AITeach_OneClick_Package folder.",
  "- Do not ship your own .env.local with secrets inside.",
  "- Re-run build_oneclick_package.ps1 whenever you need to refresh the package."
) -join [Environment]::NewLine

Set-Content -LiteralPath (Join-Path $BundleDir "Launch_AITeach.bat") -Value $StartLauncher -Encoding ASCII
Set-Content -LiteralPath (Join-Path $BundleDir "Stop_AITeach.bat") -Value $StopLauncher -Encoding ASCII
Set-Content -LiteralPath (Join-Path $BundleDir "Edit_API_Key.bat") -Value $ConfigLauncher -Encoding ASCII
Set-Content -LiteralPath (Join-Path $BundleDir "README_PACKAGE.md") -Value $PackageReadme -Encoding UTF8

Write-Host "AITeach one-click package is ready."
Write-Host "Folder: $BundleDir"
