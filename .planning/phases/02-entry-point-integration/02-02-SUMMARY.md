---
plan: 02-02
phase: 02-entry-point-integration
status: complete
completed: "2026-03-29"
commits:
  - B1: 0f503d7
  - B2: dab9bf6
  - B3: 5330c11
  - B4: 329df6a
  - B5: d032252
---

# Summary: Plan 02-02 — Web Integration (app.py + index.html + script.js)

## What Was Done

Wired `translate_with_grid()` into the web entry point across all three files.

### Task B1 — app.py: Imports
- Removed `import time` (no longer used after retry logic moved to `grid_translator.py`)
- Added `translate_with_grid` to the `grid_translator` import line

### Task B2 — app.py: grid_size parse
- Added `grid_size = request.form.get('grid_size', 'off')` after `target_lang` read
- Defensive parse: `int(grid_size.split('x')[0])` for `NxN` values, `1` for `'off'`
- `except (ValueError, IndexError)` defaults to `grid_n=1` with Vietnamese warning print

### Task B3 — app.py: Replace retry+parse block
- Deleted the entire inline retry loop (38 lines): `retry_delay`, `response = None`, `for attempt in range(MAX_RETRIES):`, dual-format `part.image`/`part.inline_data` parse, and error returns
- Replaced with single call: `result_pil_img = translate_with_grid(base_image, client, prompt, grid_n)`
- Preserved: `result_pil_img.resize(orig_size, Image.LANCZOS)` + JPEG save + base64 return
- Error propagation: outer `except Exception as e:` still catches failures from `translate_with_grid()` and returns HTTP 500

### Task B4 — index.html: Grid dropdown
- Added `<div class="input-group">` with `<label for="grid-size">Grid:</label>` and `<select id="grid-size" class="glass-input">` inside `controls-section`
- 4 options: `Off`, `2×2`, `3×3`, `4×4` with values `off`, `2x2`, `3x3`, `4x4`
- Placed after target-lang group, before `</section>`

### Task B5 — script.js: DOM ref + FormData
- Added `const gridSizeSel = document.getElementById('grid-size');` after `apiKeyInput` ref
- Added `formData.append('grid_size', gridSizeSel.value);` after `api_key` append in the fetch loop

## Verification

| Check | Result |
|-------|--------|
| `translate_with_grid` imported and called with `(base_image, client, prompt, grid_n)` | ✅ |
| Inline retry loop fully removed | ✅ |
| `import time` absent | ✅ |
| `grid_size` form field read with defensive parse | ✅ |
| Grid dropdown in index.html with 4 options | ✅ |
| Dropdown uses `glass-input` class inside `controls-section` | ✅ |
| `gridSizeSel` DOM ref in script.js | ✅ |
| `grid_size` appended to FormData | ✅ |
| `result_pil_img.resize(orig_size, Image.LANCZOS)` preserved | ✅ |
| JPEG save + base64 return unchanged | ✅ |

## End-to-End Flow

Selecting "3×3" in the dropdown:
1. Frontend sends `grid_size=3x3` in FormData
2. Backend: `grid_size.split('x')[0]` → `int('3')` → `grid_n=3`
3. `translate_with_grid(base_image, client, prompt, 3)` called
4. 9 tiles processed sequentially, stitched, returned as JPEG
