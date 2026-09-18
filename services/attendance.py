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
    Tự động xác định 'present' (có mặt) vs 'late' (đi muộn) dựa theo thời gian.
    Tự động ghi nhận 'absent' (vắng) cho sinh viên còn lại khi kết thúc buổi.
    """

    def __init__(self):
        self._current_session_id: Optional[int] = None
        self._class_id: Optional[int] = None
        self._start_time_str: str = "08:00"
        self._late_time_str: str = "08:15"
        self._session_type: str = "Lý thuyết"
        self._recognized_in_session: set = set()  # student_id đã điểm danh

    def start_session(
        self, 
        class_id: int, 
        title: str, 
        start_time: str = "", 
        late_time: str = "", 
        session_type: str = "Lý thuyết",
        note: str = ""
    ) -> int:
        """Tạo buổi điểm danh mới với thông số thời gian & loại buổi học."""
        now = datetime.now()
        start_time = start_time or now.strftime("%H:%M")
        late_time = late_time or start_time

        session_id = db.create_session(
            class_id=class_id,
            title=title,
            date=now.strftime("%Y-%m-%d"),
            start_time=start_time,
            late_time=late_time,
            session_type=session_type,
            note=note,
        )
        self._current_session_id = session_id
        self._class_id = class_id
        self._start_time_str = start_time
        self._late_time_str = late_time
        self._session_type = session_type
        self._recognized_in_session.clear()

        logger.info(
            f"Bắt đầu buổi điểm danh ID={session_id}: {title} ({session_type}) | "
            f"Bắt đầu: {start_time}, Tính trễ sau: {late_time}"
        )
        return session_id

    def stop_session(self) -> dict:
        """
        Kết thúc buổi điểm danh hiện tại.
        Tự động chèn trạng thái 'absent' cho các sinh viên chưa được quét mặt.
        Returns:
            dict chứa thống kê (present, late, absent)
        """
        stats = {"present": 0, "late": 0, "absent": 0}
        if self._current_session_id and self._class_id:
            # Ghi nhận Vắng cho sinh viên chưa điểm danh
            absent_count = db.mark_absent_for_unrecorded_students(
                session_id=self._current_session_id,
                class_id=self._class_id
            )
            # Thống kê tổng hợp kết quả buổi học
            logs = db.get_attendance_by_session(self._current_session_id)
            for log in logs:
                st = log["status"]
                if st in stats:
                    stats[st] += 1

            logger.info(
                f"Kết thúc buổi ID={self._current_session_id}: "
                f"Có mặt: {stats['present']}, Đi muộn: {stats['late']}, Vắng: {stats['absent']}"
            )

        self._current_session_id = None
        self._class_id = None
        self._recognized_in_session.clear()
        return stats

    @property
    def session_id(self) -> Optional[int]:
        return self._current_session_id

    @property
    def is_active(self) -> bool:
        return self._current_session_id is not None

    @property
    def late_time_str(self) -> str:
        return self._late_time_str

    def calculate_status(self) -> str:
        """Tính toán trạng thái 'present' hay 'late' dựa trên thời gian thực hiện quét mặt."""
        if not self._late_time_str:
            return "present"
        now_str = datetime.now().strftime("%H:%M")
        # So sánh HH:MM dạng string
        if now_str > self._late_time_str:
            return "late"
        return "present"

    def mark_attendance(
        self,
        student_id: str,
        confidence: float,
        override_status: Optional[str] = None,
    ) -> bool:
        """
        Ghi điểm danh cho sinh viên.
        Tự động xác định 'present' hay 'late' nếu không chỉ định override_status.
        """
        if not self.is_active:
            logger.warning("Chưa có buổi điểm danh nào đang mở")
            return False

        # Chống ghi trùng
        if student_id in self._recognized_in_session:
            return False

        status = override_status or self.calculate_status()

        success = db.log_attendance(
            session_id=self._current_session_id,
            student_id=int(student_id),
            confidence=confidence,
            status=status,
        )

        if success:
            self._recognized_in_session.add(student_id)
            logger.info(f"✅ Điểm danh [{status.upper()}]: student_id={student_id}, conf={confidence:.3f}")

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
