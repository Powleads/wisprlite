@echo off
REM One-shot: push this folder to https://github.com/Powleads/wisprlite
REM which triggers the GitHub Actions build of WisprLite-Setup.exe.
REM First push opens a GitHub sign-in in your browser (Git Credential Manager).
cd /d "%~dp0"

where git >nul 2>nul
if errorlevel 1 (
    echo Git is not installed. Install "Git for Windows" then run this again:
    echo   https://git-scm.com/download/win
    pause
    exit /b 1
)

if not exist ".git" git init -b main

REM Set a commit identity for this repo (local only, no global changes).
git config user.email "james@powleads.com"
git config user.name "Powleads"

git add -A
git commit -m "WisprLite"
git branch -M main
git remote remove origin 2>nul
git remote add origin https://github.com/Powleads/wisprlite.git

echo.
echo Pushing to GitHub (a browser sign-in may pop up the first time)...
git push -u origin main
if errorlevel 1 (
    echo.
    echo Push failed. If it mentions authentication, complete the browser sign-in
    echo and run this file again. Otherwise copy the error and send it to Claude.
    pause
    exit /b 1
)

echo.
echo Pushed! Now go to https://github.com/Powleads/wisprlite/actions
echo Wait for the green build, open it, and download the WisprLite-Setup artifact.
pause
