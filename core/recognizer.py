"""
recognizer.py - ArcFace Face Recognizer wrapper (ONNX)
Trích xuất embedding 512-d từ ảnh khuôn mặt đã align
"""
import numpy as np
import onnxruntime as ort
from loguru import logger

from utils.config import ARCFACE_MODEL_PATH, ONNX_PROVIDERS, FACE_SIZE


class ArcFaceRecognizer:
    """
    Wrapper cho ArcFace R50 chạy qua ONNXRuntime.

    Model: w600k_r50.onnx
    Download: https://github.com/deepinsight/insightface/tree/master/recognition/arcface_torch
    Output: embedding 512-d (L2 normalized)
    """

    def __init__(self):
        if not ARCFACE_MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Không tìm thấy ArcFace model tại: {ARCFACE_MODEL_PATH}\n"
                "Tải model tại: https://github.com/deepinsight/insightface"
            )

        logger.info(f"Loading ArcFace from {ARCFACE_MODEL_PATH} ...")
        
        # Cấu hình tối ưu đa luồng CPU và bộ nhớ
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 4
        opts.inter_op_num_threads = 2
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

        self.session = ort.InferenceSession(
            str(ARCFACE_MODEL_PATH),
            sess_options=opts,
            providers=ONNX_PROVIDERS,
        )
        self.input_name = self.session.get_inputs()[0].name
        self.face_size  = FACE_SIZE   # (112, 112)
        logger.info("ArcFace loaded OK (Optimized)")

    def _preprocess(self, face_img: np.ndarray) -> np.ndarray:
        """
        Chuẩn hóa ảnh khuôn mặt về format input ArcFace.
        Input: BGR 112x112
        Output: float32 tensor (1, 3, 112, 112) normalized [-1, 1]
        """
        import cv2
        if face_img.shape[:2] != self.face_size:
            face_img = cv2.resize(face_img, self.face_size)

        blob = face_img.astype(np.float32)
        blob = (blob / 127.5) - 1.0               # normalize to [-1, 1]
        blob = blob.transpose(2, 0, 1)[np.newaxis] # (1, 3, 112, 112)
        return blob

    def get_embedding(self, face_img: np.ndarray) -> np.ndarray:
        """
        Trích xuất embedding 512-d từ ảnh khuôn mặt.

        Args:
            face_img: BGR numpy array, ideally 112x112 aligned
        Returns:
            embedding: (512,) float32, L2 normalized
        """
        blob = self._preprocess(face_img)
        embedding = self.session.run(None, {self.input_name: blob})[0].flatten()

        # L2 normalize
        norm = np.linalg.norm(embedding)
        embedding = embedding / (norm + 1e-6)
        return embedding.astype(np.float32)

    def get_embedding_batch(self, face_imgs: list) -> np.ndarray:
        """
        Trích xuất embedding cho nhiều khuôn mặt cùng lúc (tối ưu GPU).

        Args:
            face_imgs: List ảnh BGR 112x112
        Returns:
            embeddings: (N, 512) float32, mỗi hàng đã L2 normalized
        """
        blobs = np.concatenate([self._preprocess(img) for img in face_imgs], axis=0)
        embeddings = self.session.run(None, {self.input_name: blobs})[0]

        # Normalize từng hàng
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / (norms + 1e-6)
        return embeddings.astype(np.float32)
