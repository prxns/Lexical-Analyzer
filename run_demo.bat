@echo off
setlocal
cd /d "%~dp0"
call build.bat
if errorlevel 1 exit /b 2
build\lexical_analyzer.exe samples\demo.c
exit /b %errorlevel%
