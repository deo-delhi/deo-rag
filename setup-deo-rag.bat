@echo off
REM DEO RAG Auto-Downloader and Setup
REM Auto-elevate to Administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrative privileges...
    powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /b
)

set "SETUP_DIR=%~dp0DEO-RAG"
if not exist "%SETUP_DIR%" mkdir "%SETUP_DIR%"
cd /d "%SETUP_DIR%"

echo ===================================================
echo Fetching DEO RAG Installation Scripts from GitHub...
echo ===================================================

powershell -Command "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/deo-delhi/deo-rag/main/install-and-run.bat' -OutFile 'install-and-run.bat'"
powershell -Command "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/deo-delhi/deo-rag/main/install-and-run.ps1' -OutFile 'install-and-run.ps1'"

if not exist "install-and-run.bat" (
    echo [ERROR] Failed to download installation scripts. Please check your internet connection.
    pause
    exit /b 1
)

echo.
echo ===================================================
echo Launching the Master Installer...
echo ===================================================
call install-and-run.bat

exit /b %ERRORLEVEL%
