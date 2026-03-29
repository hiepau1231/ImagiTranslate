---
phase: 02-entry-point-integration
verified_by: claude-code
date: "2026-03-29"
verdict: PASS
---

# Phase 02 Verification Report

**Phase goal:** Wire `translate_with_grid()` into both entry points (CLI and Web) so grid-based translation is accessible from both interfaces.
**Requirement IDs in scope:** CLI-01, WEB-01, WEB-02
**Plans verified:** 02-01 (image_translator.py), 02-02 (app.py + index.html + script.js)

---

## 1. Requirement ID Coverage

Cross-referenced every requirement ID appearing in plan frontmatter against REQUIREMENTS.md.

| Requirement ID | Defined in REQUIREMENTS.md | Assigned Phase | Covered by Plan | Status |
|----------------|---------------------------|----------------|-----------------|--------|
| CLI-01 | ✅ (v1, Phase 2) | Phase 2 | 02-01 (task A4) | ✅ ACCOUNTED |
| WEB-01 | ✅ (v1, Phase 2) | Phase 2 | 02-02 (task B4) | ✅ ACCOUNTED |
| WEB-02 | ✅ (v1, Phase 2) | Phase 2 | 02-02 (tasks B2+B3+B5) | ✅ ACCOUNTED |

All 3 requirement IDs from both plan frontmatter entries are defined in REQUIREMENTS.md. No orphan IDs, no missing IDs.

---

## 2. Success Criteria Verification (ROADMAP.md Phase 2)

### SC-1 — CLI `--grid 2x2` accepted; invalid format rejected with Vietnamese error + sys.exit(1)

**Evidence in `image_translator.py`:**
- `--grid` argparse flag present at line 93 with `default=None` (line 94)
- Validation at lines 102–107:
  ```python
  match = re.fullmatch(r'([1-4])x([1-4])', args.grid)
  if not match or match.group(1) != match.group(2):
      print("Lỗi: --grid phải có định dạng NxN (N từ 1-4), ví dụ: --grid 2x2")
      sys.exit(1)
  ```
- `import re` at line 2 (top-level, not inline)
- `import sys` at line 3 (top-level)
- Regex `([1-4])x([1-4])` enforces N in range 1–4; `match.group(1) != match.group(2)` enforces square (N==N)
- Error message is Vietnamese ✅
- `sys.exit(1)` is called on invalid input ✅

**Cases covered by validation logic:**
- `--grid 5x5` → regex `[1-4]` fails → print + exit(1) ✅
- `--grid abc` → `re.fullmatch` returns None → print + exit(1) ✅
- `--grid 2x3` → match but `group(1)('2') != group(2)('3')` → print + exit(1) ✅
- `--grid 2x2` → match, groups equal → `grid_n = 2` ✅

**Verdict: SC-1 PASS**

---

### SC-2 — `translate_images()` has `grid_n=1` default, backward-compatible

**Evidence in `image_translator.py` line 14:**
```python
def translate_images(input_dir: str, output_dir: str, source_lang: str, target_lang: str, grid_n: int = 1):
```
- `grid_n: int = 1` default present ✅
- Calling without `--grid` produces `grid_n = 1` (set at line 101, `if args.grid is not None:` block not entered) ✅
- `translate_with_grid(base_image, client, prompt, 1)` → `grid_translator.py` line 91: `if grid_n == 1:` → calls `_translate_single_tile()` directly, no split/stitch → identical path to old inline code ✅

**Verdict: SC-2 PASS**

---

### SC-3 — Web 3×3 grid works end-to-end (dropdown → FormData → backend parse → translate_with_grid)

**Dropdown in `templates/index.html` (lines 68–76):**
```html
<div class="input-group">
    <label for="grid-size">Grid:</label>
    <select id="grid-size" class="glass-input">
        <option value="off">Off</option>
        <option value="2x2">2×2</option>
        <option value="3x3">3×3</option>
        <option value="4x4">4×4</option>
    </select>
</div>
```
- `id="grid-size"` present ✅
- `class="glass-input"` on select ✅
- Inside `controls-section` ✅ (positioned after target-lang group, before `</section>` at line 77)
- 4 options: Off/2x2/3x3/4x4 all present ✅
- `3×3` option has `value="3x3"` ✅

**FormData in `static/script.js`:**
- DOM reference at line 17: `const gridSizeSel = document.getElementById('grid-size');` ✅
- Append at line 171: `formData.append('grid_size', gridSizeSel.value);` ✅ (after `api_key` append at line 170)

**Backend parse in `app.py` (lines 41–46):**
```python
grid_size = request.form.get('grid_size', 'off')
try:
    grid_n = int(grid_size.split('x')[0]) if grid_size != 'off' else 1
except (ValueError, IndexError):
    grid_n = 1
    print(f"Cảnh báo: Giá trị grid_size không hợp lệ '{grid_size}', dùng mặc định: off")
```
- `grid_size = '3x3'` → `grid_size.split('x')[0]` = `'3'` → `int('3')` = `3` → `grid_n = 3` ✅
- Defensive `try/except (ValueError, IndexError)` with Vietnamese warning print ✅

**translate_with_grid call in `app.py` line 86:**
```python
result_pil_img = translate_with_grid(base_image, client, prompt, grid_n)
```
- Called with `grid_n=3` when 3×3 selected ✅
- `grid_translator.py` line 95: `tiles = _split_tiles(image, 3)` → 9 tiles → all translated sequentially → stitched ✅

**Verdict: SC-3 PASS**

---

### SC-4 — Both entry points call translate_with_grid() instead of inline Gemini

**`image_translator.py` — Inline Gemini call removed:**
- No `client.models.generate_content(` anywhere in file ✅
- No `for attempt in range(MAX_RETRIES):` anywhere in file ✅
- No `retry_delay = RETRY_DELAY_SECONDS` anywhere in file ✅
- No `part.inline_data` anywhere in file ✅
- No `part.image` anywhere in file ✅
- No `response = None` anywhere in file ✅
- Single call at line 68: `result_image = translate_with_grid(base_image, client, prompt, grid_n)` ✅

**`app.py` — Inline Gemini call removed:**
- No `client.models.generate_content(` anywhere in file ✅
- No `for attempt in range(MAX_RETRIES):` anywhere in file ✅
- No `retry_delay = RETRY_DELAY_SECONDS` anywhere in file ✅
- No `part.inline_data` anywhere in file ✅
- No `part.image` anywhere in file ✅
- No `time.sleep(` anywhere in file ✅ (also: `import time` removed ✅)
- Single call at line 86: `result_pil_img = translate_with_grid(base_image, client, prompt, grid_n)` ✅

**translate_with_grid import verified in both files:**
- `image_translator.py` line 8: `from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS, translate_with_grid` ✅
- `app.py` line 7: `from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS, translate_with_grid` ✅

**Verdict: SC-4 PASS**

---

### SC-5 — grid_n=1 (no grid) behavior identical to current behavior

**`grid_translator.py` fast path (lines 91–93):**
```python
if grid_n == 1:
    result = _translate_single_tile(image, client, prompt)
    return result.resize(image.size, Image.LANCZOS)
```
- `_translate_single_tile` contains the same retry loop (3 attempts, exponential backoff) and dual-format parse (`part.image` / `part.inline_data`) as the original inline code ✅
- No tile splitting or stitching performed ✅
- Result resized to input image size, matching original contract ✅

**CLI backward compat (image_translator.py):**
- `grid_n=1` default in `translate_images()` signature ✅
- Without `--grid` flag: `grid_n = 1` (lines 101–107, `args.grid is None` → block skipped) ✅
- Upscale-before / resize-after contract unchanged (lines 61–71) ✅
- RGBA→RGB on output preserved (line 73–74, asymmetric pattern per CLAUDE.md §6.2) ✅
- `out_file_path` defined before `result_image.save(out_file_path)` (lines 67, 76) ✅

**Web backward compat (app.py):**
- `grid_size` defaults to `'off'` when field absent: `request.form.get('grid_size', 'off')` → `grid_n = 1` ✅
- RGBA→RGB on input preserved (lines 66–67, asymmetric pattern per CLAUDE.md §6.2) ✅
- `result_pil_img.resize(orig_size, Image.LANCZOS)` preserved at line 89 ✅
- JPEG save + base64 return block unchanged (lines 91–100) ✅

**Verdict: SC-5 PASS**

---

## 3. Plan must_haves Checklist

### Plan 02-01 (image_translator.py) — 11 must_haves

| # | must_have | Verified |
|---|-----------|----------|
| 1 | `translate_with_grid` imported and called with `(base_image, client, prompt, grid_n)` | ✅ lines 8, 68 |
| 2 | `--grid NxN` flag exists with validation range 1-4, square only | ✅ lines 92–107 |
| 3 | Invalid `--grid` values (5x5, abc, 2x3) produce Vietnamese error + sys.exit(1) | ✅ lines 104–106 |
| 4 | No `--grid` flag defaults to `grid_n=1` (backward compatible) | ✅ line 101 + default path |
| 5 | Inline retry loop and dual-format parse fully removed | ✅ no `generate_content`, no retry loop |
| 6 | `io` and `time` imports removed | ✅ neither present in file |
| 7 | `import re` at top-level imports (not inline in `__main__`) | ✅ line 2 |
| 8 | `out_file_path` defined before `result_image.save(out_file_path)` | ✅ lines 67, 76 |
| 9 | `result_image.save(out_file_path)` present in the for-loop | ✅ line 76 |
| 10 | RGBA→RGB conversion on output preserved (asymmetric pattern) | ✅ lines 73–74 |
| 11 | `result_image.resize(orig_size, Image.LANCZOS)` preserved after translate_with_grid call | ✅ line 71 |

**All 11 must_haves: PASS**

---

### Plan 02-02 (app.py + index.html + script.js) — 10 must_haves

| # | must_have | Verified |
|---|-----------|----------|
| 1 | `translate_with_grid` imported in app.py and called with `(base_image, client, prompt, grid_n)` | ✅ lines 7, 86 |
| 2 | Inline retry loop and dual-format parse fully removed from app.py | ✅ no `generate_content`, no retry loop |
| 3 | `import time` removed from app.py | ✅ not present |
| 4 | `grid_size` form field read with defensive parsing (try/except defaulting to 1 with print warning) | ✅ lines 41–46 |
| 5 | Grid dropdown in index.html with 4 options: Off, 2x2, 3x3, 4x4 | ✅ lines 68–76 |
| 6 | Dropdown uses `glass-input` class and is inside `controls-section` | ✅ line 70, inside `<section class="controls-section">` |
| 7 | `gridSizeSel` DOM reference added to script.js | ✅ line 17 |
| 8 | `grid_size` appended to FormData in script.js fetch block | ✅ line 171 |
| 9 | `result_pil_img.resize(orig_size, Image.LANCZOS)` preserved after translate_with_grid call | ✅ line 89 |
| 10 | JPEG save + base64 return unchanged | ✅ lines 91–100 |

**All 10 must_haves: PASS**

---

## 4. Task-Level Acceptance Criteria Spot-Check

### Plan 02-01 Tasks (A1–A4) — selected criteria

| Task | Criterion | Verified |
|------|-----------|----------|
| A1 | `import re` present (top-level) | ✅ line 2 |
| A1 | `import sys` present | ✅ line 3 |
| A1 | `from grid_translator import ... translate_with_grid` | ✅ line 8 |
| A1 | No `import io` | ✅ absent |
| A1 | No `import time` | ✅ absent |
| A2 | `def translate_images(... grid_n: int = 1):` | ✅ line 14 |
| A3 | `result_image = translate_with_grid(base_image, client, prompt, grid_n)` | ✅ line 68 |
| A3 | No `for attempt in range(MAX_RETRIES):` | ✅ absent |
| A3 | No `retry_delay = RETRY_DELAY_SECONDS` | ✅ absent |
| A3 | No `client.models.generate_content(` | ✅ absent |
| A3 | No `part.inline_data` / `part.image` | ✅ absent |
| A4 | `"--grid",` argparse argument | ✅ line 93 |
| A4 | `default=None,` | ✅ line 94 |
| A4 | `re.fullmatch(r'([1-4])x([1-4])', args.grid)` | ✅ line 103 |
| A4 | `match.group(1) != match.group(2)` | ✅ line 104 |
| A4 | `sys.exit(1)` | ✅ line 106 |
| A4 | Vietnamese error message | ✅ line 105 |
| A4 | `translate_images(args.input, args.output, args.source_lang, args.target_lang, grid_n)` | ✅ line 109 |
| A4 | `import re` NOT inside `__main__` block | ✅ line 2 (top-level) |

### Plan 02-02 Tasks (B1–B5) — selected criteria

| Task | Criterion | Verified |
|------|-----------|----------|
| B1 | `from grid_translator import ... translate_with_grid` | ✅ app.py line 7 |
| B1 | No `import time` | ✅ absent |
| B1 | `import io` present | ✅ app.py line 2 |
| B2 | `grid_size = request.form.get('grid_size', 'off')` | ✅ app.py line 41 |
| B2 | `grid_n = int(grid_size.split('x')[0]) if grid_size != 'off' else 1` | ✅ app.py line 43 |
| B2 | `except (ValueError, IndexError):` | ✅ app.py line 44 |
| B2 | Vietnamese warning print on invalid grid_size | ✅ app.py line 46 |
| B3 | `result_pil_img = translate_with_grid(base_image, client, prompt, grid_n)` | ✅ app.py line 86 |
| B3 | No `for attempt in range(MAX_RETRIES):` | ✅ absent |
| B3 | No `retry_delay = RETRY_DELAY_SECONDS` | ✅ absent |
| B3 | No `client.models.generate_content(` | ✅ absent |
| B3 | No `part.inline_data` / `part.image` | ✅ absent |
| B3 | No `time.sleep(` | ✅ absent |
| B3 | `result_pil_img = result_pil_img.resize(orig_size, Image.LANCZOS)` | ✅ app.py line 89 |
| B4 | `id="grid-size"` | ✅ index.html line 70 |
| B4 | `<label for="grid-size">Grid:</label>` | ✅ index.html line 69 |
| B4 | `class="glass-input"` on the select | ✅ index.html line 70 |
| B4 | `<option value="off">Off</option>` | ✅ index.html line 71 |
| B4 | `<option value="2x2">2×2</option>` | ✅ index.html line 72 |
| B4 | `<option value="3x3">3×3</option>` | ✅ index.html line 73 |
| B4 | `<option value="4x4">4×4</option>` | ✅ index.html line 74 |
| B5 | `const gridSizeSel = document.getElementById('grid-size');` | ✅ script.js line 17 |
| B5 | `formData.append('grid_size', gridSizeSel.value);` | ✅ script.js line 171 |

---

## 5. Behavioral Contract Preservation

### CLAUDE.md Asymmetric RGBA Pattern (§6.2)

| Entry Point | Expected Behavior | Actual |
|-------------|------------------|--------|
| `app.py` | RGBA→RGB on **input**, only JPEG | ✅ lines 66–67: `if base_image.mode in ('RGBA', 'P') and file.filename.lower().endswith(('.jpg', '.jpeg')): base_image = base_image.convert('RGB')` |
| `image_translator.py` | RGBA→RGB on **output**, only JPEG | ✅ lines 73–74: `if img_file.suffix.lower() in {'.jpg', '.jpeg'} and result_image.mode in ('RGBA', 'P'): result_image = result_image.convert('RGB')` |

Asymmetry preserved correctly.

### Upscale-before / Resize-after Contract

| File | Upscale (before translate_with_grid) | Resize (after translate_with_grid) |
|------|--------------------------------------|-------------------------------------|
| `image_translator.py` | lines 61–65 | line 71 |
| `app.py` | lines 70–74 | line 89 |

Contract unchanged in both entry points ✅

### grid_translator.py Public API Used Correctly

`translate_with_grid(image, client, prompt, grid_n=1)` — confirmed signature at `grid_translator.py` line 89.

Both call sites match:
- `image_translator.py` line 68: `translate_with_grid(base_image, client, prompt, grid_n)` ✅
- `app.py` line 86: `translate_with_grid(base_image, client, prompt, grid_n)` ✅

---

## 6. Observations / Notes

1. **`MAX_RETRIES` and `RETRY_DELAY_SECONDS` still imported but not used directly** in `image_translator.py` (line 8) and `app.py` (line 7). These constants are now used inside `grid_translator.py`. The imports are technically dead code in the entry points. This is a minor cleanup opportunity (v3 requirements or Phase 3 cleanup), but not a regression and not a Phase 2 goal — both files import them as part of the same import line that was already there (Phase 1 refactor). No functional impact.

2. **`grid_size` parse order in `app.py`**: `grid_size` is parsed at lines 41–46, *before* the `target_lang` validation at line 48. This is a logical ordering and matches the plan intent (B2 inserts after `target_lang` read, before `if not target_lang:`). The actual file has the grid parse inserted directly after `target_lang = request.form.get(...)` (line 40) and before `if not target_lang:` (line 48) — exactly as specified.

3. **`grid_n` variable scoping in `image_translator.py`**: Initialized to `1` at line 101, then conditionally updated inside `if args.grid is not None:` (line 102). If the block is entered and `sys.exit(1)` is not called, `grid_n` is updated to `int(match.group(1))` at line 107. Correct.

---

## 7. Summary Verdict

| Criterion | Result |
|-----------|--------|
| SC-1: CLI `--grid` flag + invalid rejection | ✅ PASS |
| SC-2: `translate_images()` backward-compatible default | ✅ PASS |
| SC-3: Web 3×3 grid end-to-end flow | ✅ PASS |
| SC-4: Both entry points use translate_with_grid() | ✅ PASS |
| SC-5: grid_n=1 behavior identical to previous | ✅ PASS |
| All CLI-01 criteria | ✅ PASS |
| All WEB-01 criteria | ✅ PASS |
| All WEB-02 criteria | ✅ PASS |
| Requirement IDs fully accounted (CLI-01, WEB-01, WEB-02) | ✅ PASS |
| CLAUDE.md RGBA asymmetry preserved | ✅ PASS |
| Upscale-before / resize-after contract preserved | ✅ PASS |

**Overall verdict: PASS — Phase 02 goals fully achieved. All 5 success criteria and all 21 combined must_haves verified against actual codebase.**
