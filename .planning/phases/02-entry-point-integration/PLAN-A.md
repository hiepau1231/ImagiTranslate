# Plan A: CLI Integration — image_translator.py

```yaml
wave: 1
depends_on: []
files_modified:
  - image_translator.py
requirements:
  - CLI-01
autonomous: true
```

## Summary

Wire `translate_with_grid()` into the CLI entry point (`image_translator.py`):
- Add `--grid NxN` argparse flag with validation (1–4, square only)
- Replace inline retry+parse block with single `translate_with_grid()` call
- Clean up unused imports (`io`, `time`)
- Add `sys` and `re` imports for `sys.exit(1)` and regex validation

---

## Tasks

<task id="A1" title="Update imports: add sys, re, translate_with_grid; remove io, time">
<read_first>
- image_translator.py (entire file — verify current imports at lines 1-8)
- grid_translator.py (verify translate_with_grid export exists)
</read_first>

<action>
Edit `image_translator.py` imports block (lines 1-8).

**Remove** lines 2-3:
```python
import io
import time
```

**Add** after line 1 (`import os`):
```python
import re
import sys
```

**Change** line 8 from:
```python
from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS
```
to:
```python
from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS, translate_with_grid
```

Final imports block should be:
```python
import os
import re
import sys
import argparse
from pathlib import Path
from PIL import Image
from google import genai
from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS, translate_with_grid
```
</action>

<acceptance_criteria>
- image_translator.py contains `import re` (at top-level imports, NOT inside `__main__`)
- image_translator.py contains `import sys`
- image_translator.py contains `from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS, translate_with_grid`
- image_translator.py does NOT contain `import io`
- image_translator.py does NOT contain `import time`
</acceptance_criteria>
</task>

<task id="A2" title="Add grid_n parameter to translate_images() signature">
<read_first>
- image_translator.py (line 14 — current function signature)
</read_first>

<action>
Change line 14 from:
```python
def translate_images(input_dir: str, output_dir: str, source_lang: str, target_lang: str):
```
to:
```python
def translate_images(input_dir: str, output_dir: str, source_lang: str, target_lang: str, grid_n: int = 1):
```
</action>

<acceptance_criteria>
- image_translator.py contains `def translate_images(input_dir: str, output_dir: str, source_lang: str, target_lang: str, grid_n: int = 1):`
</acceptance_criteria>
</task>

<task id="A3" title="Replace retry+parse block with translate_with_grid() call">
<read_first>
- image_translator.py (lines 51-124 — the entire for-loop body inside translate_images)
- grid_translator.py (lines 89-102 — translate_with_grid signature and return type)
</read_first>

<action>
Inside the `for img_file in images_found:` loop, replace the block from line 67 (`retry_delay = RETRY_DELAY_SECONDS`) through line 120 (`print(f"    [-] Lỗi: Không nhận được phản hồi hợp lệ cho {img_file.name}.")`) with the following code.

The new code goes after line 65 (closing of the upscale `if` block). Delete lines 67-120 entirely and insert:

```python
            out_file_path = output_path / img_file.name
            result_image = translate_with_grid(base_image, client, prompt, grid_n)

            # Normalize output về kích thước gốc — Gemini có thể trả về size khác
            result_image = result_image.resize(orig_size, Image.LANCZOS)

            if img_file.suffix.lower() in {'.jpg', '.jpeg'} and result_image.mode in ('RGBA', 'P'):
                result_image = result_image.convert('RGB')

            result_image.save(out_file_path)
            print(f"    [+] Đã lưu thành công: {out_file_path}")
```

The `except Exception as e:` block at the current line 122-123 remains unchanged — it catches any error from `translate_with_grid()` (which raises on failure after 3 retries) and prints skip message.

The final try/except body inside the for-loop should look like:

```python
        try:
            base_image = Image.open(img_file)

            # Lưu kích thước gốc trước mọi xử lý — output sẽ được normalize về size này
            orig_size = base_image.size
            w, h = orig_size
            # Scale up để Gemini nhìn rõ chữ nhỏ (bỏ qua nếu ảnh đã quá lớn)
            if max(w, h) * UPSCALE_FACTOR <= UPSCALE_MAX_DIMENSION:
                base_image = base_image.resize(
                    (w * UPSCALE_FACTOR, h * UPSCALE_FACTOR),
                    Image.LANCZOS
                )

            out_file_path = output_path / img_file.name
            result_image = translate_with_grid(base_image, client, prompt, grid_n)

            # Normalize output về kích thước gốc — Gemini có thể trả về size khác
            result_image = result_image.resize(orig_size, Image.LANCZOS)

            if img_file.suffix.lower() in {'.jpg', '.jpeg'} and result_image.mode in ('RGBA', 'P'):
                result_image = result_image.convert('RGB')

            result_image.save(out_file_path)
            print(f"    [+] Đã lưu thành công: {out_file_path}")

        except Exception as e:
            print(f"    [!] Lỗi khi xử lý {img_file.name}: {e}")
```
</action>

<acceptance_criteria>
- image_translator.py contains `result_image = translate_with_grid(base_image, client, prompt, grid_n)`
- image_translator.py contains `out_file_path = output_path / img_file.name`
- image_translator.py contains `result_image = result_image.resize(orig_size, Image.LANCZOS)`
- image_translator.py contains `result_image = result_image.convert('RGB')`
- image_translator.py contains `result_image.save(out_file_path)`
- image_translator.py does NOT contain `for attempt in range(MAX_RETRIES):`
- image_translator.py does NOT contain `retry_delay = RETRY_DELAY_SECONDS`
- image_translator.py does NOT contain `response = None`
- image_translator.py does NOT contain `client.models.generate_content(`
- image_translator.py does NOT contain `part.inline_data`
- image_translator.py does NOT contain `part.image`
</acceptance_criteria>
</task>

<task id="A4" title="Add --grid argparse argument and validation in __main__">
<read_first>
- image_translator.py (lines 127-138 — current __main__ block with argparse)
</read_first>

<action>
Replace the `__main__` block (lines 127-138) with:

```python
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Dịch hàng loạt văn bản trong ảnh, giữ nguyên layout, dùng Gemini 3.1 Flash Image Preview."
    )
    parser.add_argument("-i", "--input", default="./input", help="Thư mục chứa ảnh gốc. Mặc định: ./input")
    parser.add_argument("-o", "--output", default="./output", help="Thư mục lưu ảnh đã dịch. Mặc định: ./output")
    parser.add_argument("-s", "--source-lang", default="auto-detect", help="Ngôn ngữ nguồn (vd: 'English'). Mặc định: auto-detect")
    parser.add_argument("-t", "--target-lang", required=True, help="Ngôn ngữ đích (vd: 'Vietnamese'). Bắt buộc.")
    parser.add_argument(
        "--grid",
        default=None,
        help="Kích thước lưới chia ảnh, ví dụ: --grid 2x2, --grid 3x3. Mặc định: không chia (xử lý toàn bộ ảnh). Hợp lệ: 1x1-4x4."
    )

    args = parser.parse_args()

    # Parse và validate --grid
    grid_n = 1
    if args.grid is not None:
        match = re.fullmatch(r'([1-4])x([1-4])', args.grid)
        if not match or match.group(1) != match.group(2):
            print("Lỗi: --grid phải có định dạng NxN (N từ 1-4), ví dụ: --grid 2x2")
            sys.exit(1)
        grid_n = int(match.group(1))

    translate_images(args.input, args.output, args.source_lang, args.target_lang, grid_n)
```

Note: `import re` is at the top-level imports (Task A1), NOT inline here. This follows CLAUDE.md §1.1 convention.
</action>

<acceptance_criteria>
- image_translator.py contains `"--grid",`
- image_translator.py contains `default=None,`
- image_translator.py contains `re.fullmatch(r'([1-4])x([1-4])', args.grid)`
- image_translator.py contains `match.group(1) != match.group(2)`
- image_translator.py contains `sys.exit(1)`
- image_translator.py contains `print("Lỗi: --grid phải có định dạng NxN (N từ 1-4), ví dụ: --grid 2x2")`
- image_translator.py contains `translate_images(args.input, args.output, args.source_lang, args.target_lang, grid_n)`
- image_translator.py does NOT contain `import re` inside the `__main__` block (must be at top-level)
</acceptance_criteria>
</task>

---

## Verification

After all tasks, the complete `image_translator.py` should:

1. **Import check:** `import re` and `import sys` present at top-level; `import io` and `import time` absent; `translate_with_grid` in grid_translator import
2. **Signature check:** `translate_images(...)` has `grid_n: int = 1` as last parameter
3. **No inline Gemini call:** no `client.models.generate_content(` anywhere in file
4. **Grid flag:** `--grid` argument in argparse with `default=None`
5. **Validation:** regex validates `NxN` format, N in 1-4, both parts equal; invalid → Vietnamese error + `sys.exit(1)`
6. **Backward compat:** running without `--grid` uses `grid_n=1` → same behavior as before

---

## must_haves

- [ ] `translate_with_grid` is imported and called with `(base_image, client, prompt, grid_n)`
- [ ] `--grid NxN` flag exists with validation range 1-4, square only
- [ ] Invalid `--grid` values (5x5, abc, 2x3) produce Vietnamese error + sys.exit(1)
- [ ] No `--grid` flag defaults to `grid_n=1` (backward compatible)
- [ ] Inline retry loop and dual-format parse are fully removed
- [ ] `io` and `time` imports are removed (no longer needed)
- [ ] `import re` is at top-level imports (not inline in `__main__`)
- [ ] `out_file_path` is defined before `result_image.save(out_file_path)`
- [ ] `result_image.save(out_file_path)` is present in the for-loop
- [ ] RGBA→RGB conversion on output is preserved (asymmetric pattern per CLAUDE.md)
- [ ] `result_image.resize(orig_size, Image.LANCZOS)` is preserved after translate_with_grid call
