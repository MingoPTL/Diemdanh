"""
download_models.py
Tự động tải SCRFD + ArcFace models từ InsightFace về thư mục models/
Chạy 1 lần duy nhất: python download_models.py
"""
import shutil
from pathlib import Path

MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

print("=" * 55)
print("  Tải SCRFD + ArcFace models (InsightFace buffalo_l)")
print("=" * 55)

# Dùng insightface để tải model tự động
import insightface
from insightface.app import FaceAnalysis

print("\n[1/3] Đang tải buffalo_l pack (lần đầu sẽ lâu ~300MB)...")
app = FaceAnalysis(name="buffalo_l", root=str(MODELS_DIR / "_insightface_cache"))
app.prepare(ctx_id=0)   # 0 = GPU, -1 = CPU
print("      ✅ Tải xong!")

# Tìm file model trong cache và copy ra models/
cache_dir = MODELS_DIR / "_insightface_cache" / "models" / "buffalo_l"

print("\n[2/3] Copy model files sang thư mục models/...")

# Map tên file trong cache → tên file project dùng
model_map = {
    "det_10g.onnx":     "scrfd_10g_bnkps.onnx",   # detector lớn hơn
    "det_2.5g.onnx":    "scrfd_2.5g_bnkps.onnx",  # detector nhỏ (mặc định)
    "w600k_r50.onnx":   "w600k_r50.onnx",          # recognizer
}

copied = []
for src_name, dst_name in model_map.items():
    src = cache_dir / src_name
    dst = MODELS_DIR / dst_name
    if src.exists():
        shutil.copy2(src, dst)
        size_mb = dst.stat().st_size / 1024 / 1024
        print(f"      ✅ {dst_name} ({size_mb:.1f} MB)")
        copied.append(dst_name)
    else:
        print(f"      ⚠️  Không tìm thấy: {src_name} (bỏ qua)")

print(f"\n[3/3] Đã copy {len(copied)} model files vào: {MODELS_DIR}")

print("""
╔══════════════════════════════════════════════════╗
║  ✅ Hoàn tất! Models sẵn sàng.                  ║
║                                                  ║
║  Chạy app:  streamlit run app.py                 ║
╚══════════════════════════════════════════════════╝
""")
