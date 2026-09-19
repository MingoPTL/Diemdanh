@echo off
title He Thong Diem Danh - Desktop App (PyQt6)
cd /d "%~dp0"

echo ============================================
echo   HE THONG DIEM DANH - DESKTOP APP
echo   (PyQt6 + SCRFD + ArcFace + Barcode)
echo ============================================
echo.

:: Activate conda environment
call E:\IDE\Miniconda3\condabin\conda.bat activate diemdanh

:: Run Desktop App
echo Dang khoi chay Desktop App...
python -m desktop.main

pause
