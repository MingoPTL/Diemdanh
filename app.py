"""
app.py - Entry point chính của ứng dụng Streamlit
Sử dụng st.navigation để hiển thị Menu điều hướng Tiếng Việt có dấu chuẩn đẹp
"""
import streamlit as st
from utils.config import APP_TITLE, APP_ICON
import database.db as db

# ── Cấu hình trang toàn cục ───────────────────────────────────────────────────
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Khởi tạo DB & Migration ───────────────────────────────────────────────────
db.init_db()

# ── Khởi tạo Navigation với Tiếng Việt có dấu chuẩn đẹp ───────────────────────
pages = [
    st.Page("pages/0_🏠_Trang_Chu.py", title="Trang Chủ Dashboard", icon="🏠", default=True),
    st.Page("pages/1_📷_Diem_Danh.py", title="Điểm Danh", icon="📷"),
    st.Page("pages/2_👤_Dang_Ky.py", title="Đăng Ký Khuôn Mặt", icon="👤"),
    st.Page("pages/3_📋_Quan_Ly_Lop.py", title="Quản Lý Lớp & Sinh Viên", icon="📋"),
    st.Page("pages/4_📊_Bao_Cao.py", title="Báo Cáo & Xuất File", icon="📊"),
]

pg = st.navigation(pages)
pg.run()
