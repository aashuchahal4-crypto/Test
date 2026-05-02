@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0\..\.."
title Local AI Video Studio - Windows EXE Builder

echo.
echo ============================================================
echo  Local AI Video Studio - Windows bundle builder
echo ============================================================
echo This creates the native Tauri Windows installer/bundle on Windows.
echo Run scripts\windows\Install-And-Run.bat first if dependencies are missing.
echo.

where npm >nul 2>nul || (echo npm missing. Run Install-And-Run.bat first.& pause& exit /b 1)
where cargo >nul 2>nul || (echo Rust/Cargo missing. Run Install-And-Run.bat first.& pause& exit /b 1)
where ffmpeg >nul 2>nul || (echo FFmpeg missing. Run Install-And-Run.bat first.& pause& exit /b 1)

call npm install
if errorlevel 1 exit /b 1
call npm run build
if errorlevel 1 exit /b 1
call npm run tauri:build
if errorlevel 1 exit /b 1

echo.
echo Build complete.
echo Look in: src-tauri\target\release\bundle\
echo Typical outputs: .msi, .exe, or nsis installer depending on Tauri target support.
pause
