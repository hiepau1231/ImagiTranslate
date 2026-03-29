# Phase 1: Grid Module Core - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-29
**Phase:** 01-grid-module-core
**Areas discussed:** Coordinate space

---

## Coordinate Space

| Option | Description | Selected |
|--------|-------------|----------|
| Upscaled space (caller upscales trước) | Nhận ảnh đã upscale từ caller, split trong upscaled space, stitch xong trả về upscaled size. Caller vẫn resize về orig_size như hiện tại. Grid module đơn giản hơn, caller contract không đổi. | ✓ |
| Original space (module tự upscale từng tile) | Nhận ảnh original, tự upscale từng tile trước khi gửi Gemini, resize tile về original tile dims sau, stitch trong original space. Grid module kiểm soát toàn bộ pipeline. | |

**User's choice:** Upscaled space (caller upscales trước)
**Notes:** Giữ nguyên caller contract — upscale trước khi gọi, resize sau khi nhận về.

---

## Claude's Discretion

- Constants ownership: định nghĩa trong `grid_translator.py`, import vào 2 entry points
- 1×1 fallback: skip split/stitch, gọi thẳng `_translate_single_tile()`
- Tile failure behavior: raise Exception, propagate lên caller (no partial stitch)
- Stitch method: hard-paste (defer blending to v2)

## Deferred Ideas

- Overlap/padding v2
- Feather blending v2
- Style-anchor prompt v2
- Per-tile progress v2
