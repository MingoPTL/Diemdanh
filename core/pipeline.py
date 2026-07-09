"""
pipeline.py - Pipeline tổng hợp: Detect → Align → Recognize → Match
Đây là entry point chính cho mọi luồng nhận diện khuôn mặt
"""
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple
from loguru import logger

from core.detector   import SCRFDDetector, FaceDetection
from core.aligner    import align_face, crop_face
from core.recognizer import ArcFaceRecognizer
from utils.config    import MIN_FACE_SIZE


@dataclass
class RecognitionResult:
    """Kết quả nhận diện 1 khuôn mặt."""
    bbox: Tuple[float, float, float, float]   # (x1, y1, x2, y2)
    student_id: Optional[str]                 # None nếu Unknown
    name: str                                 # Tên hoặc "Unknown"
    confidence: float                         # Cosine similarity
    face_crop: Optional[np.ndarray] = None    # Ảnh khuôn mặt đã crop


class FacePipeline:
    """
    Pipeline hoàn chỉnh: frame → detect → align → embed → match.
    Lazy-init: models chỉ load khi lần đầu gọi.
    """

    def __init__(self):
        self._detector: Optional[SCRFDDetector]   = None
        self._recognizer: Optional[ArcFaceRecognizer] = None
        self._loaded = False

    def load(self):
        """Load tất cả models vào bộ nhớ (GPU)."""
        if self._loaded:
            return
        logger.info("Đang load AI models...")
        self._detector   = SCRFDDetector()
        self._recognizer = ArcFaceRecognizer()
        self._loaded = True
        logger.info("Models loaded thành công!")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def get_embedding(self, face_crop: np.ndarray) -> np.ndarray:
        """
        Trích xuất embedding từ ảnh khuôn mặt đã crop/align.
        Dùng khi đăng ký khuôn mặt mới.
        """
        if not self._loaded:
            self.load()
        return self._recognizer.get_embedding(face_crop)

    def extract_faces(self, frame: np.ndarray) -> List[Tuple[FaceDetection, np.ndarray]]:
        """
        Detect + align tất cả khuôn mặt trong frame.

        Returns:
            List of (FaceDetection, aligned_face_112x112)
        """
        if not self._loaded:
            self.load()

        detections = self._detector.detect(frame)
        results = []

        for det in detections:
            x1, y1, x2, y2 = det.bbox
            face_w = x2 - x1
            face_h = y2 - y1

            # Bỏ qua khuôn mặt quá nhỏ
            if face_w < MIN_FACE_SIZE or face_h < MIN_FACE_SIZE:
                continue

            if det.landmarks is not None:
                face_crop = align_face(frame, det.landmarks)
            else:
                face_crop = crop_face(frame, det.bbox)

            results.append((det, face_crop))

        return results

    def process_frame(
        self,
        frame: np.ndarray,
        face_db,               # FaceDatabase instance
    ) -> List[RecognitionResult]:
        """
        Xử lý toàn bộ 1 frame: detect → align → embed → match.

        Args:
            frame: BGR numpy array từ camera
            face_db: FaceDatabase để tra cứu embedding
        Returns:
            Danh sách RecognitionResult cho mỗi khuôn mặt tìm thấy
        """
        if not self._loaded:
            self.load()

        face_pairs = self.extract_faces(frame)
        if not face_pairs:
            return []

        # Batch embedding để tận dụng GPU
        face_crops = [fc for _, fc in face_pairs]
        embeddings = self._recognizer.get_embedding_batch(face_crops)

        results = []
        for (det, face_crop), embedding in zip(face_pairs, embeddings):
            student_id, name, confidence = face_db.match(embedding)
            results.append(RecognitionResult(
                bbox=det.bbox,
                student_id=student_id,
                name=name,
                confidence=confidence,
                face_crop=face_crop,
            ))

        return results


# Singleton instance — dùng chung toàn app
pipeline = FacePipeline()
