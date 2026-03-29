# Architecture Research: Grid-Split + Stitch Integration

*Research date: 2026-03-29*
*Scope: How to add NxN grid splitting to the existing ImagiTranslate pipeline*

---

## 1. Current Pipeline (Baseline)

Both entry points execute the same logical steps, duplicated in each file:

```
PIL Image (open)
    │
    ├─ [RGBA→RGB if JPEG input]         ← web only, on input
    │
    ├─ Scale up 2x (if max dim ≤ 3000)
    │
    ├─ generate_content(model, [image, prompt])   ← Gemini call (retry x3)
    │
    ├─ Parse response part (image | inline_data)
    │
    ├─ Resize to orig_size (LANCZOS)
    │
    ├─ [RGBA→RGB if JPEG output]        ← CLI only, on output
    │
    └─ Deliver: base64 JSON (web) | save file (CLI)
```

The core Gemini call is **inlined directly** in both `app.py:translate_image()` and
`image_translator.py:translate_images()`. There is no shared utility function today —
the two files are parallel implementations.

---

## 2. Integration Point Analysis

### What needs to happen

The grid pipeline wraps the single-image Gemini call:

```
PIL Image
    │
    ├─ split_into_tiles(image, grid_n)  → tiles[]: list[PIL Image]
    │
    ├─ for each tile:
    │       translate_tile(tile, client, prompt)  → translated_tile: PIL Image
    │
    └─ stitch_tiles(translated_tiles, grid_n, orig_size)  → PIL Image
```

This replaces the single `generate_content()` call, not the surrounding entry-point
logic. Everything that comes before (RGBA conversion, upscale) and after (normalize to
orig_size, encode/save) stays exactly where it is.

### What must NOT move

Each entry point handles concerns that are legitimately its own:

| Concern | Stays in |
|---------|----------|
| RGBA→RGB on **input** (JPEG) | `app.py` |
| RGBA→RGB on **output** (JPEG) | `image_translator.py` |
| base64 encoding → JSON | `app.py` |
| File save + extension preservation | `image_translator.py` |
| Upscale 2x before Gemini | Both (unchanged) |
| Resize to `orig_size` after result | Both (unchanged) |

The upscale happens **before** splitting, and the resize to `orig_size` happens
**after** stitching. The grid layer operates on the already-upscaled image and returns
a result at that same (upscaled) size. The caller then normalizes to `orig_size` as
it does today.

---

## 3. New Module: `grid_translator.py`

### Why a new file

- Neither `app.py` nor `image_translator.py` is a good host: both are entry-point
  files with their own concerns (HTTP routes, CLI arg parsing).
- The grid logic has no dependency on Flask or argparse — it only needs PIL and the
  `genai.Client` object.
- A shared module makes both entry points call identical code, preventing the
  current divergence pattern from repeating itself.
- Testable in isolation without starting Flask or setting up a CLI invocation.

### Module contract

```python
# grid_translator.py

def translate_with_grid(
    image: PIL.Image.Image,
    client: genai.Client,
    prompt: str,
    grid_n: int = 2,
) -> PIL.Image.Image:
    """
    Split `image` into grid_n × grid_n tiles, translate each tile via Gemini,
    stitch translated tiles back into a full image, and return it.

    The returned image has the same pixel dimensions as the input image.
    Caller is responsible for all pre/post processing (RGBA conversion,
    upscaling, final resize to orig_size).

    Raises:
        Exception: if any tile fails after MAX_RETRIES (caller decides how to handle)
    """
```

Internal helpers (private to the module):

```python
def _split_tiles(image, grid_n) -> list[PIL.Image.Image]:
    """Slice image into grid_n*grid_n equal rectangular tiles, row-major order."""

def _translate_single_tile(tile, client, prompt) -> PIL.Image.Image:
    """Single Gemini call for one tile. Same retry logic as existing code."""

def _stitch_tiles(tiles, grid_n, target_size) -> PIL.Image.Image:
    """Paste translated tiles back at their original offsets."""
```

`_translate_single_tile` is the **extracted** version of the retry+parse block that
currently lives inline in both files. It contains:
- `client.models.generate_content(model, [tile, prompt])`
- Retry loop with exponential backoff (MAX_RETRIES, RETRY_DELAY_SECONDS)
- Dual response format handling (`part.image` vs `part.inline_data`)

Constants used by `grid_translator.py` are **imported** from it (or re-declared
identically — see §5 on constants).

---

## 4. Full Data Flow After Integration

### Shared (both entry points call this)

```
PIL Image  (already upscaled by caller)
    │
    ▼
grid_translator.translate_with_grid(image, client, prompt, grid_n=2)
    │
    ├─ _split_tiles(image, 2)
    │       ┌───────┬───────┐
    │       │ t[0,0]│ t[0,1]│   ← PIL crop regions, tile_w × tile_h px
    │       ├───────┼───────┤
    │       │ t[1,0]│ t[1,1]│
    │       └───────┴───────┘
    │       → [tile_00, tile_01, tile_10, tile_11]
    │
    ├─ for tile in tiles (sequential):
    │       _translate_single_tile(tile, client, prompt)
    │           ├─ generate_content([tile, prompt])    ← Gemini
    │           ├─ retry x3, backoff 2s→4s
    │           ├─ parse part.image | part.inline_data
    │           └─ resize tile result to tile input size
    │       → translated_tiles[]
    │
    └─ _stitch_tiles(translated_tiles, 2, image.size)
            ├─ new blank Image, same size as input
            ├─ paste tile[0] at (0, 0)
            ├─ paste tile[1] at (tile_w, 0)
            ├─ paste tile[2] at (0, tile_h)
            └─ paste tile[3] at (tile_w, tile_h)
            → stitched PIL Image (same size as input)
    │
    ▼
Returns: PIL Image  (same dimensions as input to translate_with_grid)
```

### Web entry point (`app.py`) — after integration

```
file bytes
    ↓
PIL Image.open()
orig_size = image.size                     ← save before anything
[RGBA→RGB if JPEG input]                   ← unchanged
[upscale 2x if small]                      ← unchanged
    ↓
translate_with_grid(image, client, prompt) ← replaces single generate_content block
    ↓
result_pil_img.resize(orig_size, LANCZOS)  ← unchanged (normalizes back)
save to BytesIO → base64 → JSON            ← unchanged
```

### CLI entry point (`image_translator.py`) — after integration

```
Path(img_file)
    ↓
PIL Image.open()
orig_size = image.size                     ← save before anything
[upscale 2x if small]                      ← unchanged
    ↓
translate_with_grid(image, client, prompt) ← replaces single generate_content block
    ↓
result.resize(orig_size, LANCZOS)          ← unchanged
[RGBA→RGB if JPEG output]                  ← unchanged
result.save(out_file_path)                 ← unchanged
```

The two entry points change **only** the middle section: the inline retry+parse block
is removed and replaced with a single call to `translate_with_grid`.

---

## 5. Constants and Configuration

### Shared constants

`grid_translator.py` defines (or imports from a shared location):

```python
GEMINI_MODEL          = 'gemini-3.1-flash-image-preview'
MAX_RETRIES           = 3
RETRY_DELAY_SECONDS   = 2
```

Both `app.py` and `image_translator.py` currently define these identically. After
integration they can either:

- **Option A** — Import from `grid_translator`: `from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS`
  - Single source of truth, but creates a coupling on a "logic" module for constants.
- **Option B** — Keep duplicated in each file, let `grid_translator` define its own
  - More friction if values need changing, but keeps files independently readable.

**Recommendation: Option A.** The constants are behavior-defining for the Gemini
integration, which now lives in `grid_translator`. Duplication is a maintenance hazard.

### New constant

```python
GRID_N = 2   # Default grid size (2×2 = 4 tiles)
```

Defined in `grid_translator.py`. Callers can override per-call; the default covers
the primary use case.

---

## 6. Wrap vs. Replace

The grid logic **wraps** the Gemini call — it does not replace the overall translation
function signature from the entry point's perspective.

From `app.py`'s point of view, the change is surgical:

```python
# Before
response = client.models.generate_content(...)     # inline ~25 lines
part = response.candidates[0].content.parts[0]
result_pil_img = ...

# After
result_pil_img = translate_with_grid(base_image, client, prompt)
```

The function name `translate_image` (the Flask route handler) stays the same.
The function name `translate_images` (the CLI batch function) stays the same.
No external contract changes.

---

## 7. Tile Sizing and Edge Cases

### Even splits

For a 2×2 grid on a 1000×800 image:
- `tile_w = 1000 // 2 = 500`
- `tile_h = 800 // 2 = 400`
- Tiles: `(0,0,500,400)`, `(500,0,1000,400)`, `(0,400,500,800)`, `(500,400,1000,800)`

### Odd dimensions

If width or height is not evenly divisible by `grid_n`, PIL `crop()` handles fractional
tile sizes by flooring. The stitch paste offsets use the same floor values, so tiles
cover the full image without gaps. The last column/row tile will be 1px wider/taller.

### Gemini output size per tile

Gemini may return a tile at a different size than it was sent (same issue as the full
image). `_translate_single_tile` resizes each result back to the input tile's exact
dimensions before returning — identical to how both entry points currently resize the
full result to `orig_size`.

### Upscale interaction

The upscale (2x) is applied by the caller **before** `translate_with_grid` is called.
The grid splits the already-upscaled image. This is correct: tiles are larger (clearer
text) when sent to Gemini, which is the goal of upscaling. The caller normalizes back
to `orig_size` after receiving the stitched result.

---

## 8. Error Handling

### Tile failure policy

If a single tile fails after all retries, `_translate_single_tile` raises. The
`translate_with_grid` caller (entry point) catches this:

- **Web**: caught by the outer `try/except` in `translate_image()`, returns HTTP 500
  (same behavior as today when the full image fails).
- **CLI**: caught by the outer `try/except` per file, prints error and skips file
  (same behavior as today).

### Partial success

No partial stitching — if any tile fails, the whole image fails. This aligns with the
current all-or-nothing behavior. Partial results would produce a broken image that
is worse than no image.

---

## 9. Suggested Build Order

The following phased order minimizes risk by validating each layer before building
on top of it.

```
Phase 1 — Extract shared Gemini call
    Create grid_translator.py with _translate_single_tile() only.
    This is a direct extraction of the existing retry+parse block.
    Both app.py and image_translator.py import and call it in place
    of the inline block. No behavior change. Validate parity.

Phase 2 — Add split + stitch scaffolding
    Add _split_tiles() and _stitch_tiles() to grid_translator.py.
    Verify: split an image then stitch with no translation →
    result matches original pixel-for-pixel (pure PIL crop + paste).

Phase 3 — Wire translate_with_grid()
    Implement the loop: split → translate each tile → stitch.
    Replace the inline Gemini call in app.py and image_translator.py
    with a single translate_with_grid() call.

Phase 4 — Validate end-to-end
    Test with known game UI screenshots. Compare 1x1 grid (=original
    behavior, single Gemini call) vs 2x2 grid. Confirm:
    - No missing text in tiles
    - Stitch seams not visible
    - Output dimensions match original

Phase 5 — Expose grid_n control (optional)
    Web: add grid_n form field (default 2, UI option 1/2/3)
    CLI: add --grid-n argument (default 2)
```

Phase 1 delivers immediate value: it unifies the retry logic that is currently
duplicated between both files, reducing future maintenance surface before any grid
feature is added.

---

## 10. Quality Gate Checklist

- [x] **Integration point clearly defined**: `translate_with_grid()` replaces the
  inline `generate_content` block in both entry points. Entry point outer logic
  (RGBA, upscale, resize, encode/save) is untouched.
- [x] **Data flow explicit**: Full before/after flow documented for both web and CLI
  in §4, including tile split offsets, per-tile resize, and stitch paste positions.
- [x] **Both entry points addressed**: `app.py` and `image_translator.py` both call
  `translate_with_grid()` with an identical call signature; each retains its own
  format-specific handling around it.

---

## 11. File Map After Integration

```
ImagiTranslate/
├── app.py                    MODIFIED — inline Gemini block → translate_with_grid()
├── image_translator.py       MODIFIED — inline Gemini block → translate_with_grid()
├── grid_translator.py        NEW — split / translate-tile / stitch
├── test_api.py               unchanged
├── static/
│   ├── script.js             unchanged (grid is server-side only)
│   └── style.css             unchanged
└── templates/
    └── index.html            unchanged (unless Phase 5 grid_n UI added)
```

No new dependencies. Pillow (`crop`, `paste`, `new`) already in `requirements.txt`.
`genai.Client` already imported in both entry points and passed as an argument.
