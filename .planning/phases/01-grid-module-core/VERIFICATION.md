---
phase: 01
verified_by: Claude Code
verified_date: 2026-03-29
verdict: PASS
---

# Phase 01 Verification — Grid Module Core

**Phase goal:** Xây dựng `grid_translator.py` — module độc lập chứa toàn bộ grid logic (split → translate → stitch), tập trung constants, và đảm bảo behavior hiện tại 100% không đổi khi `grid_n=1`.

**Plans verified:** 01-01 (Create `grid_translator.py`), 01-02 (Constants migration)

---

## 1. Requirement ID Cross-Reference

Every GRID-01 through GRID-07 ID from REQUIREMENTS.md is accounted for:

| Requirement ID | Description | Plan | Status |
|----------------|-------------|------|--------|
| GRID-01 | `translate_with_grid(image, client, prompt, grid_n)` public API | 01-01 Task 5 | ✅ PASS |
| GRID-02 | `_split_tiles(image, grid_n)` — crop NxN, last tile absorbs remainder | 01-01 Task 3 | ✅ PASS |
| GRID-03 | `_translate_single_tile` — Gemini call + retry + dual-format + resize | 01-01 Task 2 | ✅ PASS |
| GRID-04 | `_stitch_tiles` — paste tiles, hard-paste, canvas size = input size | 01-01 Task 4 | ✅ PASS |
| GRID-05 | Constants centralised in `grid_translator.py`, imported by both files | 01-02 Tasks 1-2 | ✅ PASS |
| GRID-06 | `grid_n=1` fast path: calls `_translate_single_tile` directly, no split/stitch | 01-01 Task 5 | ✅ PASS |
| GRID-07 | Tile failure after 3 retries raises Exception — no partial result | 01-01 Task 2, 5 | ✅ PASS |

---

## 2. Success Criteria (from ROADMAP.md)

### SC-1: `translate_with_grid(image, client, prompt, grid_n=1)` importable, returns PIL Image with `size == input.size`

**Result: PASS**

```
translate_with_grid signature: (image, client, prompt, grid_n=1)
Constants OK: gemini-3.1-flash-image-preview 3 2
Import OK: translate_with_grid, all private functions, all constants
```

- `grid_translator.py` exists at project root
- `from grid_translator import translate_with_grid` succeeds with no errors
- Signature: `(image, client, prompt, grid_n=1)` — `grid_n` defaults to `1`
- `grid_n=1` fast path: `result.resize(image.size, Image.LANCZOS)` guarantees return size == input size
- `grid_n>1` path: `_stitch_tiles` creates canvas with `Image.new(canvas_mode, image_size)` where `image_size = image.size`, asserts `canvas.size == image_size`

### SC-2: `grid_n=1` output matches direct `generate_content` call behavior

**Result: PASS (structural)**

> Live API equality cannot be tested without a real API key. Structural verification confirms the fast path is behaviorally equivalent.

- `translate_with_grid(image, client, prompt, grid_n=1)` calls `_translate_single_tile(image, client, prompt)` directly
- `_translate_single_tile` uses identical retry loop (3 attempts, 2s→4s backoff), identical dual-format parse (`part.image` / `part.inline_data`), and the same `client.models.generate_content(model=GEMINI_MODEL, contents=[tile, prompt])` call
- The only addition vs `app.py`'s inline code: `result.resize(tile_size, ...)` — which `app.py` also does post-response (`result_pil_img.resize(orig_size, ...)`)
- No behavioral difference at `grid_n=1`; code path is a direct extraction of the existing retry block

### SC-3: `grid_n=2` splits into 4 tiles, stitched result has correct size

**Result: PASS**

```
grid_n=2 -> 4 tiles (expected 4)
  Tile (0,0): crop=(0,0,50,50)   size=(50, 50)
  Tile (0,1): crop=(50,0,100,50) size=(50, 50)
  Tile (1,0): crop=(0,50,50,100) size=(50, 50)
  Tile (1,1): crop=(50,50,100,100) size=(50, 50)
canvas.size = (200, 150), orig_size = (200, 150)
_stitch_tiles canvas.size == orig_size: PASS
```

- `_split_tiles(img, 2)` on a 100×100 image produces exactly 4 tiles
- Each tile is a 7-element tuple `(row, col, left, upper, right, lower, tile_image)`
- `_stitch_tiles` creates canvas of `image_size`, pastes all 4 tiles, `assert canvas.size == image_size` passes
- Tested on 200×150 image: result canvas = (200, 150) ✓

**Note on assert semantics:** `assert canvas.size == image_size` always holds because `canvas = Image.new(canvas_mode, image_size)` sets size at creation. PIL `paste()` clips out-of-bounds pixels silently. The assert guards against accidental `image_size` mutation bugs — consistent with CONTEXT D-06 design intent.

### SC-4: Tile failure after 3 retries raises Exception — no partial result

**Result: PASS**

- `translate_with_grid` contains **zero** `try`/`except` blocks (verified via AST walk)
- `_translate_single_tile` re-raises on final retry: `else: raise` (bare re-raise, not `return None`)
- Exception propagates through `translate_with_grid` → caller unmodified
- Callers handle as designed: `app.py` returns HTTP 500; `image_translator.py` catches and skips file

```python
# AST confirmed: 0 Try nodes inside translate_with_grid function body
translate_with_grid: NO try/except (GRID-07 propagation) OK
```

### SC-5: `app.py` and `image_translator.py` import from `grid_translator` — no duplicate definitions

**Result: PASS**

```
app.py: import from grid_translator OK -> ['GEMINI_MODEL', 'MAX_RETRIES', 'RETRY_DELAY_SECONDS']
app.py: no duplicate definitions OK
app.py: remaining constants OK

image_translator.py: import from grid_translator OK -> ['GEMINI_MODEL', 'MAX_RETRIES', 'RETRY_DELAY_SECONDS']
image_translator.py: no duplicate definitions OK
image_translator.py: remaining constants OK
```

---

## 3. must_haves Checklist

### Plan 01-01 must_haves

- [x] `grid_translator.py` exists in project root and is importable without errors
- [x] `translate_with_grid(image, client, prompt, grid_n=1)` is a callable public function with `grid_n` defaulting to 1
- [x] `_split_tiles` returns tiles with crop coordinates; last tile absorbs remainder pixels
  - Verified on 101×101 / grid_n=2: last tile `right=101`, `lower=101` (equals `img_w`, `img_h`)
- [x] `_translate_single_tile` has retry loop (3 attempts, exponential backoff), dual-format image parse, resize to input tile size, and raises Exception on final failure
- [x] `_stitch_tiles` uses `slot_w = right - left` (not generic `tile_w`), converts tile mode, hard-pastes, asserts canvas size; accesses tile image at tuple index `[4]`
  - Confirmed: `canvas_mode = translated_tiles[0][4].mode` (index 4, not 1) ✓
- [x] `grid_n=1` fast path calls `_translate_single_tile` directly without split/stitch
- [x] Tile failure propagates as Exception — no try/except in `translate_with_grid`
- [x] Constants `GEMINI_MODEL`, `MAX_RETRIES`, `RETRY_DELAY_SECONDS` are defined with correct values
  - `GEMINI_MODEL = 'gemini-3.1-flash-image-preview'` ✓
  - `MAX_RETRIES = 3` ✓
  - `RETRY_DELAY_SECONDS = 2` ✓

### Plan 01-02 must_haves

- [x] `app.py` imports `GEMINI_MODEL`, `MAX_RETRIES`, `RETRY_DELAY_SECONDS` from `grid_translator`
- [x] `image_translator.py` imports `GEMINI_MODEL`, `MAX_RETRIES`, `RETRY_DELAY_SECONDS` from `grid_translator`
- [x] Neither `app.py` nor `image_translator.py` contains inline constant definitions for these three values
- [x] `app.py` still contains `MAX_FILE_SIZE_MB`, `UPSCALE_FACTOR`, `UPSCALE_MAX_DIMENSION` as local definitions
- [x] `image_translator.py` still contains `VALID_EXTENSIONS`, `UPSCALE_FACTOR`, `UPSCALE_MAX_DIMENSION` as local definitions
- [x] All existing usages of `GEMINI_MODEL`, `MAX_RETRIES`, `RETRY_DELAY_SECONDS` in both files remain unchanged

---

## 4. Detailed Acceptance Criteria Results

### grid_translator.py — Task 1 (Imports & Constants)

| Criterion | Result |
|-----------|--------|
| First non-blank line is `import io` | ✅ |
| Contains `import time` | ✅ |
| Contains `from PIL import Image` | ✅ |
| Contains `GEMINI_MODEL = 'gemini-3.1-flash-image-preview'` | ✅ |
| Contains `MAX_RETRIES = 3` | ✅ |
| Contains `RETRY_DELAY_SECONDS = 2` | ✅ |
| Does NOT contain `from google import genai` | ✅ |
| Does NOT contain `import flask` | ✅ |
| Does NOT contain `import base64` | ✅ |

### grid_translator.py — Task 2 (`_translate_single_tile`)

| Criterion | Result |
|-----------|--------|
| `def _translate_single_tile(tile, client, prompt):` | ✅ |
| `tile_size = tile.size` | ✅ |
| `retry_delay = RETRY_DELAY_SECONDS` | ✅ |
| `for attempt in range(MAX_RETRIES):` | ✅ |
| `model=GEMINI_MODEL` | ✅ |
| `contents=[tile, prompt]` | ✅ |
| `hasattr(part, 'image') and part.image` | ✅ |
| `hasattr(part, 'inline_data') and part.inline_data` | ✅ |
| `Image.open(io.BytesIO(part.inline_data.data))` | ✅ |
| `result.resize(tile_size, Image.LANCZOS)` | ✅ |
| Bare `raise` in final else (not `return None`) | ✅ |
| `return result` at end | ✅ |

### grid_translator.py — Task 3 (`_split_tiles`)

| Criterion | Result |
|-----------|--------|
| `def _split_tiles(image, grid_n):` | ✅ |
| `tile_w = img_w // grid_n` | ✅ |
| `tile_h = img_h // grid_n` | ✅ |
| Last-column guard: `right = img_w if col == grid_n - 1 else left + tile_w` | ✅ |
| Last-row guard: `lower = img_h if row == grid_n - 1 else upper + tile_h` | ✅ |
| 7-element tuples: `(row, col, left, upper, right, lower, tile_image)` | ✅ |
| Uses `image.crop((left, upper, right, lower))` | ✅ |
| Returns `tiles` list | ✅ |

### grid_translator.py — Task 4 (`_stitch_tiles`)

| Criterion | Result |
|-----------|--------|
| `def _stitch_tiles(translated_tiles, image_size, grid_n):` | ✅ |
| `Image.new(canvas_mode, image_size)` | ✅ |
| `canvas_mode = translated_tiles[0][4].mode` (index 4, not 1) | ✅ |
| `slot_w = right - left` | ✅ |
| `slot_h = lower - upper` | ✅ |
| `tile.convert(canvas_mode)` | ✅ |
| `tile.resize((slot_w, slot_h), Image.LANCZOS)` | ✅ |
| `canvas.paste(tile, (left, upper))` (no mask arg) | ✅ |
| `del tile` after paste | ✅ |
| `assert canvas.size == image_size` | ✅ |
| `return canvas` | ✅ |

### grid_translator.py — Task 5 (`translate_with_grid`)

| Criterion | Result |
|-----------|--------|
| `def translate_with_grid(image, client, prompt, grid_n=1):` | ✅ |
| `if grid_n == 1:` as first conditional | ✅ |
| Fast path: `_translate_single_tile(image, client, prompt)` | ✅ |
| Fast path: `result.resize(image.size, Image.LANCZOS)` | ✅ |
| `_split_tiles(image, grid_n)` | ✅ |
| `for row, col, left, upper, right, lower, tile in tiles:` | ✅ |
| `_translate_single_tile(tile, client, prompt)` per tile | ✅ |
| Builds `(left, upper, right, lower, result)` tuples | ✅ |
| `_stitch_tiles(translated, image.size, grid_n)` | ✅ |
| NO `try`/`except` wrapping tile calls | ✅ |
| `translate_with_grid` is LAST function in file | ✅ (order: `_translate_single_tile`, `_split_tiles`, `_stitch_tiles`, `translate_with_grid`) |

### app.py — Task (Constants Migration)

| Criterion | Result |
|-----------|--------|
| `from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS` | ✅ |
| No `GEMINI_MODEL = '...'` inline definition | ✅ |
| No `MAX_RETRIES = 3` inline definition | ✅ |
| No `RETRY_DELAY_SECONDS = 2` inline definition | ✅ |
| Still contains `MAX_FILE_SIZE_MB = 10` | ✅ |
| Still contains `UPSCALE_FACTOR = 2` | ✅ |
| Still contains `UPSCALE_MAX_DIMENSION = 3000` | ✅ |
| Still contains `# --- Constants ---` section | ✅ |
| Still uses `model=GEMINI_MODEL` | ✅ |
| Still uses `retry_delay = RETRY_DELAY_SECONDS` | ✅ |
| Still uses `for attempt in range(MAX_RETRIES):` | ✅ |

### image_translator.py — Task (Constants Migration)

| Criterion | Result |
|-----------|--------|
| `from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS` | ✅ |
| No `GEMINI_MODEL = '...'` inline definition | ✅ |
| No `MAX_RETRIES = 3` inline definition | ✅ |
| No `RETRY_DELAY_SECONDS = 2` inline definition | ✅ |
| Still contains `VALID_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}` | ✅ |
| Still contains `UPSCALE_FACTOR = 2` | ✅ |
| Still contains `UPSCALE_MAX_DIMENSION = 3000` | ✅ |
| Still uses `model=GEMINI_MODEL` | ✅ |
| Still uses `retry_delay = RETRY_DELAY_SECONDS` | ✅ |
| Still uses `for attempt in range(MAX_RETRIES):` | ✅ |

---

## 5. Notes & Observations

### Assert guard semantics
`assert canvas.size == image_size` in `_stitch_tiles` always holds because PIL's `Image.new(mode, size)` creates the canvas at exactly `size`. The assert guards against accidental mutation of the `image_size` variable between canvas creation and the final check — it is not designed to detect tile overflow (PIL `paste()` silently clips). This matches CONTEXT D-06 intent.

### SC-2 partial (live API not testable)
Success Criterion 2 ("grid_n=1 output matches direct generate_content call pixel-for-pixel") cannot be tested without a live Gemini API key. The structural equivalence is confirmed: the `_translate_single_tile` function is a direct extraction of the retry+parse block from `app.py` lines 83–121, with identical parameters. Pixel-level equivalence is reserved for Phase 3 end-to-end validation.

### No regressions in entry points
`app.py` and `image_translator.py` are unchanged except for the import/constant-removal surgery. All existing logic, error handling, RGBA conversion, upscaling, and output paths are intact. The constants resolve through the import rather than local definitions — behavior is identical.

---

## 6. Verdict

**Phase 01: PASS**

All 7 requirement IDs (GRID-01 through GRID-07) are implemented and verified.
All 5 ROADMAP success criteria are satisfied (SC-2 confirmed structurally; live-API validation deferred to Phase 3).
All must_haves from both plans (01-01, 01-02) are checked off.
No regressions introduced in `app.py` or `image_translator.py`.

Phase 02 (Entry Point Integration: CLI-01, WEB-01, WEB-02) may proceed.
