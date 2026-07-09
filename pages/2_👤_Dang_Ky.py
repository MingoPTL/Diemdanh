"""
pages/2_👤_Dang_Ky.py
Trang đăng ký khuôn mặt: chụp N ảnh → trích embedding → lưu DB
"""
import cv2
import numpy as np
import streamlit as st
from PIL import Image

import database.db as db
from core.pipeline import pipeline
from core.aligner import align_face, crop_face
from services.face_db import face_db
from utils.helpers import save_photo
from utils.config import REGISTER_SAMPLES

st.set_page_config(page_title="Đăng Ký Khuôn Mặt", page_icon="👤", layout="wide")

st.markdown("""
<style>
.step-box {
    background: #1C2333; border-radius: 12px;
    padding: 20px; border: 1px solid #2D3748;
}
.face-thumb {
    border-radius: 8px; border: 2px solid #4F8EF7;
}
.success-banner {
    background: linear-gradient(90deg, #1C4532, #276749);
    border: 1px solid #38A169; border-radius: 10px;
    padding: 16px; text-align: center;
    font-size: 1.1rem; font-weight: 700; color: #9AE6B4;
}
</style>
""", unsafe_allow_html=True)

st.markdown("## 👤 Đăng Ký Khuôn Mặt")
st.caption(f"Hệ thống sẽ chụp **{REGISTER_SAMPLES} ảnh** để trích xuất embedding khuôn mặt.")
st.divider()

# ── Load models ───────────────────────────────────────────────────────────────
if not pipeline.is_loaded:
    with st.spinner("⏳ Đang load AI models..."):
        pipeline.load()

# ── Chọn sinh viên ────────────────────────────────────────────────────────────
st.markdown("### Bước 1 · Chọn sinh viên")

classes = db.get_all_classes()
if not classes:
    st.error("Chưa có lớp học! Hãy tạo lớp trước ở trang Quản Lý Lớp.")
    st.stop()

col_cls, col_stu = st.columns(2)
with col_cls:
    class_options = {f"{c['name']} ({c['code']})": c["id"] for c in classes}
    selected_cls_label = st.selectbox("🏫 Lớp học", list(class_options.keys()))
    selected_cls_id    = class_options[selected_cls_label]

students = db.get_all_students(selected_cls_id)
unregistered = [s for s in students if not s["registered"]]
registered   = [s for s in students if s["registered"]]

with col_stu:
    if not unregistered:
        st.success("✅ Tất cả sinh viên trong lớp đã đăng ký khuôn mặt!")
        selected_student = None
    else:
        stu_options = {f"{s['student_code']} - {s['full_name']}": s for s in unregistered}
        selected_stu_label = st.selectbox(
            f"👤 Sinh viên chưa đăng ký ({len(unregistered)} người)",
            list(stu_options.keys()),
        )
        selected_student = stu_options[selected_stu_label]

st.divider()

# ── Phần đăng ký ─────────────────────────────────────────────────────────────
if selected_student:
    st.markdown(f"### Bước 2 · Chụp ảnh cho **{selected_student['full_name']}**")
    st.caption(f"MSSV: `{selected_student['student_code']}` · ID: `{selected_student['id']}`")

    col_cam, col_preview = st.columns([3, 2])

    # ── Camera chụp ảnh ───────────────────────────────────────────────────────
    with col_cam:
        st.markdown('<div class="step-box">', unsafe_allow_html=True)
        cam_img = st.camera_input(
            label="📸 Nhìn thẳng vào camera rồi nhấn chụp",
            key=f"cam_{selected_student['id']}",
        )

        # Session state lưu ảnh đã chụp
        ss_key = f"captured_{selected_student['id']}"
        if ss_key not in st.session_state:
            st.session_state[ss_key] = []

        captured_list: list = st.session_state[ss_key]

        if cam_img is not None:
            # Decode ảnh từ camera
            img_bytes = cam_img.getvalue()
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            frame_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            # Detect khuôn mặt trong ảnh
            face_pairs = pipeline.extract_faces(frame_bgr)

            if not face_pairs:
                st.warning("⚠️ Không phát hiện khuôn mặt! Thử lại với ánh sáng tốt hơn.")
            else:
                # Tính khoảng cách từ tâm mỗi khuôn mặt đến tâm ảnh để tìm mặt ở trung tâm nhất
                img_h, img_w = frame_bgr.shape[:2]
                img_center_x = img_w / 2
                img_center_y = img_h / 2

                def distance_to_center(pair):
                    det, _ = pair
                    x1, y1, x2, y2 = det.bbox
                    face_center_x = (x1 + x2) / 2
                    face_center_y = (y1 + y2) / 2
                    return (face_center_x - img_center_x) ** 2 + (face_center_y - img_center_y) ** 2

                # Sắp xếp các khuôn mặt theo khoảng cách tăng dần (gần tâm nhất lên đầu)
                face_pairs = sorted(face_pairs, key=distance_to_center)

                if len(face_pairs) > 1:
                    st.info("ℹ️ Phát hiện nhiều khuôn mặt, hệ thống tự động chọn khuôn mặt ở trung tâm.")

                det, face_crop = face_pairs[0]
                if len(captured_list) < REGISTER_SAMPLES:
                    captured_list.append(face_crop)
                    st.session_state[ss_key] = captured_list
                    st.success(f"✅ Đã chụp {len(captured_list)}/{REGISTER_SAMPLES} ảnh")
                else:
                    st.info(f"Đã đủ {REGISTER_SAMPLES} ảnh. Nhấn **Đăng ký** để lưu.")

        # Progress
        progress_val = len(captured_list) / REGISTER_SAMPLES
        st.progress(progress_val, text=f"Tiến trình: {len(captured_list)}/{REGISTER_SAMPLES} ảnh")

        # Nút reset
        if captured_list and st.button("🗑️ Chụp lại từ đầu", use_container_width=True):
            st.session_state[ss_key] = []
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    # ── Preview ảnh đã chụp ───────────────────────────────────────────────────
    with col_preview:
        st.markdown("**Preview ảnh đã chụp:**")
        if captured_list:
            cols = st.columns(min(len(captured_list), 3))
            for i, face in enumerate(captured_list):
                face_rgb = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
                cols[i % 3].image(face_rgb, caption=f"Ảnh {i+1}", use_container_width=True)
        else:
            st.caption("Chưa có ảnh nào. Hãy nhìn thẳng và chụp.")

    st.divider()

    # ── Nút đăng ký ───────────────────────────────────────────────────────────
    st.markdown("### Bước 3 · Lưu đăng ký")
    if len(captured_list) < REGISTER_SAMPLES:
        st.info(f"Cần chụp đủ **{REGISTER_SAMPLES} ảnh** (hiện có {len(captured_list)})", icon="📸")
        st.button("💾 Đăng ký khuôn mặt", disabled=True, use_container_width=True)
    else:
        if st.button("💾 Đăng ký khuôn mặt", type="primary", use_container_width=True):
            with st.spinner("🧠 Đang trích xuất embeddings..."):
                # Batch embedding
                embeddings = pipeline._recognizer.get_embedding_batch(captured_list)
                mean_embedding = embeddings.mean(axis=0)

                sid = str(selected_student["id"])
                face_db.save_embedding(sid, mean_embedding, selected_student["full_name"])

                # Lưu ảnh đại diện
                save_photo(captured_list[0], sid, 0)
                db.update_student_registered(
                    selected_student["id"],
                    photo_path=str(f"data/photos/{sid}/000.jpg"),
                )

                # Clear session state
                st.session_state[ss_key] = []

            st.markdown(f"""
            <div class="success-banner">
            ✅ Đã đăng ký thành công khuôn mặt cho <b>{selected_student['full_name']}</b>!
            </div>
            """, unsafe_allow_html=True)
            st.balloons()

st.divider()

# ── Danh sách đã đăng ký ─────────────────────────────────────────────────────
with st.expander(f"📋 Sinh viên đã đăng ký trong lớp ({len(registered)} người)", expanded=False):
    if not registered:
        st.caption("Chưa có sinh viên nào đăng ký.")
    else:
        cols_header = st.columns([1, 3, 2, 1])
        cols_header[0].markdown("**MSSV**")
        cols_header[1].markdown("**Họ tên**")
        cols_header[2].markdown("**Trạng thái**")
        cols_header[3].markdown("**Xóa**")

        for s in registered:
            c1, c2, c3, c4 = st.columns([1, 3, 2, 1])
            c1.code(s["student_code"])
            c2.write(s["full_name"])
            c3.markdown('<span style="color:#9AE6B4">✅ Đã đăng ký</span>', unsafe_allow_html=True)
            if c4.button("🗑", key=f"del_{s['id']}"):
                face_db.delete_embedding(str(s["id"]))
                db.update_student_registered(s["id"])
                st.warning(f"Đã xóa embedding của {s['full_name']}")
                st.rerun()
