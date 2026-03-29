# Phase 1: Grid Module Core - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Xây dựng `grid_translator.py` — Python module độc lập chứa toàn bộ grid logic: split image thành NxN tiles, dịch từng tile qua Gemini, stitch lại thành ảnh hoàn chỉnh. Tập trung constants từ cả 2 entry point vào module này.

**Không trong scope phase này:** CLI flag `--grid`, web UI dropdown, bất kỳ thay đổi nào trong `app.py` hay `image_translator.py` ngoài việc import constants.

</domain>

<decisions>
## Implementation Decisions

### Coordinate Space
- **D-01:** `translate_with_grid()` nhận ảnh đã được upscale bởi caller (không tự upscale). Split và stitch đều xảy ra trong upscaled space. Caller vẫn giữ nguyên trách nhiệm resize về `orig_size` sau khi nhận kết quả — contract hiện tại không đổi.
- **D-02:** Module không biết về `orig_size` — chỉ xử lý image ở kích thước nhận được. Tile dimensions được tính từ input image size.

### Constants Ownership
- **D-03:** `GEMINI_MODEL`, `MAX_RETRIES`, `RETRY_DELAY_SECONDS` được định nghĩa trong `grid_translator.py` làm single source of truth. Cả `app.py` và `image_translator.py` import từ đây (xóa định nghĩa duplicate). Không tạo file `constants.py` riêng — module đủ nhỏ.

### 1×1 Fallback Path
- **D-04:** Khi `grid_n=1`, `translate_with_grid()` gọi thẳng `_translate_single_tile()` — bỏ qua split/stitch hoàn toàn. Đây là fast path đảm bảo zero overhead khi grid tắt. Test 1×1 vs existing direct call phải cho output giống hệt nhau.

### Tile Failure Behavior
- **D-05:** Tile thất bại sau `MAX_RETRIES` → raise Exception, propagate lên caller. Không return None, không return original tile. Caller xử lý giống như hiện tại (HTTP 500 ở web, skip file ở CLI). Không có partial stitch.

### Stitch Method
- **D-06:** Hard-paste (không feather blending). `Image.new()` → `Image.paste(tile, (x, y))` cho từng tile. Canvas size = input image size. Tile response được resize về đúng slot dimensions trước khi paste (vì Gemini không đảm bảo trả về đúng kích thước input).

### Claude's Discretion
- Padding / overlap giữa tiles: không có trong v1 — Claude quyết định cách xử lý pixel remainder ở tile biên (tile cuối hấp thụ phần dư).
- Tên internal functions (`_split_tiles`, `_stitch_tiles`, `_translate_single_tile`): Claude quyết định signature chi tiết.
- Canvas mode: tạo canvas với mode của tile đầu tiên.
- Assertion sau stitch: thêm `assert canvas.size == input_image.size` để catch coordinate bugs sớm.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing entry points (integration points)
- `app.py` — Flask web entry point; hiện có inline Gemini call sẽ được thay bởi `translate_with_grid()`; RGBA conversion xảy ra trên input trước khi upscale
- `image_translator.py` — CLI entry point; RGBA conversion xảy ra trên output sau khi nhận kết quả

### Project requirements
- `.planning/REQUIREMENTS.md` — Full requirement list GRID-01 đến GRID-07
- `.planning/research/ARCHITECTURE.md` — Data flow diagram và build order chi tiết
- `.planning/research/PITFALLS.md` — 10 pitfalls, đặc biệt P10 (coordinate mismatch), P7 (RGBA), P4 (rate limit math)
- `.planning/research/STACK.md` — Pillow API specifics: `Image.crop(box)`, `Image.paste(tile, pos, mask)`, last-tile remainder handling

### Codebase patterns
- `.planning/codebase/CONVENTIONS.md` — Code organization: imports → constants → functions; naming conventions
- `.planning/codebase/ARCHITECTURE.md` — Existing dual-entry architecture và retry pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Retry + dual-format parse block** (dòng ~82-110 trong `app.py`, tương tự trong `image_translator.py`): Logic này sẽ được extract thành `_translate_single_tile()`. Cả 2 file dùng pattern giống nhau — dễ extract.
- **`genai.Client`**: Được tạo bởi caller và truyền vào `translate_with_grid()` — module không tự tạo client.

### Established Patterns
- **Constants**: `ALL_CAPS` module-level, sau imports — áp dụng cho `grid_translator.py`
- **Error handling**: Dùng bare `except Exception as e` với `attempt < MAX_RETRIES - 1` check — giữ nguyên pattern này trong `_translate_single_tile()`
- **Dual image response**: Luôn check cả `part.image` lẫn `part.inline_data` — bắt buộc vì Gemini SDK inconsistent

### Integration Points
- `translate_with_grid(image, client, prompt, grid_n=1)` thay thế block `client.models.generate_content(...)` trong cả 2 entry points
- Upscale xảy ra trước khi gọi `translate_with_grid()` — không thay đổi
- `result.resize(orig_size)` xảy ra sau khi nhận về — không thay đổi
- RGBA asymmetry giữa 2 entry points được giữ nguyên — module nhận ảnh "đã xử lý" từ caller

</code_context>

<specifics>
## Specific Ideas

- Coordinate space rõ ràng: **upscaled space only** — module không track orig_size
- Test quan trọng: `translate_with_grid(image, client, prompt, grid_n=1)` phải cho output giống hệt gọi thẳng `_translate_single_tile()` trên cùng ảnh

</specifics>

<deferred>
## Deferred Ideas

- Overlap/padding giữa tiles (v2) — tránh text bị cắt ở seam
- Feather blending tại interior seams (v2) — giảm đường kẻ thấy rõ
- Style-anchor prompt với thumbnail (v2) — giữ màu sắc nhất quán giữa tiles
- Per-tile progress logging (v2) — "Tile 2/4..."

</deferred>

---

*Phase: 01-grid-module-core*
*Context gathered: 2026-03-29*
