"""
attendance.py - Logic nghiệp vụ điểm danh
"""
from datetime import datetime
from typing import Optional
from loguru import logger

import database.db as db
from utils.config import COOLDOWN_SECONDS


class AttendanceService:
    """
    Quản lý logic điểm danh trong 1 buổi học.
    Chống ghi trùng: mỗi sinh viên chỉ ghi 1 lần / buổi.
    """

    def __init__(self):
        self._current_session_id: Optional[int] = None
        self._recognized_in_session: set = set()  # student_id đã điểm danh

    def start_session(self, class_id: int, title: str, note: str = "") -> int:
        """Tạo buổi điểm danh mới."""
        now = datetime.now()
        session_id = db.create_session(
            class_id=class_id,
            title=title,
            date=now.strftime("%Y-%m-%d"),
            start_time=now.strftime("%H:%M"),
            note=note,
        )
        self._current_session_id = session_id
        self._recognized_in_session.clear()
        logger.info(f"Bắt đầu buổi điểm danh ID={session_id}: {title}")
        return session_id

    def stop_session(self):
        """Kết thúc buổi điểm danh hiện tại."""
        if self._current_session_id:
            logger.info(f"Kết thúc buổi điểm danh ID={self._current_session_id}")
        self._current_session_id = None
        self._recognized_in_session.clear()

    @property
    def session_id(self) -> Optional[int]:
        return self._current_session_id

    @property
    def is_active(self) -> bool:
        return self._current_session_id is not None

    def mark_attendance(
        self,
        student_id: str,
        confidence: float,
        status: str = "present",
    ) -> bool:
        """
        Ghi điểm danh cho sinh viên.

        Args:
            student_id: ID sinh viên (string)
            confidence: Độ tin cậy nhận diện
            status: 'present' | 'late' | 'absent'
        Returns:
            True nếu ghi thành công, False nếu đã ghi rồi hoặc không có session
        """
        if not self.is_active:
            logger.warning("Chưa có buổi điểm danh nào đang mở")
            return False

        # Chống ghi trùng
        if student_id in self._recognized_in_session:
            return False

        success = db.log_attendance(
            session_id=self._current_session_id,
            student_id=int(student_id),
            confidence=confidence,
            status=status,
        )

        if success:
            self._recognized_in_session.add(student_id)
            logger.info(f"✅ Điểm danh: student_id={student_id}, conf={confidence:.3f}")

        return success

    def get_attended_ids(self) -> set:
        """Danh sách student_id đã điểm danh trong buổi hiện tại."""
        return self._recognized_in_session.copy()

    def get_session_results(self):
        """Lấy kết quả điểm danh buổi hiện tại từ DB."""
        if not self._current_session_id:
            return []
        return db.get_attendance_by_session(self._current_session_id)


# Singleton
attendance_service = AttendanceService()
