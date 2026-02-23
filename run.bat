@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "APP_DIR=%~dp0"
set "VENV_DIR=%APP_DIR%.venv"
set "PY_SYS=python"
set "PY_VENV=%VENV_DIR%\Scripts\python.exe"

REM 1) Check system python exists
where %PY_SYS% >nul 2>nul
if errorlevel 1 (
	echo [!] Python not found on PATH. Install Python 3.10+ and re-run.
    timeout /t 10
	exit /b 1
)

REM 2) Create venv if missing
if not exist "%PY_VENV%" (
	echo [*] Creating venv at "%VENV_DIR%"...
	%PY_SYS% -m venv "%VENV_DIR%"
	if errorlevel 1 (
		echo [!] Failed to create venv.
        timeout /t 10
		exit /b 1
	)
)

REM 3) (Optional) install deps if requirements.txt exists
if exist "%APP_DIR%requirements.txt" (
	echo [*] Installing/updating dependencies...
	"%PY_VENV%" -m pip install --upgrade pip >nul
	"%PY_VENV%" -m pip install -r "%APP_DIR%requirements.txt"
	if errorlevel 1 (
		echo [!] pip install failed.
        timeout /t 10
		exit /b 1
	)
)

REM 4) Run app.py using venv python
echo [*] Launching app...
"%PY_VENV%" "%APP_DIR%app.py"