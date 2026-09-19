"""
build_desktop.py — Script đóng gói ứng dụng Desktop sang file .exe bằng PyInstaller
Tự động gom models (InsightFace onnx), database, assets và dependencies.
"""
import os
import sys
import subprocess

def build():
    print("==================================================")
    print("  DONG GOI UNG DUNG DIEM DANH SANG FILE .EXE")
    print("==================================================")
    
    # Kiểm tra pyinstaller
    try:
        import PyInstaller
    except ImportError:
        print("[!] Dang cai dat PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller", "--quiet"])

    # Danh sách các thư mục / file cần gom vào bundle
    # Cấu trúc: (nguồn, đích_trong_bundle)
    data_args = [
        "--add-data=models;models",
        "--add-data=database;database",
        "--add-data=core;core",
        "--add-data=services;services",
        "--add-data=utils;utils",
        "--add-data=desktop;desktop",
    ]

    # Ẩn import các thư viện C/Cython nếu cần
    hidden_imports = [
        "--hidden-import=insightface",
        "--hidden-import=onnxruntime",
        "--hidden-import=cv2",
        "--hidden-import=pyzbar",
        "--hidden-import=PyQt6",
        "--hidden-import=openpyxl",
        "--hidden-import=pandas",
        "--hidden-import=numpy",
    ]

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=DiemDanh_AI_Pro",
        "--windowed",              # Ẩn console đen
        "--noconfirm",             # Ghi đè thư mục build cũ
        "--clean",
        "desktop/main.py",
    ] + data_args + hidden_imports

    print("\n[+] Lenh thuc thi:")
    print(" ".join(cmd))
    print("\n[+] Dang tien hanh dong goi... Vui long doi trong giay lat...\n")

    subprocess.check_call(cmd)
    print("\n==================================================")
    print("  HOAN TAT DONG GOI!")
    print("  File .exe nam tai: dist/DiemDanh_AI_Pro/DiemDanh_AI_Pro.exe")
    print("==================================================")

if __name__ == "__main__":
    build()
