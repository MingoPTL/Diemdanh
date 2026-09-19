"""
pages/3_📋_Quan_Ly_Lop.py
Trang quản lý lớp học và sinh viên: CRUD
"""
import streamlit as st
import pandas as pd

import database.db as db

st.set_page_config(page_title="Quản Lý Lớp", page_icon="📋", layout="wide")

st.markdown("""
<style>
/* CSS Custom Badges & Glass Cards */
.badge-theory {
    background: rgba(59, 130, 246, 0.15);
    color: #60A5FA;
    border: 1px solid rgba(59, 130, 246, 0.3);
    padding: 3px 10px;
    border-radius: 9999px;
    font-size: 0.78rem;
    font-weight: 600;
}
.badge-practice {
    background: rgba(16, 185, 129, 0.15);
    color: #34D399;
    border: 1px solid rgba(16, 185, 129, 0.3);
    padding: 3px 10px;
    border-radius: 9999px;
    font-size: 0.78rem;
    font-weight: 600;
}
.card {
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 12px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("## 📋 Quản Lý Lớp Học & Sinh Viên")
st.divider()

tab_class, tab_student, tab_import, tab_card = st.tabs(["🏫 Lớp học", "👥 Sinh viên", "📥 Import Excel", "🏷️ Thẻ SV & Mã Vạch"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1: QUẢN LÝ LỚP
# ═══════════════════════════════════════════════════════════════════════════════
with tab_class:
    col_list, col_form = st.columns([3, 2])

    with col_form:
        st.markdown("#### ➕ Thêm lớp mới")
        with st.form("add_class_form", clear_on_submit=True):
            cls_name = st.text_input("Tên môn / lớp", placeholder="VD: Công nghệ thông tin K22")
            cls_code = st.text_input("Mã lớp",  placeholder="VD: CNTT-K22A")
            cls_type = st.selectbox("Loại lớp học", ["Lý thuyết", "Thực hành"], 
                                    help="Phân loại lớp để điểm danh và làm báo cáo riêng")
            submitted = st.form_submit_button("💾 Tạo lớp", type="primary", use_container_width=True)
            if submitted:
                if not cls_name.strip() or not cls_code.strip():
                    st.error("Vui lòng điền đầy đủ thông tin!")
                else:
                    try:
                        db.add_class(cls_name.strip(), cls_code.strip().upper(), cls_type)
                        st.success(f"✅ Đã tạo lớp **{cls_name}** ({cls_type})!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Lỗi: {e}")

    with col_list:
        st.markdown("#### 📋 Danh sách lớp")
        classes = db.get_all_classes()
        if not classes:
            st.info("Chưa có lớp nào. Tạo lớp đầu tiên ở bên phải →")
        else:
            for c in classes:
                students = db.get_all_students(c["id"])
                reg = sum(1 for s in students if s["registered"])
                c_type = dict(c).get("type", "Lý thuyết")
                badge_html = '<span class="badge-theory">📘 Lý thuyết</span>' if c_type == "Lý thuyết" else '<span class="badge-practice">🧪 Thực hành</span>'
                
                with st.container(border=True):
                    r1, r2, r3 = st.columns([3, 1, 1])
                    r1.markdown(f"**{c['name']}**  \n`{c['code']}` &nbsp; {badge_html}", unsafe_allow_html=True)
                    r2.metric("SV", len(students))
                    r3.metric("Đã ĐK", reg)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2: QUẢN LÝ SINH VIÊN
# ═══════════════════════════════════════════════════════════════════════════════
with tab_student:
    classes = db.get_all_classes()
    if not classes:
        st.warning("Tạo lớp học trước!")
    else:
        col_l, col_r = st.columns([3, 2])

        with col_r:
            st.markdown("#### ➕ Thêm sinh viên")
            with st.form("add_student_form", clear_on_submit=True):
                cls_sel = {f"{c['name']} - {dict(c).get('type','Lý thuyết')} ({c['code']})": c["id"] for c in classes}
                stu_class = st.selectbox("Lớp", list(cls_sel.keys()))
                stu_code  = st.text_input("MSSV", placeholder="VD: 2251010001")
                stu_name  = st.text_input("Họ và Tên", placeholder="VD: Nguyễn Văn An")
                sub = st.form_submit_button("💾 Thêm sinh viên", type="primary", use_container_width=True)
                if sub:
                    if not stu_code.strip() or not stu_name.strip():
                        st.error("Điền đầy đủ MSSV và tên!")
                    else:
                        try:
                            db.add_student(stu_code.strip(), stu_name.strip(), cls_sel[stu_class])
                            st.success(f"✅ Đã thêm **{stu_name}**!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"MSSV đã tồn tại hoặc lỗi: {e}")

        with col_l:
            st.markdown("#### 👥 Danh sách sinh viên")

            # Bộ lọc lớp
            cls_filter = {f"Tất cả lớp": None} | {f"{c['name']} - {dict(c).get('type','Lý thuyết')} ({c['code']})": c["id"] for c in classes}
            filter_label = st.selectbox("Lọc theo lớp", list(cls_filter.keys()), key="filter_class")
            filter_id    = cls_filter[filter_label]

            students = db.get_all_students(filter_id)

            if not students:
                st.info("Chưa có sinh viên.")
            else:
                # Hiển thị dạng bảng
                df = pd.DataFrame([{
                    "MSSV":       s["student_code"],
                    "Họ và Tên":  s["full_name"],
                    "Lớp":        s["class_name"] or "—",
                    "Loại môn":   dict(s).get("class_type", "Lý thuyết"),
                    "Đã đăng ký": "✅ Đã đăng ký" if s["registered"] else "❌ Chưa đăng ký",
                } for s in students])

                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Đã đăng ký": st.column_config.TextColumn(width="medium"),
                        "MSSV": st.column_config.TextColumn(width="medium"),
                        "Loại môn": st.column_config.TextColumn(width="small"),
                    }
                )
                st.caption(f"Tổng: {len(students)} sinh viên")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3: IMPORT EXCEL
# ═══════════════════════════════════════════════════════════════════════════════
with tab_import:
    st.markdown("#### 📥 Import danh sách sinh viên từ Excel")
    st.markdown("""
    File Excel cần có các cột:
    | MSSV | Họ và Tên |
    |------|-----------|
    | 2251010001 | Nguyễn Văn An |

    > Các cột khác sẽ bị bỏ qua. Cột **MSSV** và **Họ và Tên** là bắt buộc.
    """)

    classes = db.get_all_classes()
    if not classes:
        st.error("Tạo lớp trước!")
    else:
        cls_sel2 = {f"{c['name']} - {dict(c).get('type','Lý thuyết')} ({c['code']})": c["id"] for c in classes}
        import_class_label = st.selectbox("📌 Nhập vào lớp:", list(cls_sel2.keys()), key="import_class")
        import_class_id    = cls_sel2[import_class_label]

        uploaded = st.file_uploader("Chọn file Excel (.xlsx)", type=["xlsx", "xls"])
        if uploaded:
            try:
                df = pd.read_excel(uploaded)
                st.markdown("**Preview (5 dòng đầu):**")
                st.dataframe(df.head(), use_container_width=True)

                col_mssv = st.selectbox("Cột MSSV:", df.columns.tolist())
                col_name = st.selectbox("Cột Họ và Tên:", df.columns.tolist(),
                                        index=min(1, len(df.columns)-1))

                if st.button("📥 Bắt đầu import", type="primary"):
                    success, dup, err = 0, 0, 0
                    for _, row in df.iterrows():
                        try:
                            db.add_student(
                                str(row[col_mssv]).strip(),
                                str(row[col_name]).strip(),
                                import_class_id,
                            )
                            success += 1
                        except Exception:
                            dup += 1

                    st.success(f"✅ Import xong! Thành công: {success} · Trùng/Lỗi: {dup}")
                    st.rerun()

            except Exception as e:
                st.error(f"Lỗi đọc file: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4: THẺ SV & MÃ VẠCH (BARCODE / QR)
# ═══════════════════════════════════════════════════════════════════════════════
with tab_card:
    st.markdown("#### 🏷️ Tạo & Xem Thẻ Sinh Viên (Mã Vạch / QR Code)")
    st.caption("Dùng để thử nghiệm tính năng quét mã điểm danh hoặc in thẻ sinh viên.")

    classes = db.get_all_classes()
    if not classes:
        st.warning("Tạo lớp học trước!")
    else:
        c_sel_dict = {f"{c['name']} ({c['code']})": c["id"] for c in classes}
        sel_card_class = st.selectbox("Chọn lớp:", list(c_sel_dict.keys()), key="card_class_sel")
        card_class_id = c_sel_dict[sel_card_class]

        students_in_cls = db.get_all_students(card_class_id)
        if not students_in_cls:
            st.info("Lớp này chưa có sinh viên.")
        else:
            s_dict = {f"{s['student_code']} - {s['full_name']}": s for s in students_in_cls}
            sel_s_label = st.selectbox("Chọn sinh viên:", list(s_dict.keys()), key="card_student_sel")
            sel_s = s_dict[sel_s_label]

            col_card_preview, col_card_info = st.columns([1, 1])

            import qrcode
            from io import BytesIO

            # Tạo QR Code
            qr = qrcode.QRCode(version=1, box_size=8, border=2)
            qr.add_data(sel_s["student_code"])
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="#0F172A", back_color="#F8FAFC")

            qr_buf = BytesIO()
            qr_img.save(qr_buf, format="PNG")
            qr_bytes = qr_buf.getvalue()

            with col_card_preview:
                st.markdown(f"""
                <div style="background: white; border-radius: 14px; padding: 20px; text-align: center; color: #0F172A; box-shadow: 0 8px 24px rgba(0,0,0,0.3); max-width: 320px; margin: auto;">
                    <div style="font-weight: 800; font-size: 1.1rem; color: #1E3A8A; letter-spacing: 0.5px;">THẺ SINH VIÊN</div>
                    <div style="font-size: 0.8rem; color: #64748B; margin-bottom: 12px;">HỆ THỐNG ĐIỂM DANH AI</div>
                    <img src="data:image/png;base64,{__import__('base64').b64encode(qr_bytes).decode()}" style="width: 160px; height: 160px; border-radius: 8px;"/>
                    <div style="font-weight: 700; font-size: 1.15rem; margin-top: 10px;">{sel_s['full_name']}</div>
                    <div style="font-family: monospace; font-size: 1.05rem; font-weight: 600; color: #2563EB;">{sel_s['student_code']}</div>
                    <div style="font-size: 0.85rem; color: #475569; margin-top: 4px;">{sel_s['class_name']}</div>
                </div>
                """, unsafe_allow_html=True)

            with col_card_info:
                st.markdown("##### 💡 Hướng dẫn kiểm tra tính năng Quét Mã:")
                st.markdown(f"""
                1. Mở trang **1. 📷 Điểm Danh**.
                2. Chọn chế độ **🚀 Quét Kép** hoặc **🏷️ Chỉ quét Mã vạch**.
                3. Đưa hình ảnh thẻ (hoặc mở hình này trên điện thoại) trước camera để hệ thống nhận diện điểm danh tức thì.
                """)
                st.download_button(
                    label="💾 Tải ảnh Thẻ Sinh Viên (PNG)",
                    data=qr_bytes,
                    file_name=f"The_SV_{sel_s['student_code']}.png",
                    mime="image/png",
                    use_container_width=True,
                )

