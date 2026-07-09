"""
face_db.py - Quản lý face embeddings (lưu/load/match)
Dùng numpy + cosine similarity (đủ dùng cho <= 500 người)
"""
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple
from loguru import logger

from utils.config import EMBEDDINGS_DIR, SIMILARITY_THRESHOLD
from utils.helpers import normalize_embedding, cosine_similarity


class FaceDatabase:
    """
    Database lưu face embeddings trong RAM, persist xuống file .npy.

    Structure:
        EMBEDDINGS_DIR/
            {student_id}.npy    ← embedding 512-d (hoặc trung bình N embeddings)

    Trong RAM:
        self._db: Dict[str, np.ndarray]   student_id → embedding (512,)
        self._names: Dict[str, str]        student_id → full_name
    """

    def __init__(self):
        self._db:    Dict[str, np.ndarray] = {}
        self._names: Dict[str, str]        = {}
        self._threshold = SIMILARITY_THRESHOLD

    def load_all(self, students: list):
        """
        Load tất cả embeddings từ file .npy và map với danh sách sinh viên.

        Args:
            students: List sqlite3.Row từ db.get_all_students()
        """
        self._db.clear()
        self._names.clear()

        loaded = 0
        for student in students:
            sid = str(student["id"])
            name = student["full_name"]
            self._names[sid] = name

            emb_path = EMBEDDINGS_DIR / f"{sid}.npy"
            if emb_path.exists():
                embedding = np.load(str(emb_path))
                self._db[sid] = normalize_embedding(embedding)
                loaded += 1

        logger.info(f"Loaded {loaded}/{len(students)} embeddings từ disk")

    def save_embedding(self, student_id: str | int, embedding: np.ndarray, name: str = ""):
        """
        Lưu/cập nhật embedding cho 1 sinh viên.

        Args:
            student_id: ID sinh viên (string hoặc int)
            embedding: (512,) hoặc (N, 512) — nếu nhiều ảnh sẽ lấy trung bình
            name: Tên sinh viên (để update cache)
        """
        sid = str(student_id)
        EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)

        # Nếu có nhiều embeddings thì lấy trung bình
        if embedding.ndim == 2:
            embedding = embedding.mean(axis=0)

        embedding = normalize_embedding(embedding)
        np.save(str(EMBEDDINGS_DIR / f"{sid}.npy"), embedding)

        # Update in-memory cache
        self._db[sid] = embedding
        if name:
            self._names[sid] = name

        logger.info(f"Saved embedding cho student_id={sid}")

    def delete_embedding(self, student_id: str | int):
        """Xóa embedding của sinh viên."""
        sid = str(student_id)
        emb_path = EMBEDDINGS_DIR / f"{sid}.npy"
        if emb_path.exists():
            emb_path.unlink()
        self._db.pop(sid, None)
        self._names.pop(sid, None)

    def match(self, query_embedding: np.ndarray) -> Tuple[Optional[str], str, float]:
        """
        Tìm sinh viên khớp nhất với query embedding.

        Args:
            query_embedding: (512,) float32, đã L2 normalized
        Returns:
            (student_id, name, confidence)
            student_id = None nếu không nhận ra
        """
        if not self._db:
            return None, "Unknown", 0.0

        best_id    = None
        best_score = -1.0

        for sid, emb in self._db.items():
            score = cosine_similarity(query_embedding, emb)
            if score > best_score:
                best_score = score
                best_id = sid

        if best_score >= self._threshold:
            name = self._names.get(best_id, "Unknown")
            return best_id, name, best_score

        return None, "Unknown", best_score

    def has_embedding(self, student_id: str | int) -> bool:
        return str(student_id) in self._db

    @property
    def count(self) -> int:
        return len(self._db)


# Singleton
face_db = FaceDatabase()
