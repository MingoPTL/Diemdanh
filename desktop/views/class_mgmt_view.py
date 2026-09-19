"""
desktop/views/class_mgmt_view.py — Quản lý Lớp Học & Sinh Viên
Hỗ trợ:
- Tạo lớp mới (Lý thuyết / Thực hành), Sửa / Xóa lớp
- Thêm sinh viên thủ công, Chọn SV có sẵn từ lớp khác, Nhập từ file Excel
- Quản lý danh sách sinh viên, sửa/xóa, tìm kiếm nhanh
"""
import os
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox, QTabWidget,
    QFormLayout, QDialog, QFileDialog, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QFont

import database.db as db
from desktop.theme import COLORS, FONT_FAMILY


class AddStudentDialog(QDialog):
    """Hộp thoại thêm sinh viên mới vào lớp."""
    def __init__(self, class_id: int, parent=None):
        super().__init__(parent)
        self.class_id = class_id
        self.setWindowTitle("➕ Thêm Sinh Viên Mới")
        self.setFixedSize(450, 320)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['bg_primary']};
                color: {COLORS['text_primary']};
            }}
            QLineEdit, QComboBox {{
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px 12px;
            }}
            QPushButton {{
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)

        self.txt_code = QLineEdit()
        self.txt_code.setPlaceholderText("VD: 20110001")
        form.addRow("Mã Sinh Viên (MSSV) *:", self.txt_code)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("VD: Nguyễn Văn A")
        form.addRow("Họ và Tên *:", self.txt_name)

        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("VD: nguyenvana@student.edu.vn")
        form.addRow("Email:", self.txt_email)

        self.txt_phone = QLineEdit()
        self.txt_phone.setPlaceholderText("VD: 0912345678")
        form.addRow("Số Điện Thoại:", self.txt_phone)

        self.txt_barcode = QLineEdit()
        self.txt_barcode.setPlaceholderText("Mã vạch thẻ SV (mặc định trùng MSSV nếu để trống)")
        form.addRow("Mã Barcode / QR:", self.txt_barcode)

        layout.addLayout(form)

        # Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Hủy")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("💾 Lưu Sinh Viên")
        btn_save.setStyleSheet(f"background-color: {COLORS['blue']}; color: white;")
        btn_save.clicked.connect(self.save_student)
        btn_box.addWidget(btn_save)

        layout.addLayout(btn_box)

    def save_student(self):
        code = self.txt_code.text().strip()
        name = self.txt_name.text().strip()
        email = self.txt_email.text().strip()
        phone = self.txt_phone.text().strip()
        barcode = self.txt_barcode.text().strip() or code

        if not code or not name:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập đầy đủ MSSV và Họ Tên!")
            return

        try:
            db.add_student(
                student_code=code,
                full_name=name,
                class_id=self.class_id
            )
            QMessageBox.information(self, "Thành Công", f"Đã thêm sinh viên {name} ({code}) vào lớp!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu sinh viên: {str(e)}")


class ClassMgmtView(QWidget):
    """Màn hình Quản Lý Lớp Học & Sinh Viên."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.load_classes()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # Header
        header_box = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel("📋 Quản Lý Lớp Học & Sinh Viên")
        lbl_title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {COLORS['text_primary']};")
        lbl_sub = QLabel("Tạo lớp, phân loại Lý thuyết/Thực hành, thêm sinh viên hoặc import từ Excel")
        lbl_sub.setStyleSheet(f"font-size: 13px; color: {COLORS['text_secondary']};")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        header_box.addLayout(title_box)
        header_box.addStretch()
        main_layout.addLayout(header_box)

        # Tab Widget: 1. Quản lý Sinh viên trong Lớp | 2. Tạo Lớp Mới | 3. Danh Sách Lớp
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {COLORS['border_light']};
                border-radius: 12px;
                background-color: {COLORS['bg_secondary']};
                padding: 12px;
            }}
            QTabBar::tab {{
                background-color: {COLORS['bg_primary']};
                color: {COLORS['text_secondary']};
                padding: 10px 20px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 4px;
                font-weight: 600;
            }}
            QTabBar::tab:selected {{
                background-color: {COLORS['bg_secondary']};
                color: {COLORS['blue_light']};
                border-bottom: 2px solid {COLORS['blue']};
            }}
        """)

        # Tab 1: Sinh viên trong lớp
        self.tab_students = QWidget()
        self.setup_students_tab()
        self.tabs.addTab(self.tab_students, "👥 Sinh Viên Trong Lớp")

        # Tab 2: Tạo lớp mới
        self.tab_create_class = QWidget()
        self.setup_create_class_tab()
        self.tabs.addTab(self.tab_create_class, "➕ Tạo Lớp Mới")

        # Tab 3: Quản lý danh sách lớp
        self.tab_classes_list = QWidget()
        self.setup_classes_list_tab()
        self.tabs.addTab(self.tab_classes_list, "🏫 Danh Sách & Sửa Lớp")

        main_layout.addWidget(self.tabs, 1)

    # ── TAB 1: Quản lý Sinh Viên ───────────────────────────────────────────────
    def setup_students_tab(self):
        layout = QVBoxLayout(self.tab_students)
        layout.setSpacing(14)

        # Toolbar chọn lớp + Thao tác
        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        lbl_cls = QLabel("🏫 Chọn Lớp:")
        lbl_cls.setStyleSheet("font-weight: 600;")
        self.cb_classes_filter = QComboBox()
        self.cb_classes_filter.setMinimumWidth(260)
        self.cb_classes_filter.currentIndexChanged.connect(self.on_class_filter_changed)
        toolbar.addWidget(lbl_cls)
        toolbar.addWidget(self.cb_classes_filter)

        self.txt_search_stu = QLineEdit()
        self.txt_search_stu.setPlaceholderText("🔍 Tìm theo tên hoặc MSSV...")
        self.txt_search_stu.setFixedWidth(220)
        self.txt_search_stu.textChanged.connect(self.filter_students_table)
        toolbar.addWidget(self.txt_search_stu)

        toolbar.addStretch()

        btn_add_stu = QPushButton("➕ Thêm SV")
        btn_add_stu.setObjectName("btn_primary")
        btn_add_stu.clicked.connect(self.open_add_student_dialog)
        toolbar.addWidget(btn_add_stu)

        btn_import_excel = QPushButton("📁 Nhập Excel")
        btn_import_excel.clicked.connect(self.import_from_excel)
        toolbar.addWidget(btn_import_excel)

        btn_export_excel = QPushButton("📥 Xuất Excel")
        btn_export_excel.clicked.connect(self.export_to_excel)
        toolbar.addWidget(btn_export_excel)

        layout.addLayout(toolbar)

        # Bảng danh sách sinh viên
        self.table_students = QTableWidget()
        self.table_students.setColumnCount(7)
        self.table_students.setHorizontalHeaderLabels([
            "MSSV", "Họ và Tên", "Mã Vạch / QR", "Email", "SĐT", "Đã Đăng Ký AI", "Thao Tác"
        ])
        self.table_students.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_students.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_students.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_students.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_students.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table_students.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table_students.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table_students.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_students.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_students.verticalHeader().setVisible(False)
        self.table_students.setAlternatingRowColors(True)

        layout.addWidget(self.table_students, 1)

    # ── TAB 2: Tạo Lớp Mới ───────────────────────────────────────────────────
    def setup_create_class_tab(self):
        layout = QVBoxLayout(self.tab_create_class)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(16)

        form_box = QFrame()
        form_box.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_primary']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 12px;
                padding: 24px;
            }}
        """)
        form_layout = QFormLayout(form_box)
        form_layout.setSpacing(14)

        self.txt_new_cls_name = QLineEdit()
        self.txt_new_cls_name.setPlaceholderText("VD: Lập trình Python Nâng Cao")
        form_layout.addRow("Tên Lớp Học *:", self.txt_new_cls_name)

        self.txt_new_cls_code = QLineEdit()
        self.txt_new_cls_code.setPlaceholderText("VD: CS101-01")
        form_layout.addRow("Mã Lớp Học *:", self.txt_new_cls_code)

        self.cb_new_cls_type = QComboBox()
        self.cb_new_cls_type.addItems(["Lý thuyết", "Thực hành"])
        form_layout.addRow("Loại Lớp *:", self.cb_new_cls_type)

        self.txt_new_cls_term = QLineEdit()
        self.txt_new_cls_term.setPlaceholderText("VD: Học kỳ 1")
        form_layout.addRow("Học Kỳ:", self.txt_new_cls_term)

        self.txt_new_cls_year = QLineEdit()
        self.txt_new_cls_year.setPlaceholderText("VD: 2024-2025")
        form_layout.addRow("Năm Học:", self.txt_new_cls_year)

        self.txt_new_cls_desc = QLineEdit()
        self.txt_new_cls_desc.setPlaceholderText("Ghi chú thêm về lớp học...")
        form_layout.addRow("Mô Tả:", self.txt_new_cls_desc)

        layout.addWidget(form_box)

        btn_save_class = QPushButton("💾 Tạo Lớp Mới")
        btn_save_class.setObjectName("btn_primary")
        btn_save_class.setMinimumHeight(40)
        btn_save_class.clicked.connect(self.create_class)
        layout.addWidget(btn_save_class)
        layout.addStretch()

    # ── TAB 3: Quản lý danh sách lớp ─────────────────────────────────────────
    def setup_classes_list_tab(self):
        layout = QVBoxLayout(self.tab_classes_list)
        layout.setSpacing(14)

        self.table_classes = QTableWidget()
        self.table_classes.setColumnCount(7)
        self.table_classes.setHorizontalHeaderLabels([
            "ID", "Mã Lớp", "Tên Lớp Học", "Loại Lớp", "Học Kỳ", "Năm Học", "Thao Tác"
        ])
        self.table_classes.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_classes.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_classes.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_classes.verticalHeader().setVisible(False)
        self.table_classes.setAlternatingRowColors(True)

        layout.addWidget(self.table_classes, 1)

    # ── LOGIC XỬ LÝ ──────────────────────────────────────────────────────────
    def load_classes(self):
        """Load danh sách lớp vào combobox và bảng quản lý."""
        self.cb_classes_filter.blockSignals(True)
        self.cb_classes_filter.clear()
        try:
            classes = db.get_all_classes()
            if not classes:
                self.cb_classes_filter.addItem("-- Chưa có lớp nào --", None)
            else:
                for c in classes:
                    c_type = dict(c).get("type", "Lý thuyết")
                    label = f"{c['name']} ({c['code']}) - {c_type}"
                    self.cb_classes_filter.addItem(label, c["id"])

            # Điền vào table_classes (Tab 3)
            self.table_classes.setRowCount(len(classes))
            for row, cls in enumerate(classes):
                c_dict = dict(cls)
                item_id = QTableWidgetItem(str(c_dict.get("id", "")))
                item_code = QTableWidgetItem(str(c_dict.get("code", "")))
                item_name = QTableWidgetItem(str(c_dict.get("name", "")))
                item_type = QTableWidgetItem(str(c_dict.get("type", "Lý thuyết")))
                item_term = QTableWidgetItem(str(c_dict.get("semester", "")))
                item_year = QTableWidgetItem(str(c_dict.get("academic_year", "")))

                self.table_classes.setItem(row, 0, item_id)
                self.table_classes.setItem(row, 1, item_code)
                self.table_classes.setItem(row, 2, item_name)
                self.table_classes.setItem(row, 3, item_type)
                self.table_classes.setItem(row, 4, item_term)
                self.table_classes.setItem(row, 5, item_year)

                # Nút xóa lớp
                btn_del = QPushButton("🗑 Xóa")
                btn_del.setObjectName("btn_danger")
                btn_del.clicked.connect(lambda _, cid=c_dict["id"]: self.delete_class(cid))
                self.table_classes.setCellWidget(row, 6, btn_del)

        finally:
            self.cb_classes_filter.blockSignals(False)

        self.on_class_filter_changed()

    def on_class_filter_changed(self):
        """Khi đổi lớp ở Tab 1, load lại danh sách sinh viên."""
        class_id = self.cb_classes_filter.currentData()
        if class_id is None:
            self.table_students.setRowCount(0)
            return

        self.current_students_data = db.get_all_students(class_id)
        self.populate_students_table(self.current_students_data)

    def populate_students_table(self, students_list):
        self.table_students.setRowCount(len(students_list))
        for row, s in enumerate(students_list):
            s_dict = dict(s)
            item_code = QTableWidgetItem(str(s_dict.get("student_code", "")))
            item_name = QTableWidgetItem(str(s_dict.get("full_name", "")))
            item_barcode = QTableWidgetItem(str(s_dict.get("barcode") or s_dict.get("student_code", "")))
            item_email = QTableWidgetItem(str(s_dict.get("email", "")))
            item_phone = QTableWidgetItem(str(s_dict.get("phone", "")))

            reg_text = "✅ Đã đăng ký" if s_dict.get("registered") else "⏳ Chưa đăng ký"
            item_reg = QTableWidgetItem(reg_text)
            if s_dict.get("registered"):
                item_reg.setForeground(Qt.GlobalColor.green)
            else:
                item_reg.setForeground(Qt.GlobalColor.yellow)

            self.table_students.setItem(row, 0, item_code)
            self.table_students.setItem(row, 1, item_name)
            self.table_students.setItem(row, 2, item_barcode)
            self.table_students.setItem(row, 3, item_email)
            self.table_students.setItem(row, 4, item_phone)
            self.table_students.setItem(row, 5, item_reg)

            # Nút xóa SV khỏi lớp
            btn_del = QPushButton("🗑 Xóa")
            btn_del.clicked.connect(lambda _, sid=s_dict["id"]: self.delete_student(sid))
            self.table_students.setCellWidget(row, 6, btn_del)

    def filter_students_table(self, query: str):
        if not hasattr(self, "current_students_data"):
            return
        q = query.lower().strip()
        if not q:
            self.populate_students_table(self.current_students_data)
            return

        filtered = [
            s for s in self.current_students_data
            if q in s["student_code"].lower() or q in s["full_name"].lower()
        ]
        self.populate_students_table(filtered)

    def open_add_student_dialog(self):
        class_id = self.cb_classes_filter.currentData()
        if class_id is None:
            QMessageBox.warning(self, "Chưa chọn lớp", "Vui lòng chọn lớp học trước!")
            return
        dlg = AddStudentDialog(class_id, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.on_class_filter_changed()

    def create_class(self):
        name = self.txt_new_cls_name.text().strip()
        code = self.txt_new_cls_code.text().strip()
        c_type = self.cb_new_cls_type.currentText()
        term = self.txt_new_cls_term.text().strip()
        year = self.txt_new_cls_year.text().strip()
        desc = self.txt_new_cls_desc.text().strip()

        if not name or not code:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập đầy đủ Tên Lớp và Mã Lớp!")
            return

        try:
            db.add_class(name=name, code=code, class_type=c_type)
            QMessageBox.information(self, "Thành Công", f"Đã tạo lớp '{name}' ({code}) thành công!")
            self.txt_new_cls_name.clear()
            self.txt_new_cls_code.clear()
            self.txt_new_cls_desc.clear()
            self.load_classes()
            self.tabs.setCurrentIndex(0)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể tạo lớp: {str(e)}")

    def delete_class(self, class_id: int):
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            "Bạn có chắc chắn muốn xóa lớp này cùng toàn bộ dữ liệu liên quan?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db.delete_class(class_id)
                QMessageBox.information(self, "Đã xóa", "Lớp học đã được xóa thành công!")
                self.load_classes()
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể xóa lớp: {str(e)}")

    def delete_student(self, student_id: int):
        class_id = self.cb_classes_filter.currentData()
        if not class_id:
            return
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            "Bạn có chắc muốn xóa sinh viên này khỏi lớp?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db.remove_student_from_class(student_id, class_id)
                self.on_class_filter_changed()
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể xóa sinh viên: {str(e)}")

    def import_from_excel(self):
        class_id = self.cb_classes_filter.currentData()
        if class_id is None:
            QMessageBox.warning(self, "Chưa chọn lớp", "Vui lòng chọn lớp học trước!")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn File Excel Danh Sách Sinh Viên", "", "Excel Files (*.xlsx *.xls)"
        )
        if not file_path:
            return

        try:
            df = pd.read_excel(file_path)
            # Chuẩn hóa tên cột
            df.columns = [str(c).strip().lower() for c in df.columns]
            
            # Tìm các cột cần thiết
            col_code = next((c for c in df.columns if any(k in c for k in ["mssv", "mã sv", "student_code", "ma_sv"])), None)
            col_name = next((c for c in df.columns if any(k in c for k in ["họ tên", "tên", "full_name", "ho_ten"])), None)

            if not col_code or not col_name:
                QMessageBox.warning(
                    self, "Sai cấu trúc file",
                    "File Excel cần có ít nhất 2 cột: 'MSSV' (Mã SV) và 'Họ và Tên'!"
                )
                return

            count = 0
            for _, row in df.iterrows():
                code = str(row[col_code]).strip()
                name = str(row[col_name]).strip()
                if not code or code == "nan" or not name or name == "nan":
                    continue

                db.add_student(
                    student_code=code,
                    full_name=name,
                    class_id=class_id
                )
                count += 1

            QMessageBox.information(self, "Thành Công", f"Đã nhập thành công {count} sinh viên từ file Excel!")
            self.on_class_filter_changed()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi Import", f"Lỗi đọc file Excel: {str(e)}")

    def export_to_excel(self):
        class_id = self.cb_classes_filter.currentData()
        if class_id is None or not hasattr(self, "current_students_data") or not self.current_students_data:
            QMessageBox.warning(self, "Không có dữ liệu", "Không có sinh viên nào để xuất!")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Lưu Danh Sách Sinh Viên", f"Danh_Sach_SV_Lop_{class_id}.xlsx", "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            data = []
            for s in self.current_students_data:
                s_dict = dict(s)
                data.append({
                    "MSSV": s_dict.get("student_code", ""),
                    "Họ và Tên": s_dict.get("full_name", ""),
                    "Mã Vạch / QR": s_dict.get("barcode") or s_dict.get("student_code", ""),
                    "Email": s_dict.get("email", ""),
                    "Số Điện Thoại": s_dict.get("phone", ""),
                    "Đã Đăng Ký AI": "Có" if s_dict.get("registered") else "Chưa"
                })
            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False)
            QMessageBox.information(self, "Thành Công", f"Đã xuất {len(data)} sinh viên ra file:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi Xuất File", f"Không thể lưu file Excel: {str(e)}")
