@echo off
REM Build a standalone Pipevoice.exe (no console window) with PyInstaller.
REM Output lands in dist\Pipevoice.exe. Run this after run.bat has set up .venv.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
pip install pyinstaller
if not exist "assets\wisprlite.ico" python assets\make_icon.py
pyinstaller --noconfirm --clean --noconsole --onefile --name Pipevoice ^
    --icon assets\wisprlite.ico ^
    --add-data "assets\wisprlite.ico;assets" ^
    --collect-all deepgram ^
    --collect-all faster_whisper ^
    --collect-all ctranslate2 ^
    --collect-all pystray ^
    --collect-all PIL ^
    launch.py
echo.
echo Done. See dist\Pipevoice.exe
echo (Local Whisper downloads its model on first use; the exe stays small.)
