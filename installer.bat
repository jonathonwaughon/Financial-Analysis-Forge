@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ====== CONFIG ======
set "REPO_URL=https://github.com/jonathonwaughon/Financial-Analysis-Forge.git"
set "APP_DIR=%~dp0"
set "VENV_DIR=%APP_DIR%\.venv"
set "PY_EXE=%VENV_DIR%\Scripts\python.exe"
set "PIP_EXE=%VENV_DIR%\Scripts\pip.exe"
REM ====================

echo.
echo ===== Financial Analysis Forge Installer =====
echo Target: "%APP_DIR%"
echo.

REM --- Require Git (install via winget if missing) ---
where git >nul 2>nul
if errorlevel 1 (
	echo [!] Git not found. Installing via winget...
	where winget >nul 2>nul || (echo [X] winget not found. Install "App Installer" from Microsoft Store.& exit /b 1)
	winget install --id Git.Git -e --source winget || (echo [X] Git install failed.& exit /b 1)
) else (
    echo Git found, skipping git installation
)

REM --- Require Python (install via winget if missing) ---
where python >nul 2>nul
if errorlevel 1 (
	echo [!] Python not found. Installing via winget...
	where winget >nul 2>nul || (echo [X] winget not found. Install "App Installer" from Microsoft Store.& exit /b 1)
	winget install --id Python.Python.3.12 -e --source winget || (echo [X] Python install failed.& exit /b 1)
) else (
    echo Python found, skipping python installation
)

REM --- Clone or update repo ---
if not exist "%APP_DIR%\" (
	echo [+] Cloning repo...
	git clone "%REPO_URL%" "%APP_DIR%" || (echo [X] Clone failed.& exit /b 1)
) else (
	echo [+] Repo exists. Pulling latest...
	pushd "%APP_DIR%" || exit /b 1
	git pull || (echo [X] git pull failed.& popd & exit /b 1)
	popd
)

REM --- Create venv if missing ---
if not exist "%PY_EXE%" (
	echo [+] Creating venv...
	python -m venv "%VENV_DIR%" || (echo [X] venv creation failed.& exit /b 1)
) else (
    echo Virtual environment found, skipping venv installation
)

REM --- Upgrade pip and install deps ---
echo [+] Installing dependencies...
"%PY_EXE%" -m pip install --upgrade pip || (echo [X] pip upgrade failed.& exit /b 1)

if exist "%APP_DIR%\requirements.txt" (
	"%PIP_EXE%" install -r "%APP_DIR%\requirements.txt" || (echo [X] pip install failed.& exit /b 1)
) else (
	echo [!] requirements.txt not found. Skipping dependency install.
)

echo.
echo [OK] FAF installed.
echo To run: "%PY_EXE%" "%APP_DIR%\main.py"
echo.

pause
exit /b 0
