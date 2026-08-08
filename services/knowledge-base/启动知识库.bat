@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Starting Zhice AI Knowledge Base...
echo Keep this window open while using the application.

set "PYTHON_EXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%PYTHON_EXE%" (
    echo Python was not found: %PYTHON_EXE%
    pause
    exit /b 1
)

"%PYTHON_EXE%" "%~dp0server.py"
pause
