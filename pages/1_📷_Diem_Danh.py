"""
pages/1_📷_Diem_Danh.py
Trang điểm danh: Camera live → SCRFD detect → ArcFace match → ghi log
"""
import cv2
import numpy as np
import streamlit as st
import av
from datetime import datetime
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration

import database.db as db
from core.pipeline import pipeline
from services.face_db import face_db
from services.attendance import attendance_service
from utils.helpers import draw_face_box
from utils.config import SIMILARITY_THRESHOLD

st.set_page_config(page_title="Điểm Danh", page_icon="📷", layout="wide")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.attend-card {
    background: linear-gradient(135deg, #1A2035, #0F1117);
    border: 1px solid #276749; border-radius: 12px;
    padding: 12px 16px; margin: 4px 0;
    display: flex; align-items: center; gap: 12px;
}
.attend-name  { font-weight: 700; font-size: 1rem; color: #9AE6B4; }
.attend-code  { font-size: 0.8rem; color: #718096; }
.attend-time  { font-size: 0.75rem; color: #4A5568; margin-left: auto; }
.conf-badge   { font-size: 0.75rem; background: #276749; color: #9AE6B4;
                padding: 2px 8px; border-radius: 999px; }
.session-box  { background: #1C2333; border: 1px solid #4F8EF7;
                border-radius: 12px; padding: 16px; margin-bottom: 12px; }
</style>
""", unsafe_allow_html=True)

# ── Tiêu đề ───────────────────────────────────────────────────────────────────
st.markdown("## 📷 Điểm Danh Khuôn Mặt")
st.divider()

# ── Sidebar: chọn buổi học ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Cài đặt buổi học")
    classes = db.get_all_classes()
    if not classes:
        st.error("Chưa có lớp! Hãy tạo lớp ở trang Quản Lý Lớp.")
        st.stop()

    class_options = {f"{c['name']} ({c['code']})": c["id"] for c in classes}
    selected_class_label = st.selectbox("🏫 Chọn lớp", list(class_options.keys()))
    selected_class_id    = class_options[selected_class_label]

    session_title = st.text_input("📝 Tên buổi học", placeholder="VD: Buổi 1 - Nhập môn AI")
    st.divider()

    col_start, col_stop = st.columns(2)
    with col_start:
        if st.button("▶️ Bắt đầu", use_container_width=True, type="primary",
                     disabled=attendance_service.is_active):
            if not session_title.strip():
                st.warning("Nhập tên buổi học!")
            else:
                attendance_service.start_session(
                    class_id=selected_class_id,
                    title=session_title.strip(),
                )
                # Load face_db với lớp hiện tại
                students = db.get_all_students(selected_class_id)
                face_db.load_all(students)
                st.success("Đã bắt đầu buổi điểm danh!")
                st.rerun()

    with col_stop:
        if st.button("⏹ Kết thúc", use_container_width=True,
                     disabled=not attendance_service.is_active):
            attendance_service.stop_session()
            st.success("Đã kết thúc buổi!")
            st.rerun()

    st.divider()
    # Thống kê realtime
    if attendance_service.is_active:
        total_students = len(db.get_all_students(selected_class_id))
        attended       = len(attendance_service.get_attended_ids())
        st.metric("✅ Đã điểm danh", f"{attended} / {total_students}")
        progress = attended / max(total_students, 1)
        st.progress(progress)

    st.markdown(f"""
    **Ngưỡng nhận diện:** `{SIMILARITY_THRESHOLD}`  
    **Trạng thái:** {"🟢 Đang điểm danh" if attendance_service.is_active else "🔴 Chưa bắt đầu"}
    """)

# ── Layout chính ──────────────────────────────────────────────────────────────
col_cam, col_log = st.columns([3, 2])

# ── Session info banner ───────────────────────────────────────────────────────
if attendance_service.is_active:
    st.markdown(f"""
    <div class="session-box">
    🟢 <b>Đang điểm danh</b> · Session ID: <code>{attendance_service.session_id}</code>
    · Buổi: <b>{session_title}</b> · {datetime.now().strftime("%H:%M %d/%m/%Y")}
    </div>
    """, unsafe_allow_html=True)
else:
    st.info("⏸ Chưa có buổi điểm danh nào đang mở. Nhấn **▶️ Bắt đầu** ở sidebar.", icon="ℹ️")

# ── WebRTC callback ───────────────────────────────────────────────────────────
# Dùng session_state để truyền kết quả từ callback ra main thread
if "latest_results" not in st.session_state:
    st.session_state.latest_results = []
if "newly_attended" not in st.session_state:
    st.session_state.newly_attended = []

FRAME_COUNTER = {"n": 0}

def video_frame_callback(frame: av.VideoFrame) -> av.VideoFrame:
    """Callback xử lý mỗi frame từ camera."""
    img = frame.to_ndarray(format="bgr24")

    # Chỉ xử lý mỗi 2 frame để giảm tải
    FRAME_COUNTER["n"] += 1
    if FRAME_COUNTER["n"] % 2 != 0:
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return av.VideoFrame.from_ndarray(img_rgb, format="rgb24")

    # Pipeline nhận diện
    if pipeline.is_loaded:
        results = pipeline.process_frame(img, face_db)

        for res in results:
            draw_face_box(img, res.bbox, res.name, res.confidence)

            # Ghi điểm danh nếu nhận ra và session đang mở
            if res.student_id and attendance_service.is_active:
                attendance_service.mark_attendance(res.student_id, res.confidence)

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return av.VideoFrame.from_ndarray(img_rgb, format="rgb24")


# ── Camera stream ─────────────────────────────────────────────────────────────
with col_cam:
    st.markdown("### 🎥 Camera")

    # Kiểm tra models trước khi load
    from utils.config import SCRFD_MODEL_PATH, ARCFACE_MODEL_PATH
    models_missing = not SCRFD_MODEL_PATH.exists() or not ARCFACE_MODEL_PATH.exists()

    if models_missing:
        st.error("""
**⚠️ Chưa có model AI!**

Chạy lệnh sau trong Anaconda Prompt để tải models (~300MB):
```
python download_models.py
```
Sau đó reload lại trang này.
        """)
        st.stop()

    if not pipeline.is_loaded:
        with st.spinner("⏳ Đang load AI models lần đầu (GPU)..."):
            try:
                pipeline.load()
            except Exception as e:
                st.error(f"❌ Lỗi load model: {e}")
                st.stop()

    # Chọn phương thức điểm danh: Ảnh tĩnh hoặc Video trực tiếp
    cam_mode = st.radio(
        "Chọn phương thức quét:",
        ["Chụp ảnh tĩnh (Khuyên dùng - Nhẹ & Mượt)", "Video trực tiếp (WebRTC - Yêu cầu cấu hình tốt)"],
        horizontal=True
    )

    if cam_mode == "Chụp ảnh tĩnh (Khuyên dùng - Nhẹ & Mượt)":
        cam_img = st.camera_input("Nhìn vào camera và chụp ảnh lớp học")
        if cam_img is not None:
            # Decode ảnh
            img_bytes = cam_img.getvalue()
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            # Xử lý nhận diện
            if pipeline.is_loaded:
                with st.spinner("🧠 Đang quét khuôn mặt trong ảnh..."):
                    results = pipeline.process_frame(img, face_db)
                
                if not results:
                    st.warning("⚠️ Không phát hiện khuôn mặt nào trong bức ảnh vừa chụp.")
                else:
                    # Vẽ khung nhận dạng lên ảnh
                    for res in results:
                        draw_face_box(img, res.bbox, res.name, res.confidence)
                        # Ghi điểm danh nếu nhận diện khớp và session đang mở
                        if res.student_id and attendance_service.is_active:
                            attendance_service.mark_attendance(res.student_id, res.confidence)
                    
                    # Convert sang RGB để hiển thị lên Streamlit
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    st.image(img_rgb, caption="Kết quả nhận diện từ ảnh chụp", use_container_width=True)
                    st.success(f"🎉 Đã phát hiện {len(results)} khuôn mặt và cập nhật điểm danh!")
    else:
        rtc_config = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

        webrtc_streamer(
            key="attendance-cam",
            mode=WebRtcMode.SENDRECV,
            rtc_configuration=rtc_config,
            video_frame_callback=video_frame_callback,
            media_stream_constraints={"video": {"width": 1280, "height": 720}, "audio": False},
            async_processing=True,
        )

# ── Log điểm danh realtime ────────────────────────────────────────────────────
with col_log:
    st.markdown("### ✅ Danh sách điểm danh")

    if attendance_service.is_active:
        results = attendance_service.get_session_results()
        if not results:
            st.caption("Chưa có ai được điểm danh...")
        else:
            for r in reversed(results[-20:]):   # hiển thị 20 gần nhất
                time_str = r["timestamp"][11:16]  # HH:MM
                conf_pct = f"{r['confidence'] * 100:.0f}%"
                st.markdown(f"""
                <div class="attend-card">
                    <span>✅</span>
                    <div>
                        <div class="attend-name">{r['full_name']}</div>
                        <div class="attend-code">{r['student_code']}</div>
                    </div>
                    <span class="conf-badge">{conf_pct}</span>
                    <span class="attend-time">{time_str}</span>
                </div>
                """, unsafe_allow_html=True)

        if st.button("🔄 Làm mới danh sách", use_container_width=True):
            st.rerun()
    else:
        st.caption("Bắt đầu buổi học để xem log điểm danh.")
