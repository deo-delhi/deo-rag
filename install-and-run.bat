@echo off
REM Auto-elevate to Administrator
net session >nul 2>&1
if %errorLevel% == 0 (
    goto :run
) else (
    echo Requesting administrative privileges...
    powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /b
)

:run
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-and-run.ps1" %*
pause
exit /b %ERRORLEVEL%
