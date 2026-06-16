@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="

if not defined PYTHON_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PYTHON_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PYTHON_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PYTHON_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"

where py >nul 2>nul
if not defined PYTHON_CMD if not errorlevel 1 set "PYTHON_CMD=py"

if not defined PYTHON_CMD (
  echo Python was not found.
  echo Install Python 3.11, 3.12, 3.13, or 3.14.
  pause
  exit /b 1
)

"%PYTHON_CMD%" -m venv .venv
if errorlevel 1 goto :failed

".venv\Scripts\python.exe" -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 30 --retries 2 --upgrade pip
if errorlevel 1 goto :failed

".venv\Scripts\python.exe" -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 30 --retries 2 -r requirements.txt -r requirements-dev.txt
if errorlevel 1 goto :failed

echo.
echo Setup completed.
pause
exit /b 0

:failed
echo.
echo Setup failed. Review the message above.
pause
exit /b 1
