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
.card { background:#1C2333; border:1px solid #2D3748; border-radius:12px; padding:16px; }
.tag  { background:#2C5282; color:#90CDF4; padding:2px 10px;
         border-radius:999px; font-size:0.78rem; font-weight:600; }
</style>
""", unsafe_allow_html=True)

st.markdown("## 📋 Quản Lý Lớp Học & Sinh Viên")
st.divider()

tab_class, tab_student, tab_import = st.tabs(["🏫 Lớp học", "👥 Sinh viên", "📥 Import Excel"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1: QUẢN LÝ LỚP
# ═══════════════════════════════════════════════════════════════════════════════
with tab_class:
    col_list, col_form = st.columns([3, 2])

    with col_form:
        st.markdown("#### ➕ Thêm lớp mới")
        with st.form("add_class_form", clear_on_submit=True):
            cls_name = st.text_input("Tên lớp", placeholder="VD: Công nghệ thông tin K22")
            cls_code = st.text_input("Mã lớp",  placeholder="VD: CNTT-K22A")
            submitted = st.form_submit_button("💾 Tạo lớp", type="primary", use_container_width=True)
            if submitted:
                if not cls_name.strip() or not cls_code.strip():
                    st.error("Vui lòng điền đầy đủ thông tin!")
                else:
                    try:
                        db.add_class(cls_name.strip(), cls_code.strip().upper())
                        st.success(f"✅ Đã tạo lớp **{cls_name}**!")
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
                with st.container(border=True):
                    r1, r2, r3 = st.columns([3, 1, 1])
                    r1.markdown(f"**{c['name']}**  \n`{c['code']}`")
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
                cls_sel = {f"{c['name']} ({c['code']})": c["id"] for c in classes}
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
            cls_filter = {f"Tất cả lớp": None} | {f"{c['name']} ({c['code']})": c["id"] for c in classes}
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
                    "Đã đăng ký": "✅" if s["registered"] else "❌",
                } for s in students])

                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Đã đăng ký": st.column_config.TextColumn(width="small"),
                        "MSSV": st.column_config.TextColumn(width="medium"),
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
        cls_sel2 = {f"{c['name']} ({c['code']})": c["id"] for c in classes}
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
