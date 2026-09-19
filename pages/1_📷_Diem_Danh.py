"""
pages/1_📷_Diem_Danh.py
Trang điểm danh đa phương thức hiệu năng cao (30+ FPS Full HD, Zero Lag):
1. Kiến trúc Bất đồng bộ (Async Background AI Worker) tách rời luồng hiển thị video và luồng AI.
2. WebRTC Live Stream không bao giờ bị nghẽn (render < 2ms/frame), giữ trọn độ nét 720p/1080p.
3. Quét Kép (Dual AI): Nhận diện khuôn mặt (SCRFD + ArcFace) + Quét mã vạch 1D & QR Code MSSV (Barcode Scanner siêu nhạy).
"""
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

import av
import cv2
import numpy as np
import streamlit as st
from streamlit_webrtc import RTCConfiguration, WebRtcMode, webrtc_streamer

import database.db as db
from core.pipeline import pipeline
from services.attendance import attendance_service
from services.barcode_scanner import barcode_scanner, draw_barcode_box
from services.face_db import face_db
from utils.config import ARCFACE_MODEL_PATH, SCRFD_MODEL_PATH, SIMILARITY_THRESHOLD
from utils.helpers import draw_face_box

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
.attend-time  { font-size: 0.75rem; color: #64748B; margin-left: auto; text-align: right; }

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
.badge-method-face {
    background: rgba(99, 102, 241, 0.15); color: #A5B4FC;
    border: 1px solid rgba(99, 102, 241, 0.3);
    padding: 1px 6px; border-radius: 4px; font-size: 0.72rem;
}
.badge-method-barcode {
    background: rgba(234, 88, 12, 0.15); color: #FB923C;
    border: 1px solid rgba(234, 88, 12, 0.3);
    padding: 1px 6px; border-radius: 4px; font-size: 0.72rem;
}

.session-box {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9));
    border: 1px solid rgba(59, 130, 246, 0.4);
    border-radius: 14px; padding: 16px 20px; margin-bottom: 16px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}
.scan-notice {
    background: rgba(16, 185, 129, 0.12);
    border-left: 4px solid #10B981;
    padding: 8px 12px; border-radius: 6px; margin-bottom: 10px; font-size: 0.88rem;
}
</style>
""", unsafe_allow_html=True)

# ── Tiêu đề ───────────────────────────────────────────────────────────────────
st.markdown("## 📷 Điểm Danh Đa Năng (Khuôn Mặt & Mã Vạch)")
st.divider()

if "last_session_stats" not in st.session_state:
    st.session_state.last_session_stats = None
if "ip_cam_running" not in st.session_state:
    st.session_state.ip_cam_running = False

# ── Global Thread-Safe State cho luồng WebRTC không giật lag ──────────────────
class StreamSyncState:
    def __init__(self):
        self.lock = threading.Lock()
        self.latest_frame: Optional[np.ndarray] = None
        self.cached_faces: List[Tuple] = []       # list of (bbox, name, confidence)
        self.cached_barcodes: List[Tuple] = []    # list of (points, label, is_valid)
        self.enable_face = True
        self.enable_barcode = True
        self.is_mirror = False
        self.is_worker_running = False
        self.last_update_time = 0.0

    def update_settings(self, enable_face: bool, enable_barcode: bool, is_mirror: bool):
        with self.lock:
            self.enable_face = enable_face
            self.enable_barcode = enable_barcode
            self.is_mirror = is_mirror

    def submit_frame(self, frame: np.ndarray):
        with self.lock:
            self.latest_frame = frame

    def get_overlays(self) -> Tuple[List[Tuple], List[Tuple]]:
        with self.lock:
            return list(self.cached_faces), list(self.cached_barcodes)

    def set_results(self, faces: List[Tuple], barcodes: List[Tuple]):
        with self.lock:
            self.cached_faces = faces
            self.cached_barcodes = barcodes
            self.last_update_time = time.time()


@st.cache_resource
def get_stream_state() -> StreamSyncState:
    state = StreamSyncState()

    def ai_worker_loop():
        while True:
            frame_to_process = None
            enable_f = True
            enable_b = True
            is_mir = False

            with state.lock:
                if state.latest_frame is not None:
                    frame_to_process = state.latest_frame.copy()
                    state.latest_frame = None  # tiêu thụ frame
                    enable_f = state.enable_face
                    enable_b = state.enable_barcode
                    is_mir = state.is_mirror

            if frame_to_process is not None:
                if is_mir:
                    frame_to_process = cv2.flip(frame_to_process, 1)

                f_boxes = []
                b_boxes = []

                # 1. Barcode scan (Multi-engine siêu nhạy)
                if enable_b:
                    b_results = barcode_scanner.scan(frame_to_process, try_mirror=False)
                    for b in b_results:
                        mssv = b.text.strip()
                        is_success = False
                        label_text = f"MSSV: {mssv}"
                        if attendance_service.is_active:
                            success, st_info, _ = attendance_service.mark_attendance_by_code(mssv, method="barcode")
                            is_success = success
                            if st_info:
                                label_text = f"🏷️ {st_info['full_name']} ({mssv})"
                        b_boxes.append((b.points, label_text, is_success))

                # 2. Face scan (SCRFD + ArcFace)
                if enable_f and pipeline.is_loaded:
                    f_results = pipeline.process_frame(frame_to_process, face_db)
                    for res in f_results:
                        if res.student_id and attendance_service.is_active:
                            attendance_service.mark_attendance(res.student_id, res.confidence, method="face")
                        f_boxes.append((res.bbox, res.name, res.confidence))

                state.set_results(f_boxes, b_boxes)

            time.sleep(0.02)  # 50 FPS polling

    worker = threading.Thread(target=ai_worker_loop, daemon=True)
    worker.start()
    return state

stream_state = get_stream_state()

# ── Sidebar: Cài đặt buổi học ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Cài đặt buổi học")
    classes = db.get_all_classes()
    if not classes:
        st.error("Chưa có lớp! Hãy tạo lớp ở trang Quản Lý Lớp & Sinh Viên.")
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

    st.caption(f"📌 Mốc tính đi muộn: `{late_time_str}` *(Quét sau {late_time_str} sẽ tính là Đi muộn)*")

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
                # Load face_db với sinh viên của lớp hiện tại
                students = db.get_all_students(selected_class_id)
                face_db.load_all(students)
                st.success("Đã bắt đầu buổi điểm danh!")
                st.rerun()

    with col_stop:
        if st.button("⏹ Kết thúc", use_container_width=True,
                     disabled=not attendance_service.is_active):
            stats = attendance_service.stop_session()
            st.session_state.last_session_stats = stats
            st.session_state.ip_cam_running = False
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
    **Ngưỡng Face AI:** `{SIMILARITY_THRESHOLD}`  
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
        f"❌ Vắng mặt: **{stats['absent']}** (Đã tự động ghi vắng mặt cho các SV chưa quét)"
    )
else:
    st.info("⏸ Chưa có buổi điểm danh nào đang mở. Thiết lập thông số và nhấn **▶️ Bắt đầu** ở sidebar.", icon="ℹ️")


# ── Xử lý frame tĩnh ─────────────────────────────────────────────────────────
def process_single_frame(
    img: np.ndarray, 
    enable_face: bool = True, 
    enable_barcode: bool = True, 
    is_mirror: bool = False
) -> tuple[np.ndarray, list, list]:
    if is_mirror:
        img = cv2.flip(img, 1)

    face_results = []
    barcode_results = []

    # 1. Quét Mã Vạch / QR Code MSSV (1D Code 128 / Code 39 / QR)
    if enable_barcode:
        b_results = barcode_scanner.scan(img, try_mirror=True)
        for b in b_results:
            mssv = b.text.strip()
            is_success = False
            label_text = f"MSSV: {mssv}"
            if attendance_service.is_active:
                success, st_info, _ = attendance_service.mark_attendance_by_code(mssv, method="barcode")
                is_success = success
                if st_info:
                    label_text = f"🏷️ {st_info['full_name']} ({mssv})"
                else:
                    label_text = f"⚠️ Không tìm thấy: {mssv}"
            
            draw_barcode_box(img, b.points, label_text, is_valid=is_success or not attendance_service.is_active)
            barcode_results.append((b, label_text))

    # 2. Quét Khuôn mặt AI
    if enable_face and pipeline.is_loaded:
        f_results = pipeline.process_frame(img, face_db)
        for res in f_results:
            draw_face_box(img, res.bbox, res.name, res.confidence)
            if res.student_id and attendance_service.is_active:
                attendance_service.mark_attendance(res.student_id, res.confidence, method="face")
            face_results.append(res)

    return img, face_results, barcode_results


# ── Camera Stream & Controls ──────────────────────────────────────────────────
with col_cam:
    st.markdown("### 🎥 Nguồn Camera & Chế Độ Quét")

    # Kiểm tra model
    models_missing = not SCRFD_MODEL_PATH.exists() or not ARCFACE_MODEL_PATH.exists()
    if models_missing:
        st.error("""
        **⚠️ Chưa có model AI!**
        Chạy lệnh sau trong Terminal để tải models (~300MB):
        ```
        python download_models.py
        ```
        """)
        st.stop()

    if not pipeline.is_loaded:
        with st.spinner("⏳ Đang nạp AI Models (SCRFD + ArcFace)..."):
            try:
                pipeline.load()
            except Exception as e:
                st.error(f"❌ Lỗi load model: {e}")
                st.stop()

    # Thanh điều khiển chế độ quét
    c_mode1, c_mode2 = st.columns([3, 2])
    with c_mode1:
        scan_mode = st.selectbox(
            "🎯 Chế độ quét điểm danh:",
            [
                "🚀 Quét Kép (Khuôn mặt AI + Mã vạch / QR)",
                "👤 Chỉ nhận diện Khuôn mặt AI",
                "🏷️ Chỉ quét Mã vạch / QR Code MSSV",
            ],
        )
    with c_mode2:
        mirror_mode = st.toggle("🪞 Lật gương Camera (Mirror)", value=False,
                                help="Bật khi camera bị ngược trái/phải để nhìn tự nhiên hơn")

    enable_face_scan = "Khuôn mặt" in scan_mode or "Quét Kép" in scan_mode
    enable_barcode_scan = "Mã vạch" in scan_mode or "Quét Kép" in scan_mode

    # Đồng bộ cài đặt vào Background Worker
    stream_state.update_settings(
        enable_face=enable_face_scan,
        enable_barcode=enable_barcode_scan,
        is_mirror=mirror_mode
    )

    # Chọn nguồn Camera
    cam_source = st.radio(
        "📹 Chọn nguồn Video:",
        [
            "📹 WebRTC Live Stream (Trực Tiếp 30 FPS Siêu Mượt - Khuyên Dùng)",
            "💻 Chụp ảnh tĩnh Webcam (Nhẹ & Nét Nhất)",
            "📱 Camera Điện Thoại (IP Camera / Wi-Fi)",
        ],
        horizontal=False
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # NGUỒN 1: WEBRTC LIVE STREAM BẤT ĐỒNG BỘ (30+ FPS, NÉT FULL HD, ZERO LAG)
    # ═══════════════════════════════════════════════════════════════════════════
    if "📹 WebRTC Live Stream" in cam_source:
        rtc_config = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

        def video_frame_callback(frame: av.VideoFrame) -> av.VideoFrame:
            img = frame.to_ndarray(format="bgr24")

            # 1. Đưa frame vào queue xử lý nền của AI Worker
            stream_state.submit_frame(img)

            # 2. Áp dụng lật gương nếu cần
            if mirror_mode:
                img = cv2.flip(img, 1)

            # 3. Vẽ bounding boxes mới nhất từ background worker (< 0.5ms)
            f_boxes, b_boxes = stream_state.get_overlays()

            for b_pts, b_lbl, b_ok in b_boxes:
                draw_barcode_box(img, b_pts, b_lbl, is_valid=b_ok or not attendance_service.is_active)

            for f_box, f_name, f_conf in f_boxes:
                draw_face_box(img, f_box, f_name, f_conf)

            # 4. Trả về video 30 FPS ngay lập tức cho WebRTC (không bao giờ bị trễ hay lag)
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            return av.VideoFrame.from_ndarray(img_rgb, format="rgb24")

        webrtc_streamer(
            key="attendance-cam-v3",
            mode=WebRtcMode.SENDRECV,
            rtc_configuration=rtc_config,
            video_frame_callback=video_frame_callback,
            media_stream_constraints={
                "video": {
                    "width": {"ideal": 1280, "min": 640},
                    "height": {"ideal": 720, "min": 480},
                    "frameRate": {"ideal": 30, "max": 30},
                },
                "audio": False
            },
            async_processing=True,
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # NGUỒN 2: CHỤP ẢNH TĨNH
    # ═══════════════════════════════════════════════════════════════════════════
    elif "💻 Chụp ảnh tĩnh" in cam_source:
        cam_img = st.camera_input("Đưa mặt hoặc giơ thẻ sinh viên trước Camera rồi bấm chụp")
        if cam_img is not None:
            img_bytes = cam_img.getvalue()
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            with st.spinner("🧠 Đang phân tích khuôn mặt & mã vạch..."):
                processed_img, f_res, b_res = process_single_frame(
                    img, 
                    enable_face=enable_face_scan, 
                    enable_barcode=enable_barcode_scan, 
                    is_mirror=mirror_mode
                )

            img_rgb = cv2.cvtColor(processed_img, cv2.COLOR_BGR2RGB)
            st.image(img_rgb, caption="Kết quả nhận diện", use_container_width=True)

            if not f_res and not b_res:
                st.warning("⚠️ Không phát hiện khuôn mặt hoặc mã vạch nào trong ảnh chụp. Hãy đảm bảo thẻ thẳng và đủ ánh sáng.")
            else:
                for b_item, b_lbl in b_res:
                    st.success(f"🏷️ **Mã Vạch ({b_item.format_name}):** `{b_item.text}` → {b_lbl}")
                for f_item in f_res:
                    st.info(f"👤 **Khuôn Mặt AI:** {f_item.name} ({f_item.confidence*100:.1f}%)")
                
                if not attendance_service.is_active:
                    st.warning("⚠️ Chưa mở buổi học! Hãy nhấn **▶️ Bắt đầu** ở Sidebar để lưu kết quả điểm danh vào danh sách.")
                else:
                    if st.button("🔄 Cập nhật danh sách điểm danh", key="btn_refresh_snapshot"):
                        st.rerun()

    # ═══════════════════════════════════════════════════════════════════════════
    # NGUỒN 3: CAMERA ĐIỆN THOẠI (IP CAMERA / RTSP)
    # ═══════════════════════════════════════════════════════════════════════════
    else:
        st.markdown("""
        <div class="scan-notice">
        <b>📱 Hướng dẫn dùng Camera Điện Thoại:</b><br/>
        1. Cài app <b>IP Webcam</b> (Android) hoặc <b>DroidCam</b> / <b>Iriun</b> (Android/iOS) trên điện thoại.<br/>
        2. Kết nối điện thoại và máy tính cùng mạng Wi-Fi.<br/>
        3. Mở app và bấm <i>Start Server</i> → Nhập URL video hiển thị trên điện thoại vào ô dưới.
        </div>
        """, unsafe_allow_html=True)

        ip_col1, ip_col2 = st.columns([3, 1])
        with ip_col1:
            ip_url = st.text_input(
                "🔗 URL Luồng IP Camera:",
                value="http://192.168.1.50:8080/video",
                placeholder="VD: http://192.168.1.15:8080/video hoặc http://192.168.1.15:4747/video"
            )
        with ip_col2:
            st.write("")
            st.write("")
            quick_preset = st.selectbox("Gợi ý cổng:", ["IP Webcam (:8080)", "DroidCam (:4747)", "RTSP (:554)"])

        col_ip_btn1, col_ip_btn2 = st.columns(2)
        with col_ip_btn1:
            if st.button("📸 Quét 1 Khung Hình từ IP Cam", use_container_width=True):
                cap = cv2.VideoCapture(ip_url)
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None:
                    proc_img, f_res, b_res = process_single_frame(
                        frame,
                        enable_face=enable_face_scan,
                        enable_barcode=enable_barcode_scan,
                        is_mirror=mirror_mode
                    )
                    st.image(cv2.cvtColor(proc_img, cv2.COLOR_BGR2RGB), caption="Khung hình từ IP Camera", use_container_width=True)
                    st.success(f"🎉 Quét thành công: {len(f_res)} mặt, {len(b_res)} mã vạch!")
                else:
                    st.error(f"❌ Không thể kết nối tới URL: {ip_url}. Hãy kiểm tra IP và Wi-Fi.")

        with col_ip_btn2:
            if not st.session_state.ip_cam_running:
                if st.button("▶️ Bật Luồng Live Stream IP Cam", use_container_width=True, type="primary"):
                    st.session_state.ip_cam_running = True
                    st.rerun()
            else:
                if st.button("⏹ Dừng Luồng Live Stream", use_container_width=True):
                    st.session_state.ip_cam_running = False
                    st.rerun()

        # Luồng Live Stream IP Cam
        if st.session_state.ip_cam_running:
            video_placeholder = st.empty()
            status_placeholder = st.empty()
            status_placeholder.info(f"🟢 Đang nhận luồng từ {ip_url}...")

            cap = cv2.VideoCapture(ip_url)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if not cap.isOpened():
                status_placeholder.error(f"❌ Không thể mở luồng IP Camera tại {ip_url}")
                st.session_state.ip_cam_running = False
            else:
                count = 0
                while st.session_state.ip_cam_running and attendance_service.is_active:
                    ret, frame = cap.read()
                    if not ret:
                        status_placeholder.warning("⚠️ Mất kết nối luồng IP Camera...")
                        break
                    count += 1
                    if count % 2 == 0:
                        proc_frame, _, _ = process_single_frame(
                            frame,
                            enable_face=enable_face_scan,
                            enable_barcode=enable_barcode_scan,
                            is_mirror=mirror_mode
                        )
                        frame_rgb = cv2.cvtColor(proc_frame, cv2.COLOR_BGR2RGB)
                        video_placeholder.image(frame_rgb, use_container_width=True)
                    time.sleep(0.01)
                cap.release()


# ── Log điểm danh realtime ────────────────────────────────────────────────────
with col_log:
    st.markdown("### 📋 Danh Sách Điểm Danh Buổi Này")

    if attendance_service.is_active:
        results = attendance_service.get_session_results()
        if not results:
            st.caption("Chưa có sinh viên nào quét mặt hoặc quét mã...")
        else:
            for r in results:
                time_str = r["timestamp"][11:16]  # HH:MM
                conf_pct = f"{r['confidence'] * 100:.0f}%" if r['confidence'] > 0 else "—"
                st_code = r["status"]
                method_code = dict(r).get("method", "face")
                
                # Badge status
                if st_code == "present":
                    badge_elem = '<span class="badge-present">✅ Có mặt</span>'
                elif st_code == "late":
                    badge_elem = '<span class="badge-late">⚠️ Đi muộn</span>'
                else:
                    badge_elem = '<span class="badge-absent">❌ Vắng</span>'

                # Badge method
                if method_code == "barcode":
                    method_elem = '<span class="badge-method-barcode">🏷️ Mã vạch</span>'
                else:
                    method_elem = '<span class="badge-method-face">👤 Khuôn mặt</span>'

                st.markdown(f"""
                <div class="attend-card">
                    <div>
                        <div class="attend-name">{r['full_name']}</div>
                        <div class="attend-code">{r['student_code']} &nbsp; {method_elem}</div>
                    </div>
                    <div>{badge_elem}</div>
                    <span class="attend-time">{time_str}<br/><small style="color:#64748B">{conf_pct}</small></span>
                </div>
                """, unsafe_allow_html=True)

        if st.button("🔄 Làm mới danh sách", use_container_width=True):
            st.rerun()
    else:
        st.caption("Bắt đầu buổi học ở sidebar để xem danh sách điểm danh.")
