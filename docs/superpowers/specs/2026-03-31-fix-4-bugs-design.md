# Fix 4 Bugs — Minimal Diff

**Date:** 2026-03-31
**Scope:** Fix 4 confirmed bugs. No refactoring, no feature additions.
**Approach:** Minimal diff — each fix is 2-8 lines, independent of others.

---

## Bug 1: XSS in `appendErrorBox()` — `static/script.js`

**Problem:** `container.innerHTML` interpolates unsanitized `filename` from user upload. A file named `<img onerror=alert(1)>` executes arbitrary JavaScript.

**Root cause:** Using `innerHTML` where only text content is needed.

**Fix:** Replace `innerHTML` with DOM API (`createElement` + `textContent`):

```js
// Before (vulnerable):
container.innerHTML = `<strong>Loi khi dich file:</strong> ${filename}`;

// After (safe):
const strong = document.createElement('strong');
strong.textContent = 'Loi khi dich file: ';
container.appendChild(strong);
container.appendChild(document.createTextNode(filename));
```

**Files changed:** `static/script.js` — function `appendErrorBox()`
**Risk:** None. Only changes error display rendering.

---

## Bug 2: `test_api.py` sends contents in wrong order

**Problem:** `contents=[img, prompt]` puts image before prompt. Per confirmed Gemini gotchas (CLAUDE.md), this causes Gemini to return text description instead of a translated image.

**Root cause:** Original code predates the discovery that prompt must come first.

**Fix:** Swap order to `contents=[prompt, img]`.

```python
# Before:
contents=[img, prompt]

# After:
contents=[prompt, img]
```

**Files changed:** `test_api.py` line 21
**Risk:** None. This is a test/smoke file, not production code.

---

## Bug 3: `_stitch_tiles` crashes on empty translated list — `grid_translator.py`

**Problem:** If every tile is detected as empty by `_is_empty_tile()`, `translate_with_grid()` passes an empty list to `_stitch_tiles()`. The function then crashes at `translated_tiles[0][4].mode` with `IndexError`.

**Trigger:** An image that is nearly blank or has very low pixel content (e.g., all-white image with transparency).

**Fix:** Add guard at the start of `_stitch_tiles`:

```python
def _stitch_tiles(translated_tiles, image_size, grid_n):
    if not translated_tiles:
        return Image.new('RGB', image_size, color=(255, 255, 255))
    # ... rest unchanged
```

**Files changed:** `grid_translator.py` — function `_stitch_tiles()`
**Risk:** Low. Returns a white canvas for edge case that previously crashed.

---

## Bug 4: Web always outputs JPEG — `app.py`

**Problem:** `result_pil_img.save(img_byte_arr, format='JPEG')` is hardcoded. PNG uploads lose alpha channel. WebP uploads lose compression benefits. The CLI (`image_translator.py`) correctly preserves the original format.

**Fix:** Detect format from upload filename extension, output in the same format:

```python
ext = os.path.splitext(file.filename)[1].lower()
fmt_map = {'.png': ('PNG', 'image/png'), '.webp': ('WEBP', 'image/webp')}
save_fmt, mime = fmt_map.get(ext, ('JPEG', 'image/jpeg'))
if save_fmt == 'JPEG' and result_pil_img.mode in ('RGBA', 'P'):
    result_pil_img = result_pil_img.convert('RGB')
result_pil_img.save(img_byte_arr, format=save_fmt)
# ... base64 response uses correct mime:
f"data:{mime};base64,{encoded_img}"
```

**Files changed:** `app.py` — route `/translate`, output section (~lines 100-109)
**Risk:** Low. Frontend already uses `data:` URLs with embedded MIME, so PNG/WebP will render correctly. Download button uses `imgSrc` directly, also fine.

---

## Summary

| Bug | File | Lines changed | Risk |
|-----|------|--------------|------|
| XSS `appendErrorBox` | `static/script.js` | ~5 | None |
| Wrong contents order | `test_api.py` | 1 | None |
| Empty tiles crash | `grid_translator.py` | 2 | Low |
| JPEG-only output | `app.py` | ~8 | Low |
| **Total** | **4 files** | **~16** | **Low** |

## Out of scope

- Duplicate prompt/upscale code (separate improvement)
- Italian comments cleanup (separate improvement)
- Logging infrastructure (separate improvement)
- Test framework migration (separate improvement)
- UX improvements (cancel, progress bar) (separate improvement)
