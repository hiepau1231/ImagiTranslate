import os
import io
import time
import argparse
from pathlib import Path
from PIL import Image
from google import genai

GEMINI_MODEL = 'gemini-3.1-flash-image-preview'
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
VALID_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
UPSCALE_FACTOR = 2
UPSCALE_MAX_DIMENSION = 3000

def translate_images(input_dir: str, output_dir: str, source_lang: str, target_lang: str):
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

            orig_size = base_image.size
            w, h = orig_size
            if max(w, h) * UPSCALE_FACTOR <= UPSCALE_MAX_DIMENSION:
                base_image = base_image.resize(
                    (w * UPSCALE_FACTOR, h * UPSCALE_FACTOR),
                    Image.LANCZOS
                )

            retry_delay = RETRY_DELAY_SECONDS
            response = None

            for attempt in range(MAX_RETRIES):
                try:
                    response = client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=[base_image, prompt]
                    )
                    if response and response.candidates and response.candidates[0].content.parts:
                        break
                    else:
                        raise Exception("Phản hồi trống hoặc không hợp lệ")
                except Exception as e:
                    print(f"    [!] Lần thử {attempt + 1}/{MAX_RETRIES} thất bại cho {img_file.name}: {e}")
                    if attempt < MAX_RETRIES - 1:
                        print(f"    [*] Thử lại sau {retry_delay} giây...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        print(f"    [-] Thất bại sau {MAX_RETRIES} lần thử cho {img_file.name}.")
                        response = None

            if response and response.candidates and response.candidates[0].content.parts:
                out_file_path = output_path / img_file.name
                part = response.candidates[0].content.parts[0]

                if hasattr(part, 'image') and part.image:
                    result_image = part.image
                elif hasattr(part, 'inline_data') and part.inline_data:
                    result_image = Image.open(io.BytesIO(part.inline_data.data))
                else:
                    print(f"    [-] Lỗi: Model không trả về ảnh hợp lệ cho {img_file.name}.")
                    continue

                # Scale về kích thước gốc
                result_image = result_image.resize(orig_size, Image.LANCZOS)

                if img_file.suffix.lower() in {'.jpg', '.jpeg'} and result_image.mode in ('RGBA', 'P'):
                    result_image = result_image.convert('RGB')

                result_image.save(out_file_path)
                print(f"    [+] Đã lưu thành công: {out_file_path}")
            else:
                print(f"    [-] Lỗi: Không nhận được phản hồi hợp lệ cho {img_file.name}.")

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

    args = parser.parse_args()

    translate_images(args.input, args.output, args.source_lang, args.target_lang)
