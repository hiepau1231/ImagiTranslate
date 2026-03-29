# Roadmap: ImagiTranslate

## Milestone 1: Grid-Split Translation

**Goal:** Dịch ảnh game UI với độ phủ text tối đa bằng cách chia ảnh thành grid nhỏ, dịch từng tile độc lập, rồi ráp lại thành ảnh hoàn chỉnh — áp dụng cho cả web app lẫn CLI tool.
**Requirements:** 10 v1 requirements
**Phases:** 3

---

## Phase 1: Grid Module Core

**Goal:** Xây dựng `grid_translator.py` — module độc lập chứa toàn bộ grid logic (split → translate → stitch), tập trung constants, và đảm bảo behavior hiện tại 100% không đổi khi `grid_n=1`.
**Requirements:** GRID-01, GRID-02, GRID-03, GRID-04, GRID-05, GRID-06, GRID-07
**UI hint:** no

### Plans

| Plan | Description | Status |
|------|-------------|--------|
| 01-01 | Create `grid_translator.py` module | Done (2026-03-29) |
| 01-02 | Constants migration (app.py + image_translator.py) | Done (2026-03-29) |

### Success Criteria

1. `translate_with_grid(image, client, prompt, grid_n=1)` có thể import và gọi được từ Python shell mà không có lỗi; trả về PIL Image với `size == input.size`.
2. Khi `grid_n=1`, output của `translate_with_grid()` khớp pixel với output của code hiện tại (gọi thẳng `generate_content`) trên cùng một ảnh test.
3. Khi `grid_n=2`, ảnh được chia thành 4 tiles, mỗi tile được xử lý riêng, và ảnh ráp lại có đúng kích thước gốc (`assert canvas.size == orig_size` pass).
4. Khi một tile thất bại sau 3 lần retry, `translate_with_grid()` raise Exception — không trả về ảnh partial.
5. `app.py` và `image_translator.py` import `GEMINI_MODEL`, `MAX_RETRIES`, `RETRY_DELAY_SECONDS` từ `grid_translator` — không còn định nghĩa duplicate trong hai file đó.

---

## Phase 2: Entry Point Integration

**Goal:** Kết nối `translate_with_grid()` vào cả hai entry point — CLI nhận flag `--grid NxN`, web nhận dropdown "Grid size" và truyền `grid_n` vào backend — để user có thể chủ động bật grid mode.
**Requirements:** CLI-01, WEB-01, WEB-02
**UI hint:** yes (web dropdown)

### Plans

| Plan | Description | Status |
|------|-------------|--------|
| 02-01 | CLI Integration — image_translator.py | ✅ Done (2026-03-29) |
| 02-02 | Web Integration — app.py + frontend | ✅ Done (2026-03-29) |

### Success Criteria

1. CLI: `python image_translator.py --grid 2x2 -i ./input -o ./output` xử lý thành công, output file ráp đủ 4 tiles không có lỗi.
2. CLI: `python image_translator.py` (không có `--grid`) cho kết quả giống hệt behavior trước khi thêm feature — không regression.
3. CLI: `--grid 5x5` hoặc `--grid abc` bị reject ngay với error message rõ ràng; process exit code khác 0.
4. Web: Dropdown "Grid size" hiển thị 4 options (Off / 2×2 / 3×3 / 4×4) trong form, cạnh các control hiện tại.
5. Web: Chọn "3×3" rồi submit → backend nhận `grid_size=3x3`, parse thành `grid_n=3`, `translate_with_grid()` được gọi với `grid_n=3`; response trả về ảnh hợp lệ (không HTTP 500).

---

## Phase 3: End-to-End Validation

**Goal:** Xác nhận toàn bộ pipeline hoạt động đúng trên các ảnh game UI thực tế — cả web lẫn CLI, mọi grid size — và đảm bảo không có regression với mode Off/1×1.
**Requirements:** *(tất cả 10 v1 requirements đã implement — phase này validate, không thêm code mới)*
**UI hint:** no

### Success Criteria

1. Dịch cùng một ảnh game UI phức tạp với Off vs 2×2 vs 3×3: kết quả 2×2 và 3×3 dịch được nhiều text hơn hoặc bằng Off, không có ảnh nào bị lỗi khi Off không lỗi.
2. Web: Batch 3 ảnh với grid 2×2 — cả 3 ảnh trả về thành công, side-by-side comparison UI hiển thị đúng, không có partial result (ảnh thiếu tile).
3. CLI: Batch thư mục 5 ảnh với `--grid 2x2` — tất cả 5 file output tồn tại, kích thước giống ảnh gốc ±1px.
4. Ảnh PNG (có alpha) xử lý qua grid mode không gây lỗi `OSError: cannot write mode RGBA as JPEG` ở bất kỳ tile nào.
5. Gọi `translate_with_grid()` với `grid_n=1` cho đúng số API call = 1; với `grid_n=2` = 4 calls; với `grid_n=3` = 9 calls (verify qua log/mock).

---

## Coverage Check

| Requirement | Phase |
|-------------|-------|
| GRID-01 | Phase 1 |
| GRID-02 | Phase 1 |
| GRID-03 | Phase 1 |
| GRID-04 | Phase 1 |
| GRID-05 | Phase 1 |
| GRID-06 | Phase 1 |
| GRID-07 | Phase 1 |
| CLI-01  | Phase 2 |
| WEB-01  | Phase 2 |
| WEB-02  | Phase 2 |

**v1 requirements mapped:** 10/10 ✓

---
*Created: 2026-03-29*
