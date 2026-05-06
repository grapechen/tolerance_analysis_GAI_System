@echo off
chcp 65001 >nul
echo =========================================
echo Starting AI Assistant (Port 7011)
echo Environment: Conda - tol_env
echo =========================================

REM Fix MKL/OpenMP DLL conflict (must be set BEFORE python.exe starts)
set KMP_DUPLICATE_LIB_OK=TRUE
set MKL_THREADING_LAYER=sequential
set MKL_DISABLE_FAST_MM=1
set MKL_NUM_THREADS=1
set NUMEXPR_NUM_THREADS=1
set OMP_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1

set PYTHON_EXE=C:\Users\User\anaconda3\envs\tol_env\python.exe

if not exist "%PYTHON_EXE%" (
    echo Error: Python not found at %PYTHON_EXE%
    pause
    exit /b 1
)

set PATH=C:\Users\User\anaconda3\envs\tol_env\Library\bin;%PATH%
set PATH=C:\Users\User\anaconda3\envs\tol_env\Library\mingw-w64\bin;%PATH%

cd /d "%~dp0server"

"%PYTHON_EXE%" ai_app.py

pause
