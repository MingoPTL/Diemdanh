"""
desktop/widgets/camera_widget.py — Widget hiển thị Camera với overlay AI
Hiển thị video Camera real-time, vẽ bounding box khuôn mặt + barcode,
và thông tin FPS/AI processing time.
"""
import cv2
import numpy as np
from typing import List, Tuple, Optional
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, QSize, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QFont, QBrush

from desktop.theme import COLORS, FONT_SIZE_SM


class CameraWidget(QWidget):
    """
    Widget hiển thị video Camera với overlay AI bounding boxes.
    Vẽ trực tiếp bằng QPainter trên QPixmap cho hiệu năng cao nhất.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        self._faces: List[Tuple] = []       # [(bbox, name, confidence, student_id), ...]
        self._barcodes: List[Tuple] = []    # [(points, label, is_valid, mssv), ...]
        self._fps: float = 0.0
        self._ai_time_ms: float = 0.0
        self._show_overlay = True

        # Layout
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._label.setMinimumSize(640, 480)
        self._label.setStyleSheet(f"""
            background-color: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['border']};
            border-radius: 12px;
        """)
        self._label.setText("📷 Camera chưa bật")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

    def set_show_overlay(self, show: bool):
        """Bật/tắt hiển thị overlay AI."""
        self._show_overlay = show

    def update_frame(self, q_image: QImage, raw_frame: np.ndarray = None):
        """Cập nhật khung hình mới từ Camera Worker."""
        pixmap = QPixmap.fromImage(q_image)

        if self._show_overlay:
            pixmap = self._draw_overlays(pixmap)

        # Scale to fit widget while maintaining aspect ratio
        label_size = self._label.size()
        scaled = pixmap.scaled(
            label_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self._label.setPixmap(scaled)

    def update_ai_results(self, faces: List[Tuple], barcodes: List[Tuple]):
        """Cập nhật kết quả AI mới nhất."""
        self._faces = faces
        self._barcodes = barcodes

    def update_fps(self, fps: float):
        """Cập nhật FPS hiện tại."""
        self._fps = fps

    def update_ai_time(self, ms: float):
        """Cập nhật thời gian xử lý AI."""
        self._ai_time_ms = ms

    def show_placeholder(self, text: str = "📷 Camera chưa bật"):
        """Hiển thị placeholder khi Camera chưa bật."""
        self._label.clear()
        self._label.setText(text)
        self._faces = []
        self._barcodes = []

    def _draw_overlays(self, pixmap: QPixmap) -> QPixmap:
        """Vẽ bounding boxes AI và FPS info lên pixmap."""
        result = pixmap.copy()
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        img_w = result.width()
        img_h = result.height()

        # ── Vẽ Face bounding boxes ────────────────────────────────────────
        for face_data in self._faces:
            if len(face_data) < 3:
                continue
            bbox, name, confidence = face_data[0], face_data[1], face_data[2]
            student_id = face_data[3] if len(face_data) > 3 else None
            x1, y1, x2, y2 = [int(v) for v in bbox]

            is_known = name != "Unknown" and student_id is not None

            if is_known:
                color = QColor(16, 185, 129)    # Green (nhận diện thành công)
                bg_color = QColor(16, 185, 129, 180)
            else:
                color = QColor(239, 68, 68)     # Red (không nhận ra)
                bg_color = QColor(239, 68, 68, 180)

            # Bounding box
            pen = QPen(color, 2)
            painter.setPen(pen)
            painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)

            # Corner accents (góc vuông nổi bật)
            corner_len = min(20, (x2 - x1) // 4, (y2 - y1) // 4)
            thick_pen = QPen(color, 3)
            painter.setPen(thick_pen)
            # Top-left
            painter.drawLine(x1, y1, x1 + corner_len, y1)
            painter.drawLine(x1, y1, x1, y1 + corner_len)
            # Top-right
            painter.drawLine(x2, y1, x2 - corner_len, y1)
            painter.drawLine(x2, y1, x2, y1 + corner_len)
            # Bottom-left
            painter.drawLine(x1, y2, x1 + corner_len, y2)
            painter.drawLine(x1, y2, x1, y2 - corner_len)
            # Bottom-right
            painter.drawLine(x2, y2, x2 - corner_len, y2)
            painter.drawLine(x2, y2, x2, y2 - corner_len)

            # Label background
            label = f"{name} ({confidence * 100:.0f}%)" if is_known else "Unknown"
            font = QFont("Segoe UI", 10, QFont.Weight.Bold)
            painter.setFont(font)
            fm = painter.fontMetrics()
            text_w = fm.horizontalAdvance(label) + 12
            text_h = fm.height() + 6

            label_y = max(0, y1 - text_h - 2)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(bg_color))
            painter.drawRoundedRect(x1, label_y, text_w, text_h, 4, 4)

            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.drawText(x1 + 6, label_y + text_h - 5, label)

        # ── Vẽ Barcode bounding boxes ─────────────────────────────────────
        for barcode_data in self._barcodes:
            if len(barcode_data) < 3:
                continue
            points, label, is_valid = barcode_data[0], barcode_data[1], barcode_data[2]

            if not points or len(points) < 4:
                continue

            if is_valid:
                color = QColor(16, 185, 129)    # Green
                bg_color = QColor(16, 185, 129, 180)
            else:
                color = QColor(249, 115, 22)    # Orange
                bg_color = QColor(249, 115, 22, 180)

            # Polygon
            from PyQt6.QtGui import QPolygon
            from PyQt6.QtCore import QPoint
            polygon = QPolygon([QPoint(int(p[0]), int(p[1])) for p in points])
            pen = QPen(color, 3)
            painter.setPen(pen)
            painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            painter.drawPolygon(polygon)

            # Label
            min_x = min(p[0] for p in points)
            min_y = min(p[1] for p in points)
            font = QFont("Segoe UI", 9, QFont.Weight.Bold)
            painter.setFont(font)
            fm = painter.fontMetrics()
            text_w = fm.horizontalAdvance(label) + 12
            text_h = fm.height() + 6

            label_y = max(0, int(min_y) - text_h - 2)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(bg_color))
            painter.drawRoundedRect(int(min_x), label_y, text_w, text_h, 4, 4)

            painter.setPen(QPen(QColor(15, 23, 42)))
            painter.drawText(int(min_x) + 6, label_y + text_h - 5, label)

        # ── FPS + AI Time info (góc trên bên trái) ────────────────────────
        info_font = QFont("Segoe UI", 9)
        painter.setFont(info_font)

        fps_text = f"CAM: {self._fps:.0f} FPS"
        ai_text = f"AI: {self._ai_time_ms:.0f} ms"

        # Background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(15, 23, 42, 180)))
        painter.drawRoundedRect(8, 8, 150, 50, 6, 6)

        painter.setPen(QPen(QColor(52, 211, 153)))  # Green
        painter.drawText(16, 28, fps_text)
        painter.setPen(QPen(QColor(96, 165, 250)))   # Blue
        painter.drawText(16, 48, ai_text)

        painter.end()
        return result

    def sizeHint(self):
        return QSize(960, 540)
