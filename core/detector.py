"""
detector.py - SCRFD Face Detector wrapper (ONNX)
Phát hiện khuôn mặt + 5 facial landmarks
"""
import numpy as np
import onnxruntime as ort
from dataclasses import dataclass, field
from typing import List, Tuple
from loguru import logger

from utils.config import (
    SCRFD_MODEL_PATH, ONNX_PROVIDERS,
    DETECTION_THRESHOLD, INPUT_SIZE,
)


@dataclass
class FaceDetection:
    """Kết quả phát hiện 1 khuôn mặt."""
    bbox: Tuple[float, float, float, float]   # (x1, y1, x2, y2)
    score: float                              # confidence
    landmarks: np.ndarray = field(default=None)  # shape (5, 2): 5 keypoints


class SCRFDDetector:
    """
    Wrapper cho SCRFD face detector chạy qua ONNXRuntime.

    Model: scrfd_2.5g_bnkps.onnx  (2.5G FLOPs, có keypoints)
    Download: https://github.com/deepinsight/insightface
    """

    def __init__(self):
        if not SCRFD_MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Không tìm thấy SCRFD model tại: {SCRFD_MODEL_PATH}\n"
                "Tải model tại: https://github.com/deepinsight/insightface/tree/master/detection/scrfd"
            )

        logger.info(f"Loading SCRFD from {SCRFD_MODEL_PATH} ...")
        self.session = ort.InferenceSession(
            str(SCRFD_MODEL_PATH),
            providers=ONNX_PROVIDERS,
        )
        self.input_name  = self.session.get_inputs()[0].name
        self.input_size  = INPUT_SIZE     # (W, H)
        self.threshold   = DETECTION_THRESHOLD
        logger.info("SCRFD loaded OK")

    def _preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, float, float]:
        """
        Resize + normalize ảnh về format input của SCRFD.
        Returns: (blob, scale_x, scale_y)
        """
        import cv2
        h, w = image.shape[:2]
        iw, ih = self.input_size

        scale_x = iw / w
        scale_y = ih / h

        resized = cv2.resize(image, (iw, ih))
        blob = resized.astype(np.float32)
        blob -= np.array([127.5, 127.5, 127.5], dtype=np.float32)
        blob /= 128.0
        blob = blob.transpose(2, 0, 1)[np.newaxis]  # (1, 3, H, W)
        return blob, scale_x, scale_y

    def detect(self, image: np.ndarray) -> List[FaceDetection]:
        """
        Phát hiện khuôn mặt trong ảnh BGR.

        Args:
            image: BGR numpy array
        Returns:
            Danh sách FaceDetection (đã lọc theo threshold)
        """
        blob, sx, sy = self._preprocess(image)

        outputs = self.session.run(None, {self.input_name: blob})

        # Parse outputs: SCRFD trả về scores, bboxes, kps theo stride
        # Format output phụ thuộc vào model, đây là cách parse chuẩn
        faces = self._parse_outputs(outputs, sx, sy)
        
        # Lọc NMS để tránh trùng lặp cùng 1 khuôn mặt ở các stride khác nhau
        faces = self._nms(faces, iou_threshold=0.45)
        return faces

    def _nms(self, dets: List[FaceDetection], iou_threshold: float = 0.4) -> List[FaceDetection]:
        """Lọc Non-Maximum Suppression loại bỏ các khung trùng lặp."""
        if not dets:
            return []
        
        # Sắp xếp theo score giảm dần
        dets = sorted(dets, key=lambda x: x.score, reverse=True)
        keep = []
        
        while dets:
            best = dets.pop(0)
            keep.append(best)
            
            remaining = []
            for d in dets:
                bi = best.bbox
                di = d.bbox
                
                # Tính IoU (Intersection over Union)
                xx1 = max(bi[0], di[0])
                yy1 = max(bi[1], di[1])
                xx2 = min(bi[2], di[2])
                yy2 = min(bi[3], di[3])
                
                w = max(0.0, xx2 - xx1)
                h = max(0.0, yy2 - yy1)
                inter = w * h
                
                area_b = (bi[2] - bi[0]) * (bi[3] - bi[1])
                area_d = (di[2] - di[0]) * (di[3] - di[1])
                union = area_b + area_d - inter
                
                iou = inter / union if union > 0 else 0.0
                if iou < iou_threshold:
                    remaining.append(d)
            dets = remaining
            
        return keep

    def _parse_outputs(
        self, outputs: List[np.ndarray], sx: float, sy: float
    ) -> List[FaceDetection]:
        """
        Parse raw ONNX outputs thành FaceDetection objects.
        SCRFD với kps=True có 9 outputs:
        - index 0, 1, 2: scores (strides 8, 16, 32)
        - index 3, 4, 5: bboxes (strides 8, 16, 32)
        - index 6, 7, 8: keypoints (strides 8, 16, 32)
        """
        faces = []
        num_anchors = [2, 2, 2]   # anchors per stride
        strides      = [8, 16, 32]

        for s, (stride, na) in enumerate(zip(strides, num_anchors)):
            scores = outputs[s].flatten()
            bboxes = outputs[s + 3]
            kps    = outputs[s + 6] if len(outputs) > s + 6 else None

            iw, ih = self.input_size
            cols = iw // stride
            rows = ih // stride

            for i, score in enumerate(scores):
                if score < self.threshold:  # Lọc sớm theo threshold cấu hình
                    continue

                row_i = i // na
                r = row_i // cols
                c = row_i % cols

                cx = (c + 0.5) * stride
                cy = (r + 0.5) * stride

                dx1, dy1, dx2, dy2 = bboxes[i] * stride
                x1 = (cx - dx1) / sx
                y1 = (cy - dy1) / sy
                x2 = (cx + dx2) / sx
                y2 = (cy + dy2) / sy

                lm = None
                if kps is not None:
                    raw = kps[i].reshape(5, 2) * stride
                    raw[:, 0] = (raw[:, 0] + cx) / sx
                    raw[:, 1] = (raw[:, 1] + cy) / sy
                    lm = raw

                faces.append(FaceDetection(
                    bbox=(x1, y1, x2, y2),
                    score=float(score),
                    landmarks=lm,
                ))

        return faces
