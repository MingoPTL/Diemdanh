"""
desktop/workers/camera_worker.py — QThread đọc Camera 30-60 FPS
Tự động dò backend (Default / DSHOW / MSMF), tự thích ứng độ phân giải phần cứng,
và hỗ trợ IP Camera / Camera điện thoại trực tiếp.
"""
import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker
from PyQt6.QtGui import QImage
from loguru import logger


class CameraWorker(QThread):
    """
    Worker thread đọc Camera Webcam / IP Cam.
    Emit frame_ready(QImage, np.ndarray) mỗi ~33ms (30 FPS).
    """
    frame_ready = pyqtSignal(QImage, np.ndarray)  # (display_image, raw_bgr_frame)
    error_occurred = pyqtSignal(str)
    camera_error = pyqtSignal(str)  # Alias tương thích
    fps_updated = pyqtSignal(float)

    def __init__(self, source=0, parent=None):
        if isinstance(source, QThread) or hasattr(source, "metaObject"):
            super().__init__(source)
            self._camera_index = 0
            self._ip_url = ""
            self._use_ip = False
        else:
            super().__init__(parent)
            if isinstance(source, str) and (source.startswith("http://") or source.startswith("https://") or source.startswith("rtsp://")):
                self._ip_url = source
                self._use_ip = True
                self._camera_index = 0
            else:
                self._camera_index = int(source) if str(source).isdigit() else 0
                self._ip_url = ""
                self._use_ip = False

        self._mutex = QMutex()
        self._running = False
        self._mirror = False
        self._cap = None

    def set_camera(self, index: int = 0):
        """Cấu hình nguồn Camera Webcam."""
        with QMutexLocker(self._mutex):
            self._camera_index = index
            self._use_ip = False

    def set_ip_camera(self, url: str):
        """Cấu hình nguồn IP Camera (HTTP/RTSP/DroidCam/IP Webcam)."""
        with QMutexLocker(self._mutex):
            self._ip_url = url.strip()
            self._use_ip = True

    def set_mirror(self, mirror: bool):
        """Bật/tắt lật gương Camera."""
        with QMutexLocker(self._mutex):
            self._mirror = mirror

    def stop(self):
        """Dừng Camera Worker."""
        with QMutexLocker(self._mutex):
            self._running = False

    def emit_error(self, err_msg: str):
        self.error_occurred.emit(err_msg)
        self.camera_error.emit(err_msg)

    def run(self):
        """Main loop: đọc Camera liên tục và emit frame."""
        with QMutexLocker(self._mutex):
            self._running = True
            use_ip = self._use_ip
            ip_url = self._ip_url
            cam_idx = self._camera_index

        self._cap = None
        try:
            if use_ip:
                logger.info(f"[CameraWorker] Kết nối IP Camera: {ip_url}")
                cap = cv2.VideoCapture(ip_url)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if cap.isOpened():
                    self._cap = cap
                else:
                    self.emit_error(f"Không thể mở luồng IP Camera tại:\n{ip_url}")
                    return
            else:
                # Thử mở webcam với nhiều backend
                backends = [None, cv2.CAP_DSHOW, cv2.CAP_MSMF]
                opened = False

                for b in backends:
                    try:
                        if b is None:
                            cap = cv2.VideoCapture(cam_idx)
                        else:
                            cap = cv2.VideoCapture(cam_idx, b)

                        if cap.isOpened():
                            # Thử đọc 1 frame để chắc chắn camera hoạt động
                            ret, test_frame = cap.read()
                            if ret and test_frame is not None:
                                self._cap = cap
                                opened = True
                                logger.info(f"[CameraWorker] Mở Camera {cam_idx} thành công (Backend: {b})")
                                break
                            else:
                                cap.release()
                    except Exception as ex:
                        logger.warning(f"[CameraWorker] Lỗi mở backend {b}: {ex}")

                if not opened or self._cap is None:
                    self.emit_error(f"Không thể mở Camera (index={cam_idx}). Vui lòng kiểm tra quyền Camera hoặc chọn cổng khác!")
                    return
        except Exception as e:
            self.emit_error(f"Lỗi khởi tạo Camera: {e}")
            return

        frame_count = 0
        fps_timer = cv2.getTickCount()

        while True:
            with QMutexLocker(self._mutex):
                if not self._running:
                    break
                mirror = self._mirror

            if self._cap is None:
                break

            ret, frame = self._cap.read()
            if not ret or frame is None:
                self.emit_error("Mất tín hiệu kết nối từ Camera!")
                break

            if mirror:
                frame = cv2.flip(frame, 1)

            # Chuyển BGR → RGB cho QImage
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h_f, w_f, ch = rgb_frame.shape
            bytes_per_line = ch * w_f
            q_image = QImage(
                rgb_frame.data, w_f, h_f, bytes_per_line, QImage.Format.Format_RGB888
            ).copy()

            self.frame_ready.emit(q_image, frame.copy())

            # Tính FPS
            frame_count += 1
            if frame_count >= 15:
                elapsed = (cv2.getTickCount() - fps_timer) / cv2.getTickFrequency()
                fps = frame_count / max(elapsed, 0.001)
                self.fps_updated.emit(fps)
                frame_count = 0
                fps_timer = cv2.getTickCount()

            self.msleep(15)

        # Cleanup
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        logger.info("[CameraWorker] Đã dừng camera.")
