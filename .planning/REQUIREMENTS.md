# Requirements: ImagiTranslate — Grid Splitting

**Defined:** 2026-03-29
**Core Value:** Mọi chữ trong ảnh game UI phải được dịch — không bỏ sót, không partial result.

## v1 Requirements

### Grid Module

- [ ] **GRID-01**: `grid_translator.py` mới với public API `translate_with_grid(image, client, prompt, grid_n)` nhận PIL Image, trả về PIL Image
- [ ] **GRID-02**: `_split_tiles(image, grid_n)` — crop ảnh thành NxN tiles bằng `Image.crop()`, tile cuối hàng/cột hấp thụ pixel dư
- [ ] **GRID-03**: `_translate_single_tile(tile, client, prompt)` — Gemini call + retry (3 lần, exponential backoff) + dual-format parse (`part.image` / `part.inline_data`), resize tile result về input tile size trước khi trả về
- [ ] **GRID-04**: `_stitch_tiles(tiles, orig_size, grid_n)` — paste tiles về canvas trống bằng `Image.paste()`, hard-paste (không blending), canvas size = input image size
- [ ] **GRID-05**: Constants (`GEMINI_MODEL`, `MAX_RETRIES`, `RETRY_DELAY_SECONDS`) tập trung vào `grid_translator.py` — cả `app.py` và `image_translator.py` import từ đây, xóa định nghĩa duplicate
- [ ] **GRID-06**: Grid mode opt-in, default `grid_n=1` (1×1 = không chia) — khi `grid_n=1`, `translate_with_grid()` gọi thẳng `_translate_single_tile()` mà không split/stitch, behavior hiện tại 100% không đổi
- [ ] **GRID-07**: Tile thất bại sau 3 lần retry → raise Exception, `translate_with_grid()` propagate lên caller — không partial stitch, xử lý lỗi y hệt hiện tại (HTTP 500 ở web, skip file ở CLI)

### CLI

- [ ] **CLI-01**: Flag `--grid NxN` (ví dụ `--grid 2x2`, `--grid 3x3`), mặc định bỏ trống = không chia; validate format và giá trị hợp lệ (1–4)

### Web

- [ ] **WEB-01**: Dropdown "Grid size" trong form: Off / 2×2 / 3×3 / 4×4 — hiển thị cạnh các control hiện tại
- [ ] **WEB-02**: Backend `/translate` nhận field `grid_size` từ form POST, parse thành `grid_n` integer, truyền vào `translate_with_grid()`

## v2 Requirements

### Grid Quality

- **QUAL-01**: Overlap/padding 64px giữa tiles để tránh text bị cắt ở seam
- **QUAL-02**: Feather blending 16–24px tại interior seams để giảm đường kẻ thấy rõ
- **QUAL-03**: Style-anchor prompt (gửi thumbnail ảnh gốc kèm tile) để Gemini giữ màu sắc nhất quán giữa các tiles

### UX

- **UX-01**: Hiển thị "Tile 2/4..." trong CLI output khi đang xử lý
- **UX-02**: Hiển thị estimated time và call count trong web UI ("3×3 = 9 calls, ~45s")
- **UX-03**: Per-tile SSE progress trong web UI
- **UX-04**: Grid preview overlay để user thấy ảnh sẽ được chia thế nào trước khi dịch

### Adaptive Grid

- **ADAPT-01**: Tự động chọn grid size dựa theo mật độ text trong ảnh

## Out of Scope

| Feature | Reason |
|---------|--------|
| Parallel tile API calls | Rate limit: 3×3 = 9 calls/image, tối đa 27 với retry; parallel phá vỡ sequential design của app |
| Per-tile manual review UI | Sai product direction — user muốn automatic không cần review |
| Non-rectangular tiles | Không cần thiết cho game UI |
| OCR để detect text regions | Out of scope theo quyết định ban đầu; Gemini đã xử lý text detection |
| Blend stitching v1 | Build hard-paste trước, đo seam quality thực tế trước khi đầu tư |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| GRID-01 | Phase 1 | Pending |
| GRID-02 | Phase 1 | Pending |
| GRID-03 | Phase 1 | Pending |
| GRID-04 | Phase 1 | Pending |
| GRID-05 | Phase 1 | Pending |
| GRID-06 | Phase 1 | Pending |
| GRID-07 | Phase 1 | Pending |
| CLI-01 | Phase 2 | Pending |
| WEB-01 | Phase 2 | Pending |
| WEB-02 | Phase 2 | Pending |

**Coverage:**
- v1 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-29*
*Last updated: 2026-03-29 after initial definition*
