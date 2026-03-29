---
plan: 03-01
status: done
date: "2026-03-29"
commit: 0e75876
files_created:
  - test_grid.py
files_modified: []
---

# Summary: Plan 03-01 — Create `test_grid.py` End-to-End Validation Script

## What Was Done

Tao `test_grid.py` tai project root theo pattern cua `test_api.py`. Script covers tat ca 5 SC cua Phase 3 voi 2 tier:

**Tier 1 — Offline (no API key):**
- SC-5: Mock `_translate_single_tile` via `unittest.mock.patch`; verify grid_n=1→1 call, grid_n=2→4 calls, grid_n=3→9 calls via `call_count`; verify output size == input size
- SC-4: RGBA (mode='RGBA') qua `translate_with_grid()` voi grid_n=1,2,3; simulate web path (RGBA→RGB convert + JPEG save, no OSError); simulate CLI path (PNG save, no error)

**Tier 2 — Live API (needs GEMINI_API_KEY):**
- SC-1: Grid comparison Off vs 2×2 vs 3×3 tren 1 anh game UI thuc tu `test_images/`
- SC-2: Batch 3 images voi grid 2×2 — ca 3 phai thanh cong, output size == input size
- SC-3: Goi `translate_images()` truc tiep voi grid_n=2 tren 5 anh; verify output files ton tai va size khop +-1px

## Verification Results

```
SC-5: PASS  (all 6 sub-checks: 3x call_count + 3x size match)
SC-4: PASS  (all 9 sub-checks: 3x translate + 3x JPEG save + 3x PNG save)
SC-1: SKIP  (no GEMINI_API_KEY — graceful skip, no crash)
SC-2: SKIP  (no GEMINI_API_KEY — graceful skip, no crash)
SC-3: SKIP  (no GEMINI_API_KEY — graceful skip, no crash)
Exit code: 0
```

All 20 acceptance criteria verified via grep + syntax check + offline test run.

## Key Design Decisions

- SC-5 patches `grid_translator._translate_single_tile` (not `grid_translator.translate_with_grid`) — verifies tile dispatch count, not just top-level call
- SC-4 mocks tile translation but tests real JPEG/PNG save paths — catches RGBA→JPEG OSError without API credits
- SC-2 falls back to synthetic images when `test_images/` has < 3 real images — still validates function behavior
- SC-3 falls back to 5 synthetic images and calls `translate_images()` directly (not subprocess) — avoids subprocess complexity, tests the actual function
- Graceful skip for SC-1/2/3: print `[!]` warning, return `None` (not `False`) — exit code 0, not 1

## Files

| File | Action | Notes |
|------|--------|-------|
| `test_grid.py` | Created | 424 lines; no new dependencies (stdlib + PIL + google.genai only) |
