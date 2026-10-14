@echo off
setlocal
title Multi-Free-Proxy
cd /d "%~dp0"

rem ---------------------------------------------------------------
rem  1) run main.py first
rem  2) install libraries ONLY if it exits with code 2 (missing lib)
rem  3) run it again
rem ---------------------------------------------------------------

where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo.
        echo  [ERROR] Python was not found on this system.
        echo          Install it from https://www.python.org/downloads/
        echo          and make sure "Add python.exe to PATH" is checked.
        echo.
        pause
        exit /b 1
    )
    set "PY=py -3"
) else (
    set "PY=python"
)

echo  Starting Multi-Free-Proxy...
echo.

%PY% main.py
set "RC=%ERRORLEVEL%"

if "%RC%"=="2" goto install
goto finish

:install
echo.
echo  [!] Missing Python libraries detected - installing requirements...
echo.
%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  [ERROR] Could not install libraries. Try manually:
    echo          python -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)
echo.
echo  [OK] Libraries installed. Starting again...
echo.
%PY% main.py

:finish
echo.
pause
endlocal
