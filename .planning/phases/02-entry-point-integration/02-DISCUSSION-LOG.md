# Phase 2: Entry Point Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-29
**Phase:** 02-entry-point-integration
**Areas discussed:** CLI function signature

---

## Gray Areas Presented

| Area | Selected for Discussion |
|------|------------------------|
| CLI: Cách truyền grid_n vào translate_images() | ✓ |
| CLI: Validate --grid và error message | (Claude's discretion) |
| Web: Vị trí đặt dropdown Grid size | (Claude's discretion) |
| Web: Cách wire grid_size từ JS vào FormData | (Claude's discretion) |

---

## CLI: Cách truyền grid_n vào translate_images()

| Option | Description | Selected |
|--------|-------------|----------|
| Thêm grid_n=1 vào signature | `translate_images(input, output, source, target, grid_n=1)` — backward-compatible, đơn giản, dễ test | ✓ |
| Hàm wrapper mới, giữ hàm cũ nguyên | Tạo `translate_images_with_grid()` riêng biệt | |

**User's choice:** Thêm `grid_n=1` vào signature
**Notes:** Default=1 đảm bảo backward-compatible hoàn toàn.

---

## Claude's Discretion

- CLI validate: regex check format `NxN`, N trong [1,4], error message tiếng Việt + sys.exit(1)
- Web dropdown placement: trong `controls-section` sau target-lang, class `glass-input`, label `"Grid:"`
- Web FormData field name: `grid_size` (khớp pattern snake_case của `source_lang`, `target_lang`)
- Backend parse: `grid_size == 'off'` → `grid_n=1`; else `int(grid_size.split('x')[0])` → `grid_n`
- Import `translate_with_grid` thêm vào đầu cả hai entry point files

## Deferred Ideas

- Hint text "3×3 = 9 calls" trên dropdown → UX-02 (v2)
- Per-tile progress log → UX-01 (v2)
