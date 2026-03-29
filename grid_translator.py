import io
import json
import math
import re
import time
import numpy as np
from PIL import Image
from google.genai import types

# Tile có ít hơn ngưỡng này pixel có nội dung thì bỏ qua, không gọi API
EMPTY_TILE_THRESHOLD = 0.02

# --- Constants ---
GEMINI_MODEL = 'gemini-3.1-flash-image-preview'
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2

# --- Verify & Patch Constants ---
VERIFY_MAX_PASSES = 3
VERIFY_CROP_MARGIN = 0.08
VERIFY_MAX_BBOX_AREA = 0.80
VERIFY_MIN_CROP_PX = 20

VERIFY_PROMPT = (
    "Examine this image carefully. "
    "Find ALL remaining Chinese characters (Hanzi/CJK Unified Ideographs, "
    "including Simplified and Traditional Chinese). "
    "Return ONLY a valid JSON array of bounding boxes: "
    '[{"x1": 0.1, "y1": 0.2, "x2": 0.3, "y2": 0.4}] '
    "Coordinates are normalized 0.0-1.0 relative to image dimensions "
    "(x1,y1 = top-left corner, x2,y2 = bottom-right corner). "
    "If no Chinese text remains, return exactly: [] "
    "Return ONLY the JSON array, nothing else."
)


def _is_empty_tile(tile):
    """Trả về True nếu tile gần như trống (< EMPTY_TILE_THRESHOLD pixel có nội dung)."""
    arr = np.array(tile)
    if tile.mode == 'RGBA':
        non_empty = np.sum(arr[:, :, 3] > 10)
    else:
        non_empty = np.sum(np.any(arr > 30, axis=2))
    total = tile.size[0] * tile.size[1]
    return (non_empty / total) < EMPTY_TILE_THRESHOLD


def _parse_bboxes(response_text):
    """Parse JSON bounding boxes from Gemini verify response.

    Returns:
        tuple (bboxes, parse_ok, had_invalid):
            - bboxes: list of valid dict {x1, y1, x2, y2} (normalized 0.0-1.0)
            - parse_ok: True if response is a valid JSON list (including empty)
            - had_invalid: True if >= 1 bbox was filtered due to invalid coordinates
    """
    text = response_text.strip()
    # Try each [...] match from last to first — Gemini's actual answer is typically last
    matches = list(re.finditer(r'\[.*?\]', text, re.DOTALL))
    if not matches:
        return [], False, False
    raw = None
    for m in reversed(matches):
        try:
            candidate = json.loads(m.group())
            if isinstance(candidate, list):
                raw = candidate
                break
        except json.JSONDecodeError:
            continue
    if raw is None:
        return [], False, False
    try:
        valid = []
        had_invalid = False
        for b in raw:
            if not all(k in b for k in ('x1', 'y1', 'x2', 'y2')):
                had_invalid = True
                continue
            try:
                x1, y1 = float(b['x1']), float(b['y1'])
                x2, y2 = float(b['x2']), float(b['y2'])
            except (ValueError, TypeError):
                had_invalid = True
                continue
            # Validate finite values and normalized range with coordinate ordering
            if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
                had_invalid = True
                continue
            if not (0.0 <= x1 < x2 <= 1.0 and 0.0 <= y1 < y2 <= 1.0):
                had_invalid = True
                continue
            valid.append({'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})
        return valid, True, had_invalid
    except (json.JSONDecodeError, ValueError, TypeError):
        return [], False, False


def _translate_single_tile(tile, client, prompt):
    """Dich mot tile qua Gemini voi retry va dual-format parse."""
    tile_size = tile.size
    retry_delay = RETRY_DELAY_SECONDS

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[tile, prompt],
                config=types.GenerateContentConfig(
                    response_modalities=['IMAGE', 'TEXT']
                )
            )
            parts = response.candidates[0].content.parts if (
                response and response.candidates
            ) else []
            has_image = any(
                (hasattr(p, 'image') and p.image) or
                (hasattr(p, 'inline_data') and p.inline_data)
                for p in parts
            )
            if has_image:
                break
            else:
                raise Exception("Phan hoi khong chua anh")
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                raise

    part = next(
        (p for p in response.candidates[0].content.parts
         if (hasattr(p, 'image') and p.image) or
            (hasattr(p, 'inline_data') and p.inline_data)),
        None
    )
    if part is None:
        raise Exception("Gemini khong tra ve anh hop le")

    if hasattr(part, 'image') and part.image:
        result = part.image
    else:
        result = Image.open(io.BytesIO(part.inline_data.data))

    result = result.resize(tile_size, Image.LANCZOS)
    return result


def _split_tiles(image, grid_n):
    """Chia anh thanh grid_n x grid_n tiles. Tile cuoi hap thu pixel du."""
    img_w, img_h = image.size
    tile_w = img_w // grid_n
    tile_h = img_h // grid_n
    tiles = []
    for row in range(grid_n):
        for col in range(grid_n):
            left = col * tile_w
            upper = row * tile_h
            right = img_w if col == grid_n - 1 else left + tile_w
            lower = img_h if row == grid_n - 1 else upper + tile_h
            tiles.append((row, col, left, upper, right, lower, image.crop((left, upper, right, lower))))
    return tiles


def _stitch_tiles(translated_tiles, image_size, grid_n):
    """Rap tiles da dich vao canvas. Hard-paste, khong blending."""
    canvas_mode = translated_tiles[0][4].mode
    bg_color = (255, 255, 255) if canvas_mode == 'RGB' else (255, 255, 255, 0)
    canvas = Image.new(canvas_mode, image_size, color=bg_color)

    for left, upper, right, lower, tile in translated_tiles:
        slot_w = right - left
        slot_h = lower - upper
        tile = tile.convert(canvas_mode)
        tile = tile.resize((slot_w, slot_h), Image.LANCZOS)
        canvas.paste(tile, (left, upper))
        del tile

    assert canvas.size == image_size, (
        f"Canvas size {canvas.size} != image size {image_size}"
    )
    return canvas


def translate_with_grid(image, client, prompt, grid_n=1):
    """Dich anh qua Gemini voi grid splitting. grid_n=1 = khong chia."""
    if grid_n == 1:
        result = _translate_single_tile(image, client, prompt)
        return result.resize(image.size, Image.LANCZOS)

    tiles = _split_tiles(image, grid_n)

    translated = []
    for row, col, left, upper, right, lower, tile in tiles:
        if _is_empty_tile(tile):
            # Tile rỗng: bỏ qua, nền canvas sẽ lấp chỗ trống
            continue
        result = _translate_single_tile(tile, client, prompt)
        translated.append((left, upper, right, lower, result))

    return _stitch_tiles(translated, image.size, grid_n)
