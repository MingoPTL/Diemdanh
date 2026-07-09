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
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS students (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_code TEXT UNIQUE NOT NULL,    -- MSSV
    full_name   TEXT NOT NULL,
    class_id    INTEGER REFERENCES classes(id),
    photo_path  TEXT,
    registered  INTEGER DEFAULT 0,       -- 1 nếu đã đăng ký khuôn mặt
    created_at  TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id   INTEGER REFERENCES classes(id),
    title      TEXT,
    date       TEXT NOT NULL,            -- YYYY-MM-DD
    start_time TEXT,                     -- HH:MM
    end_time   TEXT,
    note       TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS attendance_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER REFERENCES sessions(id),
    student_id  INTEGER REFERENCES students(id),
    timestamp   TEXT NOT NULL,
    confidence  REAL,
    status      TEXT DEFAULT 'present'   -- present | late | absent
);

-- Index để tăng tốc truy vấn
CREATE INDEX IF NOT EXISTS idx_attendance_session ON attendance_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance_logs(student_id);
CREATE INDEX IF NOT EXISTS idx_students_class     ON students(class_id);
"""


def init_db():
    """Khởi tạo database và tạo bảng nếu chưa có."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
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


def get_all_students(class_id: int = None):
    with get_conn() as conn:
        if class_id:
            return conn.execute(
                "SELECT s.*, c.name as class_name FROM students s "
                "LEFT JOIN classes c ON s.class_id = c.id "
                "WHERE s.class_id = ? ORDER BY s.student_code",
                (class_id,)
            ).fetchall()
        return conn.execute(
            "SELECT s.*, c.name as class_name FROM students s "
            "LEFT JOIN classes c ON s.class_id = c.id ORDER BY s.student_code"
        ).fetchall()


def get_student_by_id(student_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM students WHERE id = ?", (student_id,)
        ).fetchone()


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


def add_class(name: str, code: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO classes (name, code) VALUES (?, ?)", (name, code)
        )
        return cur.lastrowid


def create_session(class_id: int, title: str, date: str, start_time: str, note: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (class_id, title, date, start_time, note) VALUES (?, ?, ?, ?, ?)",
            (class_id, title, date, start_time, note),
        )
        return cur.lastrowid


def log_attendance(session_id: int, student_id: int, confidence: float, status: str = "present"):
    """Ghi 1 bản ghi điểm danh. Chống trùng: kiểm tra trước khi ghi."""
    with get_conn() as conn:
        # Kiểm tra đã điểm danh trong session này chưa
        existing = conn.execute(
            "SELECT id FROM attendance_logs WHERE session_id = ? AND student_id = ?",
            (session_id, student_id),
        ).fetchone()
        if existing:
            return False  # Đã ghi rồi

        conn.execute(
            "INSERT INTO attendance_logs (session_id, student_id, timestamp, confidence, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, student_id, datetime.now().isoformat(), confidence, status),
        )
        return True


def get_attendance_by_session(session_id: int):
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT al.*, s.full_name, s.student_code
            FROM attendance_logs al
            JOIN students s ON al.student_id = s.id
            WHERE al.session_id = ?
            ORDER BY al.timestamp
            """,
            (session_id,),
        ).fetchall()


def get_sessions_by_class(class_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE class_id = ? ORDER BY date DESC, start_time DESC",
            (class_id,),
        ).fetchall()
