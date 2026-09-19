"""
desktop/views/registration_view.py — Giao diện Đăng Ký Khuôn Mặt Sinh Viên
Hỗ trợ:
- 📹 Webcam trực tiếp hoặc 📱 IP Camera điện thoại
- 📁 Tải nhiều ảnh mẫu có sẵn từ máy tính
- Tự động căn chỉnh (align) & trích xuất vector embedding lưu vào Database + cập nhật FaceDB tức thì
"""
import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QProgressBar, QMessageBox, QGroupBox,
    QGridLayout, QScrollArea, QSplitter, QFileDialog, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSlot, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QCursor

import database.db as db
from core.pipeline import pipeline
from core.aligner import align_face, crop_face
from services.face_db import face_db
from utils.helpers import save_photo
from utils.config import REGISTER_SAMPLES
from desktop.workers.camera_worker import CameraWorker
from desktop.theme import COLORS, FONT_FAMILY


class EmbeddingExtractionWorker(QThread):
    """Worker chạy trích xuất Embedding dưới background thread để UI không bị đơ."""
    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal(bool, str) # success, message

    def __init__(self, student_id: int, student_code: str, images_list: list):
        super().__init__()
        self.student_id = student_id
        self.student_code = student_code
        self.images_list = images_list

    def run(self):
        try:
            if not pipeline.is_loaded:
                pipeline.load()

            embeddings = []
            total = len(self.images_list)
            for idx, img in enumerate(self.images_list):
                faces = pipeline.detect(img)
                if not faces:
                    continue
                # Lấy mặt lớn nhất
                largest_face = max(
                    faces,
                    key=lambda f: (f["bbox"][2] - f["bbox"][0]) * (f["bbox"][3] - f["bbox"][1])
                )
                aligned = align_face(img, largest_face["kps"])
                emb = pipeline.get_embedding(aligned)
                embeddings.append(emb)
                self.progress.emit(idx + 1, total)

            if not embeddings:
                self.finished.emit(False, "Không thể phát hiện khuôn mặt rõ nét trong các ảnh đã chọn!")
                return

            # Lưu ảnh mẫu chính làm avatar
            best_img = self.images_list[0]
            save_photo(best_img, self.student_code)

            # Lưu vào DB
            db.save_embeddings(self.student_id, embeddings)

            # Nạp ngay vào RAM face_db
            student = db.get_student_by_id(self.student_id)
            if student:
                face_db.add_student(student, embeddings)

            self.finished.emit(True, f"Đăng ký thành công {len(embeddings)} mẫu khuôn mặt cho sinh viên!")
        except Exception as e:
            self.finished.emit(False, f"Lỗi trong quá trình trích xuất đặc trưng: {str(e)}")


class RegistrationView(QWidget):
    """Màn hình đăng ký khuôn mặt với Camera và AI Extraction."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.captured_images = []
        self.camera_worker = None
        self.current_frame = None
        self.selected_student = None
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
        lbl_title = QLabel("👤 Đăng Ký Khuôn Mặt Sinh Viên")
        lbl_title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {COLORS['text_primary']};")
        lbl_sub = QLabel(f"Chụp {REGISTER_SAMPLES} góc mặt khác nhau hoặc tải ảnh từ máy tính để AI trích xuất vector đặc trưng")
        lbl_sub.setStyleSheet(f"font-size: 13px; color: {COLORS['text_secondary']};")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        header_box.addLayout(title_box)
        header_box.addStretch()

        main_layout.addLayout(header_box)

        # ── 2. Bộ lọc & Chọn sinh viên ──────────────────────────────────────
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

        # Lớp học
        lbl_cls = QLabel("🏫 Lớp:")
        lbl_cls.setStyleSheet("font-weight: 600;")
        self.cb_classes = QComboBox()
        self.cb_classes.setMinimumWidth(260)
        self.cb_classes.currentIndexChanged.connect(self.on_class_changed)
        filter_layout.addWidget(lbl_cls)
        filter_layout.addWidget(self.cb_classes)

        # Sinh viên
        lbl_stu = QLabel("👤 Sinh viên:")
        lbl_stu.setStyleSheet("font-weight: 600;")
        self.cb_students = QComboBox()
        self.cb_students.setMinimumWidth(320)
        self.cb_students.currentIndexChanged.connect(self.on_student_changed)
        filter_layout.addWidget(lbl_stu)
        filter_layout.addWidget(self.cb_students)

        # Nút reload danh sách
        btn_reload = QPushButton("🔄 Tải lại")
        btn_reload.clicked.connect(self.load_classes)
        filter_layout.addWidget(btn_reload)

        filter_layout.addStretch()
        main_layout.addWidget(filter_box)

        # ── 3. Nội dung chính: Camera & Thumbnails ───────────────────────────
        content_splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── 3A. Khung Camera bên trái ───────────────────────────────────────
        left_card = QFrame()
        left_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 12px;
            }}
        """)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(10)

        # Camera Source Toolbar
        src_box = QHBoxLayout()
        lbl_source = QLabel("📹 Nguồn:")
        lbl_source.setStyleSheet("font-weight: 600;")
        self.cb_cam_source = QComboBox()
        self.cb_cam_source.addItems([
            "💻 Webcam máy tính (Cam 0)",
            "💻 Webcam ngoài (Cam 1)",
            "📱 Camera Điện Thoại (IP Cam)",
        ])
        self.cb_cam_source.currentIndexChanged.connect(self.on_cam_source_changed)

        src_box.addWidget(lbl_source)
        src_box.addWidget(self.cb_cam_source)
        src_box.addStretch()
        left_layout.addLayout(src_box)

        # IP URL Input nếu chọn IP Cam
        self.ip_input_box = QFrame()
        self.ip_input_box.setVisible(False)
        ip_in_layout = QHBoxLayout(self.ip_input_box)
        ip_in_layout.setContentsMargins(0, 0, 0, 0)
        self.txt_ip_cam = QLineEdit("http://192.168.1.50:8080/video")
        self.txt_ip_cam.setPlaceholderText("VD: http://192.168.1.15:8080/video")
        ip_in_layout.addWidget(QLabel("URL:"))
        ip_in_layout.addWidget(self.txt_ip_cam)
        left_layout.addWidget(self.ip_input_box)

        # Camera Viewport
        self.lbl_camera = QLabel("Camera chưa khởi động\nNhấn '▶ Bật Camera' hoặc '📁 Tải ảnh từ máy' bên dưới")
        self.lbl_camera.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_camera.setStyleSheet(f"""
            QLabel {{
                background-color: #000000;
                border: 2px dashed {COLORS['border']};
                border-radius: 8px;
                color: {COLORS['text_muted']};
                font-size: 13px;
            }}
        """)
        self.lbl_camera.setMinimumSize(460, 340)
        left_layout.addWidget(self.lbl_camera, 1)

        # Controls dưới camera
        cam_controls = QHBoxLayout()
        cam_controls.setSpacing(10)

        self.btn_toggle_cam = QPushButton("▶ Bật Camera")
        self.btn_toggle_cam.setObjectName("btn_primary")
        self.btn_toggle_cam.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_toggle_cam.clicked.connect(self.toggle_camera)
        cam_controls.addWidget(self.btn_toggle_cam)

        self.btn_capture = QPushButton(f"📸 Chụp Mẫu (0/{REGISTER_SAMPLES})")
        self.btn_capture.setObjectName("btn_success")
        self.btn_capture.setEnabled(False)
        self.btn_capture.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_capture.clicked.connect(self.capture_photo)
        cam_controls.addWidget(self.btn_capture)

        btn_upload_files = QPushButton("📁 Tải ảnh từ máy...")
        btn_upload_files.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_upload_files.clicked.connect(self.upload_photos_from_disk)
        cam_controls.addWidget(btn_upload_files)

        self.btn_clear_photos = QPushButton("🗑 Xóa ảnh")
        self.btn_clear_photos.setEnabled(False)
        self.btn_clear_photos.clicked.connect(self.clear_captured_photos)
        cam_controls.addWidget(self.btn_clear_photos)

        left_layout.addLayout(cam_controls)
        content_splitter.addWidget(left_card)

        # ── 3B. Khung thông tin SV & Thumbnails bên phải ─────────────────────
        right_card = QFrame()
        right_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 12px;
            }}
        """)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(14)

        # Thông tin SV
        self.lbl_stu_info = QLabel("Vui lòng chọn sinh viên để bắt đầu")
        self.lbl_stu_info.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {COLORS['text_accent']};")
        right_layout.addWidget(self.lbl_stu_info)

        # Trạng thái đăng ký hiện tại
        self.lbl_reg_status = QLabel("")
        self.lbl_reg_status.setStyleSheet("font-size: 12px;")
        right_layout.addWidget(self.lbl_reg_status)

        # Danh sách ảnh đã chụp (Thumbnails)
        lbl_thumbs_title = QLabel(f"🖼 Các góc mặt đã chụp (Tối thiểu 1-3 mẫu, khuyến nghị {REGISTER_SAMPLES}):")
        lbl_thumbs_title.setStyleSheet("font-weight: 600; font-size: 12px;")
        right_layout.addWidget(lbl_thumbs_title)

        # ScrollArea chứa Grid thumbnails
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("background: transparent; border: none;")
        
        self.thumbs_container = QWidget()
        self.thumbs_layout = QGridLayout(self.thumbs_container)
        self.thumbs_layout.setSpacing(10)
        self.thumbs_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll_area.setWidget(self.thumbs_container)
        right_layout.addWidget(scroll_area, 1)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        right_layout.addWidget(self.progress_bar)

        # Nút Trích xuất & Lưu AI
        self.btn_save_embeddings = QPushButton("🧠 Trích Xuất AI & Lưu Vào DB")
        self.btn_save_embeddings.setObjectName("btn_primary")
        self.btn_save_embeddings.setEnabled(False)
        self.btn_save_embeddings.setMinimumHeight(42)
        self.btn_save_embeddings.setStyleSheet("font-size: 14px; font-weight: 700;")
        self.btn_save_embeddings.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_save_embeddings.clicked.connect(self.process_and_save)
        right_layout.addWidget(self.btn_save_embeddings)

        content_splitter.addWidget(right_card)
        content_splitter.setStretchFactor(0, 3)
        content_splitter.setStretchFactor(1, 2)

        main_layout.addWidget(content_splitter, 1)

    def on_cam_source_changed(self, index: int):
        self.ip_input_box.setVisible(index == 2)
        if self.camera_worker and self.camera_worker.isRunning():
            self.stop_camera()

    def load_classes(self):
        self.cb_classes.blockSignals(True)
        self.cb_classes.clear()
        try:
            classes = db.get_all_classes()
            if not classes:
                self.cb_classes.addItem("-- Không có lớp nào --", None)
            else:
                for c in classes:
                    c_type = dict(c).get("type", "Lý thuyết")
                    label = f"{c['name']} ({c['code']}) - {c_type}"
                    self.cb_classes.addItem(label, c["id"])
        finally:
            self.cb_classes.blockSignals(False)

        self.on_class_changed()

    def on_class_changed(self):
        class_id = self.cb_classes.currentData()
        self.cb_students.blockSignals(True)
        self.cb_students.clear()

        if class_id is None:
            self.cb_students.addItem("-- Chọn lớp trước --", None)
            self.cb_students.blockSignals(False)
            return

        students = db.get_all_students(class_id)
        if not students:
            self.cb_students.addItem("-- Lớp chưa có sinh viên nào --", None)
        else:
            for s in students:
                reg_mark = "✅" if s["registered"] else "⏳"
                label = f"{reg_mark} {s['student_code']} - {s['full_name']}"
                self.cb_students.addItem(label, s)

        self.cb_students.blockSignals(False)
        self.on_student_changed()

    def on_student_changed(self):
        self.clear_captured_photos()
        self.selected_student = self.cb_students.currentData()

        if not self.selected_student:
            self.lbl_stu_info.setText("Vui lòng chọn sinh viên để bắt đầu")
            self.lbl_reg_status.setText("")
            self.btn_capture.setEnabled(False)
            return

        s = self.selected_student
        self.lbl_stu_info.setText(f"👤 {s['full_name']} (MSSV: {s['student_code']})")
        if s["registered"]:
            self.lbl_reg_status.setText("🟢 Trạng thái: ĐÃ ĐĂNG KÝ (Chụp lại để cập nhật)")
            self.lbl_reg_status.setStyleSheet("color: #34D399; font-weight: 600;")
        else:
            self.lbl_reg_status.setText("🟡 Trạng thái: CHƯA ĐĂNG KÝ KHUÔN MẶT")
            self.lbl_reg_status.setStyleSheet("color: #FBBF24; font-weight: 600;")

        if self.camera_worker and self.camera_worker.isRunning():
            self.btn_capture.setEnabled(True)

    def toggle_camera(self):
        if self.camera_worker and self.camera_worker.isRunning():
            self.stop_camera()
        else:
            self.start_camera()

    def start_camera(self):
        src_idx = self.cb_cam_source.currentIndex()
        if src_idx == 2:
            url = self.txt_ip_cam.text().strip()
            self.camera_worker = CameraWorker(source=url)
        else:
            self.camera_worker = CameraWorker(source=src_idx)

        self.camera_worker.frame_ready.connect(self.on_frame_ready)
        self.camera_worker.error_occurred.connect(self.on_camera_error)
        self.camera_worker.start()

        self.btn_toggle_cam.setText("⏹ Tắt Camera")
        self.btn_toggle_cam.setObjectName("btn_danger")
        self.btn_toggle_cam.style().unpolish(self.btn_toggle_cam)
        self.btn_toggle_cam.style().polish(self.btn_toggle_cam)
        
        if self.selected_student:
            self.btn_capture.setEnabled(True)

    def stop_camera(self):
        if self.camera_worker:
            self.camera_worker.stop()
            self.camera_worker.wait(1500)
            self.camera_worker = None

        self.btn_toggle_cam.setText("▶ Bật Camera")
        self.btn_toggle_cam.setObjectName("btn_primary")
        self.btn_toggle_cam.style().unpolish(self.btn_toggle_cam)
        self.btn_toggle_cam.style().polish(self.btn_toggle_cam)
        self.btn_capture.setEnabled(False)
        self.lbl_camera.setText("Camera đã dừng")
        self.lbl_camera.setPixmap(QPixmap())

    def on_frame_ready(self, q_img: QImage, frame: np.ndarray):
        self.current_frame = frame.copy()
        scaled = q_img.scaled(
            self.lbl_camera.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.lbl_camera.setPixmap(QPixmap.fromImage(scaled))

    @pyqtSlot(str)
    def on_camera_error(self, err_msg: str):
        QMessageBox.warning(self, "Lỗi Camera", f"Không thể mở Camera: {err_msg}")
        self.stop_camera()

    def capture_photo(self):
        if self.current_frame is None or not self.selected_student:
            return

        if len(self.captured_images) >= REGISTER_SAMPLES:
            QMessageBox.information(
                self, "Đã đủ ảnh",
                f"Bạn đã chụp đủ {REGISTER_SAMPLES} ảnh mẫu! Hãy nhấn 'Trích Xuất AI & Lưu Vào DB'."
            )
            return

        img = self.current_frame.copy()
        self.captured_images.append(img)
        self.update_thumbnails()

        count = len(self.captured_images)
        self.btn_capture.setText(f"📸 Chụp Mẫu ({count}/{REGISTER_SAMPLES})")
        self.btn_clear_photos.setEnabled(True)
        self.btn_save_embeddings.setEnabled(count >= 1)

    def upload_photos_from_disk(self):
        """Tải các file ảnh có sẵn từ máy tính."""
        if not self.selected_student:
            QMessageBox.warning(self, "Chưa chọn sinh viên", "Vui lòng chọn sinh viên trước khi tải ảnh!")
            return

        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Chọn Các File Ảnh Khuôn Mặt Mẫu", "", "Image Files (*.jpg *.jpeg *.png *.bmp *.webp)"
        )
        if not file_paths:
            return

        count = 0
        for p in file_paths:
            img = cv2.imread(p)
            if img is not None:
                self.captured_images.append(img)
                count += 1

        self.update_thumbnails()
        total_count = len(self.captured_images)
        self.btn_clear_photos.setEnabled(total_count > 0)
        self.btn_save_embeddings.setEnabled(total_count >= 1)
        self.btn_capture.setText(f"📸 Chụp Mẫu ({total_count}/{REGISTER_SAMPLES})")
        QMessageBox.information(self, "Thành Công", f"Đã thêm {count} ảnh từ máy tính!")

    def clear_captured_photos(self):
        self.captured_images.clear()
        self.btn_capture.setText(f"📸 Chụp Mẫu (0/{REGISTER_SAMPLES})")
        self.btn_clear_photos.setEnabled(False)
        self.btn_save_embeddings.setEnabled(False)
        self.update_thumbnails()

    def update_thumbnails(self):
        for i in reversed(range(self.thumbs_layout.count())):
            item = self.thumbs_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)

        for idx, img in enumerate(self.captured_images):
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pix = QPixmap.fromImage(qimg).scaled(
                90, 90,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )

            lbl = QLabel()
            lbl.setPixmap(pix)
            lbl.setFixedSize(90, 90)
            lbl.setStyleSheet(f"border: 2px solid {COLORS['blue']}; border-radius: 8px;")

            row = idx // 3
            col = idx % 3
            self.thumbs_layout.addWidget(lbl, row, col)

    def process_and_save(self):
        if not self.selected_student or not self.captured_images:
            return

        self.btn_save_embeddings.setEnabled(False)
        self.btn_capture.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setRange(0, len(self.captured_images))

        stu_id = self.selected_student["id"]
        stu_code = self.selected_student["student_code"]

        self.extract_worker = EmbeddingExtractionWorker(stu_id, stu_code, self.captured_images)
        self.extract_worker.progress.connect(self.on_extract_progress)
        self.extract_worker.finished.connect(self.on_extract_finished)
        self.extract_worker.start()

    @pyqtSlot(int, int)
    def on_extract_progress(self, current: int, total: int):
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"Đang xử lý mẫu {current}/{total}...")

    @pyqtSlot(bool, str)
    def on_extract_finished(self, success: bool, message: str):
        self.progress_bar.setVisible(False)
        self.btn_save_embeddings.setEnabled(True)
        if self.camera_worker and self.camera_worker.isRunning():
            self.btn_capture.setEnabled(True)

        if success:
            QMessageBox.information(self, "Thành Công", message)
            self.on_class_changed()
            self.clear_captured_photos()
        else:
            QMessageBox.warning(self, "Thất Bại", message)

    def closeEvent(self, event):
        self.stop_camera()
        super().closeEvent(event)
