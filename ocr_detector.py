import numpy as np
from paddleocr import PaddleOCR

# Ngưỡng confidence tối thiểu để chấp nhận một bbox
CJK_CONFIDENCE_THRESHOLD = 0.5

# Chinese ideograph Unicode ranges (scope là Chinese-only, không bao gồm kana/hangul)
_CHINESE_RANGES = [
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs (main Han range)
    (0x3400, 0x4DBF),   # CJK Extension A
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
]

# Lazy-loaded PaddleOCR instance — chỉ khởi tạo khi cần
_ocr = None


def _has_chinese(text):
    """Trả về True nếu text chứa ít nhất 1 ký tự Chinese ideograph."""
    for ch in text:
        cp = ord(ch)
        for lo, hi in _CHINESE_RANGES:
            if lo <= cp <= hi:
                return True
    return False


def _get_ocr():
    """Khởi tạo PaddleOCR lần đầu, cache cho các lần sau."""
    global _ocr
    if _ocr is None:
        print("[ocr_detector] Khoi tao PaddleOCR lan dau — co the mat vai phut neu can download model (~200MB)...")
        _ocr = PaddleOCR(
            use_angle_cls=True,   # detect text bị nghiêng (game UI hay có)
            lang='ch',            # Chinese model — tốt nhất cho Han detection
            show_log=False        # tắt verbose output
        )
    return _ocr


def detect_cjk_bboxes(pil_image):
    """Phát hiện vùng còn chứa Chinese ideographs trong ảnh đã dịch.

    Scope: Chinese ideographs (U+4E00-U+9FFF và các extension). Không detect kana hay hangul.

    Args:
        pil_image: PIL.Image — ảnh đã dịch cần kiểm tra

    Returns:
        List[{x1, y1, x2, y2}] — normalized 0.0-1.0, axis-aligned bboxes.
        Trả về [] nếu không còn chữ Chinese hoặc nếu OCR lỗi.
    """
    img_w, img_h = pil_image.size
    if img_w == 0 or img_h == 0:
        return []
    # PaddleOCR yêu cầu numpy array RGB
    img_array = np.array(pil_image.convert('RGB'))

    try:
        ocr = _get_ocr()
        result = ocr.ocr(img_array, cls=True)
    except Exception as e:
        print(f"[ocr_detector] Loi OCR, bo qua detect: {e}")
        return []

    if not result or result[0] is None:
        return []

    bboxes = []
    for line in result[0]:
        try:
            polygon, (text, confidence) = line
        except (ValueError, TypeError):
            continue

        # Lọc bỏ bbox có confidence thấp (tránh false positive từ texture/background)
        if confidence < CJK_CONFIDENCE_THRESHOLD:
            continue

        # Lọc chỉ giữ bbox chứa ký tự Chinese ideograph
        if not _has_chinese(text):
            continue

        # Convert polygon 4 điểm sang axis-aligned bbox, normalize về [0, 1]
        xs = [pt[0] for pt in polygon]
        ys = [pt[1] for pt in polygon]
        x1 = max(0.0, min(1.0, min(xs) / img_w))
        y1 = max(0.0, min(1.0, min(ys) / img_h))
        x2 = max(0.0, min(1.0, max(xs) / img_w))
        y2 = max(0.0, min(1.0, max(ys) / img_h))

        if x1 < x2 and y1 < y2:
            bboxes.append({'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})

    return bboxes
