import io
import time
from PIL import Image

# --- Constants ---
GEMINI_MODEL = 'gemini-3.1-flash-image-preview'
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2


def _translate_single_tile(tile, client, prompt):
    """Dich mot tile qua Gemini voi retry va dual-format parse."""
    tile_size = tile.size
    retry_delay = RETRY_DELAY_SECONDS

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[tile, prompt]
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

    part = response.candidates[0].content.parts[0]

    if hasattr(part, 'image') and part.image:
        result = part.image
    elif hasattr(part, 'inline_data') and part.inline_data:
        result = Image.open(io.BytesIO(part.inline_data.data))
    else:
        raise Exception("Gemini khong tra ve anh hop le")

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
