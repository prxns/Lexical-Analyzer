@echo off
setlocal
cd /d "%~dp0"
where gcc >nul 2>nul
if errorlevel 1 (
    echo GCC was not found on PATH. A C11-compatible GCC installation is required.
    echo In VS Code, open a new terminal after configuring GCC on PATH.
    exit /b 2
)
where windres >nul 2>nul
if errorlevel 1 (
    echo The MinGW resource compiler windres was not found on PATH.
    exit /b 2
)
if not exist build mkdir build
gcc -std=c11 -Wall -Wextra -Wpedantic -Werror -O2 -Iinclude src/main.c src/lexer.c -o build/lexical_analyzer.exe
if errorlevel 1 exit /b 1
windres -Iresources resources/app.rc -O coff -o build/gui-resources.o
if errorlevel 1 exit /b 1
gcc -std=c11 -Wall -Wextra -Wpedantic -Werror -O2 -Iinclude src/gui.c src/analysis.c src/lexer.c build/gui-resources.o -municode -mwindows -static-libgcc -lcomctl32 -lcomdlg32 -lgdi32 -luser32 -lshell32 -luxtheme -ldwmapi -o build/LexicalAnalyzer.exe
if errorlevel 1 exit /b 1
echo Built build\lexical_analyzer.exe and build\LexicalAnalyzer.exe
exit /b 0
