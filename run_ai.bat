@echo off
chcp 65001 >nul
echo =========================================
echo Starting ISO 286 AI Assistant (Port 7011)
echo Environment: Conda - tol_env
echo =========================================

REM Use the conda environment Python directly
set PYTHON_EXE=C:\Users\User\anaconda3\envs\tol_env\python.exe

REM Check if Python exists
if not exist "%PYTHON_EXE%" (
    echo Error: Python not found at %PYTHON_EXE%
    echo Please check your conda installation.
    pause
    exit /b 1
)

REM Change to server directory
cd /d "%~dp0server"

REM Start Flask application
"%PYTHON_EXE%" ai_app.py

pause
