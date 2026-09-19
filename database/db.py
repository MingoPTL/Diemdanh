"""
db.py - Kết nối SQLite + định nghĩa schema + helper queries
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from loguru import logger

from utils.config import DATABASE_PATH


# ── Schema SQL ────────────────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS classes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    code       TEXT UNIQUE NOT NULL,
    type       TEXT DEFAULT 'Lý thuyết', -- 'Lý thuyết' | 'Thực hành'
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS students (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    student_code TEXT UNIQUE NOT NULL,    -- MSSV
    full_name    TEXT NOT NULL,
    class_id     INTEGER REFERENCES classes(id),
    photo_path   TEXT,
    registered   INTEGER DEFAULT 0,       -- 1 nếu đã đăng ký khuôn mặt
    created_at   TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id     INTEGER REFERENCES classes(id),
    title        TEXT,
    date         TEXT NOT NULL,            -- YYYY-MM-DD
    start_time   TEXT,                     -- HH:MM
    late_time    TEXT,                     -- HH:MM (mốc thời gian bắt đầu tính đi muộn)
    session_type TEXT DEFAULT 'Lý thuyết', -- 'Lý thuyết' | 'Thực hành'
    end_time     TEXT,
    note         TEXT,
    created_at   TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS attendance_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER REFERENCES sessions(id),
    student_id  INTEGER REFERENCES students(id),
    timestamp   TEXT NOT NULL,
    confidence  REAL,
    status      TEXT DEFAULT 'present',  -- present | late | absent
    method      TEXT DEFAULT 'face'     -- 'face' | 'barcode'
);

-- Index để tăng tốc truy vấn
CREATE INDEX IF NOT EXISTS idx_attendance_session ON attendance_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance_logs(student_id);
CREATE INDEX IF NOT EXISTS idx_students_class     ON students(class_id);
"""


def init_db():
    """Khởi tạo database và chạy tự động migration nếu thiếu cột."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)

        # Migration: Kiểm tra và bổ sung cột 'type' trong 'classes' nếu DB cũ chưa có
        class_cols = [row["name"] for row in conn.execute("PRAGMA table_info(classes)").fetchall()]
        if "type" not in class_cols:
            conn.execute("ALTER TABLE classes ADD COLUMN type TEXT DEFAULT 'Lý thuyết'")
            logger.info("MIGRATION: Đã thêm cột 'type' vào bảng classes")

        # Migration: Kiểm tra và bổ sung cột trong 'sessions' nếu DB cũ chưa có
        session_cols = [row["name"] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()]
        if "late_time" not in session_cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN late_time TEXT")
            logger.info("MIGRATION: Đã thêm cột 'late_time' vào bảng sessions")
        if "session_type" not in session_cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN session_type TEXT DEFAULT 'Lý thuyết'")
            logger.info("MIGRATION: Đã thêm cột 'session_type' vào bảng sessions")

        # Migration: Kiểm tra và bổ sung cột 'method' trong 'attendance_logs' nếu DB cũ chưa có
        attend_cols = [row["name"] for row in conn.execute("PRAGMA table_info(attendance_logs)").fetchall()]
        if "method" not in attend_cols:
            conn.execute("ALTER TABLE attendance_logs ADD COLUMN method TEXT DEFAULT 'face'")
            logger.info("MIGRATION: Đã thêm cột 'method' vào bảng attendance_logs")

    logger.info(f"Database sẵn sàng tại: {DATABASE_PATH}")


@contextmanager
def get_conn():
    """Context manager trả về SQLite connection."""
    conn = sqlite3.connect(str(DATABASE_PATH), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row    # trả về dict-like rows
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # tăng tốc write
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"DB error: {e}")
        raise
    finally:
        conn.close()


# ── Helper CRUD ───────────────────────────────────────────────────────────────

def get_all_classes():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM classes ORDER BY name").fetchall()


def get_class_by_id(class_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM classes WHERE id = ?", (class_id,)).fetchone()


def get_all_students(class_id: int = None):
    with get_conn() as conn:
        if class_id:
            return conn.execute(
                "SELECT s.*, c.name as class_name, c.type as class_type FROM students s "
                "LEFT JOIN classes c ON s.class_id = c.id "
                "WHERE s.class_id = ? ORDER BY s.student_code",
                (class_id,)
            ).fetchall()
        return conn.execute(
            "SELECT s.*, c.name as class_name, c.type as class_type FROM students s "
            "LEFT JOIN classes c ON s.class_id = c.id ORDER BY s.student_code"
        ).fetchall()


def get_student_by_id(student_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM students WHERE id = ?", (student_id,)
        ).fetchone()


def get_student_by_code(student_code: str):
    """
    Tìm sinh viên theo MSSV:
    1. Khớp chính xác (exact match).
    2. Khớp thông minh nếu thẻ trường có chứa tiền tố/hậu tố (ví dụ 'SV2251050001').
    """
    raw_code = str(student_code).strip()
    if not raw_code:
        return None

    with get_conn() as conn:
        # 1. Khớp chính xác không phân biệt hoa thường
        row = conn.execute(
            "SELECT s.*, c.name as class_name, c.type as class_type FROM students s "
            "LEFT JOIN classes c ON s.class_id = c.id WHERE LOWER(s.student_code) = LOWER(?)",
            (raw_code,)
        ).fetchone()
        if row:
            return row

        # 2. Tìm thông minh nếu mã thẻ chứa MSSV
        all_students = conn.execute(
            "SELECT s.*, c.name as class_name, c.type as class_type FROM students s "
            "LEFT JOIN classes c ON s.class_id = c.id"
        ).fetchall()
        for s in all_students:
            s_code = str(s["student_code"]).strip()
            if s_code and (s_code.lower() in raw_code.lower() or raw_code.lower() in s_code.lower()):
                return s

    return None


def add_student(student_code: str, full_name: str, class_id: int) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO students (student_code, full_name, class_id) VALUES (?, ?, ?)",
            (student_code, full_name, class_id),
        )
        return cur.lastrowid


def update_student_registered(student_id: int, photo_path: str = None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE students SET registered = 1, photo_path = ? WHERE id = ?",
            (photo_path, student_id),
        )


def add_class(name: str, code: str, class_type: str = "Lý thuyết") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO classes (name, code, type) VALUES (?, ?, ?)", 
            (name, code, class_type)
        )
        return cur.lastrowid


def create_session(
    class_id: int, 
    title: str, 
    date: str, 
    start_time: str, 
    late_time: str = "", 
    session_type: str = "Lý thuyết",
    note: str = ""
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (class_id, title, date, start_time, late_time, session_type, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (class_id, title, date, start_time, late_time, session_type, note),
        )
        return cur.lastrowid


def log_attendance(
    session_id: int, 
    student_id: int, 
    confidence: float, 
    status: str = "present",
    method: str = "face"
):
    """Ghi 1 bản ghi điểm danh (Khuôn mặt hoặc Mã vạch). Chống trùng: kiểm tra trước khi ghi."""
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM attendance_logs WHERE session_id = ? AND student_id = ?",
            (session_id, student_id),
        ).fetchone()
        if existing:
            return False  # Đã ghi rồi

        conn.execute(
            "INSERT INTO attendance_logs (session_id, student_id, timestamp, confidence, status, method) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, student_id, datetime.now().isoformat(), confidence, status, method),
        )
        return True


def mark_absent_for_unrecorded_students(session_id: int, class_id: int):
    """
    Tự động đánh dấu status = 'absent' cho tất cả sinh viên trong lớp 
    chưa thực hiện điểm danh trong buổi này.
    """
    with get_conn() as conn:
        students = conn.execute("SELECT id FROM students WHERE class_id = ?", (class_id,)).fetchall()
        logged_rows = conn.execute(
            "SELECT student_id FROM attendance_logs WHERE session_id = ?", (session_id,)
        ).fetchall()
        logged_ids = {r["student_id"] for r in logged_rows}
        
        now_str = datetime.now().isoformat()
        absent_count = 0
        for st in students:
            st_id = st["id"]
            if st_id not in logged_ids:
                conn.execute(
                    "INSERT INTO attendance_logs (session_id, student_id, timestamp, confidence, status) "
                    "VALUES (?, ?, ?, ?, 'absent')",
                    (session_id, st_id, now_str, 0.0),
                )
                absent_count += 1
        return absent_count


def get_attendance_by_session(session_id: int):
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT al.*, s.full_name, s.student_code
            FROM attendance_logs al
            JOIN students s ON al.student_id = s.id
            WHERE al.session_id = ?
            ORDER BY al.status ASC, al.timestamp ASC
            """,
            (session_id,),
        ).fetchall()


def get_sessions_by_class(class_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE class_id = ? ORDER BY date DESC, start_time DESC",
            (class_id,),
        ).fetchall()
