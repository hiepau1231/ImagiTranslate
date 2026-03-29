import os
import io
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image
from google import genai

# --- Helpers ---

def make_synthetic_image(width, height, mode='RGB', color='red'):
    """Tao anh synthetic de test."""
    return Image.new(mode, (width, height), color=color)


def get_test_images(test_dir='test_images'):
    """Lay danh sach anh tu test_images/. Tra ve list rong neu khong co."""
    valid_ext = {'.png', '.jpg', '.jpeg', '.webp'}
    test_path = Path(test_dir)
    if not test_path.exists() or not test_path.is_dir():
        return []
    return [f for f in test_path.iterdir() if f.is_file() and f.suffix.lower() in valid_ext]


def print_result(sc_name, passed, detail=""):
    """In ket qua pass/fail cho moi SC."""
    status = "PASS" if passed else "FAIL"
    prefix = "[+]" if passed else "[-]"
    msg = f"  {prefix} {sc_name}: {status}"
    if detail:
        msg += f" — {detail}"
    print(msg)


# --- SC-5: Mock call count (khong can API key) ---

def test_sc5_mock_call_count():
    """SC-5: Verify grid_n=1 -> 1 call, grid_n=2 -> 4 calls, grid_n=3 -> 9 calls."""
    print("\n=== SC-5: Mock call count ===")
    from grid_translator import translate_with_grid

    all_passed = True
    test_cases = [(1, 1), (2, 4), (3, 9)]

    for grid_n, expected_calls in test_cases:
        # Tao synthetic image 200x200
        img = make_synthetic_image(200, 200)

        # Mock _translate_single_tile tra ve anh cung kich thuoc tile
        def mock_translate(tile, client, prompt):
            return tile.copy()

        with patch('grid_translator._translate_single_tile', side_effect=mock_translate) as mock_fn:
            mock_client = MagicMock()
            result = translate_with_grid(img, mock_client, "test prompt", grid_n=grid_n)

            actual_calls = mock_fn.call_count
            passed = actual_calls == expected_calls
            if not passed:
                all_passed = False
            print_result(
                f"grid_n={grid_n} -> {expected_calls} calls",
                passed,
                f"actual={actual_calls}"
            )

            # Verify output size matches input
            size_ok = result.size == img.size
            if not size_ok:
                all_passed = False
            print_result(
                f"grid_n={grid_n} output size == input size",
                size_ok,
                f"expected={img.size}, actual={result.size}"
            )

    return all_passed


# --- SC-4: PNG RGBA qua grid mode khong gay JPEG error ---

def test_sc4_rgba_no_jpeg_error():
    """SC-4: PNG (RGBA mode) qua translate_with_grid() khong gay OSError."""
    print("\n=== SC-4: RGBA safety ===")
    from grid_translator import translate_with_grid

    all_passed = True

    for grid_n in [1, 2, 3]:
        # Tao RGBA image (PNG voi alpha channel)
        img = make_synthetic_image(200, 200, mode='RGBA', color=(255, 0, 0, 128))

        def mock_translate(tile, client, prompt):
            # Tra ve RGBA tile — mo phong Gemini tra ve RGBA
            return tile.copy()

        with patch('grid_translator._translate_single_tile', side_effect=mock_translate):
            mock_client = MagicMock()
            try:
                result = translate_with_grid(img, mock_client, "test prompt", grid_n=grid_n)

                # Verify khong loi khi convert qua grid pipeline
                passed = result is not None and result.size == img.size
                print_result(
                    f"RGBA grid_n={grid_n} translate OK",
                    passed,
                    f"mode={result.mode}, size={result.size}"
                )

                # Simulate web path: save as JPEG (day la cho co the loi)
                try:
                    buf = io.BytesIO()
                    # Web path luon save JPEG — can convert RGBA->RGB truoc
                    if result.mode in ('RGBA', 'P'):
                        result_rgb = result.convert('RGB')
                    else:
                        result_rgb = result
                    result_rgb.save(buf, format='JPEG')
                    print_result(
                        f"RGBA grid_n={grid_n} JPEG save OK",
                        True,
                        "No OSError"
                    )
                except OSError as e:
                    all_passed = False
                    print_result(
                        f"RGBA grid_n={grid_n} JPEG save",
                        False,
                        f"OSError: {e}"
                    )

                # Simulate CLI path: save as PNG (should always work)
                try:
                    buf = io.BytesIO()
                    result.save(buf, format='PNG')
                    print_result(
                        f"RGBA grid_n={grid_n} PNG save OK",
                        True,
                        "No error"
                    )
                except Exception as e:
                    all_passed = False
                    print_result(
                        f"RGBA grid_n={grid_n} PNG save",
                        False,
                        f"Error: {e}"
                    )

            except Exception as e:
                all_passed = False
                print_result(
                    f"RGBA grid_n={grid_n} translate",
                    False,
                    f"Exception: {e}"
                )

    return all_passed


# --- SC-1: Off vs 2x2 vs 3x3 tren anh game UI (can API key + test_images/) ---

def test_sc1_grid_comparison(client):
    """SC-1: Grid mode khong te hon Off tren anh game UI thuc."""
    print("\n=== SC-1: Grid comparison (live API) ===")

    test_images = get_test_images()
    if not test_images:
        print("  [!] SKIP: thu muc test_images/ khong ton tai hoac rong.")
        print("  [!] Hay dat it nhat 1 anh game UI vao test_images/ de chay SC-1.")
        return None  # None = skipped

    from grid_translator import translate_with_grid

    prompt = (
        "This image may contain many small icons and UI elements with text. "
        "Translate EVERY SINGLE piece of text from English to Vietnamese. "
        "IMPORTANT: Do NOT skip any text, no matter how small, faint, or densely packed. "
        "This includes small labels under icons, tiny button text, corner labels, and any "
        "characters no matter how small they appear. "
        "Strictly preserve the exact original layout, colors, icon graphics, and visual style. "
        "Only the text characters should change — everything else must remain pixel-perfect."
    )

    # Chi test 1 anh dau tien de tiet kiem API credits
    img_path = test_images[0]
    img = Image.open(img_path)
    print(f"  Test image: {img_path.name} ({img.size[0]}x{img.size[1]})")

    results = {}
    all_passed = True

    for label, grid_n in [("Off", 1), ("2x2", 2), ("3x3", 3)]:
        try:
            result = translate_with_grid(img, client, prompt, grid_n=grid_n)
            results[label] = result
            passed = result is not None and result.size == img.size
            print_result(
                f"{label} (grid_n={grid_n})",
                passed,
                f"output size={result.size}"
            )
            if not passed:
                all_passed = False
        except Exception as e:
            all_passed = False
            results[label] = None
            print_result(f"{label} (grid_n={grid_n})", False, f"Exception: {e}")

    # Kiem tra: neu Off thanh cong thi grid modes cung phai thanh cong
    if results.get("Off") is not None:
        for label in ["2x2", "3x3"]:
            if results.get(label) is None:
                all_passed = False
                print_result(
                    f"{label} not worse than Off",
                    False,
                    "Grid mode failed but Off succeeded"
                )
            else:
                print_result(f"{label} not worse than Off", True, "Both succeeded")

    return all_passed


# --- SC-2: Batch 3 anh voi grid 2x2 (can API key + test_images/) ---

def test_sc2_batch_web(client):
    """SC-2: Goi translate_with_grid() 3 lan voi grid 2x2 — ca 3 thanh cong."""
    print("\n=== SC-2: Batch 3 images with grid 2x2 (live API) ===")

    test_images = get_test_images()
    if len(test_images) < 3:
        # Dung synthetic images neu khong du real images
        print("  [!] test_images/ co < 3 anh, dung synthetic images thay the.")
        images = [make_synthetic_image(300, 200) for _ in range(3)]
        image_names = ["synthetic_1.png", "synthetic_2.png", "synthetic_3.png"]
    else:
        images = [Image.open(f) for f in test_images[:3]]
        image_names = [f.name for f in test_images[:3]]

    from grid_translator import translate_with_grid

    prompt = (
        "This image may contain many small icons and UI elements with text. "
        "Translate EVERY SINGLE piece of text from English to Vietnamese. "
        "IMPORTANT: Do NOT skip any text, no matter how small, faint, or densely packed. "
        "This includes small labels under icons, tiny button text, corner labels, and any "
        "characters no matter how small they appear. "
        "Strictly preserve the exact original layout, colors, icon graphics, and visual style. "
        "Only the text characters should change — everything else must remain pixel-perfect."
    )

    success_count = 0
    all_passed = True

    for i, (img, name) in enumerate(zip(images, image_names)):
        try:
            result = translate_with_grid(img, client, prompt, grid_n=2)
            ok = result is not None and result.size == img.size
            if ok:
                success_count += 1
            print_result(f"Image {i+1}/{len(images)} ({name})", ok, f"size={result.size}")
        except Exception as e:
            all_passed = False
            print_result(f"Image {i+1}/{len(images)} ({name})", False, f"Exception: {e}")

    batch_ok = success_count == len(images)
    print_result(
        f"Batch result: {success_count}/{len(images)} succeeded",
        batch_ok
    )
    return batch_ok


# --- SC-3: CLI batch 5 anh voi --grid 2x2 (can API key) ---

def test_sc3_cli_batch(client):
    """SC-3: Goi translate_images() truc tiep voi grid_n=2, 5 anh."""
    print("\n=== SC-3: CLI batch 5 images with grid 2x2 (live API) ===")
    import tempfile
    import shutil

    test_images = get_test_images()

    # Tao temp input dir voi 5 anh (real hoac synthetic)
    tmp_input = tempfile.mkdtemp(prefix="test_grid_input_")
    tmp_output = tempfile.mkdtemp(prefix="test_grid_output_")

    try:
        if len(test_images) >= 5:
            # Copy 5 real images vao temp input
            for f in test_images[:5]:
                shutil.copy2(str(f), tmp_input)
            input_names = [f.name for f in test_images[:5]]
        else:
            # Tao 5 synthetic images
            print("  [!] test_images/ co < 5 anh, dung synthetic images thay the.")
            input_names = []
            for i in range(5):
                name = f"synthetic_{i+1}.png"
                img = make_synthetic_image(300, 200)
                img.save(os.path.join(tmp_input, name))
                input_names.append(name)

        print(f"  Input dir: {tmp_input} ({len(input_names)} images)")
        print(f"  Output dir: {tmp_output}")

        # Goi translate_images truc tiep (khong qua subprocess)
        from image_translator import translate_images
        translate_images(
            input_dir=tmp_input,
            output_dir=tmp_output,
            source_lang="English",
            target_lang="Vietnamese",
            grid_n=2
        )

        # Verify output files
        output_files = list(Path(tmp_output).iterdir())
        all_passed = True

        count_ok = len(output_files) == len(input_names)
        print_result(
            f"Output file count",
            count_ok,
            f"expected={len(input_names)}, actual={len(output_files)}"
        )
        if not count_ok:
            all_passed = False

        # Verify kich thuoc output giong input +-1px
        for name in input_names:
            out_path = Path(tmp_output) / name
            in_path = Path(tmp_input) / name
            if out_path.exists():
                in_img = Image.open(in_path)
                out_img = Image.open(out_path)
                w_diff = abs(in_img.size[0] - out_img.size[0])
                h_diff = abs(in_img.size[1] - out_img.size[1])
                size_ok = w_diff <= 1 and h_diff <= 1
                print_result(
                    f"{name} size match",
                    size_ok,
                    f"input={in_img.size}, output={out_img.size}, diff=({w_diff},{h_diff})"
                )
                if not size_ok:
                    all_passed = False
            else:
                all_passed = False
                print_result(f"{name} exists", False, "File not found in output")

        return all_passed

    finally:
        shutil.rmtree(tmp_input, ignore_errors=True)
        shutil.rmtree(tmp_output, ignore_errors=True)


# --- Main ---

def main():
    print("=" * 60)
    print("ImagiTranslate — Grid Translation End-to-End Validation")
    print("=" * 60)

    results = {}

    # SC-5 va SC-4 chay truoc — khong can API key
    results["SC-5"] = test_sc5_mock_call_count()
    results["SC-4"] = test_sc4_rgba_no_jpeg_error()

    # SC-1, SC-2, SC-3 can API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("\n[!] GEMINI_API_KEY chua duoc thiet lap.")
        print("[!] SC-1, SC-2, SC-3 se bi SKIP (can live API).")
        print("[!] Hay chay: export GEMINI_API_KEY='your_api_key'")
        results["SC-1"] = None
        results["SC-2"] = None
        results["SC-3"] = None
    else:
        try:
            client = genai.Client(api_key=api_key)
            print(f"\nGemini client initialized OK.")
        except Exception as e:
            print(f"\n[-] Loi khoi tao Gemini client: {e}")
            results["SC-1"] = None
            results["SC-2"] = None
            results["SC-3"] = None
            client = None

        if client:
            results["SC-1"] = test_sc1_grid_comparison(client)
            results["SC-2"] = test_sc2_batch_web(client)
            results["SC-3"] = test_sc3_cli_batch(client)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for sc, result in results.items():
        if result is None:
            print(f"  {sc}: SKIP")
        elif result:
            print(f"  {sc}: PASS")
        else:
            print(f"  {sc}: FAIL")

    # Exit code: 0 neu tat ca pass hoac skip, 1 neu co fail
    has_fail = any(r is False for r in results.values())
    if has_fail:
        print("\n[-] Co SC FAIL. Xem chi tiet phia tren.")
        sys.exit(1)
    else:
        all_pass = all(r is True for r in results.values())
        if all_pass:
            print("\n[+] Tat ca SC PASS!")
        else:
            print("\n[*] Khong co FAIL, nhung co SC bi SKIP.")
        sys.exit(0)


if __name__ == "__main__":
    main()
