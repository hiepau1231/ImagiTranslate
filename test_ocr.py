import os
import sys

# Fix Windows console encoding (GBK default → UTF-8) trước khi print bất kỳ ký tự Vietnamese
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from PIL import Image, ImageDraw, ImageFont


# --- Font helper (no network dependency) ---

def _get_cjk_font(size=28):
    """Tìm font CJK trên hệ thống. Nếu không tìm thấy thì raise RuntimeError kèm hướng dẫn cài đặt."""
    font_paths = [
        'C:/Windows/Fonts/simsun.ttc',    # Windows (always present on standard install)
        'C:/Windows/Fonts/msyh.ttc',       # Windows alternative
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',   # Debian/Ubuntu: apt install fonts-wqy-zenhei
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',  # noto-cjk package
        '/System/Library/Fonts/PingFang.ttc',              # macOS
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    raise RuntimeError(
        "No CJK font found. Install one:\n"
        "  Windows: simsun.ttc is built-in. If missing, something is wrong.\n"
        "  Ubuntu/Debian: sudo apt-get install fonts-wqy-zenhei\n"
        "  macOS: PingFang.ttc should be present. If not, install Noto CJK."
    )


def _make_cjk_image():
    """Tạo ảnh synthetic có chữ Chinese để test (không cần network)."""
    font = _get_cjk_font(28)
    img = Image.new('RGB', (300, 60), color='white')
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "\u4f60\u597d\u4e16\u754c\u6d4b\u8bd5", font=font, fill='black')
    return img


# --- Detector tests ---

def test_positive():
    """detect_cjk_bboxes() trả về >= 1 bbox với ảnh có chữ Chinese."""
    print("\n=== test_positive: ảnh có chữ Chinese ===")
    from ocr_detector import detect_cjk_bboxes

    img = _make_cjk_image()
    bboxes = detect_cjk_bboxes(img)
    assert len(bboxes) >= 1, f"Expected >= 1 bbox, got {len(bboxes)}"
    for b in bboxes:
        assert all(k in b for k in ('x1', 'y1', 'x2', 'y2')), f"Thiếu key trong bbox: {b}"
        assert 0.0 <= b['x1'] < b['x2'] <= 1.0, f"x range không hợp lệ: {b}"
        assert 0.0 <= b['y1'] < b['y2'] <= 1.0, f"y range không hợp lệ: {b}"
    print(f"[PASS] Phát hiện {len(bboxes)} bbox: {bboxes}")
    return True


def test_negative():
    """detect_cjk_bboxes() trả về [] với ảnh chỉ có chữ Latin."""
    print("\n=== test_negative: ảnh chỉ có chữ Latin ===")
    from ocr_detector import detect_cjk_bboxes

    img = Image.new('RGB', (200, 50), color='white')
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "Hello World", fill='black')

    bboxes = detect_cjk_bboxes(img)
    assert bboxes == [], f"Expected [], got {bboxes}"
    print("[PASS] Không phát hiện Chinese (đúng như kỳ vọng)")
    return True


def test_empty():
    """detect_cjk_bboxes() trả về [] với ảnh trắng."""
    print("\n=== test_empty: ảnh trắng ===")
    from ocr_detector import detect_cjk_bboxes

    img = Image.new('RGB', (200, 200), color='white')
    bboxes = detect_cjk_bboxes(img)
    assert bboxes == [], f"Expected [], got {bboxes}"
    print("[PASS] Không phát hiện Chinese trong ảnh trắng")
    return True


# --- Integration test (chạy SAU khi Task 3 hoàn thành) ---

def test_verify_and_patch_integration():
    """verify_and_patch() calls detect_cjk_bboxes() và patch đúng bbox trả về.

    Test này mock detect_cjk_bboxes và _translate_single_tile để không cần
    Gemini API hay PaddleOCR chạy thật. Assert cả control flow lẫn pixel change.
    """
    print("\n=== test_verify_and_patch_integration ===")
    from unittest.mock import patch, MagicMock, call
    from grid_translator import verify_and_patch

    # Image 200x200 — pixel nền là trắng (255, 255, 255)
    img = Image.new('RGB', (200, 200), color='white')
    client = MagicMock()

    # detect: bbox normalize x1=0.1,y1=0.1,x2=0.5,y2=0.5 → pixel crop [20,20]→[100,100]
    detected = [{'x1': 0.1, 'y1': 0.1, 'x2': 0.5, 'y2': 0.5}]
    call_count = [0]

    def mock_detect(image):
        call_count[0] += 1
        return detected if call_count[0] == 1 else []

    # dummy_tile: solid blue — khi paste vào ảnh, pixel tại bbox center phải thành blue
    dummy_tile = Image.new('RGB', (80, 80), color=(0, 0, 255))
    translate_mock = MagicMock(return_value=dummy_tile)

    with patch('grid_translator.detect_cjk_bboxes', side_effect=mock_detect), \
         patch('grid_translator._translate_single_tile', translate_mock):
        result = verify_and_patch(img, client, 'Vietnamese', max_passes=3)

    # Control flow: detect gọi đúng 2 lần (pass 1: found → 1 clean → stop early)
    assert call_count[0] == 2, (
        f"Expected detect called 2x (1 found → 1 clean), got {call_count[0]}x"
    )
    # Patch path: _translate_single_tile phải được gọi ít nhất 1 lần
    translate_mock.assert_called()
    # Pixel change: pixel tại trung tâm bbox [20,20]→[100,100] → center (60,60) phải là blue
    assert isinstance(result, Image.Image), "Result should be a PIL Image"
    center_pixel = result.getpixel((60, 60))
    assert center_pixel[2] > center_pixel[0], (
        f"Expected blue (patched) pixel at (60,60), got {center_pixel}. "
        "Patch may not have executed."
    )
    print(f"[PASS] verify_and_patch: detect={call_count[0]}x, translate called, "
          f"pixel at (60,60)={center_pixel} (blue=patched ✓)")
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--integration', action='store_true',
                        help='Chạy thêm test_verify_and_patch_integration (cần Task 3 hoàn thành)')
    args = parser.parse_args()

    tests = [test_positive, test_negative, test_empty]
    if args.integration:
        tests.append(test_verify_and_patch_integration)

    results = []
    for fn in tests:
        try:
            results.append(fn())
        except AssertionError as e:
            print(f"[FAIL] {fn.__name__}: {e}")
            results.append(False)
        except Exception as e:
            print(f"[ERROR] {fn.__name__}: {e}")
            results.append(False)

    passed = sum(1 for r in results if r)
    print(f"\n{passed}/{len(results)} tests passed.")
    sys.exit(0 if all(results) else 1)
