# Phase 1: Grid Module Core — Research

**Phase:** 01-grid-module-core
**Researched:** 2026-03-29
**Status:** Ready for planning

---

## What we need to build

`grid_translator.py` — một module Python độc lập gồm:

| Symbol | Type | Requirement |
|--------|------|-------------|
| `GEMINI_MODEL`, `MAX_RETRIES`, `RETRY_DELAY_SECONDS` | Constants | GRID-05: single source of truth; `app.py` và `image_translator.py` import từ đây |
| `translate_with_grid(image, client, prompt, grid_n=1)` | Public API | GRID-01, GRID-06 |
| `_split_tiles(image, grid_n)` | Private helper | GRID-02 |
| `_translate_single_tile(tile, client, prompt)` | Private helper | GRID-03 |
| `_stitch_tiles(tiles, orig_size, grid_n)` | Private helper | GRID-04 |

**Ngoài scope:** Mọi thay đổi trong `app.py` / `image_translator.py` ngoài import constants. CLI flag, web UI dropdown — đều thuộc Phase 2.

---

## Finding 1 — Retry + dual-format parse block đã viết sẵn: chỉ cần extract

**Source:** `app.py` lines 83–118; `image_translator.py` lines 69–110 (cùng pattern)

Cả hai file có cùng một khối retry logic, hoàn toàn có thể extract nguyên vào `_translate_single_tile()`:

```python
# Pattern hiện tại trong app.py (lines 83–111) — extract nguyên:
retry_delay = RETRY_DELAY_SECONDS
for attempt in range(MAX_RETRIES):
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[tile, prompt]      # tile thay vì base_image
        )
        parts = response.candidates[0].content.parts if (
            response and response.candidates
        ) else []
        has_image = any(
            (hasattr(p, 'image') and p.image) or
            (hasattr(p, 'inline_data') and p.inline_data)
            for p in parts
        )
        if has_image:
            break
        else:
            raise Exception("Phản hồi không chứa ảnh")
    except Exception as e:
        if attempt < MAX_RETRIES - 1:
            time.sleep(retry_delay)
            retry_delay *= 2
        else:
            raise   # ← GRID-07: re-raise thay vì return None / HTTP 500

# Dual-format parse (lines 113–119 trong app.py):
part = response.candidates[0].content.parts[0]
if hasattr(part, 'image') and part.image:
    result = part.image
elif hasattr(part, 'inline_data') and part.inline_data:
    result = Image.open(io.BytesIO(part.inline_data.data))
```

**Sự khác biệt quan trọng khi extract:**
- `app.py` cuối retry loop trả về HTTP 500 (`return jsonify(...), 500`).
- `image_translator.py` cuối retry loop gán `response = None` rồi kiểm tra bên ngoài.
- `_translate_single_tile()` phải **raise Exception** (GRID-07) — không làm cả hai cách trên.
- Sau khi parse, phải `resize(tile_input_size, Image.LANCZOS)` vì Gemini không guarantee trả đúng size (đã có trong `app.py` line 123, cần áp dụng cho từng tile).

---

## Finding 2 — Coordinate space: upscaled space only; tile dimensions từ input image

**Source:** CONTEXT.md D-01, D-02; PITFALLS.md P10

`translate_with_grid()` nhận image **đã upscale** từ caller. Module chỉ biết kích thước nhận được — không track `orig_size` của file gốc.

**Split logic** (GRID-02, từ STACK.md §1.1):
```python
def _split_tiles(image, grid_n):
    img_w, img_h = image.size
    tile_w = img_w // grid_n
    tile_h = img_h // grid_n
    tiles = []
    for row in range(grid_n):
        for col in range(grid_n):
            left  = col * tile_w
            upper = row * tile_h
            right = img_w if col == grid_n - 1 else left + tile_w   # last tile absorbs remainder
            lower = img_h if row == grid_n - 1 else upper + tile_h
            tiles.append(((row, col), image.crop((left, upper, right, lower))))
    return tiles   # list of ((row, col), tile_image)
```

**Stitch logic** (GRID-04, từ STACK.md §1.2):
- Canvas mode = mode của tile đầu tiên (CONTEXT.md D-06).
- Mỗi tile được `resize((slot_w, slot_h), Image.LANCZOS)` trước khi paste — Gemini không guarantee trả đúng kích thước.
- Hard-paste `Image.paste(tile, (left, upper))` — không blending (D-06, feathering là v2).
- Sau stitch: `assert canvas.size == input_image.size` để catch coordinate bugs (D-06).

**Pitfall P10 cần tránh:** `slot_w` và `slot_h` phải tính từ `(right - left, lower - upper)` của crop box, **không phải** từ `tile_w` / `tile_h` chung — vì tile biên có thể lớn hơn do hấp thụ pixel dư.

---

## Finding 3 — grid_n=1 fast path: skip split/stitch hoàn toàn

**Source:** CONTEXT.md D-04; REQUIREMENTS.md GRID-06

Khi `grid_n=1`, `translate_with_grid()` gọi thẳng `_translate_single_tile(image, client, prompt)` và trả về kết quả — không đi qua `_split_tiles` hay `_stitch_tiles`.

```python
def translate_with_grid(image, client, prompt, grid_n=1):
    if grid_n == 1:
        result = _translate_single_tile(image, client, prompt)
        return result.resize(image.size, Image.LANCZOS)
    # else: split → translate each tile → stitch
    ...
```

**Tại sao quan trọng:**
- Zero overhead cho use case hiện tại — không split/stitch, không có risk regression.
- Test dễ viết: output của `translate_with_grid(img, client, prompt, grid_n=1)` phải pixel-match output của gọi thẳng `_translate_single_tile(img, client, prompt)` trên cùng ảnh (Success Criteria #2).

---

## Finding 4 — Tile failure: raise, không partial stitch; xử lý đồng bộ với caller

**Source:** CONTEXT.md D-05; REQUIREMENTS.md GRID-07; PITFALLS.md P4, P9

Khi `_translate_single_tile()` exhausts `MAX_RETRIES`:
- Raise `Exception` — caller nhận exception và xử lý theo cách hiện tại.
- `app.py` caller: exception được bắt ở outer `try/except`, trả về HTTP 500. ✓
- `image_translator.py` caller: exception được bắt ở `try/except` trong vòng lặp file, in lỗi và `continue`. ✓

**Không có partial stitch** — nếu tile 2/4 thất bại, không paste tile 1 rồi trả về canvas thiếu.

**Lưu ý từ PITFALLS P9:** Gemini có thể trả về text response thay vì image cho tile quá nhỏ hoặc tile không có text. `has_image` check + retry loop đã xử lý điều này — behavior không thay đổi, chỉ là frequency tăng lên với grid > 1.

---

## Finding 5 — Constants migration: 3 constants di chuyển, 3 constants ở lại

**Source:** CONTEXT.md D-03; REQUIREMENTS.md GRID-05; `app.py` lines 12–14; `image_translator.py` lines 9–11

**Di chuyển vào `grid_translator.py` (xóa khỏi 2 file kia):**
```python
GEMINI_MODEL = 'gemini-3.1-flash-image-preview'
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
```

**Giữ nguyên tại chỗ (không di chuyển):**
```python
# app.py only:
MAX_FILE_SIZE_MB = 10         # liên quan đến Flask config, không phải grid logic
UPSCALE_FACTOR = 2            # caller giữ quyết định upscale
UPSCALE_MAX_DIMENSION = 3000  # caller giữ quyết định upscale

# image_translator.py only:
VALID_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}  # CLI-specific
UPSCALE_FACTOR = 2            # (duplicate — sẽ đồng bộ sau nếu cần)
UPSCALE_MAX_DIMENSION = 3000
```

**Import pattern sau migration:**
```python
# app.py và image_translator.py:
from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS
```

---

## Finding 6 — RGBA asymmetry: module không cần xử lý, nhận ảnh "đã xử lý"

**Source:** CONTEXT.md code_context; PITFALLS.md P7; STACK.md §5

Hiện tại:
- `app.py`: RGBA→RGB trên **input** trước khi upscale (line 63–64).
- `image_translator.py`: RGBA→RGB trên **output** sau khi nhận kết quả (line 116–117).

`grid_translator.py` **không cần biết về điều này** — module nhận ảnh đã được caller xử lý RGBA. Canvas mode được set từ `tiles[0].mode` — tự động kế thừa mode từ input.

**Rủi ro duy nhất cần guard:** Nếu Gemini trả về tile với mode khác (ví dụ input là RGB nhưng response là RGBA), `tile.resize()` không convert mode. Cần `tile_result.convert(canvas.mode)` trước khi paste để tránh lỗi JPEG.

---

## Pitfalls relevant cho Phase 1

| Pitfall | Relevance | Mitigation trong Phase 1 |
|---------|-----------|--------------------------|
| **P10** Output size mismatch | **HIGH** | Compute `slot_w = right - left`, `slot_h = lower - upper` per tile; `assert canvas.size == image.size` sau stitch |
| **P7** RGBA issues per tile | MEDIUM | Canvas mode từ first tile; `tile.convert(canvas.mode)` trước paste |
| **P9** Gemini returns text response | MEDIUM | `has_image` check + raise đã handle; behavior giữ nguyên |
| **P8** Memory pressure | MEDIUM | Paste và discard mỗi tile ngay (không collect list); `del tile_img` sau paste |
| P1 Text cut at boundary | LOW (v2) | Deferred — feathering/overlap là v2 |
| P4 Rate limit multiplication | LOW (Phase 1) | Sequential by design; `grid_n=1` default giữ behavior hiện tại |

---

## Module structure đề xuất

```
grid_translator.py
├── imports: os, io, time, PIL.Image, google.genai
├── constants: GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS
├── _translate_single_tile(tile, client, prompt) → PIL.Image
│   └── retry loop + dual-format parse + resize to tile.size
├── _split_tiles(image, grid_n) → list[(row, col, left, upper, right, lower, tile)]
│   └── last tile absorbs remainder
├── _stitch_tiles(translated_tiles, image_size, grid_n) → PIL.Image
│   └── canvas = Image.new(mode, image_size)
│   └── resize each tile to slot dims → hard-paste
│   └── assert canvas.size == image_size
└── translate_with_grid(image, client, prompt, grid_n=1) → PIL.Image
    ├── grid_n == 1: fast path → _translate_single_tile + resize
    └── grid_n > 1: _split_tiles → _translate_single_tile each → _stitch_tiles
```

**Không cần thêm dependency** — Pillow (`>=10.2.0`) và stdlib đủ cho Phase 1. NumPy chỉ cần cho feather blending (v2).

---

## Checklist planning

- [ ] Xác định signature đầy đủ của 3 private functions
- [ ] Quyết định cách truyền tile metadata qua pipeline (flat list + coords, hay 2D list)
- [ ] Xác định test strategy cho `grid_n=1` pixel-match (mocking Gemini hay live call?)
- [ ] Xác định thứ tự implementation: constants migration trước hay sau khi viết module?
- [ ] Quyết định có cần `tile.convert(canvas.mode)` guard hay assume caller đảm bảo

---

*Phase: 01-grid-module-core*
*Research completed: 2026-03-29*
