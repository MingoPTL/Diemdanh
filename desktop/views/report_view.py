"""
desktop/views/report_view.py — Báo Cáo & Thống Kê Điểm Danh
Hỗ trợ:
- Lọc theo Lớp & Buổi điểm danh cụ thể hoặc Báo cáo Tổng hợp toàn kỳ
- Biểu đồ tiến độ / Tỷ lệ Có mặt, Đi muộn, Vắng mặt
- Chỉnh sửa trạng thái điểm danh trực tiếp
- Xuất báo cáo Excel chi tiết từng buổi hoặc Ma trận điểm danh cả khóa
"""
from datetime import datetime
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox, QFileDialog,
    QGridLayout, QGroupBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QColor

import database.db as db
from desktop.theme import COLORS, FONT_FAMILY


class StatMiniCard(QFrame):
    """Mini card hiển thị nhanh số lượng sinh viên theo từng trạng thái."""
    def __init__(self, title: str, value: str, bg_color: str, text_color: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {text_color};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        lbl_title = QLabel(title.upper())
        lbl_title.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {text_color}; background: transparent;")
        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {text_color}; background: transparent;")

        layout.addWidget(lbl_title)
        layout.addWidget(self.lbl_value)

    def set_value(self, val: str):
        self.lbl_value.setText(val)


class ReportView(QWidget):
    """Màn hình Báo Cáo & Xuất File Excel."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.load_classes()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # ── 1. Header ────────────────────────────────────────────────────────
        header_box = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel("📊 Báo Cáo & Thống Kê Điểm Danh")
        lbl_title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {COLORS['text_primary']};")
        lbl_sub = QLabel("Theo dõi lịch sử điểm danh theo từng buổi hoặc tổng hợp toàn bộ học kỳ, xuất file Excel")
        lbl_sub.setStyleSheet(f"font-size: 13px; color: {COLORS['text_secondary']};")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        header_box.addLayout(title_box)
        header_box.addStretch()
        main_layout.addLayout(header_box)

        # ── 2. Thanh lọc (Filter bar) ────────────────────────────────────────
        filter_box = QFrame()
        filter_box.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 12px;
                padding: 12px;
            }}
        """)
        filter_layout = QHBoxLayout(filter_box)
        filter_layout.setContentsMargins(16, 12, 16, 12)
        filter_layout.setSpacing(16)

        lbl_cls = QLabel("🏫 Lớp học:")
        lbl_cls.setStyleSheet("font-weight: 600;")
        self.cb_classes = QComboBox()
        self.cb_classes.setMinimumWidth(260)
        self.cb_classes.currentIndexChanged.connect(self.on_class_changed)
        filter_layout.addWidget(lbl_cls)
        filter_layout.addWidget(self.cb_classes)

        lbl_ses = QLabel("📅 Buổi học:")
        lbl_ses.setStyleSheet("font-weight: 600;")
        self.cb_sessions = QComboBox()
        self.cb_sessions.setMinimumWidth(260)
        self.cb_sessions.currentIndexChanged.connect(self.load_report_data)
        filter_layout.addWidget(lbl_ses)
        filter_layout.addWidget(self.cb_sessions)

        filter_layout.addStretch()

        btn_export_session = QPushButton("📥 Xuất Buổi Này (Excel)")
        btn_export_session.setObjectName("btn_primary")
        btn_export_session.clicked.connect(self.export_session_excel)
        filter_layout.addWidget(btn_export_session)

        btn_export_matrix = QPushButton("📑 Xuất Bảng Ma Trận (Cả kỳ)")
        btn_export_matrix.clicked.connect(self.export_matrix_excel)
        filter_layout.addWidget(btn_export_matrix)

        main_layout.addWidget(filter_box)

        # ── 3. Thẻ thống kê tỷ lệ ─────────────────────────────────────────────
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)

        self.card_total = StatMiniCard("Sĩ Số Lớp", "0", "rgba(59, 130, 246, 0.12)", "#60A5FA")
        self.card_present = StatMiniCard("Có Mặt", "0", "rgba(16, 185, 129, 0.12)", "#34D399")
        self.card_late = StatMiniCard("Đi Muộn", "0", "rgba(245, 158, 11, 0.12)", "#FBBF24")
        self.card_absent = StatMiniCard("Vắng Mặt", "0", "rgba(239, 68, 68, 0.12)", "#F87171")
        self.card_rate = StatMiniCard("Tỷ Lệ Đi Học", "0%", "rgba(139, 92, 246, 0.12)", "#A78BFA")

        stats_layout.addWidget(self.card_total)
        stats_layout.addWidget(self.card_present)
        stats_layout.addWidget(self.card_late)
        stats_layout.addWidget(self.card_absent)
        stats_layout.addWidget(self.card_rate)

        main_layout.addLayout(stats_layout)

        # ── 4. Bảng chi tiết kết quả ──────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "MSSV", "Họ và Tên", "Thời Gian Check-in", "Trạng Thái", "Phương Thức", "Độ Tin Cậy AI", "Đổi Trạng Thái"
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)

        main_layout.addWidget(self.table, 1)

    def load_classes(self):
        """Load danh sách lớp vào dropdown."""
        self.cb_classes.blockSignals(True)
        self.cb_classes.clear()
        try:
            classes = db.get_all_classes()
            if not classes:
                self.cb_classes.addItem("-- Chưa có lớp nào --", None)
            else:
                for c in classes:
                    c_type = dict(c).get("type", "Lý thuyết")
                    label = f"{c['name']} ({c['code']}) - {c_type}"
                    self.cb_classes.addItem(label, c["id"])
        finally:
            self.cb_classes.blockSignals(False)

        self.on_class_changed()

    def on_class_changed(self):
        """Khi đổi lớp, load danh sách các buổi học (sessions)."""
        class_id = self.cb_classes.currentData()
        self.cb_sessions.blockSignals(True)
        self.cb_sessions.clear()

        if class_id is None:
            self.cb_sessions.addItem("-- Không có buổi nào --", None)
            self.cb_sessions.blockSignals(False)
            return

        sessions = db.get_sessions_by_class(class_id)
        if not sessions:
            self.cb_sessions.addItem("-- Lớp chưa có buổi điểm danh nào --", None)
        else:
            for ses in sessions:
                s_dict = dict(ses)
                date_str = s_dict.get("date", "")
                time_str = s_dict.get("start_time", "")
                title_str = s_dict.get("title", "Buổi học")
                title = f"{title_str} ({date_str} {time_str})"
                self.cb_sessions.addItem(title, s_dict["id"])

        self.cb_sessions.blockSignals(False)
        self.load_report_data()

    def load_report_data(self):
        """Tải dữ liệu điểm danh của session đã chọn."""
        class_id = self.cb_classes.currentData()
        session_id = self.cb_sessions.currentData()

        if class_id is None or session_id is None:
            self.table.setRowCount(0)
            self.card_total.set_value("0")
            self.card_present.set_value("0")
            self.card_late.set_value("0")
            self.card_absent.set_value("0")
            self.card_rate.set_value("0%")
            return

        # Lấy tất cả sinh viên trong lớp
        students = db.get_all_students(class_id)
        # Lấy bản ghi điểm danh trong session
        records = db.get_attendance_by_session(session_id)
        records_map = {r["student_id"]: dict(r) for r in records}

        self.report_data = []
        present_cnt = 0
        late_cnt = 0
        absent_cnt = 0

        for s in students:
            sid = s["id"]
            rec = records_map.get(sid)
            if rec:
                status = rec.get("status", "present")
                time_raw = rec.get("timestamp", "")
                # Format time string nếu là ISO
                if "T" in str(time_raw):
                    time_in = str(time_raw).split("T")[1][:8]
                else:
                    time_in = str(time_raw)
                method = rec.get("method", "face")
                conf = rec.get("confidence", 0.0)
                record_id = rec.get("id")
            else:
                status = "absent"
                time_in = "--:--:--"
                method = "—"
                conf = 0.0
                record_id = None

            if status == "present":
                present_cnt += 1
            elif status == "late":
                late_cnt += 1
            else:
                absent_cnt += 1

            self.report_data.append({
                "student_id": sid,
                "record_id": record_id,
                "student_code": s["student_code"],
                "full_name": s["full_name"],
                "time_in": time_in,
                "status": status,
                "method": method,
                "confidence": conf
            })

        total = len(students)
        self.card_total.set_value(str(total))
        self.card_present.set_value(str(present_cnt))
        self.card_late.set_value(str(late_cnt))
        self.card_absent.set_value(str(absent_cnt))
        rate = int(((present_cnt + late_cnt) / total) * 100) if total > 0 else 0
        self.card_rate.set_value(f"{rate}%")

        self.populate_table(self.report_data)

    def populate_table(self, data_list):
        self.table.setRowCount(len(data_list))
        for row, item in enumerate(data_list):
            item_code = QTableWidgetItem(str(item["student_code"]))
            item_name = QTableWidgetItem(str(item["full_name"]))
            item_time = QTableWidgetItem(str(item["time_in"]))
            item_time.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Trạng thái
            st = item["status"]
            if st == "present":
                st_text = "✅ Có Mặt"
                st_color = QColor("#34D399")
            elif st == "late":
                st_text = "🟡 Đi Muộn"
                st_color = QColor("#FBBF24")
            else:
                st_text = "❌ Vắng Mặt"
                st_color = QColor("#F87171")

            item_status = QTableWidgetItem(st_text)
            item_status.setForeground(st_color)
            item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Phương thức
            m = item["method"]
            if m == "face":
                m_text = "👤 Khuôn Mặt"
            elif m == "barcode":
                m_text = "📱 Barcode/QR"
            elif m == "manual":
                m_text = "✍ Thủ Công"
            else:
                m_text = "—"
            item_method = QTableWidgetItem(m_text)
            item_method.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Confidence
            conf = item["confidence"]
            conf_text = f"{conf:.1%}" if conf > 0 else "—"
            item_conf = QTableWidgetItem(conf_text)
            item_conf.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table.setItem(row, 0, item_code)
            self.table.setItem(row, 1, item_name)
            self.table.setItem(row, 2, item_time)
            self.table.setItem(row, 3, item_status)
            self.table.setItem(row, 4, item_method)
            self.table.setItem(row, 5, item_conf)

            # Nút đổi trạng thái
            btn_toggle = QPushButton("Đổi Trạng Thái")
            btn_toggle.clicked.connect(lambda _, it=item: self.toggle_status_dialog(it))
            self.table.setCellWidget(row, 6, btn_toggle)

    def toggle_status_dialog(self, item):
        """Chuyển trạng thái điểm danh: Present -> Late -> Absent -> Present."""
        session_id = self.cb_sessions.currentData()
        if not session_id:
            return

        current_st = item["status"]
        next_status_map = {
            "absent": "present",
            "present": "late",
            "late": "absent"
        }
        new_status = next_status_map.get(current_st, "present")

        try:
            with db.get_conn() as conn:
                existing = conn.execute(
                    "SELECT id FROM attendance_logs WHERE session_id = ? AND student_id = ?",
                    (session_id, item["student_id"])
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE attendance_logs SET status = ?, method = 'manual' WHERE id = ?",
                        (new_status, existing["id"])
                    )
                else:
                    conn.execute(
                        "INSERT INTO attendance_logs (session_id, student_id, timestamp, confidence, status, method) "
                        "VALUES (?, ?, ?, 1.0, ?, 'manual')",
                        (session_id, item["student_id"], datetime.now().isoformat(), new_status)
                    )
            self.load_report_data()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể cập nhật trạng thái: {str(e)}")

    def export_session_excel(self):
        """Xuất danh sách điểm danh buổi học ra file Excel."""
        if not hasattr(self, "report_data") or not self.report_data:
            QMessageBox.warning(self, "Không có dữ liệu", "Không có dữ liệu để xuất Excel!")
            return

        class_label = self.cb_classes.currentText().replace("/", "-")
        session_id = self.cb_sessions.currentData()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Xuất Báo Cáo Buổi Học", f"Diem_Danh_Buoi_{session_id}.xlsx", "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            data = []
            for it in self.report_data:
                data.append({
                    "MSSV": it["student_code"],
                    "Họ và Tên": it["full_name"],
                    "Thời Gian": it["time_in"],
                    "Trạng Thái": "Có Mặt" if it["status"] == "present" else ("Đi Muộn" if it["status"] == "late" else "Vắng Mặt"),
                    "Phương Thức": it["method"],
                    "Độ Tin Cậy AI": f"{it['confidence']:.1%}" if it["confidence"] > 0 else ""
                })
            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False)
            QMessageBox.information(self, "Thành Công", f"Đã xuất file báo cáo buổi học thành công:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi Xuất File", f"Không thể lưu file Excel: {str(e)}")

    def export_matrix_excel(self):
        """Xuất bảng ma trận điểm danh toàn bộ các buổi trong kỳ ra file Excel."""
        class_id = self.cb_classes.currentData()
        if not class_id:
            QMessageBox.warning(self, "Chưa chọn lớp", "Vui lòng chọn lớp học trước!")
            return

        students = db.get_all_students(class_id)
        sessions = db.get_sessions_by_class(class_id)

        if not students or not sessions:
            QMessageBox.warning(self, "Thiếu dữ liệu", "Lớp cần có ít nhất 1 sinh viên và 1 buổi điểm danh để xuất ma trận!")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Xuất Ma Trận Điểm Danh", f"Ma_Tran_Diem_Danh_Lop_{class_id}.xlsx", "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            # Tạo ma trận dataframe
            matrix_data = []
            session_headers = [f"Buổi {idx+1} ({s['date']})" for idx, s in enumerate(sessions)]
            session_ids = [s["id"] for s in sessions]

            # Cache records cho từng session
            session_records = {sid: {r["student_id"]: r["status"] for r in db.get_attendance_by_session(sid)} for sid in session_ids}

            for s in students:
                row = {
                    "MSSV": s["student_code"],
                    "Họ và Tên": s["full_name"]
                }
                present_sum = 0
                for idx, sid in enumerate(session_ids):
                    st = session_records[sid].get(s["id"], "absent")
                    if st == "present":
                        val = "P" # Present
                        present_sum += 1
                    elif st == "late":
                        val = "L" # Late
                        present_sum += 1
                    else:
                        val = "A" # Absent
                    row[session_headers[idx]] = val

                row["Tổng Có Mặt"] = f"{present_sum}/{len(sessions)}"
                row["Tỷ Lệ %"] = f"{(present_sum / len(sessions)):.0%}"
                matrix_data.append(row)

            df = pd.DataFrame(matrix_data)
            df.to_excel(file_path, index=False)
            QMessageBox.information(self, "Thành Công", f"Đã xuất ma trận điểm danh ({len(students)} SV x {len(sessions)} Buổi) ra file:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi Xuất Ma Trận", f"Không thể lưu file Excel: {str(e)}")
