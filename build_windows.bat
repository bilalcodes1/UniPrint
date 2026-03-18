@echo off
echo =========================================
echo  UniPrint Windows Full Build Script
echo =========================================
echo.

:: Step 1: Install Python dependencies
echo [1/3] Installing requirements...
pip install pyinstaller uvicorn fastapi jinja2 python-multipart "qrcode[pil]" pillow websockets watchfiles colorama
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install requirements!
    pause
    exit /b 1
)
echo.

:: Step 2: Build UniPrint.exe using PyInstaller
echo [2/3] Building UniPrint.exe with PyInstaller...
pyinstaller --name "UniPrint" --noconfirm --onefile --windowed ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --hidden-import "uvicorn.logging" ^
    --hidden-import "uvicorn.loops" ^
    --hidden-import "uvicorn.loops.auto" ^
    --hidden-import "uvicorn.protocols" ^
    --hidden-import "uvicorn.protocols.http" ^
    --hidden-import "uvicorn.protocols.http.auto" ^
    --hidden-import "uvicorn.protocols.websockets" ^
    --hidden-import "uvicorn.protocols.websockets.auto" ^
    --hidden-import "uvicorn.lifespan" ^
    --hidden-import "uvicorn.lifespan.on" ^
    --hidden-import "uvicorn.lifespan.off" ^
    main.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PyInstaller build failed!
    pause
    exit /b 1
)
echo.

:: Step 3: Build the Windows Installer using Inno Setup
echo [3/3] Building Windows Installer (UniPrint_Setup.exe)...
echo.

:: Check common Inno Setup install locations
set ISCC=""
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"

if %ISCC%=="" (
    echo [!] Inno Setup not found. Skipping installer creation.
    echo     Download from: https://jrsoftware.org/isdl.php
    echo     Then re-run this script to generate UniPrint_Setup.exe
) else (
    mkdir installer_output 2>nul
    %ISCC% setup_uniprint.iss
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo =========================================
        echo  SUCCESS! Installer ready:
        echo  installer_output\UniPrint_Setup.exe
        echo =========================================
    ) else (
        echo ERROR: Inno Setup compilation failed!
    )
)

echo.
echo =========================================
echo  Build Complete!
echo  - EXE only:    dist\UniPrint.exe
echo  - Full Setup:  installer_output\UniPrint_Setup.exe
echo =========================================
pause
