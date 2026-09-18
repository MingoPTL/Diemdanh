"""
export.py - Xuất báo cáo điểm danh ra Excel
"""
import pandas as pd
from datetime import datetime
from pathlib import Path
from io import BytesIO
from loguru import logger

import database.db as db


def export_session_to_excel(
    session_id: int,
    class_name: str = "",
    session_type: str = "",
) -> bytes:
    """
    Xuất kết quả 1 buổi điểm danh ra file Excel.
    Các cột bao gồm: STT, MSSV, Họ và Tên, Lớp, Loại môn,
                      Tên buổi, Giờ Check-in, Trạng thái.

    Returns:
        bytes: nội dung file .xlsx (để Streamlit download)
    """
    rows = db.get_attendance_by_session(session_id)

    # Lấy thông tin session để điền vào cột
    with db.get_conn() as conn:
        sess = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()

    sess_title     = sess["title"] if sess else ""
    sess_date      = sess["date"]  if sess else ""
    sess_start     = sess["start_time"] if sess else ""
    resolved_type  = session_type or (dict(sess).get("session_type", "Lý thuyết") if sess else "Lý thuyết")

    data = []
    for r in rows:
        checkin_time = r["timestamp"][11:19] if r["confidence"] > 0 else "—"
        data.append({
            "STT":                len(data) + 1,
            "MSSV":               r["student_code"],
            "Họ và Tên":          r["full_name"],
            "Lớp":                class_name,
            "Loại môn":           resolved_type,
            "Tên buổi học":       sess_title,
            "Ngày":               sess_date,
            "Giờ bắt đầu":        sess_start,
            "Giờ Check-in":       checkin_time,
            "Trạng thái":         _translate_status(r["status"]),
        })

    df = pd.DataFrame(data)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Điểm Danh")

        ws = writer.sheets["Điểm Danh"]
        # Độ rộng cột
        col_widths = {
            "A": 6,   # STT
            "B": 14,  # MSSV
            "C": 28,  # Họ và Tên
            "D": 24,  # Lớp
            "E": 14,  # Loại môn
            "F": 28,  # Tên buổi học
            "G": 14,  # Ngày
            "H": 14,  # Giờ bắt đầu
            "I": 14,  # Giờ Check-in
            "J": 14,  # Trạng thái
        }
        for col, width in col_widths.items():
            ws.column_dimensions[col].width = width

    buf.seek(0)
    return buf.read()


def export_class_summary_to_excel(class_id: int) -> bytes:
    """
    Xuất tổng hợp điểm danh của cả lớp (tất cả buổi) ra Excel.
    Pivot table: Rows = sinh viên, Cols = buổi học.

    Returns:
        bytes: nội dung file .xlsx
    """
    sessions = db.get_sessions_by_class(class_id)
    students = db.get_all_students(class_id)

    session_ids = [s["id"] for s in sessions]
    session_labels = [
        "{} {} ({})".format(
            s["date"],
            s["title"] or "Buổi học",
            dict(s).get("session_type", "LT")[:2],
        )
        for s in sessions
    ]

    student_codes = {s["id"]: s["student_code"] for s in students}
    student_names = {s["id"]: s["full_name"]    for s in students}

    # Collect attendance per session
    attendance_map = {}
    for sid in session_ids:
        rows = db.get_attendance_by_session(sid)
        attendance_map[sid] = {r["student_id"]: r["status"] for r in rows}

    # Build dataframe
    records = []
    for st in students:
        row = {
            "MSSV":       student_codes[st["id"]],
            "Họ và Tên":  student_names[st["id"]],
        }
        total_present = 0
        for sid, label in zip(session_ids, session_labels):
            status = attendance_map[sid].get(st["id"], "absent")
            row[label] = _translate_status(status)
            if status in ("present", "late"):
                total_present += 1
        row["Số buổi có mặt"] = total_present
        row["Tổng buổi"]      = len(session_ids)
        row["Tỉ lệ (%)"]      = "{:.1f}%".format(total_present / max(len(session_ids), 1) * 100)
        records.append(row)

    df = pd.DataFrame(records)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Tổng hợp")
        ws = writer.sheets["Tổng hợp"]
        ws.column_dimensions["A"].width = 14
        ws.column_dimensions["B"].width = 28

    buf.seek(0)
    return buf.read()


def _translate_status(status: str) -> str:
    return {"present": "Có mặt", "late": "Đi muộn", "absent": "Vắng mặt"}.get(status, status)
