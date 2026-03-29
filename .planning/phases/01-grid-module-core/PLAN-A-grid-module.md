# Plan A: Create `grid_translator.py` Module

```yaml
wave: 1
depends_on: []
files_modified:
  - grid_translator.py (NEW)
files_read:
  - app.py
  - image_translator.py
  - .planning/phases/01-grid-module-core/01-CONTEXT.md
  - .planning/phases/01-grid-module-core/01-RESEARCH.md
  - .planning/REQUIREMENTS.md
  - .planning/codebase/CONVENTIONS.md
  - .planning/research/PITFALLS.md
  - .planning/research/STACK.md
requirements_addressed:
  - GRID-01
  - GRID-02
  - GRID-03
  - GRID-04
  - GRID-06
  - GRID-07
autonomous: true
```

---

## Goal

Create `grid_translator.py` as a standalone Python module containing the full grid translation pipeline: split image into NxN tiles, translate each tile via Gemini with retry logic, and stitch tiles back into a single image. Include the `grid_n=1` fast path that bypasses split/stitch entirely. Define shared constants (`GEMINI_MODEL`, `MAX_RETRIES`, `RETRY_DELAY_SECONDS`) here as single source of truth.

---

## Tasks

### Task 1: Create `grid_translator.py` with imports, constants, and module docstring

<read_first>
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/app.py (lines 1-17 for import style and constants)
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/image_translator.py (lines 1-14 for import style and constants)
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/.planning/codebase/CONVENTIONS.md (section 1.1 and 1.2 for file structure pattern)
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/.planning/phases/01-grid-module-core/01-CONTEXT.md (D-03 for constants ownership)
</read_first>

<action>
Create new file `grid_translator.py` in the project root with this exact structure:

```python
import io
import time
from PIL import Image


# --- Constants ---
GEMINI_MODEL = 'gemini-3.1-flash-image-preview'
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
```

Follow the established convention: stdlib imports first, then third-party (`PIL`), then a `# --- Constants ---` section comment. No `from google import genai` import needed — the module receives `client` as a parameter, never creates one.

Do NOT include `os`, `argparse`, `base64`, `flask`, or `google.genai` imports — they are not used in this module.
</action>

<acceptance_criteria>
- File `grid_translator.py` exists in project root (same directory as `app.py`)
- First non-blank line is `import io`
- File contains `import time`
- File contains `from PIL import Image`
- File contains exactly `GEMINI_MODEL = 'gemini-3.1-flash-image-preview'`
- File contains exactly `MAX_RETRIES = 3`
- File contains exactly `RETRY_DELAY_SECONDS = 2`
- File does NOT contain `from google import genai`
- File does NOT contain `import flask`
- File does NOT contain `import base64`
</acceptance_criteria>

---

### Task 2: Implement `_translate_single_tile(tile, client, prompt)`

<read_first>
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/app.py (lines 83-123 for the retry + dual-format parse + resize pattern)
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/image_translator.py (lines 69-114 for the same pattern, CLI variant)
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/.planning/phases/01-grid-module-core/01-RESEARCH.md (Finding 1 for extraction details)
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/.planning/phases/01-grid-module-core/01-CONTEXT.md (D-05 for tile failure = raise Exception)
</read_first>

<action>
Add function `_translate_single_tile` to `grid_translator.py` after the constants. This function extracts the retry + dual-format parse pattern from `app.py` lines 83-123, with these key differences from both existing entry points:

1. On final retry failure: **raise Exception** (not return HTTP 500, not set response=None)
2. After parsing the image from response: **resize to input tile size** using `tile.size`

Exact function:

```python
def _translate_single_tile(tile, client, prompt):
    """Dich mot tile qua Gemini voi retry va dual-format parse."""
    tile_size = tile.size
    retry_delay = RETRY_DELAY_SECONDS

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[tile, prompt]
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
                raise Exception("Phan hoi khong chua anh")
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                raise

    part = response.candidates[0].content.parts[0]

    if hasattr(part, 'image') and part.image:
        result = part.image
    elif hasattr(part, 'inline_data') and part.inline_data:
        result = Image.open(io.BytesIO(part.inline_data.data))
    else:
        raise Exception("Gemini khong tra ve anh hop le")

    result = result.resize(tile_size, Image.LANCZOS)
    return result
```

Key behavioral contracts:
- Takes `tile` (PIL Image), `client` (genai.Client instance), `prompt` (str)
- Returns PIL Image resized to `tile.size`
- On all retries exhausted: re-raises the last exception (GRID-07)
- Checks both `part.image` and `part.inline_data` (dual-format, same as existing code)
</action>

<acceptance_criteria>
- `grid_translator.py` contains `def _translate_single_tile(tile, client, prompt):`
- Function body contains `tile_size = tile.size`
- Function body contains `retry_delay = RETRY_DELAY_SECONDS`
- Function body contains `for attempt in range(MAX_RETRIES):`
- Function body contains `model=GEMINI_MODEL`
- Function body contains `contents=[tile, prompt]`
- Function body contains `hasattr(part, 'image') and part.image`
- Function body contains `hasattr(part, 'inline_data') and part.inline_data`
- Function body contains `Image.open(io.BytesIO(part.inline_data.data))`
- Function body contains `result.resize(tile_size, Image.LANCZOS)`
- Final `else` clause of retry loop contains `raise` (bare re-raise, NOT `return None`, NOT `return jsonify`)
- Function contains `return result` at the end
</acceptance_criteria>

---

### Task 3: Implement `_split_tiles(image, grid_n)`

<read_first>
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/.planning/phases/01-grid-module-core/01-RESEARCH.md (Finding 2 for split logic and coordinate space)
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/.planning/research/STACK.md (section 1.1 for Image.crop API and last-tile-absorbs-remainder pattern)
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/.planning/research/PITFALLS.md (P10 for slot_w = right - left, not tile_w)
</read_first>

<action>
Add function `_split_tiles` to `grid_translator.py` after `_translate_single_tile`. This function crops the image into grid_n x grid_n tiles where the last row/column absorbs remainder pixels.

Returns a flat list of tuples: `(row, col, left, upper, right, lower, tile_image)` — storing crop coordinates alongside each tile so `_stitch_tiles` can compute exact slot dimensions from `(right - left, lower - upper)` instead of using generic `tile_w`/`tile_h` (prevents P10 coordinate mismatch).

Exact function:

```python
def _split_tiles(image, grid_n):
    """Chia anh thanh grid_n x grid_n tiles. Tile cuoi hap thu pixel du."""
    img_w, img_h = image.size
    tile_w = img_w // grid_n
    tile_h = img_h // grid_n
    tiles = []
    for row in range(grid_n):
        for col in range(grid_n):
            left = col * tile_w
            upper = row * tile_h
            right = img_w if col == grid_n - 1 else left + tile_w
            lower = img_h if row == grid_n - 1 else upper + tile_h
            tiles.append((row, col, left, upper, right, lower, image.crop((left, upper, right, lower))))
    return tiles
```
</action>

<acceptance_criteria>
- `grid_translator.py` contains `def _split_tiles(image, grid_n):`
- Function computes `tile_w = img_w // grid_n`
- Function computes `tile_h = img_h // grid_n`
- Last-column guard: `right = img_w if col == grid_n - 1 else left + tile_w`
- Last-row guard: `lower = img_h if row == grid_n - 1 else upper + tile_h`
- Each tuple in returned list contains 7 elements: `(row, col, left, upper, right, lower, tile_image)`
- Function uses `image.crop((left, upper, right, lower))`
- Function returns `tiles` (a list)
</acceptance_criteria>

---

### Task 4: Implement `_stitch_tiles(translated_tiles, image_size, grid_n)`

<read_first>
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/.planning/phases/01-grid-module-core/01-RESEARCH.md (Finding 2 for stitch logic, canvas mode, assert)
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/.planning/research/STACK.md (section 1.2 for Image.paste API, slot_w/slot_h computation)
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/.planning/research/PITFALLS.md (P10 for slot_w = right - left; P7 for tile.convert(canvas.mode); P8 for memory — del after paste)
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/.planning/phases/01-grid-module-core/01-CONTEXT.md (D-06 for hard-paste, canvas mode from first tile, assert after stitch)
</read_first>

<action>
Add function `_stitch_tiles` to `grid_translator.py` after `_split_tiles`. This function takes translated tiles (with their crop coordinates) and pastes them onto a canvas.

Key requirements:
1. Canvas mode = mode of the first tile (CONTEXT D-06)
2. Each tile resized to exact slot dims `(right - left, lower - upper)` before paste (P10 prevention)
3. Mode guard: `tile.convert(canvas.mode)` before paste (P7 prevention)
4. Hard-paste only — no mask/blending (D-06)
5. `del` tile after paste for memory (P8)
6. Assert canvas.size == image_size after stitch (D-06)

Exact function:

```python
def _stitch_tiles(translated_tiles, image_size, grid_n):
    """Rap tiles da dich vao canvas. Hard-paste, khong blending."""
    canvas_mode = translated_tiles[0][1].mode
    canvas = Image.new(canvas_mode, image_size)

    for left, upper, right, lower, tile in translated_tiles:
        slot_w = right - left
        slot_h = lower - upper
        tile = tile.convert(canvas_mode)
        tile = tile.resize((slot_w, slot_h), Image.LANCZOS)
        canvas.paste(tile, (left, upper))
        del tile

    assert canvas.size == image_size, (
        f"Canvas size {canvas.size} != image size {image_size}"
    )
    return canvas
```

Note: `translated_tiles` is a list of `(left, upper, right, lower, tile_image)` tuples — the orchestrator (`translate_with_grid`) transforms the output of `_split_tiles` into this format after translating each tile.
</action>

<acceptance_criteria>
- `grid_translator.py` contains `def _stitch_tiles(translated_tiles, image_size, grid_n):`
- Function creates canvas with `Image.new(canvas_mode, image_size)`
- Function sets `canvas_mode = translated_tiles[0][1].mode`
- Function computes `slot_w = right - left` (not `tile_w`)
- Function computes `slot_h = lower - upper` (not `tile_h`)
- Function calls `tile.convert(canvas_mode)` before paste
- Function calls `tile.resize((slot_w, slot_h), Image.LANCZOS)` before paste
- Function calls `canvas.paste(tile, (left, upper))` — no mask argument
- Function contains `del tile` after paste
- Function contains `assert canvas.size == image_size`
- Function returns `canvas`
</acceptance_criteria>

---

### Task 5: Implement `translate_with_grid(image, client, prompt, grid_n=1)` — the public API

<read_first>
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/.planning/phases/01-grid-module-core/01-CONTEXT.md (D-01 for upscaled space, D-04 for grid_n=1 fast path, D-05 for tile failure propagation)
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/.planning/phases/01-grid-module-core/01-RESEARCH.md (Finding 3 for fast path, Finding 4 for tile failure)
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/.planning/REQUIREMENTS.md (GRID-01, GRID-06, GRID-07)
</read_first>

<action>
Add function `translate_with_grid` to `grid_translator.py` as the public API — place it as the LAST function in the file (after all private helpers).

This function orchestrates the full pipeline:
1. `grid_n == 1` fast path: call `_translate_single_tile` directly, resize to input image size, return (GRID-06)
2. `grid_n > 1`: split → translate each tile → stitch (GRID-01)
3. Any tile failure propagates up as Exception (GRID-07) — no try/except wrapping tile calls

Exact function:

```python
def translate_with_grid(image, client, prompt, grid_n=1):
    """Dich anh qua Gemini voi grid splitting. grid_n=1 = khong chia."""
    if grid_n == 1:
        result = _translate_single_tile(image, client, prompt)
        return result.resize(image.size, Image.LANCZOS)

    tiles = _split_tiles(image, grid_n)

    translated = []
    for row, col, left, upper, right, lower, tile in tiles:
        result = _translate_single_tile(tile, client, prompt)
        translated.append((left, upper, right, lower, result))

    return _stitch_tiles(translated, image.size, grid_n)
```

Key behavioral contracts:
- `grid_n=1`: calls `_translate_single_tile` once, returns resized result. No split/stitch.
- `grid_n>1`: splits into grid_n^2 tiles, translates each sequentially, stitches back.
- Tile failure (Exception from `_translate_single_tile`) propagates to caller unmodified — no catch.
- Returns PIL Image with `size == image.size` (guaranteed by fast-path resize or stitch assert).
</action>

<acceptance_criteria>
- `grid_translator.py` contains `def translate_with_grid(image, client, prompt, grid_n=1):`
- Function contains `if grid_n == 1:` as the first conditional
- Fast path calls `_translate_single_tile(image, client, prompt)` directly
- Fast path returns `result.resize(image.size, Image.LANCZOS)`
- For grid_n > 1: calls `_split_tiles(image, grid_n)`
- For grid_n > 1: iterates over tiles calling `_translate_single_tile(tile, client, prompt)`
- For grid_n > 1: calls `_stitch_tiles(translated, image.size, grid_n)`
- Function does NOT contain `try:` / `except` wrapping tile translation calls
- `translate_with_grid` is the LAST function defined in the file
</acceptance_criteria>

---

## Verification

After all tasks are complete, verify:

```bash
# 1. Module is importable
python -c "from grid_translator import translate_with_grid, GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS; print('OK')"

# 2. Public API signature
python -c "import inspect; from grid_translator import translate_with_grid; sig = inspect.signature(translate_with_grid); print(sig); assert 'grid_n' in sig.parameters; assert sig.parameters['grid_n'].default == 1; print('Signature OK')"

# 3. Constants values
python -c "from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS; assert GEMINI_MODEL == 'gemini-3.1-flash-image-preview'; assert MAX_RETRIES == 3; assert RETRY_DELAY_SECONDS == 2; print('Constants OK')"

# 4. Private functions exist
python -c "from grid_translator import _split_tiles, _translate_single_tile, _stitch_tiles; print('Private functions OK')"

# 5. No google.genai import in module
python -c "import ast; tree = ast.parse(open('grid_translator.py').read()); imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]; names = []; [names.extend(a.name for a in n.names) if isinstance(n, ast.Import) else names.append(n.module) for n in imports]; assert 'google' not in str(names) and 'genai' not in str(names); print('No genai import OK')"
```

---

## must_haves

- [ ] `grid_translator.py` exists in project root and is importable without errors
- [ ] `translate_with_grid(image, client, prompt, grid_n=1)` is a callable public function with `grid_n` defaulting to 1
- [ ] `_split_tiles` returns tiles with crop coordinates; last tile absorbs remainder pixels
- [ ] `_translate_single_tile` has retry loop (3 attempts, exponential backoff), dual-format image parse, resize to input tile size, and raises Exception on final failure
- [ ] `_stitch_tiles` uses `slot_w = right - left` (not generic `tile_w`), converts tile mode, hard-pastes, asserts canvas size
- [ ] `grid_n=1` fast path calls `_translate_single_tile` directly without split/stitch
- [ ] Tile failure propagates as Exception — no try/except in `translate_with_grid`
- [ ] Constants `GEMINI_MODEL`, `MAX_RETRIES`, `RETRY_DELAY_SECONDS` are defined with correct values
