import os
import re
import sys
import argparse
from pathlib import Path
from PIL import Image
from google import genai
from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS, translate_with_grid, verify_and_patch

VALID_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
UPSCALE_FACTOR = 2
UPSCALE_MAX_DIMENSION = 3000

def translate_images(input_dir: str, output_dir: str, source_lang: str, target_lang: str, grid_n: int = 1, verify_passes: int = 0):
    """Dịch văn bản trong ảnh từ ngôn ngữ nguồn sang ngôn ngữ đích dùng Gemini."""
    if not os.environ.get("GEMINI_API_KEY"):
        print("Lỗi: Biến môi trường GEMINI_API_KEY chưa được thiết lập.")
        print("Hãy chạy: export GEMINI_API_KEY='your_api_key'")
        return

    try:
        client = genai.Client()
    except Exception as e:
        print(f"Lỗi khởi tạo Gemini client: {e}")
        return

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    images_found = [f for f in input_path.iterdir() if f.is_file() and f.suffix.lower() in VALID_EXTENSIONS]

    if not images_found:
        print(f"Không tìm thấy ảnh nào trong '{input_dir}'.")
        print(f"Định dạng được hỗ trợ: {', '.join(VALID_EXTENSIONS)}")
        return

    print(f"Tìm thấy {len(images_found)} ảnh.")
    print(f"Bắt đầu dịch hàng loạt (từ '{source_lang}' sang '{target_lang}')...\n")

    prompt = (
        f"This image may contain many small icons and UI elements with text. "
        f"Translate EVERY SINGLE piece of text from {source_lang} to {target_lang}. "
        "IMPORTANT: Do NOT skip any text, no matter how small, faint, or densely packed. "
        "This includes small labels under icons, tiny button text, corner labels, and any "
        "characters no matter how small they appear. "
        "Strictly preserve the exact original layout, colors, icon graphics, and visual style. "
        "Only the text characters should change — everything else must remain pixel-perfect."
    )

    for img_file in images_found:
        print(f"[*] Đang xử lý: {img_file.name} ...")

        try:
            base_image = Image.open(img_file)

            # Lưu kích thước gốc trước mọi xử lý — output sẽ được normalize về size này
            orig_size = base_image.size
            w, h = orig_size
            # Scale up để Gemini nhìn rõ chữ nhỏ (bỏ qua nếu ảnh đã quá lớn)
            if max(w, h) * UPSCALE_FACTOR <= UPSCALE_MAX_DIMENSION:
                base_image = base_image.resize(
                    (w * UPSCALE_FACTOR, h * UPSCALE_FACTOR),
                    Image.LANCZOS
                )

            out_file_path = output_path / img_file.name
            result_image = translate_with_grid(base_image, client, prompt, grid_n)

            if verify_passes > 0:
                result_image = verify_and_patch(result_image, client, target_lang, max_passes=verify_passes)

            # Normalize output về kích thước gốc — Gemini có thể trả về size khác
            result_image = result_image.resize(orig_size, Image.LANCZOS)

            if img_file.suffix.lower() in {'.jpg', '.jpeg'} and result_image.mode in ('RGBA', 'P'):
                result_image = result_image.convert('RGB')

            result_image.save(out_file_path)
            print(f"    [+] Đã lưu thành công: {out_file_path}")

        except Exception as e:
            print(f"    [!] Lỗi khi xử lý {img_file.name}: {e}")

    print("\nDịch hàng loạt hoàn tất!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Dịch hàng loạt văn bản trong ảnh, giữ nguyên layout, dùng Gemini 3.1 Flash Image Preview."
    )
    parser.add_argument("-i", "--input", default="./input", help="Thư mục chứa ảnh gốc. Mặc định: ./input")
    parser.add_argument("-o", "--output", default="./output", help="Thư mục lưu ảnh đã dịch. Mặc định: ./output")
    parser.add_argument("-s", "--source-lang", default="auto-detect", help="Ngôn ngữ nguồn (vd: 'English'). Mặc định: auto-detect")
    parser.add_argument("-t", "--target-lang", required=True, help="Ngôn ngữ đích (vd: 'Vietnamese'). Bắt buộc.")
    parser.add_argument(
        "--grid",
        default=None,
        help="Kích thước lưới chia ảnh, ví dụ: --grid 2x2, --grid 3x3. Mặc định: không chia (xử lý toàn bộ ảnh). Hợp lệ: 1x1-4x4."
    )
    parser.add_argument(
        "--verify-passes",
        type=int,
        default=0,
        dest="verify_passes",
        help="Số vòng kiểm tra và vá chữ CJK còn sót (mặc định: 0 = tắt). Ví dụ: --verify-passes 3"
    )

    args = parser.parse_args()

    # Parse và validate --grid
    grid_n = 1
    if args.grid is not None:
        match = re.fullmatch(r'([1-4])x([1-4])', args.grid)
        if not match or match.group(1) != match.group(2):
            print("Lỗi: --grid phải có định dạng NxN (N từ 1-4), ví dụ: --grid 2x2")
            sys.exit(1)
        grid_n = int(match.group(1))

    translate_images(args.input, args.output, args.source_lang, args.target_lang, grid_n, args.verify_passes)
