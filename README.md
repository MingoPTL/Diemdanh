# 📷 Hệ Thống Điểm Danh Khuôn Mặt
**SCRFD + ArcFace · Streamlit · ONNXRuntime GPU**

---

## 🗂️ Cấu trúc project

```
DiemDanh/
├── app.py                      # Dashboard chính
├── pages/
│   ├── 1_📷_Diem_Danh.py      # Camera live + điểm danh
│   ├── 2_👤_Dang_Ky.py        # Đăng ký khuôn mặt
│   ├── 3_📋_Quan_Ly_Lop.py    # Quản lý lớp/sinh viên
│   └── 4_📊_Bao_Cao.py        # Báo cáo + xuất Excel
├── core/
│   ├── detector.py             # SCRFD wrapper
│   ├── recognizer.py           # ArcFace wrapper
│   ├── aligner.py              # Face alignment 112x112
│   └── pipeline.py             # Pipeline tổng hợp
├── services/
│   ├── face_db.py              # Quản lý embeddings
│   ├── attendance.py           # Logic điểm danh
│   └── export.py               # Xuất Excel/PDF
├── database/
│   └── db.py                   # SQLite schema + queries
├── utils/
│   ├── config.py               # Cấu hình hệ thống
│   └── helpers.py              # Tiện ích dùng chung
├── models/                     # Đặt ONNX models vào đây
├── data/
│   ├── embeddings/             # Face vectors (.npy)
│   └── photos/                 # Ảnh đăng ký
└── .streamlit/config.toml      # Streamlit dark theme
```

---

## ⚙️ Cài đặt

### 1. Tạo môi trường Python
```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Tải ONNX Models
Đặt vào thư mục `models/`:

| File | Link tải | Mô tả |
|------|----------|-------|
| `scrfd_2.5g_bnkps.onnx` | [InsightFace](https://github.com/deepinsight/insightface/tree/master/detection/scrfd) | Face detector nhẹ |
| `w600k_r50.onnx` | [ArcFace](https://github.com/deepinsight/insightface/tree/master/recognition/arcface_torch) | Face recognizer R50 |

> **Cách nhanh nhất**: Dùng `insightface` Python package tự tải:
> ```python
> import insightface
> app = insightface.app.FaceAnalysis(name='buffalo_l')
> app.prepare(ctx_id=0)  # 0 = GPU
> ```

### 3. Chạy ứng dụng
```bash
streamlit run app.py
```
Truy cập: `http://localhost:8501`

---

## 🚀 Luồng sử dụng

```
1. 📋 Quản Lý Lớp  →  Tạo lớp + thêm sinh viên (hoặc import Excel)
2. 👤 Đăng Ký      →  Chụp 5 ảnh khuôn mặt từng sinh viên
3. 📷 Điểm Danh    →  Bắt đầu buổi → camera tự nhận diện
4. 📊 Báo Cáo      →  Xem kết quả + tải Excel
```

---

## 🔧 Cấu hình

Chỉnh các tham số tại `utils/config.py`:

| Tham số | Mặc định | Ý nghĩa |
|---------|----------|---------|
| `SIMILARITY_THRESHOLD` | `0.45` | Ngưỡng nhận diện (tăng = chặt hơn) |
| `REGISTER_SAMPLES` | `5` | Số ảnh chụp khi đăng ký |
| `MIN_FACE_SIZE` | `50` | Bỏ qua khuôn mặt nhỏ hơn 50px |
| `ONNX_PROVIDERS` | `["CUDAExecutionProvider", ...]` | GPU → CPU fallback |

---

## 💻 Yêu cầu hệ thống

- Python 3.10+
- NVIDIA GPU (RTX 4050 6GB ✅)
- CUDA 11.8+ / cuDNN 8+
- Webcam
