"""
pages/1_📷_Diem_Danh.py
Trang điểm danh: Camera live / Chụp ảnh → SCRFD detect → ArcFace match → Ghi log (Có mặt / Đi muộn / Vắng)
"""
import cv2
import numpy as np
import streamlit as st
import av
from datetime import datetime, timedelta, time
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration

import database.db as db
from core.pipeline import pipeline
from services.face_db import face_db
from services.attendance import attendance_service
from utils.helpers import draw_face_box
from utils.config import SIMILARITY_THRESHOLD

st.set_page_config(page_title="Điểm Danh", page_icon="📷", layout="wide")

# ── CSS Styling ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
.attend-card {
    background: rgba(30, 41, 59, 0.7);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 12px 16px; margin: 6px 0;
    display: flex; align-items: center; gap: 12px;
}
.attend-name  { font-weight: 700; font-size: 0.98rem; color: #F8FAFC; }
.attend-code  { font-size: 0.8rem; color: #94A3B8; }
.attend-time  { font-size: 0.75rem; color: #64748B; margin-left: auto; }

.badge-present { 
    background: rgba(16, 185, 129, 0.2); color: #34D399; 
    border: 1px solid rgba(16, 185, 129, 0.4);
    padding: 2px 10px; border-radius: 9999px; font-size: 0.78rem; font-weight: 600;
}
.badge-late    { 
    background: rgba(245, 158, 11, 0.2); color: #FBBF24; 
    border: 1px solid rgba(245, 158, 11, 0.4);
    padding: 2px 10px; border-radius: 9999px; font-size: 0.78rem; font-weight: 600;
}
.badge-absent  { 
    background: rgba(239, 68, 68, 0.2); color: #F87171; 
    border: 1px solid rgba(239, 68, 68, 0.4);
    padding: 2px 10px; border-radius: 9999px; font-size: 0.78rem; font-weight: 600;
}
.badge-theory {
    background: rgba(59, 130, 246, 0.2); color: #60A5FA;
    border: 1px solid rgba(59, 130, 246, 0.4);
    padding: 2px 10px; border-radius: 9999px; font-size: 0.78rem; font-weight: 600;
}
.badge-practice {
    background: rgba(16, 185, 129, 0.2); color: #34D399;
    border: 1px solid rgba(16, 185, 129, 0.4);
    padding: 2px 10px; border-radius: 9999px; font-size: 0.78rem; font-weight: 600;
}

.session-box {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9));
    border: 1px solid rgba(59, 130, 246, 0.4);
    border-radius: 14px; padding: 16px 20px; margin-bottom: 16px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}
</style>
""", unsafe_allow_html=True)

# ── Tiêu đề ───────────────────────────────────────────────────────────────────
st.markdown("## 📷 Điểm Danh Khuôn Mặt")
st.divider()

if "last_session_stats" not in st.session_state:
    st.session_state.last_session_stats = None

# ── Sidebar: chọn buổi học ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Cài đặt buổi học")
    classes = db.get_all_classes()
    if not classes:
        st.error("Chưa có lớp! Hãy tạo lớp ở trang Quản Lý Lớp.")
        st.stop()

    class_options = {
        f"{c['name']} - {dict(c).get('type','Lý thuyết')} ({c['code']})": c
        for c in classes
    }
    selected_class_label = st.selectbox("🏫 Chọn lớp học", list(class_options.keys()))
    selected_class       = class_options[selected_class_label]
    selected_class_id    = selected_class["id"]
    class_type           = dict(selected_class).get("type", "Lý thuyết")

    badge_html = '<span class="badge-theory">📘 Lý thuyết</span>' if class_type == "Lý thuyết" else '<span class="badge-practice">🧪 Thực hành</span>'
    st.markdown(f"**Loại môn:** {badge_html}", unsafe_allow_html=True)

    session_title = st.text_input("📝 Tên buổi học", placeholder="VD: Buổi 1 - Nhập môn AI")
    
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        start_time_val = st.time_input("⏰ Giờ bắt đầu", value=datetime.now().time())
    with col_t2:
        grace_mins = st.number_input("⏱️ Phút trễ cho phép", min_value=0, max_value=120, value=15, step=5)

    # Tính mốc thời gian tính đi muộn
    dummy_date = datetime.now().date()
    dt_start = datetime.combine(dummy_date, start_time_val)
    dt_late  = dt_start + timedelta(minutes=grace_mins)
    start_time_str = start_time_val.strftime("%H:%M")
    late_time_str  = dt_late.strftime("%H:%M")

    st.caption(f"📌 Mốc tính đi muộn: `{late_time_str}` *(Quét mặt sau {late_time_str} sẽ tính là Đi muộn)*")

    st.divider()

    col_start, col_stop = st.columns(2)
    with col_start:
        if st.button("▶️ Bắt đầu", use_container_width=True, type="primary",
                     disabled=attendance_service.is_active):
            if not session_title.strip():
                st.warning("Vui lòng nhập tên buổi học!")
            else:
                st.session_state.last_session_stats = None
                attendance_service.start_session(
                    class_id=selected_class_id,
                    title=session_title.strip(),
                    start_time=start_time_str,
                    late_time=late_time_str,
                    session_type=class_type,
                )
                # Load face_db với lớp hiện tại
                students = db.get_all_students(selected_class_id)
                face_db.load_all(students)
                st.success("Đã bắt đầu buổi điểm danh!")
                st.rerun()

    with col_stop:
        if st.button("⏹ Kết thúc", use_container_width=True,
                     disabled=not attendance_service.is_active):
            stats = attendance_service.stop_session()
            st.session_state.last_session_stats = stats
            st.success("Đã kết thúc buổi & ghi nhận vắng mặt!")
            st.rerun()

    st.divider()
    # Thống kê realtime
    if attendance_service.is_active:
        total_students = len(db.get_all_students(selected_class_id))
        attended       = len(attendance_service.get_attended_ids())
        st.metric("✅ Đã có mặt / trễ", f"{attended} / {total_students}")
        progress = attended / max(total_students, 1)
        st.progress(progress)

    st.markdown(f"""
    **Ngưỡng nhận diện:** `{SIMILARITY_THRESHOLD}`  
    **Trạng thái:** {"🟢 Đang điểm danh" if attendance_service.is_active else "🔴 Chưa bắt đầu"}
    """)

# ── Layout chính ──────────────────────────────────────────────────────────────
col_cam, col_log = st.columns([3, 2])

# ── Session info banner ────────────────────────────────────────────────-------
if attendance_service.is_active:
    st.markdown(f"""
    <div class="session-box">
    🟢 <b>Đang điểm danh ({class_type})</b> · Session ID: <code>{attendance_service.session_id}</code><br/>
    · Lớp: <b>{selected_class['name']}</b> · Buổi: <b>{session_title}</b><br/>
    ⏰ <b>Giờ học:</b> {start_time_str} · ⏱️ <b>Mốc trễ:</b> Sau {late_time_str}
    </div>
    """, unsafe_allow_html=True)
elif st.session_state.last_session_stats:
    stats = st.session_state.last_session_stats
    st.success(
        f"🎉 **Đã kết thúc buổi học!** Tổng hợp: "
        f"✅ Có mặt: **{stats['present']}** · "
        f"⚠️ Đi muộn: **{stats['late']}** · "
        f"❌ Vắng mặt: **{stats['absent']}** (Đã tự động chèn vắng mặt cho các SV chưa quét)"
    )
else:
    st.info("⏸ Chưa có buổi điểm danh nào đang mở. Thiết lập thông số và nhấn **▶️ Bắt đầu** ở sidebar.", icon="ℹ️")

# ── WebRTC callback ───────────────────────────────────────────────────────────
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

            # Ghi điểm danh tự động phân loại present / late
            if res.student_id and attendance_service.is_active:
                attendance_service.mark_attendance(res.student_id, res.confidence)

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return av.VideoFrame.from_ndarray(img_rgb, format="rgb24")


# ── Camera stream ─────────────────────────────────────────────────────────────
with col_cam:
    st.markdown("### 🎥 Camera Nhận Diện")

    # Kiểm tra models trước khi load
    from utils.config import SCRFD_MODEL_PATH, ARCFACE_MODEL_PATH
    models_missing = not SCRFD_MODEL_PATH.exists() or not ARCFACE_MODEL_PATH.exists()

    if models_missing:
        st.error("""
**⚠️ Chưa có model AI!**
Chạy lệnh sau trong Terminal để tải models (~300MB):
```
python download_models.py
```
Sau đó reload lại trang này.
        """)
        st.stop()

    if not pipeline.is_loaded:
        with st.spinner("⏳ Đang load AI models lần đầu (GPU/CPU)..."):
            try:
                pipeline.load()
            except Exception as e:
                st.error(f"❌ Lỗi load model: {e}")
                st.stop()

    # Chọn phương thức điểm danh
    cam_mode = st.radio(
        "Chọn phương thức quét:",
        ["Chụp ảnh tĩnh (Khuyên dùng - Nhẹ & Mượt)", "Video trực tiếp (WebRTC - Live Stream)"],
        horizontal=True
    )

    if cam_mode == "Chụp ảnh tĩnh (Khuyên dùng - Nhẹ & Mượt)":
        cam_img = st.camera_input("Nhìn vào camera và chụp ảnh điểm danh")
        if cam_img is not None:
            img_bytes = cam_img.getvalue()
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            if pipeline.is_loaded:
                with st.spinner("🧠 Đang quét khuôn mặt trong ảnh..."):
                    results = pipeline.process_frame(img, face_db)
                
                if not results:
                    st.warning("⚠️ Không phát hiện khuôn mặt nào trong bức ảnh vừa chụp.")
                else:
                    for res in results:
                        draw_face_box(img, res.bbox, res.name, res.confidence)
                        if res.student_id and attendance_service.is_active:
                            attendance_service.mark_attendance(res.student_id, res.confidence)
                    
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
    st.markdown("### 📋 Danh sách điểm danh Buổi này")

    if attendance_service.is_active:
        results = attendance_service.get_session_results()
        if not results:
            st.caption("Chưa có sinh viên nào quét mặt...")
        else:
            for r in results:
                time_str = r["timestamp"][11:16]  # HH:MM
                conf_pct = f"{r['confidence'] * 100:.0f}%" if r['confidence'] > 0 else "—"
                st_code = r["status"]
                
                if st_code == "present":
                    badge_elem = '<span class="badge-present">✅ Có mặt</span>'
                elif st_code == "late":
                    badge_elem = '<span class="badge-late">⚠️ Đi muộn</span>'
                else:
                    badge_elem = '<span class="badge-absent">❌ Vắng</span>'

                st.markdown(f"""
                <div class="attend-card">
                    <div>
                        <div class="attend-name">{r['full_name']}</div>
                        <div class="attend-code">{r['student_code']}</div>
                    </div>
                    <div>{badge_elem}</div>
                    <span class="attend-time">{time_str} ({conf_pct})</span>
                </div>
                """, unsafe_allow_html=True)

        if st.button("🔄 Làm mới danh sách", use_container_width=True):
            st.rerun()
    else:
        st.caption("Bắt đầu buổi học ở sidebar để xem danh sách điểm danh.")
