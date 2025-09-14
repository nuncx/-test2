@echo off
setlocal

echo Starting RSPS Color Bot...

REM Activate local venv if present
if exist "%~dp0venv\Scripts\activate.bat" (
	call "%~dp0venv\Scripts\activate.bat"
)

REM Run with venv's python if available, fall back to system python
if exist "%~dp0venv\Scripts\python.exe" (
	"%~dp0venv\Scripts\python.exe" "%~dp0run.py"
) else (
	python "%~dp0run.py"
)

echo.
echo Press any key to exit . . .
pause >nul
endlocal