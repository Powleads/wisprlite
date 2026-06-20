@echo off
REM Build the full Windows installer: Pipevoice.exe -> Pipevoice-Setup.exe.
REM Requires: .venv set up (run.bat once) and Inno Setup 6 installed
REM (https://jrsoftware.org/isdl.php). Output: installer\Output\Pipevoice-Setup.exe
cd /d "%~dp0"

echo [1/2] Building Pipevoice.exe with PyInstaller...
call build_exe.bat
if not exist "dist\Pipevoice.exe" (
    echo ERROR: dist\Pipevoice.exe was not created. Aborting.
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
"%ISCC%" "installer\Pipevoice.iss"

echo.
echo Done. Installer at installer\Output\Pipevoice-Setup.exe
pause
