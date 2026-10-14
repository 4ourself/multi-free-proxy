@echo off
setlocal
title Multi-Free-Proxy
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo  [ERROR] Python was not found on this system.
        pause
        exit /b 1
    )
    set "PY=py -3"
) else (
    set "PY=python"
)

%PY% src\main.py
if "%ERRORLEVEL%"=="2" goto install
goto finish

:install
echo  [!] Missing libraries - installing...
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
    echo  [ERROR] Could not install libraries.
    pause
    exit /b 1
)
%PY% src\main.py

:finish
pause
endlocal
