# STACK.md — Grid-Split Image Translation

*Research date: 2026-03-29*
*Scope: Adding tile-based grid splitting to ImagiTranslate (Flask + Pillow + Gemini)*

---

## TL;DR Decision

**Pure Pillow. No additional libraries needed.**
Pillow 10.2+ (already in `requirements.txt`) has every primitive required for crop, paste, and gradient-mask blending. NumPy is only needed for the seam-blend gradient array — and it is already a transitive dependency of Pillow on most platforms. No new entries in `requirements.txt`.

---

## 1. Core Pillow APIs (exact signatures, Pillow 12.x stable)

### 1.1 Splitting — `Image.crop()`

```python
tile: Image.Image = image.crop(box: tuple[float, float, float, float])
# box = (left, upper, right, lower)  — pixel coordinates, exclusive on right/lower
```

- Returns a **new** Image object (does not modify the original).
- Operates on the pixel grid of `image.size` — coordinates must be ≤ width/height or Pillow will silently pad with black.
- Since Pillow 3.4.0 this is **eager**, not lazy.

**Clean 2×2 split of a 1280×720 image:**
```python
from PIL import Image

def split_grid(image: Image.Image, cols: int, rows: int) -> list[list[Image.Image]]:
    """Return a rows×cols 2-D list of tile Images."""
    img_w, img_h = image.size
    tile_w = img_w // cols
    tile_h = img_h // rows
    grid = []
    for row in range(rows):
        grid_row = []
        for col in range(cols):
            left   = col * tile_w
            upper  = row * tile_h
            right  = left + tile_w if col < cols - 1 else img_w   # last column absorbs remainder
            lower  = upper + tile_h if row < rows - 1 else img_h  # last row absorbs remainder
            grid_row.append(image.crop((left, upper, right, lower)))
        grid.append(grid_row)
    return grid
```

> The "last tile absorbs remainder" trick prevents a 1–2 px gap when image dimensions are not perfectly divisible by the grid count.

---

### 1.2 Stitching — `Image.new()` + `Image.paste()`

```python
canvas: Image.Image = Image.new(mode: str, size: tuple[int, int], color=0)
canvas.paste(im: Image.Image, box: tuple[int, int] | tuple[int, int, int, int], mask: Image.Image | None = None)
# box as 2-tuple → upper-left corner; image is pasted at natural size
# mask → "L" or "RGBA" image; 255=use source, 0=use destination, 128=50-50 blend
```

**Clean stitch (no blending):**
```python
def stitch_grid(tiles: list[list[Image.Image]], orig_size: tuple[int, int]) -> Image.Image:
    """Reassemble a 2-D tile grid back into a single image at orig_size."""
    canvas = Image.new(tiles[0][0].mode, orig_size)
    rows = len(tiles)
    cols = len(tiles[0])
    img_w, img_h = orig_size
    tile_w = img_w // cols
    tile_h = img_h // rows

    for row_idx, row in enumerate(tiles):
        for col_idx, tile in enumerate(row):
            left  = col_idx * tile_w
            upper = row_idx * tile_h
            # Resize tile back to its exact slot — Gemini may return a different size
            slot_w = img_w - left if col_idx == cols - 1 else tile_w
            slot_h = img_h - upper if row_idx == rows - 1 else tile_h
            tile_resized = tile.resize((slot_w, slot_h), Image.LANCZOS)
            canvas.paste(tile_resized, (left, upper))
    return canvas
```

> **Always call `tile.resize()` before pasting.** Gemini `gemini-3.1-flash-image-preview` does not guarantee the returned image dimensions match the input tile. This is already done in the existing single-image flow (`result_pil_img.resize(orig_size, Image.LANCZOS)`).

---

### 1.3 Seam Blending — gradient mask via `Image.paste(mask=...)`

When `paste()` receives a `mask` argument of mode `"L"`, each pixel in the overlap zone is blended:

```
output_pixel = source_pixel * (mask_value / 255) + dest_pixel * (1 - mask_value / 255)
```

**Horizontal seam blend (feather zone at tile right-edge):**
```python
import numpy as np
from PIL import Image

def make_h_feather_mask(tile_w: int, tile_h: int, feather_px: int) -> Image.Image:
    """
    Mask for a tile's RIGHT edge: left portion = 255 (opaque),
    rightmost feather_px pixels fade 255→0.
    Used when pasting tile onto the canvas: overlap zone blends with neighbor.
    """
    arr = np.ones((tile_h, tile_w), dtype=np.uint8) * 255
    for i in range(feather_px):
        alpha = int(255 * (feather_px - i - 1) / feather_px)
        arr[:, tile_w - feather_px + i] = alpha
    return Image.fromarray(arr, mode="L")
```

**Vertical seam blend (feather zone at tile bottom-edge):**
```python
def make_v_feather_mask(tile_w: int, tile_h: int, feather_px: int) -> Image.Image:
    """Mask for a tile's BOTTOM edge: top = 255, bottom feather_px rows fade 255→0."""
    arr = np.ones((tile_h, tile_w), dtype=np.uint8) * 255
    for i in range(feather_px):
        alpha = int(255 * (feather_px - i - 1) / feather_px)
        arr[tile_h - feather_px + i, :] = alpha
    return Image.fromarray(arr, mode="L")
```

**Usage pattern:**
```python
# Paste tile at (left, upper) with feathered right & bottom edges
mask = make_h_feather_mask(tile.width, tile.height, feather_px=16)
canvas.paste(tile, (left, upper), mask=mask)
```

> NumPy is used only for gradient array construction. If NumPy is unavailable, `Image.linear_gradient("L")` + `Image.resize()` can produce the same gradient without NumPy.

---

## 2. Overlap Tiles vs. Clean Cuts — Decision

### Recommendation: **Clean cuts, feathered blending only**

| Approach | How it works | Verdict for this project |
|---|---|---|
| **Clean cuts** | Tile borders are exact — no pixel is sent twice | ✅ Use this |
| **Overlap tiles** (send redundant border pixels to API) | Adjacent tiles share N px of original; merge by taking center region | ❌ Reject |
| **Overlap + seam blend in overlap zone** | Send extra px, discard outer half of overlap, feather inner half | ❌ Reject |

**Why reject overlap tiles here:**

1. **Gemini re-renders the image, not just text.** Unlike inpainting/diffusion models, `gemini-3.1-flash-image-preview` re-synthesises the entire tile. Sending overlapping source pixels does **not** guarantee the AI will produce matching content in the overlap zone — it may re-draw icons, gradients, or backgrounds differently. The overlap pixels from two adjacent tiles will therefore *disagree visually*.

2. **Overlap increases API payload size.** With a 10 MB/file cap and an upscale factor of 2×, a 3×3 grid with 64 px overlap would send ~13% more data per tile — increasing risk of approaching Gemini's per-request token budget.

3. **Feathered blending on clean cuts is sufficient.** Game UI images have strong geometric structure (solid-color panels, bordered frames, discrete icons). A 16–24 px feather zone at seams is invisible on structure that repeats across the boundary.

**When to reconsider overlap:** Only if future testing shows Gemini consistently redraws background textures with per-tile randomness that feathering cannot hide. In that case, a 32 px overlap with a center-weighted blend would be the next option.

---

## 3. Grid Size Recommendation

### Default: **2×2**

| Grid | Tiles | Per-tile size (1280×720 → 2560×1440 after 2× upscale) | Notes |
|---|---|---|---|
| 1×1 | 1 | 2560×1440 | Current behavior — skips text in dense UI |
| **2×2** | **4** | **1280×720** | ✅ Recommended default |
| 3×3 | 9 | 853×480 | Good for very dense UI; 3× more API calls |
| 4×4 | 16 | 640×360 | Risk: tiles too small → Gemini loses context for text meaning |

**Why 2×2 as default:**

- **Halves linear tile dimension** → quadruples attention density for a given image area. This directly addresses the "Gemini misses text in corners" problem described in `PROJECT.md`.
- **4 API calls instead of 1** — acceptable latency increase given sequential processing.
- **Tiles stay large enough for context.** At 1280×720 px, a 2×2 tile is still a full-featured game UI panel. At 853×480 (3×3), individual tiles may show only partial UI widgets — Gemini might mistranslate labels that make sense only in context of surrounding elements.
- **Aligns with existing upscale logic.** The current code upscales 2× before sending (up to 3000 px max). A 2×2 grid of an upscaled 2560×1440 image gives 1280×720 tiles — well within Gemini's comfort zone for image understanding.

### Adaptive grid (future)

For a future enhancement, grid size can be made adaptive based on image content density:

```python
def adaptive_grid(image: Image.Image) -> tuple[int, int]:
    """Suggest (cols, rows) based on image resolution."""
    w, h = image.size
    px = w * h
    if px < 800_000:      # < ~1 MP
        return (1, 1)     # small image — no split needed
    elif px < 3_000_000:  # 1–3 MP
        return (2, 2)
    else:                  # > 3 MP (e.g. 4K screenshot)
        return (3, 3)
```

---

## 4. Complete Pipeline Sketch

```python
from PIL import Image
import numpy as np

GRID_COLS = 2
GRID_ROWS = 2
FEATHER_PX = 16  # px to feather at each seam

def translate_with_grid(image: Image.Image, translate_fn, prompt: str) -> Image.Image:
    """
    Grid-split image → translate each tile → stitch back.
    translate_fn: callable(pil_image, prompt) -> pil_image | None
    """
    orig_size = image.size
    img_w, img_h = orig_size
    tile_w = img_w // GRID_COLS
    tile_h = img_h // GRID_ROWS

    canvas = Image.new(image.mode, orig_size)

    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            # 1. Crop tile
            left   = col * tile_w
            upper  = row * tile_h
            right  = img_w if col == GRID_COLS - 1 else left + tile_w
            lower  = img_h if row == GRID_ROWS - 1 else upper + tile_h
            tile   = image.crop((left, upper, right, lower))

            # 2. Translate tile (caller supplies retry logic)
            translated = translate_fn(tile, prompt)
            if translated is None:
                translated = tile  # fallback: use original if API fails

            # 3. Resize translated tile to exact slot dimensions
            slot_w = right - left
            slot_h = lower - upper
            translated = translated.resize((slot_w, slot_h), Image.LANCZOS)

            # 4. Paste with feather mask at seams (skip feather on outer edges)
            mask = _make_tile_mask(slot_w, slot_h, col, row,
                                   GRID_COLS, GRID_ROWS, FEATHER_PX)
            canvas.paste(translated, (left, upper), mask=mask)

    return canvas


def _make_tile_mask(w: int, h: int,
                    col: int, row: int,
                    total_cols: int, total_rows: int,
                    feather_px: int) -> Image.Image:
    """
    Full-255 mask with feather fade on interior seam edges only.
    Outer edges of the overall image are never feathered.
    """
    arr = np.full((h, w), 255, dtype=np.uint8)

    # Right seam (interior column boundary)
    if col < total_cols - 1:
        for i in range(feather_px):
            alpha = int(255 * (feather_px - i - 1) / feather_px)
            arr[:, w - feather_px + i] = np.minimum(arr[:, w - feather_px + i], alpha)

    # Bottom seam (interior row boundary)
    if row < total_rows - 1:
        for i in range(feather_px):
            alpha = int(255 * (feather_px - i - 1) / feather_px)
            arr[h - feather_px + i, :] = np.minimum(arr[h - feather_px + i, :], alpha)

    return Image.fromarray(arr, mode="L")
```

---

## 5. Mode Handling Across the Pipeline

The existing codebase has an asymmetric RGBA strategy:

| File | Where conversion happens |
|---|---|
| `app.py` | Convert RGBA→RGB on **input** (before crop) |
| `image_translator.py` | Convert RGBA→RGB on **output** (before save) |

**Grid pipeline must preserve this asymmetry:**

- `split_grid()` runs *after* the existing RGBA conversion — tiles inherit the already-converted mode.
- `stitch_grid()` outputs in whatever mode the tiles are in — no additional conversion needed.
- PNG tiles with alpha pass through unchanged (both files already handle this correctly).
- `Image.new(tiles[0][0].mode, orig_size)` automatically creates the canvas in the correct mode.

---

## 6. Libraries — What Changes in `requirements.txt`

**Nothing changes.** All required capabilities are already present:

| Capability | Library | Already in requirements? |
|---|---|---|
| `Image.crop()`, `Image.paste()`, `Image.new()` | `pillow>=10.2.0` | ✅ Yes |
| `Image.resize(..., Image.LANCZOS)` | `pillow>=10.2.0` | ✅ Yes |
| `np.full()`, `np.minimum()`, `Image.fromarray()` | `numpy` (transitive dep of pillow) | ✅ Yes (implicit) |
| HTTP handling, retry logic, base64 | stdlib / existing code | ✅ Yes |

If NumPy is explicitly required in `requirements.txt` for clarity:
```
numpy>=1.24.0
```
But this is optional — Pillow's own C extensions handle the array interface without a direct `import numpy`.

---

## 7. Edge Cases to Handle

| Case | Handling |
|---|---|
| Image dimension not divisible by grid (e.g., 1281×719 for 2×2) | Last row/column tile absorbs the remainder (see `split_grid()` above) |
| Gemini returns wrong size tile | `tile.resize((slot_w, slot_h), Image.LANCZOS)` normalises before paste |
| Gemini API fails for one tile | `translate_fn` returns `None` → paste original tile (graceful degradation) |
| FEATHER_PX > tile dimension | Guard: `feather_px = min(FEATHER_PX, slot_w // 4, slot_h // 4)` |
| Tiles with different modes (e.g., RGBA vs RGB) | Convert all tiles to canvas mode before paste: `tile.convert(canvas.mode)` |
| 10 MB/file cap + 2× upscale | At 2×2 grid with 2× upscale: each tile ≈ 25% of full image → well under 10 MB limit |

---

## 8. What Is NOT Needed

| Library | Why excluded |
|---|---|
| `opencv-python` | Provides `seamlessClone()` (Poisson blending) but adds a 35 MB binary. Feather masks in Pillow are sufficient for flat game UI. |
| `scikit-image` | `restoration.inpaint_biharmonic()` useful for missing pixels, not for this use case. Adds significant weight. |
| `imageio` | Not needed — Pillow handles all required formats. |
| Any diffusion-based inpainting | Model is Gemini, not a local diffusion pipeline. Inpainting seams would require running a second model. |

---

## 9. Version Pins

| Library | Current `requirements.txt` | Latest stable (2025) | Recommendation |
|---|---|---|---|
| `pillow` | `>=10.2.0` | 12.1.1 | Keep `>=10.2.0`. All APIs used exist since 9.x. |
| `numpy` | not pinned | 2.2.x | Add `numpy>=1.24.0` explicitly if desired |
| `flask` | `>=3.0.0` | 3.1.x | No change |
| `google-genai` | `>=0.2.2` | 1.x | No change (existing concern, not this milestone) |

---

*This document feeds directly into ROADMAP.md for the grid-splitting milestone.*
