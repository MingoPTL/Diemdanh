@echo off
title He Thong Diem Danh Khuon Mat
echo ====================================
echo   He Thong Diem Danh Khuon Mat
echo ====================================
echo.

set CONDA_PYTHON=E:\IDE\Miniconda3\envs\diemdanh\python.exe
set CONDA_ACTIVATE=E:\IDE\Miniconda3\Scripts\activate.bat
set APP_URL=http://localhost:8501

if exist "%CONDA_PYTHON%" (
    echo [OK] Da tim thay moi truong Conda: diemdanh
    echo [*] Dang khoi dong Streamlit...
    echo.
    start "" "%APP_URL%"
    "%CONDA_PYTHON%" -m streamlit run app.py --server.port 8501 --server.headless false
) else if exist "%CONDA_ACTIVATE%" (
    call "%CONDA_ACTIVATE%" diemdanh
    echo [OK] Da kich hoat moi truong Conda: diemdanh
    echo [*] Dang khoi dong Streamlit...
    echo.
    start "" "%APP_URL%"
    python -m streamlit run app.py --server.port 8501 --server.headless false
) else (
    echo [WARN] Dang dung Python mac dinh...
    echo.
    start "" "%APP_URL%"
    python -m streamlit run app.py --server.port 8501 --server.headless false
)

pause
