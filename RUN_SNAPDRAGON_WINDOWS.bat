@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Local AI Video Studio - Foundry Local NPU Mode

echo.
echo ============================================================
echo  Local AI Video Studio - Foundry Local / Snapdragon X NPU
echo ============================================================
echo AI inference: Microsoft Foundry Local QNN NPU models only.
echo Rendering: FFmpeg on CPU only.
echo.

set "VIDEO_RENDER_THREADS=4"
set "VIDEO_RENDER_PRESET=ultrafast"
set "LOCAL_AI_VIDEO_PORT=8765"

where winget >nul 2>nul
if errorlevel 1 (
  echo ERROR: winget is required. Install "App Installer" from Microsoft Store.
  pause
  exit /b 1
)

call :ensure_cmd python "Python.Python.3.12" "python --version"
call :ensure_cmd ffmpeg "Gyan.FFmpeg" "ffmpeg -version"

where foundry >nul 2>nul
if errorlevel 1 (
  echo.
  echo ERROR: Foundry Local command not found.
  echo Install Microsoft Foundry Local, confirm it is in PATH, then rerun this file.
  pause
  exit /b 1
)

echo.
echo Foundry Local models:
foundry model list
if errorlevel 1 (
  echo ERROR: Foundry Local is not responding to 'foundry model list'.
  pause
  exit /b 1
)

echo.
echo Starting/discovering Foundry Local service endpoint...
foundry service start

echo.
echo Checking selected NPU model and active REST endpoint...
python core\pipeline.py status
if errorlevel 1 (
  echo ERROR: No supported QNN NPU model is available.
  echo Install one of: phi-3.5-mini-instruct-qnn-npu, qwen2.5-1.5b-instruct-qnn-npu, deepseek-r1-distill-qwen-7b-qnn-npu.
  pause
  exit /b 1
)

if not exist dist\index.html (
  echo.
  echo Packaged frontend is missing, so Node.js is needed once to build it.
  call :ensure_cmd node "OpenJS.NodeJS.LTS" "node --version"
  call :ensure_cmd npm "OpenJS.NodeJS.LTS" "npm --version"
  call npm install
  if errorlevel 1 exit /b 1
  call npm run build
  if errorlevel 1 exit /b 1
)

echo.
echo Starting app at http://127.0.0.1:%LOCAL_AI_VIDEO_PORT%
echo Keep this window open. Close it to stop the app.
python core\server.py --port %LOCAL_AI_VIDEO_PORT%
pause
exit /b 0

:ensure_cmd
where %~1 >nul 2>nul
if errorlevel 1 (
  echo.
  echo Installing %~1 via winget package %~2 ...
  winget install --id %~2 -e --accept-source-agreements --accept-package-agreements
  if errorlevel 1 (
    echo Failed to install %~1. Install %~2 manually and rerun.
    pause
    exit /b 1
  )
  for /f "tokens=2,*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "MACHINE_PATH=%%B"
  for /f "tokens=2,*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USER_PATH=%%B"
  set "PATH=!MACHINE_PATH!;!USER_PATH!;%PATH%;%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%ProgramFiles%\nodejs"
  for /d %%D in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin") do set "PATH=!PATH!;%%~fD"
  for /d %%D in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\bin") do set "PATH=!PATH!;%%~fD"
)
%~3 >nul 2>nul
if errorlevel 1 (
  echo WARNING: %~1 command check failed. If next steps fail, restart Terminal and rerun.
) else (
  echo OK: %~1 found.
)
exit /b 0
