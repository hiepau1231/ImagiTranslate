# PaddleOCR Verify Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thay thế bước Gemini TEXT-only bbox detection trong `verify_and_patch()` bằng PaddleOCR để detect **chữ Chinese ideographs (Han, U+4E00–U+9FFF)** còn sót chính xác hơn, không tốn Gemini API call. Scope là Chinese-only (không bao gồm kana hay hangul) — phù hợp với use case Chinese game UI → Vietnamese.

**Architecture:** Tạo `ocr_detector.py` wrap PaddleOCR với lazy init, expose `detect_cjk_bboxes(pil_image) → list[dict]`. Sửa `grid_translator.py` xóa `VERIFY_PROMPT`, `_parse_bboxes()`, và Gemini detect block — thay bằng call `detect_cjk_bboxes()` có try/except. Phần patch (crop → upscale → Gemini image gen → paste) giữ nguyên; các guard `VERIFY_MIN_CROP_PX`/`VERIFY_MAX_BBOX_AREA` xử lý box fragmentation của OCR.

**Tech Stack:** PaddleOCR 2.7+, PaddlePaddle 2.6+, Pillow (đã có), NumPy (đã có)

---

## File Map

| File | Action | Mô tả |
|------|--------|-------|
| `ocr_detector.py` | Create | Wrap PaddleOCR, expose `detect_cjk_bboxes()` |
| `test_ocr.py` | Create | Smoke tests: 3 detector tests + 1 verify_and_patch integration test |
| `grid_translator.py` | Modify | Xóa Gemini detect block + dead code, thêm OCR call với try/except |
| `requirements.txt` | Modify | Thêm paddlepaddle + paddleocr |

---

## Task 1: Cài PaddleOCR dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Thêm dependencies vào requirements.txt**

Mở `requirements.txt` và thêm 2 dòng cuối:

```
google-genai>=0.2.2
pillow>=10.2.0
flask>=3.0.0
werkzeug>=3.0.0
paddlepaddle>=2.6.0
paddleocr>=2.7.0
```

- [ ] **Step 2: Install dependencies**

```bash
pip install "paddlepaddle>=2.6.0" "paddleocr>=2.7.0"
```

Expected output (sau khi hoàn tất, không có error):
```
Successfully installed paddlepaddle-... paddleocr-...
```

> **Lưu ý:** `pip install` có thể mất 2-5 phút do package lớn. Model OCR (~200MB) sẽ download lần đầu chạy, không phải lúc install.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add paddlepaddle and paddleocr dependencies"
```

---

## Task 2: Tạo `ocr_detector.py` (TDD)

**Files:**
- Create: `test_ocr.py`
- Create: `ocr_detector.py`

- [ ] **Step 1: Viết test file (failing)**

**Prerequisite (font):** `_get_cjk_font()` tìm font CJK trên hệ thống, không có network fallback. Trên Windows (dev machine), `simsun.ttc` luôn có sẵn. Trên Linux: `sudo apt-get install fonts-wqy-zenhei`. Trên macOS: `PingFang.ttc` có sẵn. Nếu không có font, `_get_cjk_font()` raise RuntimeError với hướng dẫn.

Tạo file `test_ocr.py` ở root project:

```python
import os
import sys
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

    # Control flow: detect gọi đúng 2 lần (pass 1: found, pass 2: clean → stop early)
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
```

- [ ] **Step 2: Chạy test — verify FAIL**

```bash
python test_ocr.py
```

Expected output:
```
[ERROR] test_positive: No module named 'ocr_detector'
[ERROR] test_negative: No module named 'ocr_detector'
[ERROR] test_empty: No module named 'ocr_detector'
0/3 tests passed.
```

Nếu thấy `ModuleNotFoundError: No module named 'ocr_detector'` — đây là trạng thái fail đúng, tiếp tục.

- [ ] **Step 3: Implement `ocr_detector.py`**

Tạo file `ocr_detector.py` ở root project. Scope là Chinese ideographs (Hanzi) — phù hợp với use case Chinese game UI:

```python
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
        print("[ocr_detector] Khởi tạo PaddleOCR lần đầu — có thể mất vài phút nếu cần download model (~200MB)...")
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
    # PaddleOCR yêu cầu numpy array RGB
    img_array = np.array(pil_image.convert('RGB'))

    try:
        ocr = _get_ocr()
        result = ocr.ocr(img_array, cls=True)
    except Exception as e:
        print(f"[ocr_detector] Lỗi OCR, bỏ qua detect: {e}")
        return []

    if not result or result[0] is None:
        return []

    bboxes = []
    for line in result[0]:
        polygon, (text, confidence) = line

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
```

**Lưu ý về OCR box fragmentation:** PaddleOCR thường trả về các box nhỏ (1-3 ký tự mỗi box). Các guard đã có trong `grid_translator.py` xử lý điều này:
- `VERIFY_MIN_CROP_PX = 20`: bỏ qua box quá nhỏ để patch
- `VERIFY_MAX_BBOX_AREA = 0.80`: bỏ qua box chiếm > 80% ảnh

Không cần preprocessing thêm.

- [ ] **Step 4: Chạy test — verify PASS**

```bash
python test_ocr.py
```

Expected output (lần đầu chạy sẽ thấy download log của PaddleOCR):
```
[ocr_detector] Khởi tạo PaddleOCR lần đầu — có thể mất vài phút nếu cần download model (~200MB)...

=== test_positive: ảnh có chữ Chinese ===
[PASS] Phát hiện 1 bbox: [{'x1': 0.03, 'y1': 0.1, 'x2': 0.94, 'y2': 0.9}]

=== test_negative: ảnh chỉ có chữ Latin ===
[PASS] Không phát hiện Chinese (đúng như kỳ vọng)

=== test_empty: ảnh trắng ===
[PASS] Không phát hiện Chinese trong ảnh trắng

3/3 tests passed.
```

Gate yêu cầu **3/3 passed**. Nếu bất kỳ test nào FAIL hoặc ERROR, debug trước khi commit.

- [ ] **Step 5: Commit**

```bash
git add ocr_detector.py test_ocr.py
git commit -m "feat: add ocr_detector with PaddleOCR Chinese ideograph detection"
```

---

## Task 3: Cập nhật `grid_translator.py`

**Files:**
- Modify: `grid_translator.py` (xóa dead code + thay Gemini detect block)

- [ ] **Step 1: Xóa unused imports**

Mở `grid_translator.py`. Dòng 1-8 hiện tại:

```python
import io
import json
import math
import re
import time
import numpy as np
from PIL import Image
from google.genai import types
```

Sau khi xóa `_parse_bboxes()`, các import `json`, `math`, `re` trở nên không dùng. Sửa thành:

```python
import io
import time
import numpy as np
from PIL import Image
from google.genai import types
from ocr_detector import detect_cjk_bboxes
```

- [ ] **Step 2: Xóa `VERIFY_PROMPT` constant**

Tìm và xóa toàn bộ block này (dòng 24-34):

```python
VERIFY_PROMPT = (
    "Examine this image carefully. "
    "Find ALL remaining Chinese characters (Hanzi/CJK Unified Ideographs, "
    "including Simplified and Traditional Chinese). "
    "Return ONLY a valid JSON array of bounding boxes: "
    '[{"x1": 0.1, "y1": 0.2, "x2": 0.3, "y2": 0.4}] '
    "Coordinates are normalized 0.0-1.0 relative to image dimensions "
    "(x1,y1 = top-left corner, x2,y2 = bottom-right corner). "
    "If no Chinese text remains, return exactly: [] "
    "Return ONLY the JSON array, nothing else."
)
```

- [ ] **Step 3: Xóa `_parse_bboxes()` function**

Tìm và xóa toàn bộ function `_parse_bboxes()` (khoảng dòng 48-111):

```python
def _parse_bboxes(response_text):
    """Parse JSON bounding boxes from Gemini verify response.
    ...
    """
    # ... toàn bộ function body ...
```

Xóa từ dòng `def _parse_bboxes(response_text):` đến dòng `return [], False, False` cuối cùng (kèm dòng trắng sau).

- [ ] **Step 4: Thay Gemini detect block trong `verify_and_patch()`**

Trong function `verify_and_patch()`, tìm block này (bắt đầu từ comment `# Send image to Gemini to detect remaining CJK text`):

```python
        # Send image to Gemini to detect remaining CJK text
        try:
            verify_response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[image, VERIFY_PROMPT],
                config=types.GenerateContentConfig(
                    response_modalities=['TEXT']
                )
            )
            response_text = ''
            if verify_response and verify_response.candidates:
                for part in verify_response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                        response_text += part.text
        except Exception as e:
            print(f"[verify_and_patch] Pass {pass_num + 1}: Lỗi gọi verify API: {e}")
            break

        bboxes, parse_ok, had_invalid = _parse_bboxes(response_text)

        if not parse_ok:
            # Gemini returned non-JSON: log warning, skip this pass
            print(f"[verify_and_patch] Pass {pass_num + 1}: Cảnh báo — Gemini trả về non-JSON. Bỏ qua lượt này.")
            continue

        if not bboxes and had_invalid:
            # Gemini detected text but all coordinates were invalid: log, skip
            print(f"[verify_and_patch] Pass {pass_num + 1}: Cảnh báo — Gemini trả về bbox không hợp lệ. Bỏ qua lượt này.")
            continue

        if not bboxes and not had_invalid:
            # Gemini confirmed no CJK remaining: early exit
            print(f"[verify_and_patch] Pass {pass_num + 1}: Không còn chữ CJK. Dừng sớm.")
            break

        print(f"[verify_and_patch] Pass {pass_num + 1}: Phát hiện {len(bboxes)} vùng cần patch.")
```

Thay toàn bộ block trên bằng snippet có 2 lớp bảo vệ: `detect_cjk_bboxes()` trả `[]` khi OCR lỗi bên trong (lớp 1), còn `verify_and_patch()` cũng wrap try/except ở ngoài phòng trường hợp bất kỳ exception nào thoát ra (lớp 2, belt-and-suspenders):

```python
        # Detect remaining Chinese ideographs using PaddleOCR (local, no Gemini call)
        try:
            bboxes = detect_cjk_bboxes(image)
        except Exception as e:
            print(f"[verify_and_patch] Pass {pass_num + 1}: Lỗi OCR detect: {e}. Dừng verify.")
            break
        if not bboxes:
            print(f"[verify_and_patch] Pass {pass_num + 1}: Không còn chữ Chinese. Dừng sớm.")
            break
        print(f"[verify_and_patch] Pass {pass_num + 1}: Phát hiện {len(bboxes)} vùng cần patch.")
```

> **Note on OCR box fragmentation:** PaddleOCR có thể trả nhiều box nhỏ (1-3 ký tự). Các guard đã có xử lý điều này: `VERIFY_MIN_CROP_PX = 20` bỏ qua box < 20px, `VERIFY_MAX_BBOX_AREA = 0.80` bỏ qua box > 80% ảnh. Không cần xử lý thêm.

- [ ] **Step 5: Chạy `test_grid.py` — verify không có regression**

```bash
python test_grid.py
```

`test_grid.py` có 5 scenarios. **SC-4 và SC-5 chạy offline (mock, không cần API key)** — đây là regression gate cốt lõi. SC-1/2/3 cần live API và sẽ SKIP nếu không có `GEMINI_API_KEY`:

```
=== SC-5: Mock call count ===
[PASS] ...

=== SC-4: RGBA safety ===
[PASS] ...

[!] GEMINI_API_KEY chua duoc thiet lap.
[!] SC-1, SC-2, SC-3 se bi SKIP (can live API).

SUMMARY
  SC-5: PASS
  SC-4: PASS
  SC-1: SKIP
  SC-2: SKIP
  SC-3: SKIP

[*] Khong co FAIL, nhung co SC bi SKIP.
```

Pass condition: **SC-4 = PASS và SC-5 = PASS**, không có FAIL (SKIP là acceptable). Script exit 0 khi không có FAIL.

Nếu SC-4 hoặc SC-5 FAIL, kiểm tra lại các bước xóa code ở trên — có thể đã xóa nhầm dòng.

- [ ] **Step 6: Chạy integration test — verify_and_patch() flow đúng**

```bash
python test_ocr.py --integration
```

Expected output:
```
=== test_positive: ảnh có chữ Chinese ===
[PASS] ...

=== test_negative: ảnh chỉ có chữ Latin ===
[PASS] ...

=== test_empty: ảnh trắng ===
[PASS] ...

=== test_verify_and_patch_integration ===
[PASS] verify_and_patch gọi detect 2x, trả về image

4/4 tests passed.
```

Nếu `test_verify_and_patch_integration` FAIL: kiểm tra lại Task 3 Step 4 — mock path `grid_translator.detect_cjk_bboxes` phải khớp với import trong `grid_translator.py`.

- [ ] **Step 7: Commit**

```bash
git add grid_translator.py
git commit -m "feat: replace Gemini detect in verify_and_patch with PaddleOCR"
```

---

## Checklist hoàn thành

Sau khi 3 task trên done, kiểm tra nhanh:

- [ ] `python test_ocr.py` → **3/3 passed** (không chấp nhận SKIP)
- [ ] `python test_ocr.py --integration` → **4/4 passed**
- [ ] `python test_grid.py` → **SC-4 PASS và SC-5 PASS**, không có FAIL (SC-1/2/3 SKIP là OK)
- [ ] `python app.py` khởi động không lỗi
- [ ] `VERIFY_PROMPT`, `_parse_bboxes` không còn trong `grid_translator.py` (search để confirm)
- [ ] `import json`, `import math`, `import re` không còn trong `grid_translator.py`
- [ ] `detect_cjk_bboxes()` wraps OCR call trong try/except, trả `[]` khi lỗi
