@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title A-Stock Quant Client

set "CLIENT_URL=http://127.0.0.1:5000/"

call :check_server
if "%SERVER_OK%"=="1" goto :open_browser

if not exist ".venv\Scripts\python.exe" goto :setup
".venv\Scripts\python.exe" -c "import flask, pandas, akshare, pyarrow" >nul 2>nul
if errorlevel 1 goto :setup
goto :start_server

:setup
if exist ".venv" rmdir /s /q ".venv"
echo First run: installing the local runtime. Please wait...
call setup_windows.bat
if errorlevel 1 (
  echo.
  echo Setup failed. Send a screenshot of this window to Codex.
  pause
  exit /b 1
)

:start_server
echo Starting local client service...
start "A-Stock Quant Service" /min ".venv\Scripts\python.exe" web_main.py --host 127.0.0.1 --no-browser

for /l %%i in (1,1,20) do (
  timeout /t 1 /nobreak >nul
  call :check_server
  if "!SERVER_OK!"=="1" goto :open_browser
)

echo.
echo The local client service did not start in time.
echo Send a screenshot of this window to Codex.
pause
exit /b 1

:open_browser
echo Opening the local client...
if exist "%PROGRAMFILES%\Google\Chrome\Application\chrome.exe" (
  start "" "%PROGRAMFILES%\Google\Chrome\Application\chrome.exe" --app=%CLIENT_URL%
) else if exist "%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe" (
  start "" "%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe" --app=%CLIENT_URL%
) else if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" (
  start "" "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" --app=%CLIENT_URL%
) else (
  start "" "%CLIENT_URL%"
)
exit /b 0

:check_server
set "SERVER_OK=0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing '%CLIENT_URL%' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 set "SERVER_OK=1"
exit /b 0
