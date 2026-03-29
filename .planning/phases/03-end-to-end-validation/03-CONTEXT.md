# Phase 3: End-to-End Validation - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Validate toàn bộ pipeline grid splitting đã build trong Phase 1 và Phase 2 — cả web lẫn CLI, mọi grid size — và đảm bảo không có regression với mode Off/1×1. **Không thêm feature mới.** Nếu phát hiện bug, sửa luôn trong phase này để SC pass.

5 Success Criteria cần verify:
- SC-1: Off vs 2×2 vs 3×3 trên ảnh game UI thực — grid không tệ hơn Off
- SC-2: Web batch 3 ảnh với grid 2×2 — cả 3 thành công, side-by-side UI đúng
- SC-3: CLI batch 5 ảnh với `--grid 2x2` — 5 file output tồn tại, kích thước ±1px
- SC-4: PNG (alpha) qua grid mode không gây `OSError: cannot write mode RGBA as JPEG`
- SC-5: `grid_n=1` = 1 call; `grid_n=2` = 4 calls; `grid_n=3` = 9 calls

</domain>

<decisions>
## Implementation Decisions

### Test Approach
- **D-01:** Viết live API test script (`test_grid.py`) theo pattern của `test_api.py` hiện có — cần `GEMINI_API_KEY` env var, gọi Gemini thực. Không dùng pytest framework, không thêm dependencies mới.
- **D-02:** File đặt tại project root cùng với `test_api.py`.

### Test Data
- **D-03:** Dùng real game UI images trong thư mục `test_images/` tại project root. User tự đặt ảnh vào trước khi chạy. Test script cần graceful skip nếu `test_images/` không tồn tại hoặc rỗng (print warning, không crash).
- **D-04:** SC-1, SC-2, SC-3 dùng real images từ `test_images/`. SC-4 và SC-5 có thể dùng synthetic image (Image.new) để không phụ thuộc real images.

### SC-5: API Call Count Verification
- **D-05:** Mock `_translate_single_tile` bằng `unittest.mock.patch` trong test script — patch function, đếm số lần được gọi (`call_count`). Không tốn API credits cho test này, verify chính xác grid_n^2 calls.

### Bug Handling
- **D-06:** Nếu test script phát hiện bug trong quá trình validate, sửa luôn trong phase này trước khi mark SC là pass. Phase hoàn thành khi tất cả 5 SC pass — không chuyển sang gap-closure nếu còn SC nào fail vì bug có thể sửa được.

### Claude's Discretion
- Cấu trúc nội bộ của `test_grid.py` (functions, ordering)
- Format output của test (print statements vs logging)
- Cách report kết quả (pass/fail per SC)
- Synthetic image dimensions cho SC-4, SC-5

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Pipeline đã build (integration targets)
- `grid_translator.py` — Module cần validate: `translate_with_grid()`, `_split_tiles()`, `_stitch_tiles()`, `_translate_single_tile()`; constants `MAX_RETRIES`, `RETRY_DELAY_SECONDS`
- `image_translator.py` — CLI entry point đã được modify ở Phase 2: `--grid NxN` flag, `translate_images(grid_n=1)`
- `app.py` — Web entry point đã được modify ở Phase 2: `grid_size` form field, `translate_with_grid()` call

### Existing test pattern
- `test_api.py` — Pattern hiện có: `GEMINI_API_KEY` env var, `genai.Client(api_key=...)`, synthetic image, print-based output. `test_grid.py` theo cùng pattern này.

### Success Criteria (source of truth)
- `.planning/ROADMAP.md` §Phase 3 — 5 SC definitions (SC-1 đến SC-5) là spec chính xác cần verify
- `.planning/REQUIREMENTS.md` — GRID-01 đến GRID-07, CLI-01, WEB-01, WEB-02 (all v1 requirements)

### Prior phase artifacts
- `.planning/phases/02-entry-point-integration/02-VERIFICATION.md` — Xác nhận what Phase 2 delivered; cross-check với SC-2, SC-3, SC-4
- `.planning/phases/01-grid-module-core/VERIFICATION.md` — Xác nhận grid_translator.py contract; cross-check với SC-5

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`test_api.py`** pattern — Import style, client init, synthetic image creation, print-based pass/fail. `test_grid.py` extends this pattern, không thay thế.
- **`unittest.mock.patch`** (stdlib) — Dùng cho SC-5 mock, không cần install gì thêm.

### Established Patterns
- **Error handling:** Cả 2 entry points propagate Exception từ `translate_with_grid()` lên — web trả HTTP 500, CLI skip file. Test script cần expect behavior này.
- **RGBA asymmetry:** `app.py` convert RGBA→RGB trên input; `image_translator.py` convert trên output. SC-4 cần test cả 2 paths.
- **Sequential processing:** Không thay đổi — test script cũng chạy sequential.

### Integration Points
- SC-2 (web batch): Test script không test Flask server trực tiếp — test `translate_with_grid()` function với real client thay thế
- SC-3 (CLI batch): Có thể gọi trực tiếp `translate_images()` function thay vì subprocess CLI
- `test_images/` directory tại project root — cần tồn tại với ít nhất 1 ảnh game UI trước khi chạy SC-1, SC-2, SC-3

</code_context>

<deferred>
## Deferred Ideas

- QUAL-01/QUAL-02/QUAL-03 (overlap padding, feather blending, style-anchor) — v2 requirements
- UX-01 đến UX-04 (tile progress, estimated time, SSE, grid preview) — v2 requirements
- ADAPT-01 (auto grid size selection) — v2 requirements
- pytest migration — nếu project phát triển thêm, xem xét sau milestone v1.0

</deferred>

---

*Phase: 03-end-to-end-validation*
*Context gathered: 2026-03-29*
