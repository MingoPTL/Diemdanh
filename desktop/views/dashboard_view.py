"""
desktop/views/dashboard_view.py — Dashboard tổng quan hệ thống điểm danh
Hiển thị KPI Cards (Số lớp, Tổng SV, Đã đăng ký, Embeddings, Buổi điểm danh),
danh sách lớp học trực quan với badge và các phím tắt nhanh.
"""
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QGridLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QCursor

import database.db as db
from services.face_db import face_db
from desktop.theme import COLORS, FONT_FAMILY


class StatCard(QFrame):
    """Thẻ thống kê KPI với hiệu ứng Glassmorphism hiện đại."""
    def __init__(self, icon: str, title: str, value: str, subtext: str = "", accent_color: str = COLORS["blue"], parent=None):
        super().__init__(parent)
        self.setObjectName("card_glass")
        self.setMinimumHeight(110)
        self.setStyleSheet(f"""
            QFrame#card_glass {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border_light']};
                border-left: 4px solid {accent_color};
                border-radius: 12px;
                padding: 14px;
            }}
            QFrame#card_glass:hover {{
                border-color: {accent_color};
                background-color: {COLORS['bg_elevated']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # Top row: icon + title
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)

        lbl_icon = QLabel(icon)
        lbl_icon.setStyleSheet("font-size: 20px; background: transparent;")
        lbl_title = QLabel(title.upper())
        lbl_title.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['text_secondary']}; letter-spacing: 1px; background: transparent;")
        top_layout.addWidget(lbl_icon)
        top_layout.addWidget(lbl_title)
        top_layout.addStretch()

        # Value
        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet(f"font-size: 26px; font-weight: 700; color: {COLORS['text_primary']}; background: transparent;")

        # Subtext
        self.lbl_subtext = QLabel(subtext)
        self.lbl_subtext.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; background: transparent;")

        layout.addLayout(top_layout)
        layout.addWidget(self.lbl_value)
        if subtext:
            layout.addWidget(self.lbl_subtext)
        layout.addStretch()

    def update_value(self, value: str, subtext: str = ""):
        self.lbl_value.setText(value)
        if subtext:
            self.lbl_subtext.setText(subtext)


class DashboardView(QWidget):
    """Trang chủ / Dashboard Tổng quan hệ thống."""
    # Signal điều hướng sang các tab khác
    navigate_to_tab = pyqtSignal(int)  # 0: Dashboard, 1: Attendance, 2: Register, 3: Classes, 4: Reports

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.refresh_data()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(18)

        # ── 1. Header Section ────────────────────────────────────────────────
        header_layout = QHBoxLayout()
        
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel("📊 Bảng Điều Khiển Tổng Quan")
        lbl_title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {COLORS['text_primary']};")
        self.lbl_subtitle = QLabel("Hệ thống điểm danh thông minh — Nhận diện đa phương thức")
        self.lbl_subtitle.setStyleSheet(f"font-size: 13px; color: {COLORS['text_secondary']};")
        title_box.addWidget(lbl_title)
        title_box.addWidget(self.lbl_subtitle)

        header_layout.addLayout(title_box)
        header_layout.addStretch()

        btn_refresh = QPushButton("🔄 Làm mới dữ liệu")
        btn_refresh.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg_secondary']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['blue']};
                border-color: {COLORS['blue']};
                color: white;
            }}
        """)
        btn_refresh.clicked.connect(self.refresh_data)
        header_layout.addWidget(btn_refresh)

        main_layout.addLayout(header_layout)

        # ── 2. KPI Cards Grid ────────────────────────────────────────────────
        kpi_grid = QGridLayout()
        kpi_grid.setHorizontalSpacing(16)
        kpi_grid.setVerticalSpacing(12)

        self.card_classes = StatCard("🏫", "Lớp Học", "0", "Đang quản lý", COLORS["blue"])
        self.card_students = StatCard("👥", "Tổng Sinh Viên", "0", "Trên toàn hệ thống", COLORS["purple"])
        self.card_registered = StatCard("✅", "Đã Đăng Ký AI", "0", "0% hoàn thành", COLORS["green"])
        self.card_faces = StatCard("🧠", "Face Embeddings", "0", "Trong bộ nhớ RAM", COLORS["orange"])

        kpi_grid.addWidget(self.card_classes, 0, 0)
        kpi_grid.addWidget(self.card_students, 0, 1)
        kpi_grid.addWidget(self.card_registered, 0, 2)
        kpi_grid.addWidget(self.card_faces, 0, 3)

        main_layout.addLayout(kpi_grid)

        # ── 3. Quick Action Buttons ──────────────────────────────────────────
        action_box = QFrame()
        action_box.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 12px;
                padding: 12px;
            }}
        """)
        action_layout = QHBoxLayout(action_box)
        action_layout.setContentsMargins(16, 12, 16, 12)
        action_layout.setSpacing(14)

        lbl_quick = QLabel("⚡ Thao tác nhanh:")
        lbl_quick.setStyleSheet(f"font-weight: 700; color: {COLORS['text_accent']}; font-size: 13px; background: transparent;")
        action_layout.addWidget(lbl_quick)

        btn_go_attendance = QPushButton("📷 Bắt Đầu Điểm Danh")
        btn_go_attendance.setObjectName("btn_primary")
        btn_go_attendance.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_go_attendance.clicked.connect(lambda: self.navigate_to_tab.emit(1))
        action_layout.addWidget(btn_go_attendance)

        btn_go_register = QPushButton("👤 Đăng Ký Khuôn Mặt")
        btn_go_register.setObjectName("btn_success")
        btn_go_register.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_go_register.clicked.connect(lambda: self.navigate_to_tab.emit(2))
        action_layout.addWidget(btn_go_register)

        btn_go_classes = QPushButton("📋 Quản Lý Lớp Học")
        btn_go_classes.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_go_classes.clicked.connect(lambda: self.navigate_to_tab.emit(3))
        action_layout.addWidget(btn_go_classes)

        btn_go_reports = QPushButton("📊 Xem Báo Cáo & Xuất Excel")
        btn_go_reports.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_go_reports.clicked.connect(lambda: self.navigate_to_tab.emit(4))
        action_layout.addWidget(btn_go_reports)

        action_layout.addStretch()
        main_layout.addWidget(action_box)

        # ── 4. Class List Section ────────────────────────────────────────────
        class_section = QVBoxLayout()
        class_section.setSpacing(10)

        sec_header = QHBoxLayout()
        lbl_sec = QLabel("🏫 Danh Sách Lớp Học & Tiến Độ Đăng Ký")
        lbl_sec.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {COLORS['text_primary']};")
        sec_header.addWidget(lbl_sec)
        sec_header.addStretch()

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Tìm lớp theo tên hoặc mã...")
        self.txt_search.setFixedWidth(260)
        self.txt_search.textChanged.connect(self.filter_classes)
        sec_header.addWidget(self.txt_search)

        class_section.addLayout(sec_header)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Mã Lớp", "Tên Lớp Học", "Loại Lớp", "Sĩ Số", "Đã Đăng Ký AI", "Số Buổi Học"
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['bg_secondary']};
                alternate-background-color: {COLORS['bg_elevated']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 10px;
                gridline-color: {COLORS['border']};
            }}
            QHeaderView::section {{
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text_primary']};
                padding: 10px;
                font-weight: 600;
                border: none;
                border-bottom: 2px solid {COLORS['blue']};
            }}
            QTableWidget::item {{
                padding: 10px;
                color: {COLORS['text_primary']};
            }}
        """)

        class_section.addWidget(self.table)
        main_layout.addLayout(class_section)

    def refresh_data(self):
        """Tải lại dữ liệu từ Database & cập nhật UI."""
        try:
            classes = db.get_all_classes()
            students = db.get_all_students()
            
            # Đảm bảo Face DB được đồng bộ
            if face_db.count == 0 and students:
                face_db.load_all(students)

            total_cls = len(classes)
            total_stu = len(students)
            reg_count = sum(1 for s in students if s["registered"])
            pct = int(reg_count / total_stu * 100) if total_stu > 0 else 0

            # Cập nhật KPI
            self.card_classes.update_value(str(total_cls), "Lớp học đang quản lý")
            self.card_students.update_value(str(total_stu), "Sinh viên đã thêm")
            self.card_registered.update_value(f"{reg_count}/{total_stu}", f"{pct}% đã đăng ký khuôn mặt")
            self.card_faces.update_value(str(face_db.count), "Khuôn mặt trong bộ nhớ RAM")

            # Cập nhật subtitle thời gian
            now_str = datetime.now().strftime("%A, %d/%m/%Y · %H:%M")
            self.lbl_subtitle.setText(f"Hệ thống điểm danh thông minh · Cập nhật lúc {now_str}")

            # Lưu danh sách lớp vào cache để lọc
            self.classes_data = []
            for cls in classes:
                sts = db.get_all_students(cls["id"])
                reg_sts = sum(1 for s in sts if s["registered"])
                sessions = db.get_sessions_by_class(cls["id"])
                c_type = dict(cls).get("type", "Lý thuyết")
                self.classes_data.append({
                    "id": cls["id"],
                    "code": cls["code"],
                    "name": cls["name"],
                    "type": c_type,
                    "total_students": len(sts),
                    "registered_students": reg_sts,
                    "sessions_count": len(sessions)
                })

            self.populate_table(self.classes_data)
        except Exception as e:
            print(f"[DashboardView] Error refreshing data: {e}")

    def populate_table(self, data_list):
        """Điền dữ liệu vào bảng danh sách lớp."""
        self.table.setRowCount(len(data_list))
        for row, item in enumerate(data_list):
            item_code = QTableWidgetItem(str(item["code"]))
            item_code.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_code.setForeground(Qt.GlobalColor.white)
            
            item_name = QTableWidgetItem(str(item["name"]))
            
            type_text = f"📘 {item['type']}" if item["type"] == "Lý thuyết" else f"🧪 {item['type']}"
            item_type = QTableWidgetItem(type_text)
            item_type.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            item_total = QTableWidgetItem(f"{item['total_students']} SV")
            item_total.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            reg_text = f"{item['registered_students']} / {item['total_students']}"
            item_reg = QTableWidgetItem(reg_text)
            item_reg.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if item['total_students'] > 0 and item['registered_students'] == item['total_students']:
                item_reg.setForeground(Qt.GlobalColor.green)

            item_sessions = QTableWidgetItem(f"{item['sessions_count']} buổi")
            item_sessions.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table.setItem(row, 0, item_code)
            self.table.setItem(row, 1, item_name)
            self.table.setItem(row, 2, item_type)
            self.table.setItem(row, 3, item_total)
            self.table.setItem(row, 4, item_reg)
            self.table.setItem(row, 5, item_sessions)

    def filter_classes(self, text: str):
        """Lọc danh sách lớp theo từ khóa tìm kiếm."""
        if not hasattr(self, "classes_data"):
            return
        query = text.lower().strip()
        if not query:
            self.populate_table(self.classes_data)
            return

        filtered = [
            c for c in self.classes_data
            if query in c["code"].lower() or query in c["name"].lower()
        ]
        self.populate_table(filtered)
