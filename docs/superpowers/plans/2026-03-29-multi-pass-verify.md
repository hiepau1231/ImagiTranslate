# Multi-pass Verify & Patch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sau khi dịch xong, gửi ảnh lại Gemini để kiểm tra còn sót chữ CJK không — nếu có, crop vùng đó, dịch lại, paste đè — lặp tối đa 3 lần.

**Architecture:** Thêm `verify_and_patch()` vào `grid_translator.py` (logic thuần), wire vào `app.py` qua form field `verify_passes`, wire vào `image_translator.py` qua `--verify-passes` CLI flag, thêm checkbox vào web UI.

**Tech Stack:** Python 3, Pillow (PIL), google-genai SDK, Flask, vanilla JS

---

## File Map

| File | Thay đổi |
|------|----------|
| `grid_translator.py` | Thêm constants, `_parse_bboxes()`, `verify_and_patch()` |
| `app.py` | Đọc `verify_passes` từ form, gọi `verify_and_patch` sau translate |
| `image_translator.py` | Thêm `--verify-passes` argparse flag, truyền vào `translate_images()` |
| `templates/index.html` | Thêm checkbox "Dịch triệt để" vào controls section |
| `static/script.js` | Append `verify_passes` vào FormData khi submit |

---

## Task 1: Thêm constants và `_parse_bboxes()` vào `grid_translator.py`

**Files:**
- Modify: `grid_translator.py`

- [ ] **Bước 1: Thêm constants sau dòng `RETRY_DELAY_SECONDS = 2`**

Mở `grid_translator.py`, sau dòng `RETRY_DELAY_SECONDS = 2` (dòng 12), thêm vào:

```python
# --- Verify & Patch Constants ---
VERIFY_MAX_PASSES = 3
VERIFY_CROP_MARGIN = 0.08
VERIFY_MAX_BBOX_AREA = 0.80
VERIFY_MIN_CROP_PX = 20

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

- [ ] **Bước 2: Thêm `import json`, `import re`, `import math` vào đầu file**

Sau `import io` (dòng 1), thêm:

```python
import io
import json
import math
import re
```

File hiện tại đã có `import io`, chỉ cần thêm 3 imports còn lại vào ngay sau.

- [ ] **Bước 3: Thêm hàm `_parse_bboxes()` vào `grid_translator.py`, sau hàm `_is_empty_tile()`**

> ⚠️ **[Fix ISSUE-1, ISSUE-4]:** Hàm trả về tuple `(bboxes, parse_ok, had_invalid)` — phân biệt 3 trạng thái: parse failure / truly empty / có invalid bboxes bị lọc.

```python
import math

def _parse_bboxes(response_text):
    """Parse JSON bounding boxes từ Gemini verify response.

    Returns:
        tuple (bboxes, parse_ok, had_invalid):
            - bboxes: list of valid dict {x1, y1, x2, y2} (normalized 0.0-1.0)
            - parse_ok: True nếu response là JSON list hợp lệ (kể cả empty)
            - had_invalid: True nếu có >= 1 bbox bị lọc do tọa độ invalid
    """
    text = response_text.strip()
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if not match:
        return [], False, False
    try:
        raw = json.loads(match.group())
        if not isinstance(raw, list):
            return [], False, False
        valid = []
        had_invalid = False
        for b in raw:
            if not all(k in b for k in ('x1', 'y1', 'x2', 'y2')):
                had_invalid = True
                continue
            try:
                x1, y1 = float(b['x1']), float(b['y1'])
                x2, y2 = float(b['x2']), float(b['y2'])
            except (ValueError, TypeError):
                had_invalid = True
                continue
            # Validate finite values và normalized range với coordinate ordering
            if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
                had_invalid = True
                continue
            if not (0.0 <= x1 < x2 <= 1.0 and 0.0 <= y1 < y2 <= 1.0):
                had_invalid = True
                continue
            valid.append({'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})
        return valid, True, had_invalid
    except (json.JSONDecodeError, ValueError, TypeError):
        return [], False, False
```

**Lưu ý:** Cần thêm `import math` vào đầu file cùng với `import json` và `import re`.

- [ ] **Bước 4: Smoke test `_parse_bboxes()` thủ công**

Chạy Python interactive:

```bash
cd d:\_Dev\GoodFirstIsuuses\ImagiTranslate
python -c "
from grid_translator import _parse_bboxes

# Test 1: valid JSON — parse_ok=True, 1 bbox, had_invalid=False
bboxes, ok, invalid = _parse_bboxes('[{\"x1\": 0.1, \"y1\": 0.2, \"x2\": 0.3, \"y2\": 0.4}]')
assert ok is True and invalid is False, f'FAIL: {ok}, {invalid}'
assert bboxes == [{'x1': 0.1, 'y1': 0.2, 'x2': 0.3, 'y2': 0.4}], f'FAIL: {bboxes}'

# Test 2: empty list — parse_ok=True, no bboxes, had_invalid=False (truly clean)
bboxes, ok, invalid = _parse_bboxes('[]')
assert ok is True and invalid is False and bboxes == [], f'FAIL: {ok}, {invalid}, {bboxes}'

# Test 3: Gemini adds extra text — still parseable
bboxes, ok, invalid = _parse_bboxes('Here are the bounding boxes: [{\"x1\": 0.5, \"y1\": 0.5, \"x2\": 0.8, \"y2\": 0.9}]')
assert ok is True and len(bboxes) == 1, f'FAIL: {ok}, {bboxes}'

# Test 4: invalid JSON — parse_ok=False
bboxes, ok, invalid = _parse_bboxes('Sorry, no Chinese text found.')
assert ok is False and bboxes == [], f'FAIL: {ok}, {bboxes}'

# Test 5: inverted bbox — had_invalid=True, empty valid list
bboxes, ok, invalid = _parse_bboxes('[{\"x1\": 0.8, \"y1\": 0.2, \"x2\": 0.3, \"y2\": 0.4}]')
assert ok is True and invalid is True and bboxes == [], f'FAIL inverted: {ok}, {invalid}, {bboxes}'

# Test 6: out-of-range bbox — had_invalid=True
bboxes, ok, invalid = _parse_bboxes('[{\"x1\": -0.1, \"y1\": 0.2, \"x2\": 1.5, \"y2\": 0.4}]')
assert ok is True and invalid is True and bboxes == [], f'FAIL range: {ok}, {invalid}, {bboxes}'

print('All _parse_bboxes tests passed!')
"
```

Expected output: `All _parse_bboxes tests passed!`

- [ ] **Bước 5: Commit**

```bash
cd d:\_Dev\GoodFirstIsuuses\ImagiTranslate
git add grid_translator.py
git commit -m "feat: add _parse_bboxes() and verify constants to grid_translator"
```

---

## Task 2: Thêm `verify_and_patch()` vào `grid_translator.py`

**Files:**
- Modify: `grid_translator.py`

- [ ] **Bước 1: Thêm hàm `verify_and_patch()` vào cuối `grid_translator.py`, sau `translate_with_grid()`**

> ⚠️ **[Fix ISSUE-1 R2]:** Dùng 3-tuple `(bboxes, parse_ok, had_invalid)`. Nếu `not bboxes and had_invalid` → log + continue (KHÔNG dừng sớm). Chỉ dừng sớm khi `ok=True, bboxes=[], had_invalid=False`.
> ⚠️ **[Fix ISSUE-2 R1]:** Clamp `max_passes` ngay đầu hàm.

```python
def verify_and_patch(image, client, target_lang, max_passes=VERIFY_MAX_PASSES):
    """Kiểm tra ảnh đã dịch còn sót chữ CJK không, patch các vùng bị bỏ sót.

    Args:
        image: PIL.Image - ảnh đã dịch xong
        client: genai.Client
        target_lang: str - ngôn ngữ đích để dịch lại
        max_passes: int - số vòng kiểm tra tối đa (default VERIFY_MAX_PASSES=3)

    Returns:
        PIL.Image - ảnh đã patch (có thể là object cũ nếu không có gì cần fix)
    """
    # Clamp để đảm bảo không vượt quá giới hạn đã định
    max_passes = min(max(0, max_passes), VERIFY_MAX_PASSES)
    if max_passes == 0:
        return image

    patch_prompt = (
        f"Translate EVERY SINGLE piece of text from Chinese to {target_lang}. "
        "Do NOT skip any text. Preserve layout, colors, and visual style exactly."
    )
    img_w, img_h = image.size
    img_area = img_w * img_h

    for pass_num in range(max_passes):
        # Gửi ảnh đến Gemini để detect chữ CJK còn sót
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
            # Gemini trả về non-JSON hoàn toàn: log warning, skip pass
            print(f"[verify_and_patch] Pass {pass_num + 1}: Cảnh báo — Gemini trả về non-JSON. Bỏ qua lượt này.")
            continue

        if not bboxes and had_invalid:
            # Gemini detect text nhưng tọa độ không hợp lệ: log warning, tiếp tục
            print(f"[verify_and_patch] Pass {pass_num + 1}: Cảnh báo — Gemini trả về bbox không hợp lệ. Bỏ qua lượt này.")
            continue

        if not bboxes and not had_invalid:
            # Gemini xác nhận không còn CJK: dừng sớm
            print(f"[verify_and_patch] Pass {pass_num + 1}: Không còn chữ CJK. Dừng sớm.")
            break

        print(f"[verify_and_patch] Pass {pass_num + 1}: Phát hiện {len(bboxes)} vùng cần patch.")

        # Bước 2: Patch từng bbox
        patched_any = False
        for bbox in bboxes:
            try:
                x1 = bbox['x1']
                y1 = bbox['y1']
                x2 = bbox['x2']
                y2 = bbox['y2']

                # Mở rộng margin 8%
                margin_x = (x2 - x1) * VERIFY_CROP_MARGIN
                margin_y = (y2 - y1) * VERIFY_CROP_MARGIN
                x1 = max(0.0, x1 - margin_x)
                y1 = max(0.0, y1 - margin_y)
                x2 = min(1.0, x2 + margin_x)
                y2 = min(1.0, y2 + margin_y)

                # Convert sang pixel
                px1 = int(x1 * img_w)
                py1 = int(y1 * img_h)
                px2 = int(x2 * img_w)
                py2 = int(y2 * img_h)

                crop_w = px2 - px1
                crop_h = py2 - py1
                crop_area = crop_w * crop_h

                # Skip if crop is too small
                if crop_w < VERIFY_MIN_CROP_PX or crop_h < VERIFY_MIN_CROP_PX:
                    print(f"[verify_and_patch] Skip small bbox: {crop_w}x{crop_h}px")
                    continue

                # Skip if bbox covers > 80% of image (prevent infinite re-translate)
                if crop_area > img_area * VERIFY_MAX_BBOX_AREA:
                    print(f"[verify_and_patch] Skip large bbox: {crop_area/img_area:.1%}")
                    continue

                # Crop and upscale 2x so Gemini can read small text
                crop = image.crop((px1, py1, px2, py2))
                upscaled_crop = crop.resize((crop_w * 2, crop_h * 2), Image.LANCZOS)

                # Re-translate the cropped region
                translated_crop = _translate_single_tile(upscaled_crop, client, patch_prompt)

                # Resize back to original crop size and paste over
                translated_crop = translated_crop.resize((crop_w, crop_h), Image.LANCZOS)
                translated_crop = translated_crop.convert(image.mode)
                image.paste(translated_crop, (px1, py1))
                patched_any = True

            except Exception as e:
                print(f"[verify_and_patch] Lỗi patch bbox {bbox}: {e}. Bỏ qua, tiếp tục.")
                continue

        if not patched_any:
            print(f"[verify_and_patch] Pass {pass_num + 1}: Không patch được vùng nào. Dừng.")
            break

    return image
```

- [ ] **Bước 2: Smoke test `verify_and_patch()` import được**

```bash
cd d:\_Dev\GoodFirstIsuuses\ImagiTranslate
python -c "
from grid_translator import verify_and_patch, VERIFY_MAX_PASSES, VERIFY_CROP_MARGIN, VERIFY_MAX_BBOX_AREA, VERIFY_MIN_CROP_PX
print('verify_and_patch import OK')
print(f'VERIFY_MAX_PASSES={VERIFY_MAX_PASSES}')
print(f'VERIFY_CROP_MARGIN={VERIFY_CROP_MARGIN}')
"
```

Expected:
```
verify_and_patch import OK
VERIFY_MAX_PASSES=3
VERIFY_CROP_MARGIN=0.08
```

- [ ] **Bước 3: Commit**

```bash
cd d:\_Dev\GoodFirstIsuuses\ImagiTranslate
git add grid_translator.py
git commit -m "feat: add verify_and_patch() to grid_translator"
```

---

## Task 3: Integrate `verify_and_patch` vào `app.py`

**Files:**
- Modify: `app.py`

- [ ] **Bước 1: Cập nhật import trong `app.py`**

Tìm dòng:
```python
from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS, translate_with_grid
```

Thay thành:
```python
from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS, translate_with_grid, verify_and_patch, VERIFY_MAX_PASSES
```

- [ ] **Bước 2: Đọc `verify_passes` từ form data**

> ⚠️ **[Fix ISSUE-2]:** Clamp cả lower bound (0) lẫn upper bound (VERIFY_MAX_PASSES=3) để tránh tampered requests.

Trong hàm `translate_image()`, sau dòng:
```python
    try:
        grid_n = int(grid_size.split('x')[0]) if grid_size != 'off' else 1
    except (ValueError, IndexError):
        grid_n = 1
        print(f"Cảnh báo: Giá trị grid_size không hợp lệ '{grid_size}', dùng mặc định: off")
```

Thêm ngay sau:
```python
    try:
        verify_passes = int(request.form.get('verify_passes', 0))
        verify_passes = max(0, min(verify_passes, VERIFY_MAX_PASSES))
    except (ValueError, TypeError):
        verify_passes = 0
```

- [ ] **Bước 3: Gọi `verify_and_patch` sau `translate_with_grid`**

Tìm đoạn:
```python
        result_pil_img = translate_with_grid(base_image, client, prompt, grid_n)

        # Normalize output về kích thước gốc — Gemini có thể trả về size khác
        result_pil_img = result_pil_img.resize(orig_size, Image.LANCZOS)
```

Thay thành:
```python
        result_pil_img = translate_with_grid(base_image, client, prompt, grid_n)

        if verify_passes > 0:
            result_pil_img = verify_and_patch(result_pil_img, client, target_lang, max_passes=verify_passes)

        # Normalize output về kích thước gốc — Gemini có thể trả về size khác
        result_pil_img = result_pil_img.resize(orig_size, Image.LANCZOS)
```

- [ ] **Bước 4: Test app.py import được và server khởi động**

```bash
cd d:\_Dev\GoodFirstIsuuses\ImagiTranslate
python -c "import app; print('app.py import OK')"
```

Expected: `app.py import OK` (không có error)

- [ ] **Bước 5: Commit**

```bash
cd d:\_Dev\GoodFirstIsuuses\ImagiTranslate
git add app.py
git commit -m "feat: integrate verify_and_patch into app.py web route"
```

---

## Task 4: Thêm `--verify-passes` flag vào `image_translator.py`

**Files:**
- Modify: `image_translator.py`

- [ ] **Bước 1: Cập nhật import**

Tìm dòng:
```python
from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS, translate_with_grid
```

Thay thành:
```python
from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS, translate_with_grid, verify_and_patch
```

- [ ] **Bước 2: Thêm `verify_passes` parameter vào `translate_images()`**

Tìm dòng:
```python
def translate_images(input_dir: str, output_dir: str, source_lang: str, target_lang: str, grid_n: int = 1):
```

Thay thành:
```python
def translate_images(input_dir: str, output_dir: str, source_lang: str, target_lang: str, grid_n: int = 1, verify_passes: int = 0):
```

- [ ] **Bước 3: Gọi `verify_and_patch` trong vòng lặp xử lý file**

Tìm đoạn trong `translate_images()`:
```python
            result_image = translate_with_grid(base_image, client, prompt, grid_n)

            # Normalize output về kích thước gốc — Gemini có thể trả về size khác
            result_image = result_image.resize(orig_size, Image.LANCZOS)
```

Thay thành:
```python
            result_image = translate_with_grid(base_image, client, prompt, grid_n)

            if verify_passes > 0:
                result_image = verify_and_patch(result_image, client, target_lang, max_passes=verify_passes)

            # Normalize output về kích thước gốc — Gemini có thể trả về size khác
            result_image = result_image.resize(orig_size, Image.LANCZOS)
```

- [ ] **Bước 4: Thêm `--verify-passes` vào argparse**

Tìm đoạn argparse (sau `--grid`):
```python
    parser.add_argument(
        "--grid",
        default=None,
        help="Kích thước lưới chia ảnh, ví dụ: --grid 2x2, --grid 3x3. Mặc định: không chia (xử lý toàn bộ ảnh). Hợp lệ: 1x1-4x4."
    )
```

Thêm ngay sau:
```python
    parser.add_argument(
        "--verify-passes",
        type=int,
        default=0,
        dest="verify_passes",
        help="Số vòng kiểm tra và vá chữ CJK còn sót (mặc định: 0 = tắt). Ví dụ: --verify-passes 3"
    )
```

- [ ] **Bước 5: Truyền `verify_passes` vào `translate_images()`**

Tìm dòng:
```python
    translate_images(args.input, args.output, args.source_lang, args.target_lang, grid_n)
```

Thay thành:
```python
    translate_images(args.input, args.output, args.source_lang, args.target_lang, grid_n, args.verify_passes)
```

- [ ] **Bước 6: Test CLI help và import**

```bash
cd d:\_Dev\GoodFirstIsuuses\ImagiTranslate
python image_translator.py --help
```

Expected output phải chứa:
```
--verify-passes VERIFY_PASSES
                      Số vòng kiểm tra và vá chữ CJK còn sót (mặc định: 0 = tắt).
```

- [ ] **Bước 7: Commit**

```bash
cd d:\_Dev\GoodFirstIsuuses\ImagiTranslate
git add image_translator.py
git commit -m "feat: add --verify-passes flag to CLI image_translator"
```

---

## Task 5: Thêm checkbox vào Web UI

**Files:**
- Modify: `templates/index.html`
- Modify: `static/script.js`

### Phần 5A — HTML checkbox

- [ ] **Bước 1: Thêm checkbox vào `index.html`, trong `.controls-section`**

Tìm đoạn đóng thẻ `</section>` của `controls-section` (sau `</div>` của grid input group, khoảng dòng 77):

```html
        </section>
```

Thay thành — thêm `div` checkbox VÀO TRONG section, trước `</section>`:

```html
            <div class="input-group verify-toggle-group">
                <label class="toggle-label">
                    <input type="checkbox" id="verify-toggle">
                    <span>Dịch triệt để (multi-pass)</span>
                </label>
            </div>
        </section>
```

### Phần 5B — JavaScript

- [ ] **Bước 2: Thêm DOM reference cho checkbox trong `script.js`**

Tìm đoạn khai báo các DOM element (khoảng dòng 14-20):
```javascript
    const sourceLangSel = document.getElementById('source-lang');
    const targetLangSel = document.getElementById('target-lang');
    const apiKeyInput = document.getElementById('api-key');
    const gridSizeSel = document.getElementById('grid-size');
```

Thêm ngay sau dòng `const gridSizeSel`:
```javascript
    const verifyToggle = document.getElementById('verify-toggle');
```

- [ ] **Bước 3: Append `verify_passes` vào FormData khi submit**

Tìm đoạn trong translateBtn click handler, nơi build FormData (khoảng dòng 166-172):
```javascript
            formData.append('image', currentFile);
            formData.append('source_lang', sourceLangSel.value);
            formData.append('target_lang', targetLangSel.value);
            formData.append('api_key', apiKeyInput.value.trim());
            formData.append('grid_size', gridSizeSel.value);
```

Thêm sau dòng `grid_size`:
```javascript
            formData.append('verify_passes', verifyToggle.checked ? '3' : '0');
```

- [ ] **Bước 4: Kiểm tra HTML và JS bằng cách mở app**

```bash
cd d:\_Dev\GoodFirstIsuuses\ImagiTranslate
python app.py
```

Mở `http://localhost:5000` trong trình duyệt.
Kiểm tra: Trong phần controls, có checkbox "Dịch triệt để (multi-pass)" xuất hiện không.
Mở DevTools → Network → submit một ảnh với checkbox được tick → kiểm tra request body có `verify_passes=3`.
Mở DevTools → Network → submit với checkbox không tick → kiểm tra `verify_passes=0`.

- [ ] **Bước 5: Commit**

```bash
cd d:\_Dev\GoodFirstIsuuses\ImagiTranslate
git add templates/index.html static/script.js
git commit -m "feat: add verify-toggle checkbox to web UI"
```

---

## Task 6: End-to-end smoke test với ảnh thực

- [ ] **Bước 1: Chạy app và dịch ảnh với verify mode bật**

```bash
cd d:\_Dev\GoodFirstIsuuses\ImagiTranslate
python app.py
```

Mở `http://localhost:5000`, tick checkbox "Dịch triệt để", chọn ảnh có chữ Trung, nhấn Dịch.
Xem console của server — phải thấy log từ `verify_and_patch`:
```
[verify_and_patch] Pass 1: ...
```

- [ ] **Bước 2: Kiểm tra CLI với `--verify-passes`**

```bash
cd d:\_Dev\GoodFirstIsuuses\ImagiTranslate
# Cần có ảnh trong ./input và GEMINI_API_KEY
python image_translator.py -t Vietnamese --verify-passes 1
```

Console phải in log `[verify_and_patch] Pass 1: ...` trong quá trình xử lý.

- [ ] **Bước 3: Commit cuối**

```bash
cd d:\_Dev\GoodFirstIsuuses\ImagiTranslate
git add .
git commit -m "feat: multi-pass verify & patch complete — end-to-end tested"
```

---

## Self-Review Checklist

- [x] **Spec coverage:**
  - `verify_and_patch()` + `_parse_bboxes()` → Task 1 & 2 ✓
  - Constants `VERIFY_MAX_PASSES`, `VERIFY_CROP_MARGIN`, `VERIFY_MAX_BBOX_AREA`, `VERIFY_MIN_CROP_PX` → Task 1 ✓
  - `VERIFY_PROMPT` → Task 1 ✓
  - `app.py` integration → Task 3 ✓
  - `image_translator.py` `--verify-passes` → Task 4 ✓
  - `index.html` checkbox → Task 5A ✓
  - `script.js` FormData → Task 5B ✓
  - Error handling (non-JSON, per-bbox try/except, max bbox area, min crop size) → Task 2 ✓
  - 2x upscale của crop → Task 2 ✓
  - 8% margin → Task 2 ✓

- [x] **Placeholder scan:** Không có TBD/TODO trong plan

- [x] **Type consistency:**
  - `verify_and_patch(image, client, target_lang, max_passes)` — nhất quán giữa Task 2, 3, 4
  - `_parse_bboxes(response_text)` → `tuple(list[dict], bool, bool)` — dùng đúng trong Task 2 với 3-tuple unpack
  - `VERIFY_PROMPT` — define Task 1, dùng Task 2 ✓
  - `VERIFY_MAX_PASSES` — define Task 1, clamp trong Task 2 và Task 3 ✓

- [x] **Codex plan review:** 2 rounds, 5 issues raised. ISSUE-1 (parse failure state), ISSUE-2 (upper bound clamp), ISSUE-4 (bbox validation) accepted and fixed. ISSUE-3 (Chinese-only scope) and ISSUE-5 (no automated tests) disputed and defended. Final VERDICT expected: APPROVE after Round 3.
