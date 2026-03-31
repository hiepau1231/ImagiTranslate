"""Tests for bug fixes — offline, no API key needed."""
import sys
from PIL import Image


def test_stitch_tiles_empty_list_rgb():
    """_stitch_tiles() must return a canvas matching the input image mode when
    translated_tiles is empty — RGB input → RGB canvas, not crash with IndexError."""
    from grid_translator import _stitch_tiles

    image_size = (200, 200)
    grid_n = 2

    # This should NOT raise IndexError
    result = _stitch_tiles([], image_size, grid_n)

    assert isinstance(result, Image.Image), f"Expected PIL Image, got {type(result)}"
    assert result.size == image_size, f"Expected size {image_size}, got {result.size}"
    assert result.mode == 'RGB', f"Expected RGB mode, got {result.mode}"
    print(f"[+] test_stitch_tiles_empty_list_rgb: returned mode={result.mode}, size={result.size}")
    return True


def test_stitch_tiles_empty_list_rgba():
    """_stitch_tiles() must return an RGBA canvas when called for an RGBA image
    with all tiles empty — mode must NOT be downgraded to RGB."""
    from grid_translator import _stitch_tiles

    image_size = (200, 200)
    grid_n = 2

    # This should NOT raise IndexError AND must preserve RGBA mode
    result = _stitch_tiles([], image_size, grid_n, image_mode='RGBA')

    assert isinstance(result, Image.Image), f"Expected PIL Image, got {type(result)}"
    assert result.size == image_size, f"Expected size {image_size}, got {result.size}"
    assert result.mode == 'RGBA', f"Expected RGBA mode, got {result.mode}"
    print(f"[+] test_stitch_tiles_empty_list_rgba: returned mode={result.mode}")
    return True


if __name__ == "__main__":
    results = []
    for fn in [test_stitch_tiles_empty_list_rgb, test_stitch_tiles_empty_list_rgba]:
        try:
            results.append(fn())
        except AssertionError as e:
            print(f"[-] {fn.__name__}: FAIL — {e}")
            results.append(False)
        except Exception as e:
            print(f"[!] {fn.__name__}: ERROR — {e}")
            results.append(False)

    passed = sum(1 for r in results if r)
    print(f"\n{passed}/{len(results)} tests passed.")
    sys.exit(0 if all(results) else 1)
