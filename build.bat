@echo off
setlocal
cd /d "%~dp0"
where gcc >nul 2>nul
if errorlevel 1 (
    echo GCC was not found on PATH. A C11-compatible GCC installation is required.
    echo In VS Code, open a new terminal after configuring GCC on PATH.
    exit /b 2
)
if not exist build mkdir build
gcc -std=c11 -Wall -Wextra -Wpedantic -Werror -O2 -Iinclude src/main.c src/lexer.c -o build/lexical_analyzer.exe
if errorlevel 1 exit /b 1
echo Built build\lexical_analyzer.exe
exit /b 0
