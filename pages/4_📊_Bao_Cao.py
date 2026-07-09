"""
pages/4_📊_Bao_Cao.py
Trang báo cáo: xem kết quả điểm danh + xuất Excel
"""
import streamlit as st
import pandas as pd
from datetime import date

import database.db as db
from services.export import export_session_to_excel, export_class_summary_to_excel
from utils.helpers import format_datetime

st.set_page_config(page_title="Báo Cáo", page_icon="📊", layout="wide")

st.markdown("""
<style>
.stat-row { display:flex; gap:12px; margin-bottom:12px; flex-wrap:wrap; }
.stat-chip {
    background:#1C2333; border:1px solid #2D3748; border-radius:8px;
    padding:8px 16px; font-size:0.85rem;
}
.stat-chip b { color:#90CDF4; }
.present-row { background: rgba(39,103,73,0.15); }
.absent-row  { background: rgba(116,42,42,0.15); }
.late-row    { background: rgba(116,66,16,0.15); }
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
    cls_options = {f"{c['name']} ({c['code']})": c for c in classes}
    selected_cls_label = st.selectbox("🏫 Chọn lớp", list(cls_options.keys()))
    selected_cls = cls_options[selected_cls_label]

sessions = db.get_sessions_by_class(selected_cls["id"])
students = db.get_all_students(selected_cls["id"])

with col_sel2:
    if not sessions:
        st.warning("Lớp này chưa có buổi điểm danh nào.")
        st.stop()

    session_options = {
        f"[{s['date']}] {s['title'] or 'Buổi học'} ({s['start_time'] or '--'})": s
        for s in sessions
    }
    selected_session_label = st.selectbox("📅 Chọn buổi học", list(session_options.keys()))
    selected_session = session_options[selected_session_label]

st.divider()

# ── Thống kê buổi học ─────────────────────────────────────────────────────────
attendance_rows = db.get_attendance_by_session(selected_session["id"])
attended_ids    = {r["student_id"] for r in attendance_rows}
total_students  = len(students)
total_present   = len(attended_ids)
total_absent    = total_students - total_present
rate            = total_present / max(total_students, 1) * 100

st.markdown(f"### 📅 {selected_session['title']} · {selected_session['date']}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("👥 Tổng sinh viên", total_students)
col2.metric("✅ Có mặt",   total_present, delta=f"+{total_present}" if total_present else None)
col3.metric("❌ Vắng",     total_absent,  delta=f"-{total_absent}"  if total_absent  else None, delta_color="inverse")
col4.metric("📈 Tỉ lệ",   f"{rate:.1f}%")

st.progress(rate / 100)
st.divider()

# ── Bảng chi tiết ─────────────────────────────────────────────────────────────
tab_present, tab_absent, tab_all = st.tabs(
    [f"✅ Có mặt ({total_present})", f"❌ Vắng ({total_absent})", f"📋 Tất cả ({total_students})"]
)

def make_present_df(rows):
    return pd.DataFrame([{
        "STT": i+1,
        "MSSV": r["student_code"],
        "Họ và Tên": r["full_name"],
        "Thời gian": r["timestamp"][11:19],
        "Độ tin cậy": f"{r['confidence']*100:.1f}%",
        "Trạng thái": {"present":"✅ Có mặt","late":"⚠️ Muộn","absent":"❌ Vắng"}.get(r["status"],"—"),
    } for i, r in enumerate(rows)])

def make_absent_df(all_students, attended_ids):
    absent = [s for s in all_students if s["id"] not in attended_ids]
    return pd.DataFrame([{
        "STT": i+1,
        "MSSV": s["student_code"],
        "Họ và Tên": s["full_name"],
        "Trạng thái": "❌ Vắng",
    } for i, s in enumerate(absent)])

with tab_present:
    if attendance_rows:
        df_p = make_present_df(attendance_rows)
        st.dataframe(df_p, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có ai được điểm danh trong buổi này.")

with tab_absent:
    df_a = make_absent_df(students, attended_ids)
    if df_a.empty:
        st.success("🎉 Tất cả sinh viên đều có mặt!")
    else:
        st.dataframe(df_a, use_container_width=True, hide_index=True)

with tab_all:
    # Gộp cả 2 danh sách
    present_map = {r["student_id"]: r for r in attendance_rows}
    all_rows = []
    for i, s in enumerate(students):
        r = present_map.get(s["id"])
        all_rows.append({
            "STT": i+1,
            "MSSV": s["student_code"],
            "Họ và Tên": s["full_name"],
            "Thời gian": r["timestamp"][11:19] if r else "—",
            "Độ tin cậy": f"{r['confidence']*100:.1f}%" if r else "—",
            "Trạng thái": "✅ Có mặt" if r else "❌ Vắng",
        })
    df_all = pd.DataFrame(all_rows)
    st.dataframe(df_all, use_container_width=True, hide_index=True,
                 column_config={"Trạng thái": st.column_config.TextColumn(width="small")})

st.divider()

# ── Xuất file ─────────────────────────────────────────────────────────────────
st.markdown("### 📥 Xuất báo cáo")
col_dl1, col_dl2 = st.columns(2)

with col_dl1:
    with st.container(border=True):
        st.markdown("**📄 Xuất buổi học này**")
        st.caption(f"File Excel chi tiết buổi: {selected_session['title']}")
        excel_bytes = export_session_to_excel(selected_session["id"])
        filename = f"diemdanh_{selected_cls['code']}_{selected_session['date']}.xlsx"
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
        st.caption(f"Pivot table tất cả {len(sessions)} buổi của lớp {selected_cls['name']}")
        summary_bytes = export_class_summary_to_excel(selected_cls["id"])
        summary_filename = f"tonghop_{selected_cls['code']}.xlsx"
        st.download_button(
            label="⬇️ Tải Excel tổng hợp",
            data=summary_bytes,
            file_name=summary_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

# ── Lịch sử các buổi ─────────────────────────────────────────────────────────
st.divider()
with st.expander(f"📅 Lịch sử {len(sessions)} buổi học của lớp {selected_cls['name']}", expanded=False):
    sess_data = []
    for s in sessions:
        rows = db.get_attendance_by_session(s["id"])
        sess_data.append({
            "Ngày": s["date"],
            "Giờ bắt đầu": s["start_time"] or "—",
            "Tên buổi": s["title"] or "—",
            "Có mặt": len(rows),
            "Vắng": total_students - len(rows),
            "Tỉ lệ (%)": f"{len(rows)/max(total_students,1)*100:.1f}%",
        })
    df_sess = pd.DataFrame(sess_data)
    st.dataframe(df_sess, use_container_width=True, hide_index=True)
