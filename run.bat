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
rem  To always use a private copy: set EH_PRIVATE_PYTHON=1 first.
rem ================================================================
setlocal EnableExtensions
title Erwin's Hypothesis
cd /d "%~dp0"

set "RT=%~dp0runtime"
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
"%UVEXE%" venv --quiet --python 3.12 --python-preference only-managed "%VENV%"
if errorlevel 1 goto :fail

rem --- Install or update the libraries when requirements change -----
:deps
fc /b "backend\requirements.txt" "%VENV%\requirements.installed" >nul 2>&1
if not errorlevel 1 goto :start
echo Installing the app's libraries (first run or update; about a minute)...
if exist "%UVEXE%" (
  "%UVEXE%" pip install --quiet --python "%PY%" -r "backend\requirements.txt"
) else (
  "%PY%" -m pip install --quiet --no-cache-dir -r "backend\requirements.txt"
)
if errorlevel 1 goto :fail
copy /y "backend\requirements.txt" "%VENV%\requirements.installed" >nul

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

:get_uv
mkdir "%RT%\uv" 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue';" ^
  "$d=$env:RT + '\uv'; $z=Join-Path $d 'uv.zip';" ^
  "Invoke-WebRequest -UseBasicParsing ('https://github.com/astral-sh/uv/releases/latest/download/uv-' + $env:UVARCH + '-pc-windows-msvc.zip') -OutFile $z;" ^
  "Expand-Archive -Force $z $d; Remove-Item $z;" ^
  "Get-ChildItem $d -Recurse -Filter uv.exe | Select-Object -First 1 | ForEach-Object { if ($_.DirectoryName -ne $d) { Move-Item -Force $_.FullName $d } }"
exit /b 0
