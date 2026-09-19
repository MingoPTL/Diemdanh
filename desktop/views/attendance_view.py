"""
desktop/views/attendance_view.py — Giao diện Điểm Danh đồng nhất 100% với Streamlit
Tự động bật Camera live preview để căn chỉnh góc mặt/thẻ, hỗ trợ cả 3 chế độ:
1. 📹 WebRTC Live Stream (Trực Tiếp 30 FPS Siêu Mượt)
2. 💻 Chụp ảnh tĩnh Webcam (Nhẹ & Nét Nhất - Live Viewfinder + Nút Chụp)
3. 📱 Camera Điện Thoại (IP Camera / Wi-Fi)
"""
from datetime import datetime, timedelta
import cv2
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QComboBox, QLineEdit, QPushButton,
    QTimeEdit, QSpinBox, QProgressBar,
    QRadioButton, QButtonGroup, QCheckBox, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox, QStackedWidget
)
from PyQt6.QtCore import Qt, QTime, pyqtSlot, QTimer
from PyQt6.QtGui import QColor, QFont, QCursor, QImage, QPixmap
from PyQt6.QtWidgets import QScrollArea

import database.db as db
from core.pipeline import pipeline
from services.attendance import attendance_service
from services.face_db import face_db
from services.barcode_scanner import barcode_scanner
from desktop.theme import COLORS, FONT_SIZE_SM, FONT_SIZE_MD, FONT_SIZE_LG, FONT_SIZE_XL
from desktop.widgets.camera_widget import CameraWidget
from desktop.workers.camera_worker import CameraWorker
from desktop.workers.ai_worker import AIWorker, AIResult


class AttendanceView(QWidget):
    """Màn hình Điểm Danh chuẩn giao diện Streamlit."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._camera_worker: CameraWorker = None
        self._ai_worker: AIWorker = None
        self._is_session_active = False
        self._is_snapshot_frozen = False
        self._class_map = {}
        self._current_raw_frame = None
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_attendance_table)
        self._init_ui()

        # Tự động kích hoạt Camera Live Preview ngay khi mở để người dùng căn chỉnh
        QTimer.singleShot(200, self._auto_start_camera)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(12)

        # ── 1. Thanh điều khiển buổi học (Top Bar) ───────────────────────────
        control_panel = self._create_control_panel()
        main_layout.addWidget(control_panel)

        # ── 2. Banner trạng thái buổi học ────────────────────────────────────
        self._status_banner = QLabel("⏸ Chưa có buổi điểm danh nào đang mở. Thiết lập thông số và nhấn ▶ Bắt đầu.")
        self._status_banner.setWordWrap(True)
        self._status_banner.setStyleSheet(f"""
            background-color: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['border']};
            border-radius: 10px;
            padding: 10px 16px;
            color: {COLORS['text_secondary']};
            font-size: {FONT_SIZE_MD}px;
        """)
        main_layout.addWidget(self._status_banner)

        # ── 3. Vùng chính: Trái = Camera View & Chế Độ | Phải = Danh Sách Điểm Danh
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(3)

        cam_panel = self._create_camera_panel()
        splitter.addWidget(cam_panel)

        log_panel = self._create_log_panel()
        splitter.addWidget(log_panel)

        splitter.setSizes([750, 420])
        main_layout.addWidget(splitter, 1)

    # ──────────────────────────────────────────────────────────────────────────
    # CONTROL PANEL
    # ──────────────────────────────────────────────────────────────────────────
    def _create_control_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        lbl_class = QLabel("🏫 Lớp:")
        lbl_class.setStyleSheet("border: none; font-weight: 600;")
        self._combo_class = QComboBox()
        self._combo_class.setMinimumWidth(240)
        self.load_classes()

        lbl_session = QLabel("📝 Buổi:")
        lbl_session.setStyleSheet("border: none; font-weight: 600;")
        self._txt_session = QLineEdit()
        self._txt_session.setPlaceholderText("VD: Buổi 1 - Điểm danh")
        self._txt_session.setMinimumWidth(160)

        lbl_time = QLabel("⏰")
        lbl_time.setStyleSheet("border: none;")
        self._time_start = QTimeEdit()
        self._time_start.setDisplayFormat("HH:mm")
        self._time_start.setTime(QTime.currentTime())

        lbl_late = QLabel("⏱ Mốc trễ:")
        lbl_late.setStyleSheet("border: none; font-weight: 600;")
        self._spin_late = QSpinBox()
        self._spin_late.setRange(0, 120)
        self._spin_late.setValue(15)
        self._spin_late.setSuffix(" phút")

        self._btn_start = QPushButton("▶ Bắt đầu")
        self._btn_start.setObjectName("btn_success")
        self._btn_start.setMinimumWidth(100)
        self._btn_start.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_start.clicked.connect(self._on_start_session)

        self._btn_stop = QPushButton("⏹ Kết thúc")
        self._btn_stop.setObjectName("btn_danger")
        self._btn_stop.setMinimumWidth(100)
        self._btn_stop.setEnabled(False)
        self._btn_stop.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_stop.clicked.connect(self._on_stop_session)

        layout.addWidget(lbl_class)
        layout.addWidget(self._combo_class)
        layout.addWidget(lbl_session)
        layout.addWidget(self._txt_session)
        layout.addWidget(lbl_time)
        layout.addWidget(self._time_start)
        layout.addWidget(lbl_late)
        layout.addWidget(self._spin_late)
        layout.addWidget(self._btn_start)
        layout.addWidget(self._btn_stop)

        return panel

    # ──────────────────────────────────────────────────────────────────────────
    # CAMERA PANEL (Y CHANG 100% GIAO DIỆN STREAMLIT)
    # ──────────────────────────────────────────────────────────────────────────
    def _create_camera_panel(self) -> QWidget:
        # Outer wrapper with scroll
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(8)

        # ── Tiêu đề section ───────────────────────────────────────────────────
        lbl_sec_title = QLabel("🎥 Nguồn Camera & Chế Độ Quét")
        lbl_sec_title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {COLORS['text_primary']};")
        layout.addWidget(lbl_sec_title)

        # ── Hàng 1: Chế độ quét & Lật gương ──────────────────────────────────
        row_mode = QHBoxLayout()
        row_mode.setSpacing(10)

        lbl_scan = QLabel("🎯 Chế độ quét điểm danh:")
        lbl_scan.setStyleSheet("font-weight: 600; color: #F8FAFC;")
        self._combo_mode = QComboBox()
        self._combo_mode.addItems([
            "🚀 Quét Kép (Khuôn mặt AI + Mã vạch / QR)",
            "👤 Chỉ nhận diện Khuôn mặt AI",
            "🏷️ Chỉ quét Mã vạch / QR Code MSSV"
        ])
        self._combo_mode.currentIndexChanged.connect(self._on_mode_changed)

        self._chk_mirror = QCheckBox("🪞 Lật gương Camera (Mirror)")
        self._chk_mirror.setChecked(False)
        self._chk_mirror.toggled.connect(self._on_mirror_toggled)

        row_mode.addWidget(lbl_scan)
        row_mode.addWidget(self._combo_mode, 1)
        row_mode.addWidget(self._chk_mirror)
        layout.addLayout(row_mode)

        # ── Hàng 2: Chọn nguồn Video (Radio buttons) ──────────────────────────
        lbl_src_title = QLabel("📹 Chọn nguồn Video:")
        lbl_src_title.setStyleSheet("font-weight: 600; color: #F8FAFC; margin-top: 4px;")
        layout.addWidget(lbl_src_title)

        radio_box = QHBoxLayout()
        radio_box.setSpacing(14)
        self.radio_group = QButtonGroup(self)

        self.rb_live = QRadioButton("📹 WebRTC Live Stream (Trực Tiếp 30 FPS Siêu Mượt)")
        self.rb_static = QRadioButton("💻 Chụp ảnh tĩnh Webcam (Nhẹ & Nét Nhất)")
        self.rb_ip = QRadioButton("📱 Camera Điện Thoại (IP Camera / Wi-Fi)")

        # Mặc định chọn Chế độ Live Stream hoặc Tĩnh
        self.rb_live.setChecked(True)
        self.radio_group.addButton(self.rb_live, 0)
        self.radio_group.addButton(self.rb_static, 1)
        self.radio_group.addButton(self.rb_ip, 2)
        self.radio_group.idClicked.connect(self._on_source_radio_changed)

        radio_box.addWidget(self.rb_live)
        radio_box.addWidget(self.rb_static)
        radio_box.addWidget(self.rb_ip)
        radio_box.addStretch()
        layout.addLayout(radio_box)

        # ── Controls phụ theo từng nguồn (IP guide, nút chụp...) ─────────────
        self.stack_controls = QStackedWidget()

        # Page 0: Live Stream controls
        page_live = QWidget()
        l_layout = QHBoxLayout(page_live)
        l_layout.setContentsMargins(0, 4, 0, 4)
        self.lbl_live_hint = QLabel("💡 Đưa mặt hoặc giơ thẻ sinh viên trước Camera để hệ thống tự động nhận diện liên tục.")
        self.lbl_live_hint.setStyleSheet("color: #94A3B8; font-size: 12px;")
        self._btn_restart_cam = QPushButton("🔄 Khởi động lại Cam")
        self._btn_restart_cam.clicked.connect(self._restart_camera)
        l_layout.addWidget(self.lbl_live_hint, 1)
        l_layout.addWidget(self._btn_restart_cam)
        self.stack_controls.addWidget(page_live)

        # Page 1: Static mode controls
        page_static = QWidget()
        s_layout = QVBoxLayout(page_static)
        s_layout.setContentsMargins(0, 4, 0, 4)
        s_layout.setSpacing(6)
        
        lbl_static_hint = QLabel("Đưa mặt hoặc giơ thẻ sinh viên trước Camera rồi bấm chụp")
        lbl_static_hint.setStyleSheet("font-size: 13px; color: #E2E8F0; font-weight: 500;")
        
        s_btn_row = QHBoxLayout()
        self.btn_snap = QPushButton("📸 Bấm Chụp & Điểm Danh (Snapshot)")
        self.btn_snap.setObjectName("btn_success")
        self.btn_snap.setMinimumHeight(38)
        self.btn_snap.setStyleSheet("font-size: 13px; font-weight: 700;")
        self.btn_snap.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_snap.clicked.connect(self._process_snapshot)

        btn_upload = QPushButton("📁 Tải Ảnh Lên Từ Máy Tính...")
        btn_upload.setMinimumHeight(38)
        btn_upload.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_upload.clicked.connect(self._upload_image_file)

        s_btn_row.addWidget(self.btn_snap, 2)
        s_btn_row.addWidget(btn_upload, 1)

        s_layout.addWidget(lbl_static_hint)
        s_layout.addLayout(s_btn_row)
        self.stack_controls.addWidget(page_static)

        # Page 2: IP Camera controls
        page_ip = QWidget()
        ip_layout = QVBoxLayout(page_ip)
        ip_layout.setContentsMargins(0, 4, 0, 4)
        ip_layout.setSpacing(6)

        lbl_ip_guide = QLabel(
            "📱 <b>Hướng dẫn dùng Camera Điện Thoại:</b><br/>"
            "1. Cài app <b>IP Webcam</b> (Android) hoặc <b>DroidCam / Iriun</b> trên điện thoại.<br/>"
            "2. Kết nối điện thoại và máy tính cùng mạng Wi-Fi.<br/>"
            "3. Mở app và bấm <i>Start Server</i> → Nhập URL video hiển thị trên điện thoại vào ô dưới."
        )
        lbl_ip_guide.setStyleSheet("""
            background-color: rgba(16, 185, 129, 0.12);
            border-left: 4px solid #10B981;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
        """)
        ip_layout.addWidget(lbl_ip_guide)

        ip_in_row = QHBoxLayout()
        ip_in_row.addWidget(QLabel("🔗 URL Luồng IP Camera:"))
        self._txt_ip_url = QLineEdit("http://192.168.1.50:8080/video")
        self._txt_ip_url.setPlaceholderText("VD: http://192.168.1.15:8080/video hoặc http://192.168.1.15:4747/video")
        ip_in_row.addWidget(self._txt_ip_url, 1)

        self._combo_ip_preset = QComboBox()
        self._combo_ip_preset.addItems(["Gợi ý: IP Webcam (:8080)", "Gợi ý: DroidCam (:4747)", "Gợi ý: RTSP (:554)"])
        self._combo_ip_preset.currentIndexChanged.connect(self._apply_ip_preset)
        ip_in_row.addWidget(self._combo_ip_preset)
        ip_layout.addLayout(ip_in_row)

        ip_btn_row = QHBoxLayout()
        btn_ip_snap = QPushButton("📸 Quét 1 Khung Hình từ IP Cam")
        btn_ip_snap.clicked.connect(self._capture_ip_snapshot)
        ip_btn_row.addWidget(btn_ip_snap)

        self._btn_ip_live = QPushButton("▶ Bật Luồng Live Stream IP Cam")
        self._btn_ip_live.setObjectName("btn_primary")
        self._btn_ip_live.clicked.connect(self._toggle_ip_live)
        ip_btn_row.addWidget(self._btn_ip_live)
        ip_layout.addLayout(ip_btn_row)

        self.stack_controls.addWidget(page_ip)
        layout.addWidget(self.stack_controls)

        # ── Camera Viewport Display (Luôn hiển thị live để căn chỉnh) ──────────
        self._camera_widget = CameraWidget()
        layout.addWidget(self._camera_widget, 1)

        # ── Khung hiển thị kết quả quét Snapshot (ẩn/hiện) ────────────────────
        self._static_result_box = QLabel("")
        self._static_result_box.setVisible(False)
        self._static_result_box.setWordWrap(True)
        layout.addWidget(self._static_result_box)

        scroll.setWidget(panel)
        outer_layout.addWidget(scroll)
        return outer

    # ──────────────────────────────────────────────────────────────────────────
    # LOG PANEL (Danh sách điểm danh bên phải)
    # ──────────────────────────────────────────────────────────────────────────
    def _create_log_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 0, 0, 0)
        layout.setSpacing(8)

        header = QLabel("📋 Danh Sách Điểm Danh Buổi Này")
        header.setStyleSheet("font-size: 16px; font-weight: 700; color: #F8FAFC;")
        layout.addWidget(header)

        self.lbl_session_hint = QLabel("Bắt đầu buổi học ở trên để xem danh sách điểm danh.")
        self.lbl_session_hint.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(self.lbl_session_hint)

        # Thống kê
        stats_layout = QHBoxLayout()
        self._lbl_present = QLabel("✅ Có mặt: 0")
        self._lbl_present.setStyleSheet(f"color: {COLORS['green_light']}; font-weight: 600; font-size: {FONT_SIZE_SM}px;")
        self._lbl_late = QLabel("⚠ Trễ: 0")
        self._lbl_late.setStyleSheet(f"color: {COLORS['yellow_light']}; font-weight: 600; font-size: {FONT_SIZE_SM}px;")
        self._lbl_total = QLabel("👥 Tổng: 0")
        self._lbl_total.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: 600; font-size: {FONT_SIZE_SM}px;")

        stats_layout.addWidget(self._lbl_present)
        stats_layout.addWidget(self._lbl_late)
        stats_layout.addWidget(self._lbl_total)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setValue(0)
        self._progress.setFormat("%v/%m sinh viên (%p%)")
        self._progress.setMinimumHeight(20)
        layout.addWidget(self._progress)

        # Bảng kết quả điểm danh
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["MSSV", "Họ và Tên", "Giờ", "Phương thức", "Trạng thái"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table, 1)

        self._btn_refresh = QPushButton("🔄 Cập nhật danh sách điểm danh")
        self._btn_refresh.clicked.connect(self._refresh_attendance_table)
        layout.addWidget(self._btn_refresh)

        return panel

    # ──────────────────────────────────────────────────────────────────────────
    # CAMERA LIFECYCLE & AUTOMATIC START
    # ──────────────────────────────────────────────────────────────────────────
    def _auto_start_camera(self):
        """Tự động khởi động camera live preview ngay khi mở app."""
        self._start_camera_stream(source=0)

    def _restart_camera(self):
        self._start_camera_stream(source=0)

    def _start_camera_stream(self, source):
        self._stop_camera_stream()

        # Load models
        if not pipeline.is_loaded:
            try:
                pipeline.load()
            except Exception as e:
                print(f"[AttendanceView] Lỗi load AI: {e}")

        # Khởi tạo Camera Worker
        self._camera_worker = CameraWorker(source=source)
        self._camera_worker.set_mirror(self._chk_mirror.isChecked())
        self._camera_worker.frame_ready.connect(self._on_frame_ready)
        self._camera_worker.fps_updated.connect(self._camera_widget.update_fps)
        self._camera_worker.error_occurred.connect(self._on_camera_error)
        self._camera_worker.start()

        # Khởi tạo AI Worker
        self._ai_worker = AIWorker()
        self._update_scan_mode()
        self._ai_worker.results_ready.connect(self._on_ai_results)
        self._ai_worker.processing_time.connect(self._camera_widget.update_ai_time)
        self._ai_worker.attendance_logged.connect(self._on_attendance_logged)
        self._ai_worker.start()

    def _stop_camera_stream(self):
        if self._camera_worker:
            self._camera_worker.stop()
            self._camera_worker.wait(1500)
            self._camera_worker = None

        if self._ai_worker:
            self._ai_worker.stop()
            self._ai_worker.wait(1500)
            self._ai_worker = None

    def _on_source_radio_changed(self, idx: int):
        self.stack_controls.setCurrentIndex(idx)
        self._is_snapshot_frozen = False
        self.btn_snap.setText("📸 Bấm Chụp & Điểm Danh (Snapshot)")
        self._static_result_box.setVisible(False)

        if idx in [0, 1]:
            # Đảm bảo webcam live đang chạy để preview căn chỉnh
            if self._camera_worker is None or not self._camera_worker.isRunning() or self._camera_worker._use_ip:
                self._start_camera_stream(source=0)
        elif idx == 2:
            # IP Cam
            self._stop_camera_stream()
            self._camera_widget.show_placeholder("📱 Nhập URL IP Camera và bấm '▶ Bật Luồng Live Stream'")

    def _on_mirror_toggled(self, checked: bool):
        if self._camera_worker:
            self._camera_worker.set_mirror(checked)

    def _on_mode_changed(self, index: int):
        self._update_scan_mode()

    def _update_scan_mode(self):
        if self._ai_worker is None:
            return
        mode = self._combo_mode.currentIndex()
        if mode == 0:  # Quét kép
            self._ai_worker.set_settings(enable_face=True, enable_barcode=True)
        elif mode == 1:  # Chỉ Face
            self._ai_worker.set_settings(enable_face=True, enable_barcode=False)
        else:  # Chỉ Barcode
            self._ai_worker.set_settings(enable_face=False, enable_barcode=True)

    def _normalize_ip_url(self, raw_url: str) -> str:
        url = raw_url.strip()
        if not url:
            return ""
        if not (url.startswith("http://") or url.startswith("https://") or url.startswith("rtsp://")):
            url = f"http://{url}"
        # Tự động thêm /video nếu người dùng chỉ nhập IP và port ví dụ http://192.168.1.15:8080
        if url.startswith("http://") or url.startswith("https://"):
            parts = url.split("://", 1)[1].split("/")
            if len(parts) == 1 and ":" in parts[0]:
                url = url.rstrip("/") + "/video"
        return url

    def _apply_ip_preset(self, index: int):
        cur_text = self._txt_ip_url.text().strip()
        import re
        m = re.search(r"https?://([^:/]+)", cur_text)
        host = m.group(1) if m else "192.168.1.50"
        if index == 0:
            self._txt_ip_url.setText(f"http://{host}:8080/video")
        elif index == 1:
            self._txt_ip_url.setText(f"http://{host}:4747/video")
        elif index == 2:
            self._txt_ip_url.setText(f"rtsp://{host}:554/live/ch0")

    def _toggle_ip_live(self):
        if self._camera_worker and self._camera_worker.isRunning() and self._camera_worker._use_ip:
            self._stop_camera_stream()
            self._btn_ip_live.setText("▶ Bật Luồng Live Stream IP Cam")
            self._btn_ip_live.setObjectName("btn_primary")
            self._btn_ip_live.style().unpolish(self._btn_ip_live)
            self._btn_ip_live.style().polish(self._btn_ip_live)
        else:
            url = self._normalize_ip_url(self._txt_ip_url.text())
            if not url:
                QMessageBox.warning(self, "Thiếu URL", "Vui lòng nhập URL IP Camera!")
                return
            self._start_camera_stream(source=url)
            self._btn_ip_live.setText("⏹ Dừng Luồng Live Stream")
            self._btn_ip_live.setObjectName("btn_danger")
            self._btn_ip_live.style().unpolish(self._btn_ip_live)
            self._btn_ip_live.style().polish(self._btn_ip_live)

    # ──────────────────────────────────────────────────────────────────────────
    # FRAME READY & AI RESULTS
    # ──────────────────────────────────────────────────────────────────────────
    def _on_frame_ready(self, q_image, raw_frame):
        self._current_raw_frame = raw_frame
        # Nếu đang xem ảnh tĩnh đóng băng thì không đè video live
        if not self._is_snapshot_frozen:
            self._camera_widget.update_frame(q_image, raw_frame)
            if self._ai_worker:
                self._ai_worker.submit_frame(raw_frame)

    def _on_ai_results(self, result: AIResult):
        # Nếu đang ở chế độ Live Stream -> vẽ overlay real-time
        if self.stack_controls.currentIndex() == 0 or (self.stack_controls.currentIndex() == 2 and self._camera_worker and self._camera_worker.isRunning()):
            self._camera_widget.update_ai_results(result.faces, result.barcodes)

    @pyqtSlot(str)
    def _on_camera_error(self, error_msg: str):
        self._camera_widget.show_placeholder(f"❌ {error_msg}")
        self._stop_camera_stream()
        if hasattr(self, "_btn_ip_live"):
            self._btn_ip_live.setText("▶ Bật Luồng Live Stream IP Cam")
            self._btn_ip_live.setObjectName("btn_primary")
            self._btn_ip_live.style().unpolish(self._btn_ip_live)
            self._btn_ip_live.style().polish(self._btn_ip_live)

    @pyqtSlot(str, str, str, str)
    def _on_attendance_logged(self, name: str, mssv: str, status: str, method: str):
        self._refresh_attendance_table()

    # ──────────────────────────────────────────────────────────────────────────
    # SNAPSHOT & STATIC SCAN (Y CHANG STREAMLIT)
    # ──────────────────────────────────────────────────────────────────────────
    def _process_snapshot(self):
        """Bấm chụp frame hiện tại từ video viewfinder đang chạy."""
        if self._is_snapshot_frozen:
            # Mở lại viewfinder camera trực tiếp
            self._is_snapshot_frozen = False
            self.btn_snap.setText("📸 Bấm Chụp & Điểm Danh (Snapshot)")
            self._static_result_box.setVisible(False)
            return

        if self._current_raw_frame is None:
            QMessageBox.warning(self, "Camera chưa sẵn sàng", "Vui lòng chờ camera bật lên để căn chỉnh góc rồi bấm chụp!")
            return

        frame_to_process = self._current_raw_frame.copy()
        self._is_snapshot_frozen = True
        self.btn_snap.setText("🔄 Chụp Tiếp / Xem Trực Tiếp")
        self._analyze_and_report_frame(frame_to_process, source_name="Ảnh Chụp Webcam")

    def _upload_image_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn File Ảnh Điểm Danh", "", "Image Files (*.jpg *.jpeg *.png *.bmp *.webp)"
        )
        if not file_path:
            return
        img = cv2.imread(file_path)
        if img is None:
            QMessageBox.critical(self, "Lỗi", "Không thể đọc file ảnh đã chọn!")
            return
        self._is_snapshot_frozen = True
        self.btn_snap.setText("🔄 Chụp Tiếp / Xem Trực Tiếp")
        self._analyze_and_report_frame(img, source_name="File Ảnh Tải Lên")

    def _capture_ip_snapshot(self):
        url = self._normalize_ip_url(self._txt_ip_url.text())
        if not url:
            QMessageBox.warning(self, "Thiếu URL", "Vui lòng nhập URL IP Camera!")
            return

        cap = cv2.VideoCapture(url)
        if not cap.isOpened():
            QMessageBox.critical(self, "Lỗi Kết Nối", f"❌ Không thể kết nối tới URL: {url}\nHãy kiểm tra Wi-Fi và IP trên điện thoại.")
            return

        ret, frame = cap.read()
        cap.release()

        if ret and frame is not None:
            self._is_snapshot_frozen = True
            self._analyze_and_report_frame(frame, source_name="Khung Hình IP Camera")
        else:
            QMessageBox.warning(self, "Lỗi", "Không thể đọc khung hình từ IP Camera!")

    def _analyze_and_report_frame(self, img: np.ndarray, source_name: str = ""):
        """Xử lý phân tích và hiển thị kết quả y chang Streamlit."""
        if not pipeline.is_loaded:
            pipeline.load()

        mode = self._combo_mode.currentIndex()
        enable_face = (mode in [0, 1])
        enable_barcode = (mode in [0, 2])

        if self._chk_mirror.isChecked():
            img = cv2.flip(img, 1)

        detected_faces = []
        detected_barcodes = []
        report_lines = []

        # 1. Barcode scan
        if enable_barcode:
            b_results = barcode_scanner.scan(img, try_mirror=True)
            for b in b_results:
                mssv = b.text.strip()
                is_valid = False
                label = f"MSSV: {mssv}"
                if attendance_service.is_active:
                    success, st_info, _ = attendance_service.mark_attendance_by_code(mssv, method="barcode")
                    is_valid = success
                    if st_info:
                        label = f"🏷️ {st_info['full_name']} ({mssv})"
                        report_lines.append(f"🏷️ <b>Mã Vạch ({b.format_name}):</b> <code>{mssv}</code> ➔ <b>{st_info['full_name']}</b> (✅ Điểm danh thành công)")
                    else:
                        report_lines.append(f"⚠️ <b>Mã Vạch:</b> <code>{mssv}</code> ➔ <i>Không tìm thấy trong lớp này</i>")
                else:
                    report_lines.append(f"🏷️ <b>Mã Vạch ({b.format_name}):</b> <code>{mssv}</code>")
                detected_barcodes.append((b.points, label, is_valid, mssv))

        # 2. Face AI scan
        if enable_face and pipeline.is_loaded:
            f_results = pipeline.process_frame(img, face_db)
            for res in f_results:
                if res.student_id and attendance_service.is_active:
                    attendance_service.mark_attendance(res.student_id, res.confidence, method="face")
                    report_lines.append(f"👤 <b>Khuôn Mặt AI:</b> <b>{res.name}</b> (Độ tin cậy: {res.confidence*100:.1f}%)")
                else:
                    report_lines.append(f"👤 <b>Khuôn Mặt AI:</b> {res.name} ({res.confidence*100:.1f}%)")
                detected_faces.append((res.bbox, res.name, res.confidence, res.student_id))

        # Cập nhật hiển thị lên viewport
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        q_img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
        self._camera_widget.update_ai_results(detected_faces, detected_barcodes)
        self._camera_widget.update_frame(q_img, img)

        self._refresh_attendance_table()

        # Hiển thị thông báo chi tiết bên dưới
        if not detected_faces and not detected_barcodes:
            self._static_result_box.setText("⚠️ <b>Không phát hiện khuôn mặt hoặc mã vạch nào trong ảnh chụp.</b> Hãy đảm bảo thẻ thẳng và đủ ánh sáng.")
            self._static_result_box.setStyleSheet("background-color: rgba(245, 158, 11, 0.15); border: 1px solid #F59E0B; padding: 10px; border-radius: 8px; color: #FBBF24;")
        else:
            session_notice = ""
            if not attendance_service.is_active:
                session_notice = "<br/><span style='color: #F87171; font-weight: 600;'>⚠️ Chưa mở buổi học! Hãy nhấn ▶ Bắt đầu ở trên để lưu kết quả điểm danh vào danh sách.</span>"
            res_html = f"🎉 <b>Kết quả nhận diện ({source_name}):</b><br/>" + "<br/>".join(report_lines) + session_notice
            self._static_result_box.setText(res_html)
            self._static_result_box.setStyleSheet("background-color: rgba(16, 185, 129, 0.15); border: 1px solid #10B981; padding: 10px; border-radius: 8px; color: #34D399;")

        self._static_result_box.setVisible(True)

    # ──────────────────────────────────────────────────────────────────────────
    # SESSION CONTROL & DATABASE
    # ──────────────────────────────────────────────────────────────────────────
    def load_classes(self):
        self._combo_class.clear()
        classes = db.get_all_classes()
        self._class_map = {}
        for c in classes:
            c_type = dict(c).get("type", "Lý thuyết")
            label = f"{c['name']} - {c_type} ({c['code']})"
            self._combo_class.addItem(label)
            self._class_map[label] = dict(c)

    def _on_start_session(self):
        label = self._combo_class.currentText()
        if label not in self._class_map:
            self._status_banner.setText("⚠ Chưa chọn lớp học!")
            return

        session_title = self._txt_session.text().strip()
        if not session_title:
            self._status_banner.setText("⚠ Vui lòng nhập tên buổi học!")
            return

        cls = self._class_map[label]
        class_id = cls["id"]
        class_type = dict(cls).get("type", "Lý thuyết")

        start_time = self._time_start.time().toString("HH:mm")
        grace_mins = self._spin_late.value()

        dt_start = datetime.strptime(start_time, "%H:%M")
        dt_late = dt_start + timedelta(minutes=grace_mins)
        late_time = dt_late.strftime("%H:%M")

        if not pipeline.is_loaded:
            self._status_banner.setText("⏳ Đang nạp AI Models (SCRFD + ArcFace)...")
            self._status_banner.repaint()
            try:
                pipeline.load()
            except Exception as e:
                self._status_banner.setText(f"❌ Lỗi load model: {e}")
                return

        students = db.get_all_students(class_id)
        face_db.load_all(students)

        attendance_service.start_session(
            class_id=class_id,
            title=session_title,
            start_time=start_time,
            late_time=late_time,
            session_type=class_type,
        )

        self._is_session_active = True
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._combo_class.setEnabled(False)
        self._txt_session.setEnabled(False)
        self.lbl_session_hint.setVisible(False)

        total_students = len(students)
        self._progress.setMaximum(max(total_students, 1))
        self._progress.setValue(0)
        self._lbl_total.setText(f"👥 Tổng: {total_students}")

        self._status_banner.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {COLORS['bg_secondary']}, stop:1 rgba(16, 185, 129, 0.12));
            border: 1px solid {COLORS['present_border']};
            border-radius: 12px;
            padding: 12px 18px;
            color: {COLORS['text_primary']};
            font-size: {FONT_SIZE_MD}px;
        """)
        self._status_banner.setText(
            f"🟢 Đang điểm danh ({class_type}) · Lớp: {cls['name']} · "
            f"Buổi: {session_title} · ⏰ {start_time} · ⏱ Mốc trễ: {late_time}"
        )

        self._refresh_timer.start(2000)

    def _on_stop_session(self):
        if not self._is_session_active:
            return

        stats = attendance_service.stop_session()
        self._is_session_active = False
        self._refresh_timer.stop()

        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._combo_class.setEnabled(True)
        self._txt_session.setEnabled(True)
        self.lbl_session_hint.setVisible(True)

        self._status_banner.setStyleSheet(f"""
            background-color: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['blue']};
            border-radius: 12px;
            padding: 12px 18px;
            color: {COLORS['text_primary']};
            font-size: {FONT_SIZE_MD}px;
        """)
        self._status_banner.setText(
            f"🎉 Đã kết thúc buổi! "
            f"✅ Có mặt: {stats.get('present', 0)} · "
            f"⚠ Trễ: {stats.get('late', 0)} · "
            f"❌ Vắng: {stats.get('absent', 0)}"
        )

        self._refresh_attendance_table()

    def _refresh_attendance_table(self):
        if not self._is_session_active or attendance_service.session_id is None:
            return

        session_id = attendance_service.session_id
        records = db.get_attendance_by_session(session_id)

        present_count = sum(1 for r in records if r["status"] == "present")
        late_count = sum(1 for r in records if r["status"] == "late")
        self._lbl_present.setText(f"✅ Có mặt: {present_count}")
        self._lbl_late.setText(f"⚠ Trễ: {late_count}")
        total_attended = present_count + late_count
        self._progress.setValue(total_attended)

        self._table.setRowCount(len(records))
        for row, r in enumerate(records):
            r_dict = dict(r)
            mssv = r_dict.get("student_code", "")
            name = r_dict.get("full_name", "")
            time_raw = r_dict.get("timestamp", "")
            if "T" in str(time_raw):
                timestamp = str(time_raw).split("T")[1][:8]
            else:
                timestamp = str(time_raw)

            method = r_dict.get("method", "face")
            status = r_dict.get("status", "")

            item_mssv = QTableWidgetItem(mssv)
            item_name = QTableWidgetItem(name)
            item_time = QTableWidgetItem(timestamp)
            item_method = QTableWidgetItem("👤 Face" if method == "face" else ("📱 Barcode" if method == "barcode" else "✍ Thủ công"))
            item_status = QTableWidgetItem("✅ Có mặt" if status == "present" else ("⚠ Trễ" if status == "late" else "❌ Vắng"))

            item_mssv.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_time.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_method.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            if status == "present":
                item_status.setForeground(QColor(COLORS["green_light"]))
            elif status == "late":
                item_status.setForeground(QColor(COLORS["yellow_light"]))
            else:
                item_status.setForeground(QColor(COLORS["red_light"]))

            self._table.setItem(row, 0, item_mssv)
            self._table.setItem(row, 1, item_name)
            self._table.setItem(row, 2, item_time)
            self._table.setItem(row, 3, item_method)
            self._table.setItem(row, 4, item_status)

    def closeEvent(self, event):
        self._stop_camera_stream()
        super().closeEvent(event)
