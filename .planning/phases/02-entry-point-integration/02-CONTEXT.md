# Phase 2: Entry Point Integration - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Kết nối `translate_with_grid()` vào cả hai entry point:
- **CLI** (`image_translator.py`): thêm flag `--grid NxN`, validate input, truyền `grid_n` vào `translate_images()` và xuống `translate_with_grid()`
- **Web** (`app.py` + `templates/index.html` + `static/script.js`): thêm dropdown "Grid size" vào form, backend đọc `grid_size` từ POST, parse thành `grid_n`, truyền vào `translate_with_grid()`

**Không trong scope phase này:** thay đổi logic dịch, thay đổi upscale/resize pipeline, UI redesign, bất kỳ thay đổi nào trong `grid_translator.py`.

</domain>

<decisions>
## Implementation Decisions

### CLI — Function Signature
- **D-01:** Thêm `grid_n=1` vào signature của `translate_images()`: `translate_images(input_dir, output_dir, source_lang, target_lang, grid_n=1)`. Default=1 đảm bảo backward-compatible — hành vi hiện tại 100% không đổi khi không truyền `grid_n`.
- **D-02:** Trong `__main__` block: parse `args.grid` → tính `grid_n` → truyền vào `translate_images(..., grid_n=grid_n)`.

### CLI — Flag Design
- **D-03:** Flag: `--grid NxN` (ví dụ `--grid 2x2`, `--grid 3x3`). Mặc định bỏ trống (không dùng grid). Format: `{N}x{N}` trong đó N là số nguyên 1–4.
- **D-04:** Validation: parse bằng regex hoặc split `x`, check cả hai phần bằng nhau và trong range [1,4]. Nếu `--grid 1x1` → `grid_n=1` (tương đương không dùng grid — fast path).
- **D-05:** Error handling: invalid format hoặc out-of-range → in error message bằng tiếng Việt + `sys.exit(1)`. Ví dụ: `"Lỗi: --grid phải có định dạng NxN (N từ 1-4), ví dụ: --grid 2x2"`.

### CLI — Integration Point
- **D-06:** Thay thế `client.models.generate_content(...)` call trong vòng lặp `for img_file in images_found` bằng `translate_with_grid(base_image, client, prompt, grid_n)`. Upscale xảy ra trước như hiện tại; `result_image.resize(orig_size)` xảy ra sau như hiện tại — không thay đổi caller contract.
- **D-07:** Import: `from grid_translator import translate_with_grid` — thêm vào đầu file (sau các import hiện có).

### Web — Frontend (index.html)
- **D-08:** Dropdown `<select id="grid-size">` đặt trong `controls-section`, sau dropdown "Sang:" (target-lang). Dùng class `glass-input` để đồng bộ style với các controls hiện tại.
- **D-09:** Label: `"Grid:"`. Options: `Off` (value `"off"`), `2×2` (value `"2x2"`), `3×3` (value `"3x3"`), `4×4` (value `"4x4"`). Default: `Off`.

### Web — Frontend (script.js)
- **D-10:** Thêm `const gridSizeSel = document.getElementById('grid-size');` vào DOM references block.
- **D-11:** Trong `formData.append` block: `formData.append('grid_size', gridSizeSel.value);`. Field name `grid_size` phải khớp với backend.

### Web — Backend (app.py)
- **D-12:** Đọc field: `grid_size = request.form.get('grid_size', 'off')`.
- **D-13:** Parse: `grid_n = int(grid_size[0]) if grid_size != 'off' else 1`. Hoặc parse format `NxN` bằng `int(grid_size.split('x')[0])` — vì frontend luôn gửi `"off"` hoặc `"2x2"`, `"3x3"`, `"4x4"`.
- **D-14:** Thay thế `client.models.generate_content(...)` block bằng `translate_with_grid(base_image, client, prompt, grid_n)`. Upscale xảy ra trước như hiện tại; resize về `orig_size` sau như hiện tại.
- **D-15:** Import: `from grid_translator import translate_with_grid` — thêm vào đầu file (sau các import hiện có).

### Claude's Discretion
- Vị trí chính xác của `--grid` trong argparse help string — Claude quyết định help text tiếng Việt phù hợp
- Có validate cả hai chiều NxN (chỉ chấp nhận N==N, tức là square grid) hay chấp nhận NxM — Claude quyết định: chỉ square (NxN với N==N) vì requirements nói "NxN grid"
- Backend validation: nếu frontend gửi giá trị không hợp lệ, Claude quyết định cách xử lý (default về 1 hoặc return 400)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing entry points (integration points)
- `app.py` — Flask web entry point; inline `client.models.generate_content()` cần được thay bằng `translate_with_grid()`; đọc kỹ flow từ line 34 (`translate_image()`) đến line 134
- `image_translator.py` — CLI entry point; `translate_images()` function cần thêm `grid_n=1` param; argparse block ở cuối file (line 129–140)
- `templates/index.html` — controls-section chứa source-lang và target-lang dropdowns; grid dropdown thêm vào đây
- `static/script.js` — FormData append block (line 165–169) cần thêm `grid_size`; DOM references block (line 14–16) cần thêm `gridSizeSel`

### Phase 1 output (module được wire vào)
- `grid_translator.py` — Public API: `translate_with_grid(image, client, prompt, grid_n=1)`; đây là function sẽ thay thế inline Gemini call trong cả hai entry points

### Project requirements
- `.planning/REQUIREMENTS.md` — CLI-01, WEB-01, WEB-02 definitions (page source of truth)
- `.planning/ROADMAP.md` — Phase 2 success criteria (5 criteria, đặc biệt SC-1 validate format, SC-3 web 3x3)

### Codebase patterns
- `CLAUDE.md` — Conventions: imports → constants → functions; Vietnamese comments; error handling patterns; RGBA asymmetry giữa 2 entry points giữ nguyên

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`glass-input` CSS class** — Dùng cho tất cả select/input trong controls-section; dropdown grid-size dùng class này để consistent
- **argparse block** (`image_translator.py` line 129–140) — Pattern add_argument đã có; thêm `--grid` theo cùng pattern
- **FormData append block** (`static/script.js` line 165–169) — Thêm `grid_size` theo cùng pattern với `source_lang`, `target_lang`

### Established Patterns
- **CLI error + exit**: print error message → `sys.exit(1)` (hoặc raise SystemExit) — pattern chưa có trong `__main__` nhưng cần thêm cho `--grid` validation
- **Backend form read**: `request.form.get('field', default)` — đã dùng cho `source_lang`, `target_lang`, `api_key`
- **Upscale-before, resize-after contract**: cả 2 entry points upscale trước khi gọi translate, resize về `orig_size` sau khi nhận kết quả — contract này KHÔNG thay đổi khi wire `translate_with_grid()`

### Integration Points
- `image_translator.py` line 72–99: vòng lặp retry + `client.models.generate_content()` sẽ được thay bằng 1 dòng `translate_with_grid(...)`
- `app.py` line 83–120: block retry + generate_content + dual-format parse sẽ được thay bằng 1 dòng `translate_with_grid(...)`; kết quả gán vào `result_pil_img`
- Sau khi gọi `translate_with_grid()`, cả 2 entry points tiếp tục: CLI save file, web encode base64 — không thay đổi

</code_context>

<specifics>
## Specific Ideas

- CLI flag format: `--grid 2x2` (lowercase x) — consistent với requirement examples
- Web field name: `grid_size` (snake_case) — consistent với `source_lang`, `target_lang` naming
- Dropdown label: `"Grid:"` — ngắn gọn, fit với layout `"Từ:"` / `"Sang:"`
- Validation range 1–4: giới hạn theo REQUIREMENTS.md CLI-01 (không tự ý mở rộng)

</specifics>

<deferred>
## Deferred Ideas

- Hint text trên dropdown ("3×3 = 9 API calls") — UX-02 trong v2 requirements
- CLI progress per tile ("Tile 2/4...") — UX-01 trong v2 requirements
- Validate NxM (non-square) grid — không trong scope, grid_translator chỉ hỗ trợ NxN

</deferred>

---

*Phase: 02-entry-point-integration*
*Context gathered: 2026-03-29*
