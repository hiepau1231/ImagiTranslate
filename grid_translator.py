import io
import time
import numpy as np
from PIL import Image
from google.genai import types
from ocr_detector import detect_cjk_bboxes

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


def _is_empty_tile(tile):
    """Trả về True nếu tile gần như trống (< EMPTY_TILE_THRESHOLD pixel có nội dung)."""
    arr = np.array(tile)
    if tile.mode == 'RGBA':
        non_empty = np.sum(arr[:, :, 3] > 10)
    else:
        non_empty = np.sum(np.any(arr > 30, axis=2))
    total = tile.size[0] * tile.size[1]
    return (non_empty / total) < EMPTY_TILE_THRESHOLD


def _translate_single_tile(tile, client, prompt):
    """Dich mot tile qua Gemini voi retry va dual-format parse."""
    tile_size = tile.size
    retry_delay = RETRY_DELAY_SECONDS

    for attempt in range(MAX_RETRIES):
        try:
            image_prompt = prompt + " Output the result as an image."
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[image_prompt, tile],
                config=types.GenerateContentConfig(
                    response_modalities=['IMAGE', 'TEXT']
                )
            )

            parts = response.candidates[0].content.parts if (
                response and response.candidates
                and response.candidates[0].content
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


def _stitch_tiles(translated_tiles, image_size, grid_n, image_mode='RGB'):
    """Rap tiles da dich vao canvas. Hard-paste, khong blending."""
    if not translated_tiles:
        bg = (255, 255, 255, 0) if image_mode == 'RGBA' else (255, 255, 255) if image_mode == 'RGB' else 255
        return Image.new(image_mode, image_size, color=bg)
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

    return _stitch_tiles(translated, image.size, grid_n, image_mode=image.mode)


def verify_and_patch(image, client, target_lang, max_passes=VERIFY_MAX_PASSES):
    """Kiểm tra ảnh đã dịch còn sót chữ CJK không, patch các vùng bị bỏ sót.

    Args:
        image: PIL.Image - ảnh đã dịch xong
        client: genai.Client
        target_lang: str - ngôn ngữ đích để dịch lại
        max_passes: int - số vòng kiểm tra tối đa (default VERIFY_MAX_PASSES=3)

    Returns:
        PIL.Image - ảnh đã patch (có thể là object cũ nếu không có gì cần fix)
    """
    # Clamp to ensure we never exceed the configured limit
    max_passes = min(max(0, max_passes), VERIFY_MAX_PASSES)
    if max_passes == 0:
        return image

    patch_prompt = (
        f"Translate EVERY SINGLE piece of text from Chinese to {target_lang}. "
        "Do NOT skip any text. Preserve layout, colors, and visual style exactly."
    )
    img_w, img_h = image.size
    img_area = img_w * img_h

    for pass_num in range(max_passes):
        # Detect remaining Chinese ideographs using PaddleOCR (local, no Gemini call)
        try:
            bboxes = detect_cjk_bboxes(image)
        except Exception as e:
            print(f"[verify_and_patch] Pass {pass_num + 1}: Loi OCR detect: {e}. Dung verify.")
            break
        if not bboxes:
            print(f"[verify_and_patch] Pass {pass_num + 1}: Khong con chu Chinese. Dung som.")
            break
        print(f"[verify_and_patch] Pass {pass_num + 1}: Phat hien {len(bboxes)} vung can patch.")

        # Patch each bbox
        patched_any = False
        for bbox in bboxes:
            try:
                x1 = bbox['x1']
                y1 = bbox['y1']
                x2 = bbox['x2']
                y2 = bbox['y2']

                # Expand by 8% margin
                margin_x = (x2 - x1) * VERIFY_CROP_MARGIN
                margin_y = (y2 - y1) * VERIFY_CROP_MARGIN
                x1 = max(0.0, x1 - margin_x)
                y1 = max(0.0, y1 - margin_y)
                x2 = min(1.0, x2 + margin_x)
                y2 = min(1.0, y2 + margin_y)

                # Convert to pixels
                px1 = int(x1 * img_w)
                py1 = int(y1 * img_h)
                px2 = int(x2 * img_w)
                py2 = int(y2 * img_h)

                crop_w = px2 - px1
                crop_h = py2 - py1
                crop_area = crop_w * crop_h

                # Skip if crop is too small
                if crop_w < VERIFY_MIN_CROP_PX or crop_h < VERIFY_MIN_CROP_PX:
                    print(f"[verify_and_patch] Skip small bbox: {crop_w}x{crop_h}px")
                    continue

                # Skip if bbox covers > 80% of image (prevent infinite re-translate)
                if crop_area > img_area * VERIFY_MAX_BBOX_AREA:
                    print(f"[verify_and_patch] Skip large bbox: {crop_area/img_area:.1%}")
                    continue

                # Crop and upscale 2x so Gemini can read small text
                crop = image.crop((px1, py1, px2, py2))
                upscaled_crop = crop.resize((crop_w * 2, crop_h * 2), Image.LANCZOS)

                # Re-translate the cropped region
                translated_crop = _translate_single_tile(upscaled_crop, client, patch_prompt)

                # Resize back to original crop size and paste over
                translated_crop = translated_crop.resize((crop_w, crop_h), Image.LANCZOS)
                translated_crop = translated_crop.convert(image.mode)
                image.paste(translated_crop, (px1, py1))
                patched_any = True

            except Exception as e:
                print(f"[verify_and_patch] Lỗi patch bbox {bbox}: {e}. Bỏ qua, tiếp tục.")
                continue

        if not patched_any:
            print(f"[verify_and_patch] Pass {pass_num + 1}: Không patch được vùng nào. Dừng.")
            break

    return image
