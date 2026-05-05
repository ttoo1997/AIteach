@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0start_aiteach.ps1"
if errorlevel 1 (
  echo.
  echo AITeach failed to start. Check .runtime_tmp\web.stderr.log for details.
  pause
)
endlocal
