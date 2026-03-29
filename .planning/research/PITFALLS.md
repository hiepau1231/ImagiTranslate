# PITFALLS: Tile-Based AI Image Translation

**Date:** 2026-03-29
**Scope:** Grid-splitting → per-tile Gemini → stitch for ImagiTranslate
**Model:** `gemini-3.1-flash-image-preview` (re-renders the whole tile, not OCR+overlay)
**Consumer:** Roadmap / planning — prevent mistakes before implementation begins

---

## P1 — Text Cut at Tile Boundaries

**What goes wrong:**
A word, character, or UI label straddles the cut line between two tiles. The left tile sees half a word; the right tile sees the other half. Gemini re-renders each tile independently, so it either invents a plausible-but-wrong completion for each half, drops the fragment entirely, or (worst case) duplicates it. The stitched result contains garbled, doubled, or missing text near every seam.

**Warning signs:**
- Words in the final image that end abruptly at a tile edge
- Unexpected line breaks that don't exist in the source image
- Characters repeated once on each side of a visible seam

**Prevention strategy:**
- **Overlap tiles** by a fixed margin (e.g., 64–128 px). Each tile receives its own content plus a "bleed" strip from its neighbours. After translation, the bleed strips are discarded and only the authoritative centre region is used in the stitch.
- Choose tile boundaries deliberately: cut on visually "empty" regions (gutters, sky, solid-colour bars) rather than through dense text blocks. This requires a lightweight pre-scan step.
- Alternatively, cap the grid size so tiles are large enough that the probability of any single text element crossing a boundary is low (see P5).

**Phase to address:** Grid-split design phase (before any tile API calls are made).

---

## P2 — Visual Seams at Tile Joins

**What goes wrong:**
Gemini is a generative model — it does not guarantee pixel-for-pixel reproduction of non-text areas. Even with an identical style prompt, colour tone, sharpness, JPEG compression artefacts, and background texture will differ subtly between tiles. When stitched at exact boundaries the discontinuities become visible as grid lines, especially on:
- Gradient backgrounds
- Blurred or bokeh areas
- Semi-transparent UI panels (alpha blending)
- Any texture that spans multiple tiles

**Warning signs:**
- A faint grid is visible in the output when zoomed in
- Colour temperature shifts between adjacent tiles
- Sharpness or grain differs noticeably at the cut

**Prevention strategy:**
- **Overlap + alpha-blending seam**: use the same overlap margin from P1, but instead of a hard cut, blend the overlapping strips with a linear alpha gradient (full opacity at tile centre, 0 at tile edge). PIL supports this via `Image.paste()` with an alpha mask.
- Include a reference colour patch in the prompt: send a small thumbnail of the full image alongside the tile so Gemini has global colour context ("match the overall colour palette of this reference").
- Post-process with Pillow's `ImageFilter.SMOOTH` or a narrow Gaussian along the seam line only — not the whole image.
- Keep tiles large (≥ 512 px after accounting for any upscaling). Small tiles exaggerate seam frequency.

**Phase to address:** Stitch implementation phase; also prompting phase.

---

## P3 — Gemini Inconsistent Style Between Tiles

**What goes wrong:**
`gemini-3.1-flash-image-preview` makes independent creative decisions for each API call. The same game UI sent as two separate tiles may come back with:
- Different font rendering (weight, anti-aliasing, letter-spacing)
- Different icon colouration or saturation
- Background re-interpreted differently (e.g., a sky gradient rendered warmer in one tile)
- Different text shadow or glow style

This is the tile equivalent of the known problem that Gemini occasionally changes visual style per image. With a grid, it happens with certainty on every image.

**Warning signs:**
- Icons look slightly different on the left vs. right tile
- Font appears bold in one tile and regular in another
- The final stitched image feels "collaged" rather than coherent

**Prevention strategy:**
- **Anchored style prompt**: include a precise description of the visual style extracted from the source image. Example suffix: `"Preserve exactly: flat vector icons, dark navy background #1a2030, white UI text with 1px drop shadow, no gradients."` The more specific, the more constrained the model.
- **Pass a small full-image thumbnail** as an additional context input alongside the tile. The model can use it as a global style reference. This is supported by the existing dual-image content list: `contents=[thumbnail, tile, prompt]`.
- Treat style consistency as a known limitation and document it: grid splitting helps text coverage but accepts a small visual consistency trade-off.
- Do not use very small tiles (e.g., 1×4 or 4×1 grids on a narrow strip) — the smaller the tile, the less context Gemini has to maintain style.

**Phase to address:** Prompting phase; architecture decision (thumbnail reference).

---

## P4 — API Rate Limit Multiplication

**What goes wrong:**
The current code makes 1 API call per image (with up to 3 retries = max 3 calls). With an NxN grid, each image now requires N² calls, each with its own retry budget:

```
Grid size   Calls/image (nominal)   Calls/image (max, all retries)
──────────  ─────────────────────   ──────────────────────────────
1×1         1                        3
2×2         4                       12
3×3         9                       27
4×4        16                       48
```

For the web batch flow processing a folder of 20 images at 3×3:
- Nominal: 20 × 9 = **180 calls**
- Max with retries: 20 × 27 = **540 calls**

Gemini Flash free-tier quota is typically 15 requests/minute. At 3×3, a single image takes 9 sequential calls; if each takes ~5 s, that is **45 seconds per image** before accounting for rate-limit backoffs.

If a 429 "Too Many Requests" hits mid-tile, the current retry logic (2s → 4s backoff) is not tuned for quota exhaustion — it retries 3 times and gives up, leaving a hole in the stitched result.

**Warning signs:**
- 429 HTTP errors appearing in logs that never appeared with single-image calls
- Processing time growing super-linearly with grid size
- Partially translated images (some tiles succeeded, some failed)

**Prevention strategy:**
- **Rate-limit-aware delay between tile calls**: add a configurable `TILE_DELAY_SECONDS` (default: 4 s) between each tile call, separate from the retry delay. This fits the current sequential design philosophy.
- **Detect 429 separately from other errors**: catch `google.api_core.exceptions.ResourceExhausted` or check for `429` in the exception message. On 429, wait longer (e.g., 60 s) before retrying rather than the standard 2s/4s backoff.
- **Fail the whole image gracefully if any tile fails** after all retries — return the original untranslated image rather than a partial stitch. Partial stitches are worse than no translation.
- Expose `GRID_SIZE` as a user-configurable parameter (not hardcoded) so users on quota-constrained keys can choose 2×2 instead of 3×3.
- Document the call-count math in the UI: "3×3 grid = 9 API calls per image."

**Phase to address:** API integration phase; configuration design.

---

## P5 — Tile Too Small: Loss of Translation Context

**What goes wrong:**
When a tile is very small (e.g., a 4×4 grid on a 512×512 image = 128×128 px tiles), each tile contains so little context that Gemini cannot reliably:
- Identify what language the text is in (auto-detect fails on 1–2 characters)
- Decide how to translate abbreviations or acronyms (needs surrounding UI context)
- Maintain grammatical form (e.g., gendered nouns in target language require sentence context)
- Avoid hallucinating text that was not there

Additionally, the current `UPSCALE_FACTOR = 2` means a 128 px tile becomes 256 px before being sent — still small for a model built for full-screen UI screenshots.

**Warning signs:**
- Translations that are grammatically wrong or nonsensical
- Text that appears in the output but was not in the source tile
- Untranslated text (Gemini couldn't detect the language from so few characters)
- Tiles that come back as pure text responses instead of images (model refuses to re-render)

**Prevention strategy:**
- **Enforce a minimum tile dimension**: 256 px × 256 px *after* upscaling is a reasonable floor. At `UPSCALE_FACTOR = 2`, the source tile must be ≥ 128 px on each side before splitting.
- For a 512×512 source image, this means the maximum useful grid is 2×2 (not 4×4).
- For a 1024×768 source, 3×3 is feasible (tile = ~341×256 px, upscaled = ~682×512 px).
- Compute the valid grid size range dynamically from image dimensions rather than accepting any NxN from the user.
- Formula: `max_n = floor(min(w, h) / MIN_TILE_PX)` — cap grid to this.

**Phase to address:** Grid-split design phase; input validation.

---

## P6 — Tile Too Large: Same Problem as Before

**What goes wrong:**
If the grid is 1×1 (or a very coarse split like 2×2 on a huge image), tiles are large enough that the original problem recurs — Gemini fails to attend to every small text element in a dense UI, which is the whole reason for splitting in the first place. Additionally, the existing `UPSCALE_MAX_DIMENSION = 3000` cap means large tiles may not benefit from the upscale at all:
- A 1500×1000 image split 2×2 → tiles of 750×500 → upscaled to 1500×1000 (just fits under 3000)
- A 2000×1500 image split 2×2 → tiles of 1000×750 → upscaled to 2000×1500 (already > limit on one axis if we tried 3×) → upscale silently skipped

**Warning signs:**
- Missed translations in dense regions despite grid splitting
- No improvement over the baseline single-image approach

**Prevention strategy:**
- The sweet spot for this model appears to be tiles in the 400–800 px range (pre-upscale). That region gives Gemini enough context to understand the UI while being small enough to attend to every element.
- For very large images (e.g., 4K screenshots), a 4×4 or even 5×5 grid may be required.
- Do not let `UPSCALE_MAX_DIMENSION` silently suppress the upscale for large tiles — either log a warning or scale the upscale factor down proportionally so the tile always hits a target pixel budget.

**Phase to address:** Grid-split design phase; per-tile upscale logic.

---

## P7 — RGBA / Format Issues Per Tile

**What goes wrong:**
The existing RGBA→RGB asymmetry (CONCERNS.md §3) compounds with tiling:
- `app.py` converts RGBA→RGB on the **full image** input before tiling. If conversion happens after splitting, tiles cropped from an RGBA image retain the alpha channel, but mode is inconsistent across tiles depending on crop region.
- If tiling happens before mode conversion, some tiles may have transparent padding (crop regions that fall outside the image boundary when overlap extends past edges) and others won't.
- Edge tiles at the right/bottom of an image that is not evenly divisible by N need padding. If that padding is transparent (mode `RGBA`) and then saved as JPEG for the response, PIL raises an error: `OSError: cannot write mode RGBA as JPEG`.
- The CLI does RGBA→RGB conversion on the **output** tile — but the output format depends on the original file extension, creating 4 different code paths (app×input vs CLI×output × JPEG vs PNG).

**Warning signs:**
- `OSError: cannot write mode RGBA as JPEG` in Flask logs
- Edge tiles (row/column N-1) failing while centre tiles succeed
- Inconsistent alpha in PNG output (some tiles transparent-padded, others not)

**Prevention strategy:**
- **Normalise mode before splitting**: convert RGBA→RGB (or RGBA→RGBA with white matte) on the full image once, before any tile logic. This is consistent with the existing `app.py` approach and ensures all tiles share the same mode.
- **Pad to a multiple of tile size** using a solid colour fill (not transparent) before splitting, then crop back to `orig_size` after stitching.
- Unit-test specifically with PNG files that have alpha channels and images whose dimensions are not multiples of the chosen grid size.

**Phase to address:** Tile splitting implementation; extend existing RGBA handling.

---

## P8 — Memory Pressure from Holding All Tiles In-Flight

**What goes wrong:**
A naïve implementation collects all N² translated tile images into a list before stitching. With a large image at 3×3:
- Source: 2000×1500 px → upscaled to 3000×2250 (hits cap) → split 3×3 = tiles of 1000×750
- Each tile sent to Gemini; response image also ~1000×750 JPEG decoded to RGB array
- 9 response tiles × 1000×750×3 bytes = 9 × 2.25 MB ≈ **20 MB in memory simultaneously**
- Plus the original image, the upscaled version, and the final stitched canvas
- Total peak: ~60–80 MB for a single 10 MB input image

For the Flask web server handling concurrent users or a CLI batch of 50 images, this accumulates quickly.

**Warning signs:**
- `MemoryError` or `Killed` (OOM) on the server
- Swap usage spiking during batch processing
- Slower processing over time (memory pressure causing GC pressure)

**Prevention strategy:**
- **Stitch incrementally**: paste each tile into the output canvas immediately after receiving it and discard the tile object. Do not accumulate all tiles first.
- Explicitly call `del tile_img` and `gc.collect()` after each paste.
- The output canvas itself can be pre-allocated: `canvas = Image.new('RGB', orig_size)`. This is a single fixed allocation, not N² tile allocations.
- For the web path, consider a per-request memory budget guard: reject grid sizes that would exceed a threshold (e.g., estimated peak > 100 MB).

**Phase to address:** Stitch implementation phase.

---

## P9 — Gemini Returns Text Response Instead of Image for a Tile

**What goes wrong:**
The model occasionally refuses to re-render a tile, returning a text explanation instead of an image. The existing code already handles this (the `has_image` check + retry loop). However, with tiling, this failure is more frequent because:
- Small tiles may look like "just a background" with no text — Gemini may respond with "No text found to translate" instead of re-rendering
- Edge tiles with heavy transparent padding or solid-colour fill may trigger safety filters or confuse the model
- The model may return text on attempt 1, then an image on attempt 2 — the retry loop handles this, but the 2s/4s delay is now multiplied by N²

A single text-response failure within a tile grid currently has no fallback — the implementation would need to decide: use the original (untranslated) tile? Retry with a different prompt? Abort the whole image?

**Warning signs:**
- `Exception("Phản hồi không chứa ảnh")` appearing repeatedly in logs
- Specific tiles always failing (usually blank or very simple edge tiles)
- Retry exhaustion happening more frequently after grid splitting than before

**Prevention strategy:**
- **Fallback to original tile on final failure**: if all retries are exhausted for a tile, paste the original (untranslated) source tile into the canvas. The image is partially translated rather than broken.
- For tiles that are visually blank (variance below a threshold), skip the API call entirely and paste the source tile directly. This also saves API quota.
- Add a tile-level prompt suffix: `"If there is no text to translate, reproduce the image exactly as provided."` This converts "no text" refusals into valid image responses.
- Log which tiles fell back to source so the user is informed.

**Phase to address:** Tile API call implementation; error handling design.

---

## P10 — Output Size Mismatch After Stitch

**What goes wrong:**
The existing code normalises Gemini output to `orig_size` after each call:
```python
result_pil_img = result_pil_img.resize(orig_size, Image.LANCZOS)
```
With tiles, each tile's Gemini output must be resized to the *tile's* expected dimensions (not `orig_size`). If this resize is omitted or uses the wrong target size:
- Tiles are pasted at wrong coordinates → image tears
- Final canvas dimensions are wrong → browser/PIL raises size mismatch errors

Additionally, the upscale step (`UPSCALE_FACTOR = 2`) applies to the full image pre-split. If tiles are split from the *upscaled* image but the stitch canvas is `orig_size`, each tile's expected paste coordinates must be computed in upscaled space then mapped back — a fencepost error waiting to happen.

**Warning signs:**
- Tiles visibly squashed or stretched in the output
- Tile coordinates off by exactly 2× (upscale factor leak)
- Final image dimensions not matching the source

**Prevention strategy:**
- **Define a single coordinate space** and stick to it. Recommendation: split in *original* pixel space (before upscaling), upscale each tile individually before sending to Gemini, resize each response back to the *tile's original dimensions*, then stitch in original space.
  - Source tile crop box: `(x, y, x+tile_w, y+tile_h)` in original pixels
  - Upscale tile: `tile.resize((tile_w * FACTOR, tile_h * FACTOR), LANCZOS)`
  - Resize response: `response_tile.resize((tile_w, tile_h), LANCZOS)`
  - Paste at: `canvas.paste(response_tile, (x, y))`
- Verify canvas dimensions equal `orig_size` after final stitch with an assertion.
- Write a unit test with a known 400×300 image and 2×2 grid, verifying output is exactly 400×300.

**Phase to address:** Tile splitting and stitching implementation; coordinate system design.

---

## Summary Table

| # | Pitfall | Severity | Phase to Address |
|---|---------|----------|-----------------|
| P1 | Text cut at tile boundaries | HIGH | Grid-split design |
| P2 | Visual seams at tile joins | HIGH | Stitch + prompting |
| P3 | Inconsistent Gemini style between tiles | HIGH | Prompting + architecture |
| P4 | API rate limit multiplication | HIGH | API integration |
| P5 | Tile too small → context loss | MEDIUM | Grid-split design |
| P6 | Tile too large → same problem as before | MEDIUM | Grid-split design |
| P7 | RGBA/format issues per tile | MEDIUM | Tile splitting impl |
| P8 | Memory pressure from holding all tiles | MEDIUM | Stitch implementation |
| P9 | Gemini returns text response for a tile | MEDIUM | Error handling design |
| P10 | Output size mismatch after stitch | HIGH | Coordinate system design |

---

## Rate Limit Reference: Worst-Case Call Budget

```
Grid    Tiles   Max calls (×3 retries)   Time @ 5s/call (sequential)
──────  ──────  ──────────────────────   ───────────────────────────
2×2       4        12                    60 s / image
3×3       9        27                   135 s / image
4×4      16        48                   240 s / image

Batch of 20 images at 3×3 (nominal, no retries):
  20 × 9 calls × 5 s = 900 s = 15 minutes

Free tier (15 req/min) with TILE_DELAY_SECONDS = 4:
  9 tiles × 4 s gap = 36 s minimum inter-tile delay per image
  Effective throughput: ~1.6 images/minute at 3×3
```

Key implication: **grid size is a user-facing UX parameter**, not just an internal constant. Users should understand the time/quality trade-off before choosing it.

---

*References: CLAUDE.md (architecture + constants), CONCERNS.md (existing technical debt), PROJECT.md (requirements + constraints)*
