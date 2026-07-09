"""
aligner.py - Căn chỉnh khuôn mặt theo 5 facial landmarks (ArcFace chuẩn)
"""
import cv2
import numpy as np
from loguru import logger


# Template landmarks chuẩn của ArcFace (112x112)
ARCFACE_SRC = np.array([
    [38.2946, 51.6963],
    [73.5318, 51.5014],
    [56.0252, 71.7366],
    [41.5493, 92.3655],
    [70.7299, 92.2041],
], dtype=np.float32)


def align_face(image: np.ndarray, landmarks: np.ndarray, size: int = 112) -> np.ndarray:
    """
    Căn chỉnh khuôn mặt về kích thước 112x112 chuẩn ArcFace.

    Args:
        image: Ảnh BGR gốc
        landmarks: (5, 2) array - 5 keypoints từ SCRFD
        size: output size (mặc định 112)
    Returns:
        Ảnh khuôn mặt đã căn chỉnh (112x112, BGR)
    """
    dst = ARCFACE_SRC * (size / 112.0)

    # Tính similarity transform
    M, _ = cv2.estimateAffinePartial2D(landmarks, dst, method=cv2.LMEDS)
    if M is None:
        logger.warning("Không tính được affine transform, dùng crop thô")
        return _fallback_crop(image, landmarks, size)

    aligned = cv2.warpAffine(image, M, (size, size), flags=cv2.INTER_LINEAR)
    return aligned


def crop_face(image: np.ndarray, bbox: tuple, margin: float = 0.2) -> np.ndarray:
    """
    Crop khuôn mặt từ bounding box (không align) — dùng khi không có landmarks.

    Args:
        image: Ảnh BGR
        bbox: (x1, y1, x2, y2)
        margin: % mở rộng bbox
    """
    h, w = image.shape[:2]
    x1, y1, x2, y2 = [int(v) for v in bbox]

    bw = x2 - x1
    bh = y2 - y1
    mx = int(bw * margin)
    my = int(bh * margin)

    x1 = max(0, x1 - mx)
    y1 = max(0, y1 - my)
    x2 = min(w, x2 + mx)
    y2 = min(h, y2 + my)

    crop = image[y1:y2, x1:x2]
    return cv2.resize(crop, (112, 112))


def _fallback_crop(image: np.ndarray, landmarks: np.ndarray, size: int) -> np.ndarray:
    """Fallback: crop dựa trên bounding box của landmarks."""
    x_min, y_min = landmarks.min(axis=0)
    x_max, y_max = landmarks.max(axis=0)
    return crop_face(image, (x_min, y_min, x_max, y_max))
