@echo off
rem ================================================================
rem  Erwin's Hypothesis - Windows launcher. Double-click to start.
rem
rem  Everything stays inside this folder:
rem    runtime\   Python environment + libraries (made on first run)
rem    projects\  your projects
rem    exports\   exported graphs
rem  Uses the Python already on this computer (3.10 or newer) if there
rem  is one; otherwise downloads a private copy into runtime\python.
rem
rem  Options (set before running):
rem    EH_PRIVATE_PYTHON=1   always use a private Python copy
rem    EH_NO_UPDATE=1        don't check GitHub for updates at start
rem ================================================================
setlocal EnableExtensions
title Erwin's Hypothesis

rem Run from a copy inside runtime\, so an update can safely replace
rem this file while the app is starting.
if not "%EH_FROM_COPY%"=="1" (
  if not exist "%~dp0runtime" mkdir "%~dp0runtime"
  copy /y "%~f0" "%~dp0runtime\launcher.bat" >nul
  set "EH_FROM_COPY=1"
  set "EH_ROOT=%~dp0"
  call "%~dp0runtime\launcher.bat"
  exit /b
)
cd /d "%EH_ROOT%"

set "RT=%EH_ROOT%runtime"
set "VENV=%RT%\venv"
set "PY=%VENV%\Scripts\python.exe"
set "UVEXE=%RT%\uv\uv.exe"
rem Keep every download cache inside this folder, and ignore any
rem libraries installed elsewhere on the computer.
set "PIP_CACHE_DIR=%RT%\cache\pip"
set "UV_CACHE_DIR=%RT%\cache\uv"
set "UV_PYTHON_INSTALL_DIR=%RT%\python"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PYTHONNOUSERSITE=1"

rem --- Warn if this folder is on a network drive ----------------------
call :check_network

rem --- Get the latest version from GitHub (if this folder is a clone) --
if not "%EH_NO_UPDATE%"=="1" call :update

if not exist "%RT%" mkdir "%RT%"

rem --- 1. Reuse the existing environment if it still works ----------
if exist "%PY%" (
  "%PY%" -c "import sys" >nul 2>&1 && goto :deps
  echo The app's Python environment needs rebuilding ^(was Python updated or removed?^)...
  rmdir /s /q "%VENV%"
)

if "%EH_PRIVATE_PYTHON%"=="1" goto :private

rem --- 2. Use a suitable Python already on this computer ------------
set "SYS="
call :try_python py -3
if not defined SYS call :try_python python
if not defined SYS call :try_python python3
if not defined SYS goto :private

echo Using the Python already installed on this computer.
%SYS% -m venv "%VENV%"
if errorlevel 1 (
  echo That Python couldn't create the app's environment; using a private copy instead.
  if exist "%VENV%" rmdir /s /q "%VENV%"
  goto :private
)
goto :deps

rem --- 3. Otherwise, a private Python inside this folder -------------
:private
echo Setting up a private copy of Python inside this folder (first run only)...
if not exist "%UVEXE%" (
  set "UVARCH=x86_64"
  if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "UVARCH=aarch64"
  call :get_uv
  if not exist "%UVEXE%" goto :fail
)
"%UVEXE%" venv --python 3.12 --python-preference only-managed "%VENV%"
if errorlevel 1 goto :fail

rem --- Install or update the libraries when requirements change -----
:deps
fc /b "backend\requirements.txt" "%VENV%\requirements.installed" >nul 2>&1
if not errorlevel 1 goto :start
echo.
echo Installing the app's libraries (first run or after an update).
echo This takes 1-2 minutes on a local disk. Progress is shown below.
echo.
if exist "%UVEXE%" (
  "%UVEXE%" pip install --python "%PY%" -r "backend\requirements.txt"
) else (
  "%PY%" -m pip install --no-cache-dir --progress-bar on -r "backend\requirements.txt"
)
if errorlevel 1 goto :fail
copy /y "backend\requirements.txt" "%VENV%\requirements.installed" >nul
echo.
echo Libraries installed.

:start
cd backend
"%PY%" -m app.main
if errorlevel 1 (
  echo.
  echo The app stopped unexpectedly. The message above may explain why.
  pause
)
exit /b 0

:fail
echo.
echo Setup didn't finish. Check your internet connection and try again.
echo (Only the first run needs internet.)
pause
exit /b 1

rem ---------------------------------------------------------------
:try_python
%* -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 set "SYS=%*"
exit /b 0

:check_network
set "NETWORK="
set "HERE=%EH_ROOT%"
if "%HERE:~0,2%"=="\\" set "NETWORK=1"
if not defined NETWORK (
  powershell -NoProfile -Command "if (([IO.DriveInfo]'%HERE:~0,2%').DriveType -eq 'Network') { exit 7 } else { exit 0 }" >nul 2>&1
  if errorlevel 7 set "NETWORK=1"
)
if not defined NETWORK exit /b 0
echo.
echo  ------------------------------------------------------------------
echo   NOTE: this folder is on a NETWORK drive.
echo   The app will work, but setup can take 10-30+ minutes and it will
echo   start slowly every time. For best speed, close this window, move
echo   the whole folder to your own disk (e.g. Documents), delete the
echo   "runtime" folder inside it, and run run.bat from there.
echo  ------------------------------------------------------------------
echo.
choice /c CQ /n /m "Press C to continue anyway, or Q to quit: "
if errorlevel 2 exit
exit /b 0

:update
if not exist "%EH_ROOT%.git" exit /b 0
where git >nul 2>&1 || exit /b 0
echo Checking for updates...
git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=10 pull --ff-only --quiet >nul 2>&1
if errorlevel 1 (
  echo   Couldn't check for updates right now ^(offline?^). Starting the current version.
) else (
  echo   Up to date.
)
exit /b 0

:get_uv
mkdir "%RT%\uv" 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue';" ^
  "$d=$env:RT + '\uv'; $z=Join-Path $d 'uv.zip';" ^
  "Invoke-WebRequest -UseBasicParsing ('https://github.com/astral-sh/uv/releases/latest/download/uv-' + $env:UVARCH + '-pc-windows-msvc.zip') -OutFile $z;" ^
  "Expand-Archive -Force $z $d; Remove-Item $z;" ^
  "Get-ChildItem $d -Recurse -Filter uv.exe | Select-Object -First 1 | ForEach-Object { if ($_.DirectoryName -ne $d) { Move-Item -Force $_.FullName $d } }"
exit /b 0
