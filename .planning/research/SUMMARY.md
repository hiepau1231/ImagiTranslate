# Research Summary: Grid-Splitting Feature
*Synthesized: 2026-03-29 — Read this before opening ROADMAP.md*

---

## 1. Stack Recommendation

**Use pure Pillow. Add one new file. Touch zero dependencies.**

- `Image.crop()` / `Image.paste()` / `Image.new()` cover everything — all in Pillow ≥ 10.2.0, already in `requirements.txt`.
- NumPy is already a transitive Pillow dependency; use it only for the gradient feather mask (`np.full` / `np.minimum`). No `requirements.txt` change needed.
- **Reject OpenCV, scikit-image, or any diffusion/inpainting library.** Game UI has flat, geometric structure — a 16–24 px feather mask at seams is sufficient.

**Key decision — clean cuts, not overlap tiles:**
Gemini *re-renders* the whole tile (not OCR + overlay), so sending overlapping source pixels does not guarantee matching output in the overlap zone. Adjacent tiles will disagree visually in overlap regions. Use clean crop boundaries with feathered blending at seams instead.

---

## 2. Table Stakes — Must-Haves for v1

These five are binary; missing any one means the feature does not function.

| # | Feature | Implementation note |
|---|---------|---------------------|
| **TS-1** | Fixed grid size selection (2×2, 3×3, 4×4) | Web: dropdown; CLI: `--grid 2x2` flag |
| **TS-2** | Per-tile Gemini call reusing existing retry logic | Extract retry block → `_translate_single_tile()` helper |
| **TS-3** | Hard-paste stitch (resize each tile to slot dims before paste) | Gemini does not preserve tile dimensions — always resize before paste |
| **TS-4** | Tile failure = whole image failure (no partial stitches) | Partial result is worse than none; surface same HTTP 500 / file-skip as today |
| **TS-5** | Grid mode opt-in, off by default | `if grid_enabled:` branch — existing behavior 100% unchanged when disabled |

**Not v1 (defer):** overlap/padding between tiles, blend stitching, adaptive grid, grid preview overlay, per-tile SSE progress, parallel calls (never — rate limits).

---

## 3. Architecture Approach

**New module: `grid_translator.py`** — grid logic belongs in neither entry-point file.

```
app.py  ──────┐
              ├──► grid_translator.translate_with_grid(image, client, prompt, grid_n)
image_         │         ├─ _split_tiles()          ← PIL crop, row-major
translator.py ─┘         ├─ _translate_single_tile() ← extracted retry+parse block
                          └─ _stitch_tiles()          ← PIL paste, incremental
```

**Data flow (both entry points):**

```
open image → save orig_size
  → [RGBA→RGB if JPEG]       ← entry-point responsibility, UNCHANGED
  → [upscale 2×]             ← entry-point responsibility, UNCHANGED
  → translate_with_grid()    ← NEW: replaces the inline generate_content block
  → result.resize(orig_size) ← entry-point responsibility, UNCHANGED
  → encode/save              ← entry-point responsibility, UNCHANGED
```

The grid module receives an already-upscaled image and returns a result at that same size. The caller normalizes to `orig_size` exactly as it does today. **No external contract changes** — Flask route and CLI function signatures are untouched.

**Constants** (`GEMINI_MODEL`, `MAX_RETRIES`, `RETRY_DELAY_SECONDS`) move to `grid_translator.py` as the single source of truth; both entry points import from it.

**Recommended build order:**
1. Extract `_translate_single_tile()` — unifies duplicated retry logic, zero behavior change, validates the extraction.
2. Add `_split_tiles()` + `_stitch_tiles()` — verify round-trip is pixel-perfect with no API call.
3. Wire `translate_with_grid()` loop — replace inline block in both entry points.
4. End-to-end test (1×1 grid must match current output exactly).
5. Expose `grid_n` in web UI + CLI flag.

---

## 4. Top Pitfalls to Watch

### P1 — Text cut at tile boundaries *(HIGH)*
A label straddling a seam gets split across two independent Gemini calls → garbled or dropped text at every seam. **Mitigation for v1:** default 2×2 grid keeps tiles large (context-rich), minimising the chance any single text element crosses a boundary. Track as v2 item: 64 px overlap with centre-region stitching.

### P2 / P3 — Visual seams + style inconsistency between tiles *(HIGH)*
Gemini makes independent creative decisions per call — colour temperature, font weight, background texture can all drift. Hard-paste produces visible grid lines on gradients. **Mitigation:** apply 16–24 px feather mask at interior seams (Pillow mask paste); add style-anchor text to the prompt (`"Preserve: flat icons, dark navy #1a2030, white text..."`). Build hard-paste first, measure seam quality empirically before investing in blending.

### P4 — API rate limit multiplication *(HIGH)*
3×3 = 9 calls/image; with 3 retries each = 27 max. A batch of 20 images at 3×3 → up to 540 calls. Free tier is 15 req/min. **Mitigation:** add `TILE_DELAY_SECONDS` (default 4 s) between tiles; detect 429 separately and back off 60 s (not the standard 2/4 s); show call-count math in the UI ("3×3 = 9 calls, ~45 s").

### P10 — Output size mismatch after stitch *(HIGH)*
Confusing upscaled vs original coordinate space causes tile-coordinate off-by-2× bugs or final canvas at the wrong size. **Mitigation:** define one coordinate space and never mix. Recommended: split in *original* space → upscale each tile individually → resize each response back to original tile dims → stitch in original space. Add an assertion: `assert canvas.size == orig_size`.

### P7 — RGBA/format issues per tile *(MEDIUM)*
JPEG-destined RGBA tiles raise `OSError: cannot write mode RGBA as JPEG` at stitch time, especially for edge tiles. **Mitigation:** normalise mode on the full image *before* splitting (already done in `app.py`); ensure the stitch canvas is created with `tiles[0][0].mode` and all tiles are mode-converted before paste.

---

## 5. Recommended v1 Scope

**Build exactly this, in this order:**

1. **`grid_translator.py`** with `_translate_single_tile()`, `_split_tiles()`, `_stitch_tiles()`, and `translate_with_grid()`.
2. **Shared constants** imported into both entry points from `grid_translator.py`.
3. **CLI:** `--grid NxN` flag (default `1x1` = off); per-tile progress print ("Tile 2/4...").
4. **Web:** grid size dropdown (Off / 2×2 / 3×3 / 4×4); static warning text showing call count and estimated time.
5. **Default grid: 2×2** — halves linear tile dimension, quadruples text-attention density, stays well within rate limits and Gemini context window.

**Explicitly out of v1:** overlap padding, blend stitching, adaptive grid, SSE per-tile progress, grid preview overlay, per-tile result caching.

**Explicit never:** parallel tile calls, per-tile manual review UI, non-rectangular tiles.

---

*Source files: STACK.md · FEATURES.md · ARCHITECTURE.md · PITFALLS.md*
