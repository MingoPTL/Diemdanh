"""
desktop/main.py — Khởi chạy ứng dụng Desktop App Hệ Thống Điểm Danh Thông Minh
PyQt6 + DirectShow OpenCV + SCRFD + ArcFace + Barcode + SQLite
"""
import sys
import os

# Đảm bảo đường dẫn gốc được nhận diện
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QStatusBar, QFrame
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QFont, QCursor

import database.db as db
from services.face_db import face_db
from core.pipeline import pipeline
from desktop.theme import get_main_stylesheet, get_light_stylesheet, COLORS
from desktop.views.dashboard_view import DashboardView
from desktop.views.attendance_view import AttendanceView
from desktop.views.registration_view import RegistrationView
from desktop.views.class_mgmt_view import ClassMgmtView
from desktop.views.report_view import ReportView


class ModelPreloader(QThread):
    """Thread tải trước AI models và nạp embeddings vào RAM khi app vừa mở."""
    finished_loading = pyqtSignal()

    def run(self):
        try:
            # 1. Đảm bảo DB initialized
            db.init_db()
            
            # 2. Nạp toàn bộ Embeddings vào RAM
            students = db.get_all_students()
            face_db.load_all(students)
            
            # 3. Tải trước InsightFace SCRFD & ArcFace
            if not pipeline.is_loaded:
                pipeline.load()
        except Exception as e:
            print(f"[ModelPreloader] Error loading models: {e}")
        finally:
            self.finished_loading.emit()


class MainWindow(QMainWindow):
    """Cửa sổ chính của Hệ Thống Điểm Danh Desktop."""
    def __init__(self):
        super().__init__()
        self.is_dark_mode = True
        self.init_ui()

        # Khởi chạy tải trước AI models ở background
        self.preloader = ModelPreloader()
        self.preloader.finished_loading.connect(self.on_models_loaded)
        self.preloader.start()

    def init_ui(self):
        self.setWindowTitle("Hệ Thống Điểm Danh Sinh Viên Thông Minh — Desktop Pro (PyQt6)")
        self.resize(1360, 860)
        self.setMinimumSize(1100, 700)

        # Widget trung tâm
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 1. Top Navigation Bar ────────────────────────────────────────────
        top_bar = QFrame()
        top_bar.setFixedHeight(64)
        top_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_secondary']};
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(20, 0, 20, 0)
        top_layout.setSpacing(16)

        # Logo & App Title
        logo_layout = QHBoxLayout()
        logo_layout.setSpacing(10)
        lbl_logo = QLabel("📷")
        lbl_logo.setStyleSheet("font-size: 26px; background: transparent;")
        
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        lbl_app_title = QLabel("AI ATTENDANCE PRO")
        lbl_app_title.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {COLORS['blue_light']}; letter-spacing: 1.5px; background: transparent;")
        lbl_app_sub = QLabel("Desktop Native Application · SCRFD + ArcFace + Barcode")
        lbl_app_sub.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; background: transparent;")
        title_box.addWidget(lbl_app_title)
        title_box.addWidget(lbl_app_sub)

        logo_layout.addWidget(lbl_logo)
        logo_layout.addLayout(title_box)
        top_layout.addLayout(logo_layout)

        top_layout.addStretch()

        # Nút chuyển đổi Dark / Light Mode
        self.btn_theme_toggle = QPushButton("🌙 Dark Mode")
        self.btn_theme_toggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_theme_toggle.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['blue']};
            }}
        """)
        self.btn_theme_toggle.clicked.connect(self.toggle_theme)
        top_layout.addWidget(self.btn_theme_toggle)

        main_layout.addWidget(top_bar)

        # ── 2. Tabs Navigation ───────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # Tab Views
        self.view_dashboard = DashboardView()
        self.view_attendance = AttendanceView()
        self.view_registration = RegistrationView()
        self.view_class_mgmt = ClassMgmtView()
        self.view_reports = ReportView()

        # Kết nối signal điều hướng từ dashboard
        self.view_dashboard.navigate_to_tab.connect(self.switch_tab)

        self.tabs.addTab(self.view_dashboard, "📊  Trang Chủ")
        self.tabs.addTab(self.view_attendance, "📷  Điểm Danh")
        self.tabs.addTab(self.view_registration, "👤  Đăng Ký Khuôn Mặt")
        self.tabs.addTab(self.view_class_mgmt, "📋  Quản Lý Lớp & SV")
        self.tabs.addTab(self.view_reports, "📊  Báo Cáo & Thống Kê")

        # Khi chuyển tab -> tự động refresh view tương ứng
        self.tabs.currentChanged.connect(self.on_tab_changed)

        main_layout.addWidget(self.tabs, 1)

        # ── 3. Status Bar ────────────────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.lbl_status_ai = QLabel("⏳ Đang nạp mô hình AI & Embeddings...")
        self.lbl_status_ai.setStyleSheet(f"color: {COLORS['yellow_light']}; padding-left: 12px;")
        self.status_bar.addWidget(self.lbl_status_ai)

        self.lbl_status_fps = QLabel("DirectShow Camera Engine | 30-60 FPS")
        self.lbl_status_fps.setStyleSheet(f"color: {COLORS['text_muted']}; padding-right: 12px;")
        self.status_bar.addPermanentWidget(self.lbl_status_fps)

    def switch_tab(self, index: int):
        """Chuyển sang tab theo index."""
        if 0 <= index < self.tabs.count():
            self.tabs.setCurrentIndex(index)

    def on_tab_changed(self, index: int):
        """Refresh dữ liệu khi người dùng chuyển tab."""
        if index == 0:
            self.view_dashboard.refresh_data()
        elif index == 1:
            self.view_attendance.load_classes()
        elif index == 2:
            self.view_registration.load_classes()
        elif index == 3:
            self.view_class_mgmt.load_classes()
        elif index == 4:
            self.view_reports.load_classes()

    def toggle_theme(self):
        """Chuyển đổi giao diện Sáng / Tối."""
        self.is_dark_mode = not self.is_dark_mode
        app = QApplication.instance()
        if self.is_dark_mode:
            app.setStyleSheet(get_main_stylesheet())
            self.btn_theme_toggle.setText("🌙 Dark Mode")
        else:
            app.setStyleSheet(get_light_stylesheet())
            self.btn_theme_toggle.setText("☀️ Light Mode")

    def on_models_loaded(self):
        """Callback khi AI models và embeddings nạp xong."""
        self.lbl_status_ai.setText(f"🟢 Hệ thống sẵn sàng | Face Embeddings trong RAM: {face_db.count}")
        self.lbl_status_ai.setStyleSheet("color: #34D399; font-weight: 600; padding-left: 12px;")
        # Cập nhật lại số liệu dashboard
        self.view_dashboard.refresh_data()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(get_main_stylesheet())

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
