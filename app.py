"""
app.py - Entry point chính của ứng dụng Streamlit
Trang chủ: Dashboard tổng quan + khởi tạo DB
"""
import streamlit as st
from datetime import datetime, date

from utils.config import APP_TITLE, APP_ICON, APP_VERSION
import database.db as db
from services.face_db import face_db

# ── Cấu hình trang ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Khởi tạo DB lần đầu ───────────────────────────────────────────────────────
db.init_db()

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Metric cards ── */
div[data-testid="metric-container"] {
    background: linear-gradient(135deg, #1C2333 0%, #16213E 100%);
    border: 1px solid #2D3748;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}
div[data-testid="metric-container"] label {
    color: #90CDF4 !important;
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #FFFFFF !important;
    font-size: 2rem !important;
    font-weight: 700 !important;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D1117 0%, #1A2035 100%);
    border-right: 1px solid #2D3748;
}

/* ── Status badge ── */
.badge-present { 
    background: #276749; color: #9AE6B4; 
    padding: 2px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 600;
}
.badge-absent  { 
    background: #742A2A; color: #FEB2B2; 
    padding: 2px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 600;
}
.badge-late    { 
    background: #744210; color: #FAF089; 
    padding: 2px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 600;
}

/* ── Section header ── */
.section-header {
    font-size: 1.1rem; font-weight: 700; color: #90CDF4;
    border-left: 3px solid #4F8EF7; padding-left: 10px;
    margin: 16px 0 10px 0;
}
</style>
""", unsafe_allow_html=True)


# ── Load face DB vào RAM ───────────────────────────────────────────────────────
@st.cache_resource
def load_face_db():
    students = db.get_all_students()
    face_db.load_all(students)
    return face_db

load_face_db()

# ── Header ────────────────────────────────────────────────────────────────────
col_icon, col_title = st.columns([0.06, 0.94])
with col_icon:
    st.markdown("## 📷")
with col_title:
    st.markdown(f"## {APP_TITLE}")
    st.caption(f"v{APP_VERSION} · {datetime.now().strftime('%A, %d/%m/%Y')}")

st.divider()

# ── Thống kê nhanh ────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📊 Tổng quan hệ thống</div>', unsafe_allow_html=True)

classes  = db.get_all_classes()
students = db.get_all_students()
registered = sum(1 for s in students if s["registered"])

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🏫 Số lớp học", len(classes))
with col2:
    st.metric("👥 Tổng sinh viên", len(students))
with col3:
    st.metric("✅ Đã đăng ký khuôn mặt", registered)
with col4:
    face_count = face_db.count
    st.metric("🧠 Embeddings trong DB", face_count)

st.divider()

# ── Danh sách lớp ─────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">🏫 Các lớp học</div>', unsafe_allow_html=True)

if not classes:
    st.info("Chưa có lớp học nào. Hãy vào **Quản Lý Lớp** để tạo lớp mới.", icon="ℹ️")
else:
    for cls in classes:
        sts = [s for s in students if s["class_id"] == cls["id"]]
        reg = sum(1 for s in sts if s["registered"])
        sessions = db.get_sessions_by_class(cls["id"])

        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            c1.markdown(f"**{cls['name']}** &nbsp; `{cls['code']}`")
            c2.metric("Sinh viên", len(sts))
            c3.metric("Đã đăng ký", f"{reg}/{len(sts)}")
            c4.metric("Số buổi học", len(sessions))

# ── Sidebar info ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"### {APP_ICON} {APP_TITLE}")
    st.caption(f"Version {APP_VERSION}")
    st.divider()
    st.markdown("**📌 Hướng dẫn nhanh:**")
    st.markdown("""
    1. 🏫 **Quản Lý Lớp** → Tạo lớp & thêm sinh viên
    2. 👤 **Đăng Ký** → Chụp khuôn mặt từng sinh viên
    3. 📷 **Điểm Danh** → Bắt đầu buổi học & camera nhận diện
    4. 📊 **Báo Cáo** → Xem & xuất Excel
    """)
    st.divider()
    st.caption("🤖 AI: SCRFD + ArcFace (ONNX GPU)")
