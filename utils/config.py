"""
config.py - Hằng số và cấu hình toàn hệ thống
"""
from pathlib import Path

# ── Thư mục gốc project ───────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ── Đường dẫn models ──────────────────────────────────────────────────────────
MODELS_DIR        = BASE_DIR / "models"
SCRFD_MODEL_PATH  = MODELS_DIR / "scrfd_10g_bnkps.onnx"
ARCFACE_MODEL_PATH= MODELS_DIR / "w600k_r50.onnx"
ANTISPOOF_MODEL_PATH = MODELS_DIR / "silent_face.onnx"  # optional

# ── Đường dẫn dữ liệu ─────────────────────────────────────────────────────────
DATA_DIR          = BASE_DIR / "data"
EMBEDDINGS_DIR    = DATA_DIR / "embeddings"   # lưu {student_id}.npy
PHOTOS_DIR        = DATA_DIR / "photos"       # lưu {student_id}/*.jpg

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_DIR      = BASE_DIR / "database"
DATABASE_PATH     = DATABASE_DIR / "diemdanh.db"
DATABASE_URL      = f"sqlite:///{DATABASE_PATH}"

# ── ONNX Runtime providers ────────────────────────────────────────────────────
# Ưu tiên GPU (RTX 4050), fallback về CPU
ONNX_PROVIDERS = ["CUDAExecutionProvider", "CPUExecutionProvider"]

# ── Ngưỡng nhận diện ─────────────────────────────────────────────────────────
SIMILARITY_THRESHOLD  = 0.55   # cosine similarity để coi là khớp
DETECTION_THRESHOLD   = 0.6    # confidence tối thiểu khi detect face
INPUT_SIZE            = (640, 640)  # input SCRFD
FACE_SIZE             = (112, 112)  # input ArcFace

# ── Camera ────────────────────────────────────────────────────────────────────
CAMERA_INDEX   = 0      # 0 = webcam mặc định của laptop
FRAME_WIDTH    = 1280
FRAME_HEIGHT   = 720

# ── Logic điểm danh ───────────────────────────────────────────────────────────
COOLDOWN_SECONDS   = 60    # không ghi trùng trong vòng N giây
MIN_FACE_SIZE      = 50    # bỏ qua khuôn mặt quá nhỏ (pixel)
REGISTER_SAMPLES   = 5     # số ảnh chụp khi đăng ký khuôn mặt mới

# ── UI ────────────────────────────────────────────────────────────────────────
APP_TITLE    = "Hệ Thống Điểm Danh Khuôn Mặt"
APP_ICON     = "📷"
APP_VERSION  = "1.0.0"

# Tạo các thư mục cần thiết nếu chưa có
for _dir in [MODELS_DIR, EMBEDDINGS_DIR, PHOTOS_DIR, DATABASE_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)
