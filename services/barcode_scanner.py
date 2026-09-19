"""
services/barcode_scanner.py
Module nhận diện & giải mã Barcode (Mã vạch 1D: Code 128, Code 39, EAN...) 
và QR Code từ khung hình camera, hỗ trợ tự động xử lý ảnh lật gương (Mirror) và xoay chiều.
"""
from dataclasses import dataclass
from typing import List, Tuple, Optional
import cv2
import numpy as np
from loguru import logger

# Ưu tiên sử dụng zxingcpp (nhanh, chuẩn xác, hỗ trợ nhiều góc xoay), fallback sang pyzbar hoặc cv2
_BACKEND = "none"
try:
    import zxingcpp
    _BACKEND = "zxingcpp"
except ImportError:
    try:
        from pyzbar import pyzbar
        _BACKEND = "pyzbar"
    except ImportError:
        _BACKEND = "cv2"

logger.info(f"BarcodeScanner initialized with backend: {_BACKEND}")


@dataclass
class BarcodeResult:
    text: str                     # Nội dung mã giải mã được (MSSV)
    format_name: str              # Loại mã (QR_CODE, CODE_128, CODE_39,...)
    points: List[Tuple[int, int]] # Tọa độ 4 đỉnh đa giác quanh mã
    is_mirrored: bool = False     # Có phải phát hiện qua lật gương không


class BarcodeScanner:
    """
    Bộ quét mã vạch và QR Code thông minh:
    - Tự động quét frame gốc.
    - Nếu không thấy, tự động thử quét frame lật ngang (cv2.flip(frame, 1))
      để giải quyết triệt để trường hợp camera bị mirror/lật ngược.
    """

    def __init__(self):
        self.backend = _BACKEND
        if self.backend == "cv2":
            self._cv_barcode = cv2.barcode_BarcodeDetector() if hasattr(cv2, "barcode_BarcodeDetector") else None
            self._cv_qr = cv2.QRCodeDetector()

    def scan(self, frame: np.ndarray, try_mirror: bool = True) -> List[BarcodeResult]:
        """
        Quét và giải mã tất cả Barcode/QR trong ảnh.
        Args:
            frame: Ảnh numpy BGR hoặc Gray.
            try_mirror: Nếu True và frame gốc không tìm thấy mã, tự động lật ảnh quét lại.
        Returns:
            Danh sách BarcodeResult
        """
        if frame is None or frame.size == 0:
            return []

        # 1. Thử quét trên ảnh gốc
        results = self._decode_frame(frame, is_mirrored=False)
        if results:
            return results

        # 2. Nếu không tìm thấy và cho phép try_mirror -> Thử trên ảnh lật gương
        if try_mirror:
            flipped_frame = cv2.flip(frame, 1)
            flipped_results = self._decode_frame(flipped_frame, is_mirrored=True)
            if flipped_results:
                # Điều chỉnh lại tọa độ điểm cho khớp với frame gốc (w - x)
                w = frame.shape[1]
                adjusted_results = []
                for res in flipped_results:
                    orig_pts = [(w - x, y) for (x, y) in res.points]
                    adjusted_results.append(
                        BarcodeResult(
                            text=res.text,
                            format_name=res.format_name,
                            points=orig_pts,
                            is_mirrored=True,
                        )
                    )
                return adjusted_results

        return []

    def _decode_frame(self, img: np.ndarray, is_mirrored: bool = False) -> List[BarcodeResult]:
        results = []
        if self.backend == "zxingcpp":
            try:
                # zxingcpp hỗ trợ trực tiếp numpy ndarray
                detected = zxingcpp.read_barcodes(img)
                for item in detected:
                    if not item.text:
                        continue
                    # item.position là Position object chứa top_left, top_right, bottom_right, bottom_left
                    pos = item.position
                    pts = [
                        (int(pos.top_left.x), int(pos.top_left.y)),
                        (int(pos.top_right.x), int(pos.top_right.y)),
                        (int(pos.bottom_right.x), int(pos.bottom_right.y)),
                        (int(pos.bottom_left.x), int(pos.bottom_left.y)),
                    ]
                    results.append(
                        BarcodeResult(
                            text=item.text.strip(),
                            format_name=str(item.format).replace("BarcodeFormat.", ""),
                            points=pts,
                            is_mirrored=is_mirrored,
                        )
                    )
                return results
            except Exception as e:
                logger.debug(f"zxingcpp decode error: {e}")

        elif self.backend == "pyzbar":
            try:
                from pyzbar import pyzbar
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
                decoded = pyzbar.decode(gray)
                for item in decoded:
                    text = item.data.decode("utf-8", errors="ignore").strip()
                    if not text:
                        continue
                    pts = [(p.x, p.y) for p in item.polygon]
                    if not pts and item.rect:
                        r = item.rect
                        pts = [(r.left, r.top), (r.left + r.width, r.top),
                               (r.left + r.width, r.top + r.height), (r.left, r.top + r.height)]
                    results.append(
                        BarcodeResult(
                            text=text,
                            format_name=item.type,
                            points=pts,
                            is_mirrored=is_mirrored,
                        )
                    )
                return results
            except Exception as e:
                logger.debug(f"pyzbar decode error: {e}")

        else: # cv2 backend
            try:
                # Thử QR code
                retval, decoded_info, points, _ = self._cv_qr.detectAndDecodeMulti(img)
                if retval and points is not None:
                    for text, pts in zip(decoded_info, points):
                        if text:
                            pt_list = [(int(p[0]), int(p[1])) for p in pts]
                            results.append(BarcodeResult(text=text.strip(), format_name="QRCODE", points=pt_list, is_mirrored=is_mirrored))
                # Thử Barcode nếu có
                if not results and self._cv_barcode:
                    ok, decoded_info, decoded_type, points = self._cv_barcode.detectAndDecode(img)
                    if ok and points is not None:
                        for text, btype, pts in zip(decoded_info, decoded_type, points):
                            if text:
                                pt_list = [(int(p[0]), int(p[1])) for p in pts]
                                results.append(BarcodeResult(text=text.strip(), format_name=str(btype), points=pt_list, is_mirrored=is_mirrored))
            except Exception as e:
                logger.debug(f"cv2 barcode decode error: {e}")

        return results


def draw_barcode_box(
    img: np.ndarray,
    points: List[Tuple[int, int]],
    label: str,
    is_valid: bool = True
) -> np.ndarray:
    """
    Vẽ khung viền nổi bật & nhãn văn bản quanh mã vạch / QR Code.
    Màu xanh lá neon khi hợp lệ, màu vàng cam khi chưa xác thực hoặc cảnh báo.
    """
    if not points or len(points) < 4:
        return img

    color = (0, 230, 115) if is_valid else (0, 165, 255) # BGR
    pts_np = np.array(points, dtype=np.int32).reshape((-1, 1, 2))

    # Vẽ khung viền phát sáng
    cv2.polylines(img, [pts_np], isClosed=True, color=color, thickness=3)

    # Lấy góc trên bên trái để vẽ nhãn
    min_x = max(0, min(p[0] for p in points))
    min_y = max(0, min(p[1] for p in points))

    # Nền nhãn
    font = cv2.FONT_HERSHEY_DUPLEX
    font_scale = 0.65
    thickness = 1
    (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)

    tag_y1 = max(0, min_y - th - 12)
    tag_y2 = min_y
    tag_x1 = min_x
    tag_x2 = min_x + tw + 16

    cv2.rectangle(img, (tag_x1, tag_y1), (tag_x2, tag_y2), color, -1)
    cv2.putText(img, label, (tag_x1 + 8, tag_y2 - 6), font, font_scale, (15, 23, 42), thickness, cv2.LINE_AA)

    return img


# Singleton
barcode_scanner = BarcodeScanner()
