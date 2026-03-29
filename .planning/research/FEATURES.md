# Grid-Splitting Feature Analysis

**Date:** 2026-03-29
**Scope:** Features needed for grid-based image tiling in ImagiTranslate
**Context:** Gemini misses text in ~1/3 of complex game UI images. Fix: split → translate each tile → stitch back.

---

## What We're Building

A pre/post processing wrapper around the existing `translate_image()` call. The Gemini call itself does not change — we just feed it smaller pieces and reassemble the output.

```
Image
  ↓
[Split into N×M tiles]        ← NEW
  ↓
For each tile:
  └─ [Existing Gemini call]   ← UNCHANGED
  ↓
[Stitch tiles back together]  ← NEW
  ↓
Output
```

This scoping is important: it means most existing complexity (retry logic, dual response format, RGBA handling, upscale, API key management) is inherited for free.

---

## Table Stakes — Must Have for This to Work at All

These are binary: missing any one = the feature does not function.

---

### TS-1: Fixed Grid Size Selection
**What:** User can choose a grid (2×2, 3×3, 2×3, etc.). The image is divided into that many equal tiles.

**Why table stakes:** Without this, there is nothing to split into.

**Implementation sketch:**
- `split_into_tiles(image, cols, rows) → list[Image]`
- Tile width = `ceil(image.width / cols)`, tile height = `ceil(image.height / rows)`
- Edge tiles may be smaller if image dimensions not evenly divisible — handle cleanly
- Web: radio buttons or dropdown (2×2 / 3×3 / 4×4 / Off)
- CLI: `--grid 2x2` argument (parse as `cols×rows`)

**Complexity:** Low. Pure Pillow: `image.crop((x, y, x+w, y+h))`.

**Codebase note:** The existing `UPSCALE_FACTOR` logic already runs before the Gemini call. Grid splitting slots in at the same point — after upscaling, before the API call.

---

### TS-2: Per-Tile Gemini Call with Existing Retry Logic
**What:** Each tile is passed through the existing `generate_content` + retry wrapper individually, sequentially.

**Why table stakes:** Without this, tiles are never translated.

**Implementation sketch:**
- Extract the current retry block in `translate_image()` into a `translate_tile(client, tile_image, prompt) → Image` helper
- The grid path calls this helper once per tile
- The non-grid path calls it once on the whole image (same as today)

**Complexity:** Low. Pure refactoring — no new logic.

**Codebase note:** Sequential is already the design (Flask dev server + rate limits). With a 3×3 grid, that's 9 API calls per image instead of 1. The rate-limit patience is already there; it just costs more time and quota.

---

### TS-3: Basic Hard-Paste Stitch
**What:** Translated tiles are pasted back into a blank canvas at their original pixel coordinates to reconstruct the full image.

**Why table stakes:** Without stitching, we have N separate tile images, not a usable result.

**Implementation sketch:**
- `stitch_tiles(tiles, cols, rows, orig_size) → Image`
- Create `Image.new('RGB', orig_size)`
- `canvas.paste(tile, (col * tile_w, row * tile_h))` for each tile
- Resize each tile back to its original tile dimensions before pasting (Gemini may return a different size — same problem as today, already handled per-tile by normalizing to tile's `orig_size`)

**Complexity:** Low. Pillow paste is trivial.

**Critical detail:** Each tile must be normalized to its expected pixel dimensions before paste — not to the whole image size. This is a subtle difference from the current single-image normalize.

---

### TS-4: Tile Failure = Per-Image Failure (Not Silent Skip)
**What:** If any tile fails after all retries, the entire image is considered failed. The original image (untranslated) is returned or an error is surfaced.

**Why table stakes:** A partial stitch — some tiles translated, some blank or missing — is worse than no translation at all. A corrupted-looking image with half the text translated and half missing creates confusion.

**Options:**
- **Option A (v1 recommendation):** Fail the whole image — surface error to user, same as today's single-image failure
- Option B: Fall back to non-grid translation on per-image failure (adds complexity)
- Option C: Fill failed tiles with original image pixels (requires tracking which tiles failed)

**Complexity:** Low for Option A. Medium for B or C.

**Web behavior:** Return HTTP 500 with error, same as today.
**CLI behavior:** Print failure, skip file, continue — same as today.

---

### TS-5: Grid Mode is Opt-In, Off by Default
**What:** Grid is only activated when the user explicitly enables it. Default behavior (no grid) is completely unchanged.

**Why table stakes:** This is a safety valve. Grid mode is 3–9× more expensive in API calls and time. Forcing it on all images would break existing use cases and exceed rate limits faster.

**Web:** "Grid splitting" toggle/checkbox, collapsed by default. Selecting a grid size enables it.
**CLI:** `--grid` flag is optional and defaults to `1x1` (i.e., no grid).

**Complexity:** Trivial — an `if grid_enabled:` branch wrapping the existing call.

---

## Differentiators — Quality Improvements, Not Required for v1

These make the feature noticeably better but are not required for correctness.

---

### D-1: Overlap/Padding Between Tiles
**What:** Each tile is extracted with N pixels of overlap beyond its true boundary. After translation, only the non-overlapping center region is used in the stitch.

**Why it matters:** Text sitting exactly on a tile boundary gets cut in half. Gemini sees half a character and either drops it or mangles it. Overlap ensures border text is fully visible in at least one tile.

**How it works:**
```
Tile boundary:  |....tile A....|....tile B....|
With overlap:   |...tile A + →overlap←...|
                          |←overlap + ...tile B...|
When stitching: use only the non-overlap center of each tile
```

**Implementation:** Extract tile at `(x - overlap, y - overlap, x + w + overlap, y + h + overlap)`, clamp to image bounds. When stitching, paste at `(x, y)` and crop the `overlap` pixels from each edge of the tile result.

**Complexity:** Medium. Coordinate math is straightforward, but edge tiles (along image border) need special handling — they have overlap only on their interior edges, not at the image boundary.

**Recommended overlap:** 32–64px. Small enough to be negligible, large enough to contain most text elements.

**v1 verdict:** Nice-to-have. Start without it; add if border artifacts are visible in testing.

---

### D-2: Adaptive Grid Size
**What:** Instead of a fixed N×M grid, automatically pick grid dimensions based on image size and text density.

**Why it matters:** A 400×400 icon doesn't need a 3×3 grid. A 3840×2160 game screenshot might need 4×4. One-size-fits-all wastes API calls or under-splits.

**Heuristic options:**
- Based on pixel count: if `w*h > 1M`, use 2×2; if `> 4M`, use 3×3
- Based on file size: rough proxy for visual complexity
- Based on failed translation detection (retry with larger grid if text is missed) — but this requires a detection mechanism

**Complexity:** Medium for heuristic, High for adaptive retry loop. Auto-detection of "did Gemini miss text?" requires either a separate OCR pass or user feedback.

**v1 verdict:** Skip. Fixed manual grid is fine for v1. Users know their images better than a heuristic does.

---

### D-3: Blend Stitching (vs Hard-Paste)
**What:** At tile boundaries, apply a gradient blend between adjacent tiles instead of a hard pixel cut.

**Why it matters:** Gemini may render the same background region slightly differently in two adjacent tiles (slightly different color temperature, slight shading difference). A hard paste can produce visible seam lines.

**How it works:** Create a feathered mask at each boundary edge, alpha-composite adjacent tiles with `Image.alpha_composite()` or `numpy` weighted average.

**Complexity:** Medium-to-High. Pillow supports this but requires RGBA mode, which collides with the existing RGBA→RGB conversion logic. Would need careful ordering.

**Practical reality check:** Gemini's image output for UI/game screenshots is quite deterministic for non-text regions. Visible seams may not be a real problem in practice. Should be tested before building.

**v1 verdict:** Skip. Build with hard-paste; validate seam quality empirically. Only build blending if seams are actually visible.

---

### D-4: Progress Indication Per-Tile (Web)
**What:** During grid processing, show "Tile 3/9 — translating..." rather than the existing generic "Processing..." spinner.

**Why it matters:** A 3×3 grid on a large image can take 30–90 seconds (9 sequential API calls). Without progress feedback, the user thinks the app is frozen.

**Implementation:** Two options:
- **Simple (SSE/streaming):** Flask sends progress as Server-Sent Events; JS updates a progress bar
- **Simple (polling):** JS polls a `/status` endpoint every 2 seconds
- **Simplest (fake):** Show tile count in the UI upfront ("This will take ~N calls"), no per-tile update

**Complexity:** Low for the "fake estimate" approach. Medium for SSE. The simplest version is just updating the button label: "Translating tile 1/4..." using a JS counter that increments per fetch response.

**v1 verdict:** The existing web flow processes one image at a time and returns the whole result in one `/translate` response. With grid, this still works — the server does all 9 tiles internally before responding. User waits longer but sees the same one-response pattern. Text like "Grid mode: 9 calls, may take up to 90s" on the UI is enough for v1.

---

### D-5: CLI Progress Per-Tile
**What:** Print per-tile progress in the CLI batch tool.

**Example output:**
```
[*] Processing: game_ui.png (3×3 grid, 9 tiles)...
    [+] Tile 1/9 done
    [+] Tile 2/9 done
    ...
    [+] Stitched: output/game_ui.png
```

**Complexity:** Trivial. Already has per-file print statements; just add per-tile prints.

**v1 verdict:** Include. Trivial effort, meaningfully improves CLI UX for long batches.

---

### D-6: Grid Preview in Web UI
**What:** Show a visual overlay of the grid lines on the source image before translation begins, so the user can see how the image will be split.

**Why it matters:** Helps user choose the right grid — can see if a grid line will bisect an important text element.

**Complexity:** Medium. Requires canvas drawing in JS, or server-side Pillow to draw grid overlay and return as preview.

**v1 verdict:** Skip. Nice UX but not essential for correctness. Add post-v1.

---

## Anti-Features — Deliberately NOT Building in v1

These are excluded with explicit reasoning. Revisit only if a specific need emerges.

---

### AF-1: Parallel Tile Processing
**Do not build.** Sequential is a deliberate design constraint (rate limits, Flask dev server). With a 3×3 grid, parallel would mean 9 simultaneous Gemini requests — guaranteed rate-limit failures. The existing sequential design handles this correctly at the cost of time.

**Revisit when:** Moving to a production WSGI server + confirmed higher rate limits.

---

### AF-2: Per-Tile Manual Review UI
**Do not build.** PROJECT.md explicitly rules out "manual review of individual tiles." Auto-stitch is the design. Adding per-tile review turns a batch tool into a labeling tool — completely different product.

---

### AF-3: Smart Text-Detection to Choose Grid Size
**Do not build in v1.** Detecting whether Gemini missed text requires either a second Gemini pass (expensive) or a separate OCR library (Tesseract/EasyOCR — explicitly out of scope per PROJECT.md). The user selects grid size manually.

---

### AF-4: Different Grid Sizes Per-Image in a Batch
**Do not build in v1.** The CLI batch tool applies one grid setting to all images in a directory. Per-image configuration would require a manifest/sidecar file system — out of scope for the initial implementation.

---

### AF-5: Non-Rectangular Tiles (Irregular Region Splitting)
**Do not build.** Splitting by content-aware regions (e.g., segmenting by UI panels) requires layout detection. The value is unclear and complexity is very high. Rectangular grid is well-understood and good enough.

---

### AF-6: Tile Caching / Partial Re-Translation
**Do not build in v1.** If one tile fails, the user must re-run the entire image. Caching successful tiles to avoid re-translating them is a meaningful optimization for large grids, but adds state management complexity. Scope it to v2 if users complain about retry cost.

---

## Interaction with Existing Code

These specific intersections with the current codebase need explicit handling:

---

### Upscale Logic Interaction
The current code upscales the full image 2× before sending to Gemini (`UPSCALE_FACTOR = 2`). With grid splitting, upscaling should happen **before** splitting, so each tile is already upscaled when sent.

**Current flow:** `open image → upscale → API call`
**New flow:** `open image → upscale → split → API call per tile → stitch → downscale to orig_size`

The downscale-to-orig-size step must now happen on the **stitched result**, not on individual tiles — otherwise tile dimensions won't align at stitch time.

**Risk:** Medium. This reshuffles the upscale/normalize ordering. The existing `orig_size` tracking must be preserved correctly.

---

### RGBA→RGB Conversion Interaction
The current asymmetry (web: convert input; CLI: convert output) must be handled carefully:

- **Web:** Convert input RGBA→RGB before upscale (before splitting). Each tile is then already RGB. No change to conversion logic needed.
- **CLI:** Currently converts RGBA→RGB on output (after Gemini response). With grid, "output" is now each tile's response. Should convert each tile result before paste — the existing asymmetry is workable but should be applied per-tile consistently.

**Risk:** Low. Same logic applies, just called inside the tile loop instead of once.

---

### Output Format (Web Always JPEG)
Web always outputs JPEG. This applies to the final stitched image — no change. Individual tile images during processing can be held in memory as PIL Images (no format committed until final save).

---

### 10MB File Size Limit
Grid splitting does not change the input file size limit. The tiles are created server-side from already-uploaded images, so the 10MB limit applies to the original upload, not to tiles (which are always smaller).

**Note:** A 10MB PNG split into 9 tiles = ~1.1MB per tile on average. Well within Gemini's input limits.

---

### Rate Limit & Sequential Processing
A 3×3 grid = 9 API calls per image. Existing retry backoff (2s, 4s) applies per tile. A full retry cycle on one tile = up to 14 seconds (2+4+8s). In the worst case (all 9 tiles fail once then succeed), total extra wait = 9 × 2s = 18 additional seconds. Acceptable.

The sequential constraint means a single web request translating a 3×3 grid can take **well over a minute**. Flask's default request timeout may need review, but this is an operational concern, not a blocking implementation concern.

---

## v1 Scope Summary

| Feature | Include? | Complexity | Notes |
|---------|----------|------------|-------|
| Fixed grid selection (2×2, 3×3, 4×4) | YES | Low | Web UI + CLI flag |
| Per-tile Gemini call (sequential) | YES | Low | Refactor existing code |
| Hard-paste stitch | YES | Low | Pillow paste |
| Tile failure = image failure | YES | Low | Same error surface as today |
| Grid opt-in, off by default | YES | Trivial | `if grid:` branch |
| CLI per-tile progress prints | YES | Trivial | Already have per-file prints |
| Web "grid mode: N calls, may be slow" warning | YES | Trivial | Static UI text |
| Overlap/padding | NO — v2 | Medium | Test first, add if needed |
| Blend stitching | NO — v2 | Medium-High | Test first, add if visible seams |
| Adaptive grid size | NO | Medium-High | Users choose manually |
| Grid preview overlay | NO — v2 | Medium | Nice UX, not essential |
| Per-tile progress via SSE | NO — v2 | Medium | Static estimate text is enough |
| Parallel tile calls | NEVER v1 | N/A | Rate limit constraint |
| Per-tile manual review | NEVER | N/A | Out of scope, wrong product |

---

## Open Questions (To Resolve Before Implementation)

1. **Does the upscale still make sense per-tile?** A 2×2 grid tile of a 1000×1000 image is 500×500. Upscaled 2× = 1000×1000. This is probably fine and actually beneficial. But for a 4×4 grid of a small 400×400 image, each tile is 100×100 before upscale = 200×200 — still reasonable. No change needed, but confirm this is the intended behavior.

2. **What grid sizes should be offered?** 2×2, 3×3, 4×4 covers most cases. Is 2×3 or 3×2 (non-square) useful? For landscape/portrait game UIs, yes. But it adds UI complexity. Start with symmetric grids only.

3. **Should the non-grid path still use upscaling?** Yes — the upscale is independent of grid mode and helps regardless. Keep as-is.

4. **What is the real-world seam quality?** Cannot determine this without testing. Build hard-paste first, test with actual game UI images, then decide if blending is needed.

---

*Last updated: 2026-03-29*
