import os
import io
import base64
import traceback
from flask import Flask, render_template, request, jsonify
from PIL import Image
from google import genai
from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS, translate_with_grid, verify_and_patch, VERIFY_MAX_PASSES

app = Flask(__name__)

# --- Constants ---
MAX_FILE_SIZE_MB = 10
UPSCALE_FACTOR = 2
UPSCALE_MAX_DIMENSION = 3000

app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE_MB * 1024 * 1024

def get_client(api_key):
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        print(f"Lỗi khởi tạo Gemini client: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/translate', methods=['POST'])
def translate_image():
    api_key = request.form.get('api_key')

    client = get_client(api_key)
    if not client:
        return jsonify({"error": "API Key Gemini không hợp lệ hoặc chưa được cung cấp."}), 401

    source_lang = request.form.get('source_lang', 'auto-detect')
    target_lang = request.form.get('target_lang')
    grid_size = request.form.get('grid_size', 'off')
    try:
        grid_n = int(grid_size.split('x')[0]) if grid_size != 'off' else 1
    except (ValueError, IndexError):
        grid_n = 1
        print(f"Cảnh báo: Giá trị grid_size không hợp lệ '{grid_size}', dùng mặc định: off")

    try:
        verify_passes = int(request.form.get('verify_passes', 0))
        verify_passes = max(0, min(verify_passes, VERIFY_MAX_PASSES))
    except (ValueError, TypeError):
        verify_passes = 0

    if not target_lang:
        return jsonify({"error": "Ngôn ngữ đích là bắt buộc."}), 400

    if 'image' not in request.files:
        return jsonify({"error": "Không có ảnh nào được cung cấp."}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "Chưa chọn file."}), 400

    try:
        img_bytes = file.read()
        base_image = Image.open(io.BytesIO(img_bytes))

        # Lưu kích thước gốc trước mọi xử lý — output sẽ được normalize về size này
        orig_size = base_image.size
        w, h = orig_size

        if base_image.mode in ('RGBA', 'P') and file.filename.lower().endswith(('.jpg', '.jpeg')):
            base_image = base_image.convert('RGB')

        # Scale up để Gemini nhìn rõ chữ nhỏ (bỏ qua nếu ảnh đã quá lớn)
        if max(w, h) * UPSCALE_FACTOR <= UPSCALE_MAX_DIMENSION:
            base_image = base_image.resize(
                (w * UPSCALE_FACTOR, h * UPSCALE_FACTOR),
                Image.LANCZOS
            )

        prompt = (
            f"This image may contain many small icons and UI elements with text. "
            f"Translate EVERY SINGLE piece of text from {source_lang} to {target_lang}. "
            "IMPORTANT: Do NOT skip any text, no matter how small, faint, or densely packed. "
            "This includes small labels under icons, tiny button text, corner labels, and any "
            "characters no matter how small they appear. "
            "Strictly preserve the exact original layout, colors, icon graphics, and visual style. "
            "Only the text characters should change — everything else must remain pixel-perfect."
        )

        result_pil_img = translate_with_grid(base_image, client, prompt, grid_n)

        if verify_passes > 0:
            result_pil_img = verify_and_patch(result_pil_img, client, target_lang, max_passes=verify_passes)

        # Normalize output về kích thước gốc — Gemini có thể trả về size khác
        result_pil_img = result_pil_img.resize(orig_size, Image.LANCZOS)

        img_byte_arr = io.BytesIO()
        result_pil_img.save(img_byte_arr, format='JPEG')
        img_byte_arr.seek(0)

        encoded_img = base64.b64encode(img_byte_arr.read()).decode('utf-8')

        return jsonify({
            "success": True,
            "image": f"data:image/jpeg;base64,{encoded_img}"
        })

    except Exception as e:
        print(f"Lỗi khi xử lý: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Lỗi máy chủ: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
