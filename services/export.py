"""
export.py - Xuất báo cáo điểm danh ra Excel
"""
import pandas as pd
from datetime import datetime
from pathlib import Path
from io import BytesIO
from loguru import logger

import database.db as db


def export_session_to_excel(session_id: int) -> bytes:
    """
    Xuất kết quả 1 buổi điểm danh ra file Excel.

    Returns:
        bytes: nội dung file .xlsx (để Streamlit download)
    """
    rows = db.get_attendance_by_session(session_id)

    data = []
    for r in rows:
        data.append({
            "STT": len(data) + 1,
            "MSSV": r["student_code"],
            "Họ và Tên": r["full_name"],
            "Thời gian điểm danh": r["timestamp"][:19].replace("T", " "),
            "Độ tin cậy (%)": f"{r['confidence'] * 100:.1f}%",
            "Trạng thái": _translate_status(r["status"]),
        })

    df = pd.DataFrame(data)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Điểm Danh")

        # Style cơ bản
        ws = writer.sheets["Điểm Danh"]
        ws.column_dimensions["B"].width = 14
        ws.column_dimensions["C"].width = 28
        ws.column_dimensions["D"].width = 22
        ws.column_dimensions["E"].width = 18
        ws.column_dimensions["F"].width = 14

    buf.seek(0)
    return buf.read()


def export_class_summary_to_excel(class_id: int) -> bytes:
    """
    Xuất tổng hợp điểm danh của cả lớp (tất cả buổi) ra Excel.

    Returns:
        bytes: nội dung file .xlsx
    """
    sessions = db.get_sessions_by_class(class_id)
    students = db.get_all_students(class_id)

    # Tạo pivot table: rows=sinh viên, cols=buổi học
    session_ids   = [s["id"] for s in sessions]
    session_dates = [f"{s['date']} {s['start_time'] if s['start_time'] is not None else ''}" for s in sessions]

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
            "MSSV": student_codes[st["id"]],
            "Họ và Tên": student_names[st["id"]],
        }
        total_present = 0
        for sid, date_str in zip(session_ids, session_dates):
            status = attendance_map[sid].get(st["id"], "absent")
            row[date_str] = _translate_status(status)
            if status in ("present", "late"):
                total_present += 1
        row["Số buổi có mặt"] = total_present
        row["Tổng buổi"] = len(session_ids)
        row["Tỉ lệ (%)"] = f"{total_present / max(len(session_ids), 1) * 100:.1f}%"
        records.append(row)

    df = pd.DataFrame(records)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Tổng hợp")

    buf.seek(0)
    return buf.read()


def _translate_status(status: str) -> str:
    return {"present": "Có mặt", "late": "Muộn", "absent": "Vắng"}.get(status, status)
