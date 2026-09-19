@echo off
title Dong Goi Desktop App (.EXE)
cd /d "%~dp0"

echo ============================================
echo   DONG GOI HE THONG DIEM DANH (.EXE)
echo   PyInstaller + PyQt6 + AI Models
echo ============================================
echo.

call E:\IDE\Miniconda3\condabin\conda.bat activate diemdanh
python build_desktop.py

echo.
pause
