"""
pages/4_📊_Bao_Cao.py
Trang báo cáo: xem kết quả điểm danh + xuất Excel
"""
import streamlit as st
import pandas as pd
from datetime import date

import database.db as db
from services.export import export_session_to_excel, export_class_summary_to_excel

st.set_page_config(page_title="Báo Cáo", page_icon="📊", layout="wide")

st.markdown("""
<style>
.badge-theory {
    background: rgba(59, 130, 246, 0.15); color: #60A5FA;
    border: 1px solid rgba(59, 130, 246, 0.3);
    padding: 3px 10px; border-radius: 9999px; font-size: 0.78rem; font-weight: 600;
}
.badge-practice {
    background: rgba(16, 185, 129, 0.15); color: #34D399;
    border: 1px solid rgba(16, 185, 129, 0.3);
    padding: 3px 10px; border-radius: 9999px; font-size: 0.78rem; font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

st.markdown("## 📊 Báo Cáo Điểm Danh")
st.divider()

# ── Chọn lớp ─────────────────────────────────────────────────────────────────
classes = db.get_all_classes()
if not classes:
    st.info("Chưa có dữ liệu. Hãy tạo lớp và điểm danh trước.")
    st.stop()

col_sel1, col_sel2 = st.columns([2, 3])
with col_sel1:
    cls_options = {
        "{} - {} ({})".format(c["name"], dict(c).get("type", "Lý thuyết"), c["code"]): c
        for c in classes
    }
    selected_cls_label = st.selectbox("🏫 Chọn lớp học", list(cls_options.keys()))
    selected_cls = cls_options[selected_cls_label]
    c_type = dict(selected_cls).get("type", "Lý thuyết")

sessions = db.get_sessions_by_class(selected_cls["id"])
students = db.get_all_students(selected_cls["id"])

with col_sel2:
    if not sessions:
        st.warning("Lớp này chưa có buổi điểm danh nào.")
        st.stop()

    session_options = {
        "[{}] {} ({}) - {}".format(
            s["date"],
            s["title"] or "Buổi học",
            s["start_time"] or "--",
            dict(s).get("session_type", c_type)
        ): s
        for s in sessions
    }
    selected_session_label = st.selectbox("📅 Chọn buổi học", list(session_options.keys()))
    selected_session = session_options[selected_session_label]

st.divider()

# ── Thống kê buổi học ─────────────────────────────────────────────────────────
attendance_rows = db.get_attendance_by_session(selected_session["id"])
total_students  = len(students)

present_count = sum(1 for r in attendance_rows if r["status"] == "present")
late_count    = sum(1 for r in attendance_rows if r["status"] == "late")
absent_count  = sum(1 for r in attendance_rows if r["status"] == "absent")

# Nếu chưa có bản ghi absent nào trong log, sinh viên vắng = total - present - late
unrecorded = total_students - len(attendance_rows)
if unrecorded > 0 and absent_count == 0:
    absent_count += unrecorded

attended_total = present_count + late_count
rate           = attended_total / max(total_students, 1) * 100

# Header banner buổi học
sess_type = dict(selected_session).get("session_type", c_type)
if sess_type == "Lý thuyết":
    type_badge = '<span class="badge-theory">📘 Lý thuyết</span>'
else:
    type_badge = '<span class="badge-practice">🧪 Thực hành</span>'

st.markdown(
    "### 📅 {} · Ngày {} &nbsp;{}".format(
        selected_session["title"],
        selected_session["date"],
        type_badge
    ),
    unsafe_allow_html=True
)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("👥 Tổng sinh viên", total_students)
col2.metric("✅ Đúng giờ", present_count)
col3.metric("⚠️ Đi muộn", late_count)
col4.metric("❌ Vắng mặt", absent_count)
col5.metric("📈 Tỉ lệ tham gia", "{:.1f}%".format(rate))

st.progress(rate / 100)
st.divider()

# ── Bảng chi tiết ─────────────────────────────────────────────────────────────
tab_all, tab_present, tab_late, tab_absent = st.tabs([
    "📋 Tất cả ({})".format(total_students),
    "✅ Đúng giờ ({})".format(present_count),
    "⚠️ Đi muộn ({})".format(late_count),
    "❌ Vắng ({})".format(absent_count),
])

STATUS_LABEL = {
    "present": "✅ Đúng giờ",
    "late":    "⚠️ Đi muộn",
    "absent":  "❌ Vắng mặt",
}

def make_attendance_df(rows, status_filter=None):
    filtered = [r for r in rows if r["status"] == status_filter] if status_filter else list(rows)
    return pd.DataFrame([{
        "STT": i + 1,
        "MSSV": r["student_code"],
        "Họ và Tên": r["full_name"],
        "Giờ Check-in": r["timestamp"][11:19] if r["confidence"] > 0 else "—",
        "Trạng thái": STATUS_LABEL.get(r["status"], "—"),
    } for i, r in enumerate(filtered)])

with tab_all:
    if attendance_rows:
        st.dataframe(make_attendance_df(attendance_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có dữ liệu điểm danh.")

with tab_present:
    df_p = make_attendance_df(attendance_rows, "present")
    if df_p.empty:
        st.caption("Không có sinh viên nào đi đúng giờ.")
    else:
        st.dataframe(df_p, use_container_width=True, hide_index=True)

with tab_late:
    df_l = make_attendance_df(attendance_rows, "late")
    if df_l.empty:
        st.success("🎉 Không có sinh viên nào đi muộn!")
    else:
        st.dataframe(df_l, use_container_width=True, hide_index=True)

with tab_absent:
    df_a = make_attendance_df(attendance_rows, "absent")
    if df_a.empty:
        st.success("🎉 Không có sinh viên nào vắng mặt!")
    else:
        st.dataframe(df_a, use_container_width=True, hide_index=True)

st.divider()

# ── Xuất file ─────────────────────────────────────────────────────────────────
st.markdown("### 📥 Xuất báo cáo Excel")
col_dl1, col_dl2 = st.columns(2)

with col_dl1:
    with st.container(border=True):
        st.markdown("**📄 Xuất buổi học này**")
        st.caption("Bao gồm: MSSV, Họ tên, Lớp, Loại môn, Giờ Check-in, Trạng thái")
        excel_bytes = export_session_to_excel(
            selected_session["id"],
            class_name=selected_cls["name"],
            session_type=sess_type,
        )
        filename = "diemdanh_{}_{}.xlsx".format(selected_cls["code"], selected_session["date"])
        st.download_button(
            label="⬇️ Tải Excel buổi này",
            data=excel_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary",
        )

with col_dl2:
    with st.container(border=True):
        st.markdown("**📊 Xuất tổng hợp cả lớp**")
        st.caption("Bảng tổng hợp tất cả {} buổi của lớp {}".format(len(sessions), selected_cls["name"]))
        summary_bytes = export_class_summary_to_excel(selected_cls["id"])
        summary_filename = "tonghop_{}.xlsx".format(selected_cls["code"])
        st.download_button(
            label="⬇️ Tải Excel tổng hợp",
            data=summary_bytes,
            file_name=summary_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

# ── Lịch sử các buổi ─────────────────────────────────────────────────────────
st.divider()
with st.expander("📅 Lịch sử {} buổi học của lớp {}".format(len(sessions), selected_cls["name"]), expanded=False):
    sess_data = []
    for s in sessions:
        rows = db.get_attendance_by_session(s["id"])
        p_cnt = sum(1 for r in rows if r["status"] == "present")
        l_cnt = sum(1 for r in rows if r["status"] == "late")
        a_cnt = sum(1 for r in rows if r["status"] == "absent")
        unrec = total_students - len(rows)
        if unrec > 0 and a_cnt == 0:
            a_cnt += unrec

        sess_data.append({
            "Ngày": s["date"],
            "Loại môn": dict(s).get("session_type", c_type),
            "Giờ bắt đầu": s["start_time"] or "—",
            "Mốc trễ": s["late_time"] or "—",
            "Tên buổi": s["title"] or "—",
            "Đúng giờ": p_cnt,
            "Đi muộn": l_cnt,
            "Vắng": a_cnt,
            "Tỉ lệ tham gia (%)": "{:.1f}%".format((p_cnt + l_cnt) / max(total_students, 1) * 100),
        })
    df_sess = pd.DataFrame(sess_data)
    st.dataframe(df_sess, use_container_width=True, hide_index=True)
