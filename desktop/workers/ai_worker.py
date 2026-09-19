"""
desktop/workers/ai_worker.py — QThread xử lý AI Face + Barcode (Background)
Nhận khung hình từ Camera Worker, chạy SCRFD + ArcFace + Barcode Scanner,
emit kết quả nhận diện về UI thread để vẽ overlay.
"""
import time
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker
from loguru import logger

from core.pipeline import pipeline, RecognitionResult
from services.barcode_scanner import barcode_scanner, BarcodeResult
from services.attendance import attendance_service
from services.face_db import face_db


@dataclass
class AIResult:
    """Kết quả xử lý AI cho 1 khung hình."""
    faces: List[Tuple] = field(default_factory=list)       # [(bbox, name, confidence, student_id), ...]
    barcodes: List[Tuple] = field(default_factory=list)    # [(points, label, is_valid, mssv), ...]
    process_time_ms: float = 0.0


class AIWorker(QThread):
    """
    Worker thread xử lý nhận diện AI nền.
    Nhận frame từ Camera → chạy Face AI + Barcode → emit kết quả.
    """
    results_ready = pyqtSignal(object)        # AIResult
    attendance_logged = pyqtSignal(str, str, str, str)  # (name, mssv, status, method)
    processing_time = pyqtSignal(float)       # ms

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._running = False
        self._latest_frame: Optional[np.ndarray] = None
        self._enable_face = True
        self._enable_barcode = True
        self._process_interval_ms = 50  # 20 FPS AI processing

    def set_settings(self, enable_face: bool, enable_barcode: bool):
        """Cập nhật cài đặt chế độ quét."""
        with QMutexLocker(self._mutex):
            self._enable_face = enable_face
            self._enable_barcode = enable_barcode

    def submit_frame(self, frame: np.ndarray):
        """Gửi khung hình mới nhất để xử lý AI (non-blocking, ghi đè frame cũ)."""
        with QMutexLocker(self._mutex):
            self._latest_frame = frame

    def stop(self):
        """Dừng AI Worker."""
        with QMutexLocker(self._mutex):
            self._running = False

    def run(self):
        """Main loop: lấy frame mới nhất → xử lý AI → emit kết quả."""
        with QMutexLocker(self._mutex):
            self._running = True

        logger.info("AI Worker: Bắt đầu xử lý nhận diện nền...")

        while True:
            with QMutexLocker(self._mutex):
                if not self._running:
                    break
                frame = self._latest_frame
                self._latest_frame = None  # Tiêu thụ frame
                enable_face = self._enable_face
                enable_barcode = self._enable_barcode

            if frame is None:
                self.msleep(10)
                continue

            t_start = time.perf_counter()
            result = AIResult()

            # ── 1. Quét Barcode / QR Code ─────────────────────────────────────
            if enable_barcode:
                try:
                    b_results = barcode_scanner.scan(frame, try_mirror=True)
                    for b in b_results:
                        mssv = b.text.strip()
                        is_success = False
                        label_text = f"MSSV: {mssv}"

                        if attendance_service.is_active:
                            success, st_info, msg = attendance_service.mark_attendance_by_code(
                                mssv, method="barcode"
                            )
                            is_success = success
                            if st_info:
                                label_text = f"{st_info['full_name']} ({mssv})"
                                if success:
                                    status = attendance_service.calculate_status()
                                    self.attendance_logged.emit(
                                        st_info['full_name'],
                                        mssv,
                                        status,
                                        "barcode"
                                    )

                        result.barcodes.append((b.points, label_text, is_success, mssv))
                except Exception as e:
                    logger.debug(f"AI Worker barcode error: {e}")

            # ── 2. Quét Khuôn Mặt AI (SCRFD + ArcFace) ───────────────────────
            if enable_face and pipeline.is_loaded:
                try:
                    f_results = pipeline.process_frame(frame, face_db)
                    for res in f_results:
                        if res.student_id and attendance_service.is_active:
                            success = attendance_service.mark_attendance(
                                res.student_id, res.confidence, method="face"
                            )
                            if success:
                                self.attendance_logged.emit(
                                    res.name,
                                    str(res.student_id),
                                    attendance_service.calculate_status(),
                                    "face"
                                )
                        result.faces.append((
                            res.bbox,
                            res.name,
                            res.confidence,
                            res.student_id
                        ))
                except Exception as e:
                    logger.debug(f"AI Worker face error: {e}")

            t_end = time.perf_counter()
            result.process_time_ms = (t_end - t_start) * 1000
            self.results_ready.emit(result)
            self.processing_time.emit(result.process_time_ms)

            # Throttle: đảm bảo AI không chạy quá nhanh chiếm hết CPU
            elapsed_ms = result.process_time_ms
            wait_ms = max(1, int(self._process_interval_ms - elapsed_ms))
            self.msleep(wait_ms)

        logger.info("AI Worker: Đã dừng.")
