@echo off
setlocal
cd /d "%~dp0"
if not exist "dist\LexicalAnalyzer.exe" (
    echo The packaged desktop application was not found in dist.
    echo Download the complete project distribution from the official repository.
    pause
    exit /b 2
)
start "" "%~dp0dist\LexicalAnalyzer.exe"
exit /b 0
