@echo off
setlocal
cd /d "%~dp0"
title A股量化小白客户端

if not exist ".venv\Scripts\python.exe" goto :setup
".venv\Scripts\python.exe" -c "import flask, pandas, akshare, pyarrow" >nul 2>nul
if errorlevel 1 goto :setup
goto :start

:setup
if exist ".venv" rmdir /s /q ".venv"
(
  echo 第一次使用，正在安装运行环境，请耐心等待...
  call setup_windows.bat
  if errorlevel 1 exit /b 1
)

:start
echo 正在启动客户端，请稍候...
".venv\Scripts\python.exe" web_main.py --host 127.0.0.1
