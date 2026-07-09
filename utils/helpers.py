"""
helpers.py - Các hàm tiện ích dùng chung
"""
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path
from loguru import logger


def draw_face_box(
    frame: np.ndarray,
    box: tuple,
    name: str,
    confidence: float,
    color: tuple = (0, 255, 0),
) -> np.ndarray:
    """
    Vẽ bounding box + tên lên frame (hỗ trợ tiếng Việt Unicode).

    Args:
        frame: BGR image array
        box: (x1, y1, x2, y2)
        name: Tên sinh viên hoặc 'Unknown'
        confidence: Điểm tương đồng (0-1)
        color: BGR color tuple
    """
    x1, y1, x2, y2 = [int(v) for v in box]
    is_unknown = name == "Unknown"
    color = (0, 0, 255) if is_unknown else color  # Red nếu không nhận ra, Green nếu nhận ra

    # Vẽ bounding box bằng OpenCV
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    # Nhãn hiển thị
    label = f"{name} ({confidence:.2f})" if not is_unknown else "Unknown"
    
    # Dùng PIL để vẽ chữ Unicode tiếng Việt
    from PIL import Image, ImageDraw, ImageFont
    
    # Convert OpenCV BGR sang PIL RGB
    img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    
    # Tìm font hệ thống hỗ trợ tiếng Việt trên Windows
    font_paths = [
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\calibri.ttf",
        "arial.ttf"
    ]
    font = None
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, 15)
            break
        except Exception:
            continue
            
    if font is None:
        font = ImageFont.load_default()
        
    # Tính toán kích thước chữ để vẽ background box
    try:
        # Pillow >= 10.0.0
        bbox_text = draw.textbbox((0, 0), label, font=font)
        tw = bbox_text[2] - bbox_text[0]
        th = bbox_text[3] - bbox_text[1]
    except AttributeError:
        # Pillow < 10.0.0 fallback
        tw, th = draw.textsize(label, font=font)
        
    # Vẽ hình nền cho chữ (màu trùng với màu khung, đảo BGR -> RGB)
    rgb_color = (color[2], color[1], color[0])
    draw.rectangle([x1, y1 - th - 8, x1 + tw + 6, y1], fill=rgb_color)
    
    # Vẽ chữ màu trắng
    draw.text((x1 + 3, y1 - th - 5), label, font=font, fill=(255, 255, 255))
    
    # Ghi đè ngược lại frame gốc dạng BGR
    frame[:] = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    return frame


def bgr_to_rgb(frame: np.ndarray) -> np.ndarray:
    """Convert OpenCV BGR frame sang RGB cho Streamlit."""
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def resize_frame(frame: np.ndarray, max_width: int = 960) -> np.ndarray:
    """Thu nhỏ frame nếu quá lớn, giữ tỷ lệ khung hình."""
    h, w = frame.shape[:2]
    if w <= max_width:
        return frame
    scale = max_width / w
    return cv2.resize(frame, (max_width, int(h * scale)))


def normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    """L2-normalize embedding vector."""
    norm = np.linalg.norm(embedding)
    return embedding / (norm + 1e-6)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Tính cosine similarity giữa 2 embedding đã normalize."""
    return float(np.dot(a, b))


def save_photo(frame: np.ndarray, student_id: str, index: int) -> Path:
    """Lưu ảnh đăng ký vào data/photos/{student_id}/."""
    from utils.config import PHOTOS_DIR
    save_dir = PHOTOS_DIR / student_id
    save_dir.mkdir(parents=True, exist_ok=True)
    filename = save_dir / f"{index:03d}.jpg"
    cv2.imwrite(str(filename), frame)
    return filename


def timestamp_str() -> str:
    """Trả về chuỗi timestamp hiện tại dạng YYYYMMDD_HHMMSS."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def format_datetime(dt: datetime) -> str:
    """Format datetime sang dạng hiển thị tiếng Việt."""
    return dt.strftime("%d/%m/%Y %H:%M:%S") if dt else "--"


def setup_logger():
    """Cấu hình logger."""
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="7 days",
        level="INFO",
        encoding="utf-8",
    )
