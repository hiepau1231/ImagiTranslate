# ImagiTranslate

## What This Is

ImagiTranslate là công cụ dịch thuật hình ảnh dùng Gemini AI để re-render lại ảnh với text đã được dịch — không phải OCR+overlay thông thường. Có hai entry point: web app (Flask) để dịch từng ảnh qua browser, và CLI tool để batch dịch cả thư mục. Mục tiêu chính là dịch ảnh game UI/screenshot đang bị bỏ sót chữ do Gemini không xử lý được hết text trong ảnh phức tạp.

## Core Value

Mọi chữ trong ảnh phải được dịch — không bỏ sót, đặc biệt với game UI có nhiều text nhỏ, icon label, và các phần tử UI dày đặc.

## Requirements

### Validated

- [x] **Grid Module Core complete** — `grid_translator.py` created with full split/translate/stitch pipeline; constants centralized; `grid_n=1` fast path verified. *(Validated in Phase 1: Grid Module Core)*

### Active

- [ ] Chia ảnh thành grid nhỏ trước khi gửi Gemini để tăng độ phủ text
- [ ] Ráp lại các phần đã dịch thành ảnh hoàn chỉnh tự động (seamless stitch)
- [ ] Áp dụng grid processing cho cả web app và CLI tool
- [ ] Kết quả cuối cùng trông giống ảnh gốc về layout, màu sắc, style

### Out of Scope

- OCR riêng biệt (Tesseract/EasyOCR) — không dùng vì Gemini đã xử lý text tốt, chỉ cần chia nhỏ vùng xử lý
- Manual review từng tile — tự động hoàn toàn
- Real-time parallel API calls — giữ sequential do rate limit

## Context

**Vấn đề hiện tại:** Gemini đôi khi bỏ sót text trong ảnh game UI phức tạp (~1/3 số ảnh gặp vấn đề). Prompt hiện tại đã có `EVERY SINGLE piece of text` và `Do NOT skip` nhưng vẫn không đủ.

**Nguyên nhân có thể:** Ảnh game UI có text nhỏ, dày đặc, nhiều layer — khi gửi cả ảnh lớn, Gemini có thể không "chú ý" đủ đến từng góc nhỏ.

**Giải pháp:** Chia ảnh thành grid (ví dụ 2x2, 3x3), dịch từng tile, ráp lại. Mỗi tile nhỏ hơn → Gemini tập trung hơn → ít bỏ sót hơn.

**Tech stack hiện tại:**
- Python 3.x + Flask 3.0+
- Pillow cho image processing
- google-genai 0.2.2+ với model `gemini-3.1-flash-image-preview`
- Retry logic: 3 lần, exponential backoff 2s→4s

**Codebase notes:**
- Có sự bất đối xứng RGBA conversion giữa app.py (convert input) và image_translator.py (convert output)
- Dual response format handling đã có sẵn (part.image vs part.inline_data)
- Sequential processing là có chủ ý (Flask dev server + rate limit)

## Constraints

- **Model**: Dùng `gemini-3.1-flash-image-preview` — không thay đổi model
- **Processing**: Sequential (không parallel) — Flask dev server + API rate limit
- **Output**: Web luôn xuất JPEG; CLI giữ nguyên extension gốc
- **File size**: Max 10MB/file

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Grid splitting + auto-stitch | Giải quyết bỏ sót text do ảnh quá phức tạp | — Pending |
| Áp dụng cả web + CLI | Đảm bảo tính nhất quán giữa 2 entry point | — Pending |
| Tự động ráp lại (không manual review tile) | UX đơn giản, user không cần thao tác thêm | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-29 after Phase 1 (Grid Module Core) completion*
