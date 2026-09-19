"""
db.py - Kết nối SQLite + định nghĩa schema + helper queries
Hỗ trợ quan hệ nhiều-nhiều: 1 sinh viên có thể học nhiều lớp (Lý thuyết, Thực hành, nhiều môn...)
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
    student_code TEXT UNIQUE NOT NULL,    -- MSSV toàn hệ thống
    full_name    TEXT NOT NULL,
    class_id     INTEGER REFERENCES classes(id), -- Lớp gốc ban đầu (nếu có)
    photo_path   TEXT,
    registered   INTEGER DEFAULT 0,       -- 1 nếu đã đăng ký khuôn mặt
    created_at   TEXT DEFAULT (datetime('now', 'localtime'))
);

-- Bảng phân lớp nhiều-nhiều: 1 sinh viên có thể thuộc nhiều lớp
CREATE TABLE IF NOT EXISTS student_classes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
    class_id   INTEGER REFERENCES classes(id) ON DELETE CASCADE,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(student_id, class_id)
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
CREATE INDEX IF NOT EXISTS idx_student_classes_cid ON student_classes(class_id);
CREATE INDEX IF NOT EXISTS idx_student_classes_sid ON student_classes(student_id);
"""


def init_db():
    """Khởi tạo database và chạy tự động migration nếu thiếu cột hoặc bảng."""
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

        # Migration: Tự động đồng bộ sinh viên cũ vào bảng student_classes
        conn.execute("""
            INSERT OR IGNORE INTO student_classes (student_id, class_id)
            SELECT id, class_id FROM students WHERE class_id IS NOT NULL AND class_id > 0
        """)

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
    """
    Lấy danh sách sinh viên:
    - Nếu có class_id: Lấy tất cả sinh viên được phân vào lớp này (qua student_classes).
    - Nếu không có class_id: Lấy tất cả sinh viên toàn trường kèm danh sách các lớp đang học.
    """
    with get_conn() as conn:
        if class_id:
            return conn.execute(
                """
                SELECT s.*, c.name as class_name, c.type as class_type, sc.class_id
                FROM student_classes sc
                JOIN students s ON sc.student_id = s.id
                JOIN classes c ON sc.class_id = c.id
                WHERE sc.class_id = ?
                ORDER BY s.student_code
                """,
                (class_id,)
            ).fetchall()
        return conn.execute(
            """
            SELECT s.*, 
                   COALESCE(GROUP_CONCAT(c.name || ' (' || c.type || ')', ', '), '—') as class_names,
                   COUNT(sc.class_id) as enrolled_classes_count
            FROM students s
            LEFT JOIN student_classes sc ON s.id = sc.student_id
            LEFT JOIN classes c ON sc.class_id = c.id
            GROUP BY s.id
            ORDER BY s.student_code
            """
        ).fetchall()


def get_global_students():
    """Lấy danh sách tất cả sinh viên duy nhất trong hệ thống."""
    with get_conn() as conn:
        return conn.execute("SELECT * FROM students ORDER BY student_code").fetchall()


def get_student_by_id(student_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM students WHERE id = ?", (student_id,)
        ).fetchone()


def get_student_class_ids(student_id: int) -> set:
    """Lấy tập hợp các class_id mà sinh viên này đang tham gia."""
    with get_conn() as conn:
        rows = conn.execute("SELECT class_id FROM student_classes WHERE student_id = ?", (student_id,)).fetchall()
        return {r["class_id"] for r in rows}


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
            "SELECT * FROM students WHERE LOWER(student_code) = LOWER(?)",
            (raw_code,)
        ).fetchone()
        if row:
            return row

        # 2. Tìm thông minh nếu mã thẻ chứa MSSV
        all_students = conn.execute("SELECT * FROM students").fetchall()
        for s in all_students:
            s_code = str(s["student_code"]).strip()
            if s_code and (s_code.lower() in raw_code.lower() or raw_code.lower() in s_code.lower()):
                return s

    return None


def add_student(student_code: str, full_name: str, class_id: int = None) -> int:
    """
    Thêm sinh viên:
    - Nếu MSSV chưa có -> Tạo mới trong bảng students.
    - Nếu MSSV đã có -> Cập nhật tên (nếu có) và không báo lỗi.
    - Nếu có class_id -> Tự động ghi danh sinh viên vào lớp đó (trong bảng student_classes).
    """
    student_code = student_code.strip()
    full_name = full_name.strip()

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM students WHERE LOWER(student_code) = LOWER(?)",
            (student_code,)
        ).fetchone()

        if existing:
            student_id = existing["id"]
            if full_name:
                conn.execute("UPDATE students SET full_name = ? WHERE id = ?", (full_name, student_id))
        else:
            cur = conn.execute(
                "INSERT INTO students (student_code, full_name, class_id) VALUES (?, ?, ?)",
                (student_code, full_name, class_id),
            )
            student_id = cur.lastrowid

        if class_id:
            conn.execute(
                "INSERT OR IGNORE INTO student_classes (student_id, class_id) VALUES (?, ?)",
                (student_id, class_id)
            )

        return student_id


def enroll_student_to_class(student_id: int, class_id: int) -> bool:
    """Ghi danh 1 sinh viên đã có vào 1 lớp mới. Trả về True nếu thành công, False nếu đã có trong lớp."""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO student_classes (student_id, class_id) VALUES (?, ?)",
            (student_id, class_id)
        )
        return cur.rowcount > 0


def remove_student_from_class(student_id: int, class_id: int) -> bool:
    """Xóa sinh viên khỏi 1 lớp cụ thể (vẫn giữ thông tin sinh viên và embedding trong hệ thống)."""
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM student_classes WHERE student_id = ? AND class_id = ?",
            (student_id, class_id)
        )
        return True


def delete_student_globally(student_id: int):
    """Xóa vĩnh viễn sinh viên khỏi toàn bộ hệ thống."""
    with get_conn() as conn:
        conn.execute("DELETE FROM student_classes WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM attendance_logs WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))


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


def delete_class(class_id: int):
    """Xóa lớp học và các liên kết ghi danh."""
    with get_conn() as conn:
        conn.execute("DELETE FROM student_classes WHERE class_id = ?", (class_id,))
        conn.execute("DELETE FROM sessions WHERE class_id = ?", (class_id,))
        conn.execute("DELETE FROM classes WHERE id = ?", (class_id,))


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
        students = conn.execute(
            """
            SELECT s.id FROM student_classes sc
            JOIN students s ON sc.student_id = s.id
            WHERE sc.class_id = ?
            """,
            (class_id,)
        ).fetchall()
        
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
                    "INSERT INTO attendance_logs (session_id, student_id, timestamp, confidence, status, method) "
                    "VALUES (?, ?, ?, ?, 'absent', 'face')",
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
