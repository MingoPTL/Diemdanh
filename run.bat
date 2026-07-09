@echo off
title He Thong Diem Danh Khuon Mat
echo ====================================
echo   He Thong Diem Danh Khuon Mat
echo ====================================
echo.

REM Kích hoạt môi trường Conda diemdanh
set CONDA_ACTIVATE=E:\IDE\Miniconda3\Scripts\activate.bat
if exist "%CONDA_ACTIVATE%" (
    call "%CONDA_ACTIVATE%" diemdanh
    echo [OK] Da kich hoat moi truong Conda: diemdanh
) else (
    echo [WARN] Khong tim thay Conda tai E:\IDE\Miniconda3, su dung Python hien tai
)

echo.
echo [*] Dang khoi dong Streamlit...
start http://localhost:8501
streamlit run app.py --server.port 8501

pause
