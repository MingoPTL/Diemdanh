"""
pages/0_🏠_Trang_Chu.py - Dashboard tổng quan hệ thống điểm danh
"""
import streamlit as st
from datetime import datetime

from utils.config import APP_TITLE, APP_ICON, APP_VERSION
import database.db as db
from services.face_db import face_db

# ── Custom CSS Modern Premium Dark Theme ──────────────────────────────────────
st.markdown("""
<style>
/* Font & Base Background */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Glassmorphism Metric cards */
div[data-testid="metric-container"] {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 18px 22px;
    box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
div[data-testid="metric-container"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 15px 35px -10px rgba(59, 130, 246, 0.25);
    border-color: rgba(59, 130, 246, 0.3);
}
div[data-testid="metric-container"] label {
    color: #94A3B8 !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #F8FAFC !important;
    font-size: 2.1rem !important;
    font-weight: 700 !important;
}

/* Custom Badges */
.badge-theory {
    background: rgba(59, 130, 246, 0.15);
    color: #60A5FA;
    border: 1px solid rgba(59, 130, 246, 0.3);
    padding: 4px 12px;
    border-radius: 9999px;
    font-size: 0.78rem;
    font-weight: 600;
}
.badge-practice {
    background: rgba(16, 185, 129, 0.15);
    color: #34D399;
    border: 1px solid rgba(16, 185, 129, 0.3);
    padding: 4px 12px;
    border-radius: 9999px;
    font-size: 0.78rem;
    font-weight: 600;
}

/* Section Header */
.section-header {
    font-size: 1.15rem;
    font-weight: 700;
    color: #38BDF8;
    border-left: 4px solid #3B82F6;
    padding-left: 12px;
    margin: 20px 0 14px 0;
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
st.markdown('<div class="section-header">🏫 Các lớp học đang quản lý</div>', unsafe_allow_html=True)

if not classes:
    st.info("Chưa có lớp học nào. Hãy vào menu **Quản Lý Lớp & Sinh Viên** để tạo lớp mới.", icon="ℹ️")
else:
    for cls in classes:
        sts = db.get_all_students(cls["id"])
        reg = sum(1 for s in sts if s["registered"])
        sessions = db.get_sessions_by_class(cls["id"])
        c_type = dict(cls).get("type", "Lý thuyết")
        badge_html = '<span class="badge-theory">📘 Lý thuyết</span>' if c_type == "Lý thuyết" else '<span class="badge-practice">🧪 Thực hành</span>'

        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            c1.markdown(f"**{cls['name']}** &nbsp; `{cls['code']}` &nbsp; {badge_html}", unsafe_allow_html=True)
            c2.metric("Sinh viên", len(sts))
            c3.metric("Đã đăng ký", f"{reg}/{len(sts)}")
            c4.metric("Số buổi học", len(sessions))

# ── Sidebar info ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"### {APP_ICON} {APP_TITLE}")
    st.caption(f"Phiên bản v{APP_VERSION}")
    st.divider()
    st.markdown("**📌 Hướng dẫn sử dụng:**")
    st.markdown("""
    1. 📋 **Quản Lý Lớp & Sinh Viên** → Tạo lớp, thêm SV hoặc chọn SV có sẵn từ lớp khác.
    2. 👤 **Đăng Ký Khuôn Mặt** → Chụp và lưu mẫu khuôn mặt AI cho SV.
    3. 📷 **Điểm Danh** → Quét đồng thời Khuôn mặt + Mã vạch / QR (Webcam / Camera Điện Thoại).
    4. 📊 **Báo Cáo & Xuất File** → Xem và xuất kết quả Excel chi tiết.
    """)
    st.divider()
    st.caption("🤖 AI Engine: SCRFD + ArcFace | Barcode: Code 128 / QR")
