@echo off
REM Launch Pipevoice. First run sets up a virtual environment and installs deps.
REM If keystrokes don't reach an *elevated* terminal, right-click -> Run as administrator.
cd /d "%~dp0"
if not exist ".venv" (
    echo First run: creating virtual environment and installing dependencies...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)
if not exist "assets\wisprlite.ico" python assets\make_icon.py
python -m wisprlite
pause
