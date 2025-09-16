@echo off
setlocal

echo Starting RSPS Color Bot...

REM Determine project root (folder of this script)
set "ROOT=%~dp0"

REM Prefer .venv if present, then venv, otherwise fall back to system Python
set "PYEXE="
if exist "%ROOT%.venv\Scripts\python.exe" (
    set "PYEXE=%ROOT%.venv\Scripts\python.exe"
) else if exist "%ROOT%venv\Scripts\python.exe" (
    set "PYEXE=%ROOT%venv\Scripts\python.exe"
) else (
    set "PYEXE=python"
)

REM Run the app (pass through any additional args)
"%PYEXE%" "%ROOT%run.py" %*

echo.
echo Press any key to exit . . .
pause >nul
endlocal