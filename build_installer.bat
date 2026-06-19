@echo off
REM Build the full Windows installer: WisprLite.exe -> WisprLite-Setup.exe.
REM Requires: .venv set up (run.bat once) and Inno Setup 6 installed
REM (https://jrsoftware.org/isdl.php). Output: installer\Output\WisprLite-Setup.exe
cd /d "%~dp0"

echo [1/2] Building WisprLite.exe with PyInstaller...
call build_exe.bat
if not exist "dist\WisprLite.exe" (
    echo ERROR: dist\WisprLite.exe was not created. Aborting.
    pause
    exit /b 1
)

echo [2/2] Compiling installer with Inno Setup...
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo ERROR: ISCC.exe not found. Install Inno Setup 6 from https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)
"%ISCC%" "installer\WisprLite.iss"

echo.
echo Done. Installer at installer\Output\WisprLite-Setup.exe
pause
