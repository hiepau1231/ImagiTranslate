import os
import io
import time
import base64
from flask import Flask, render_template, request, jsonify
from PIL import Image
from google import genai

app = Flask(__name__)

# --- Constants ---
GEMINI_MODEL = 'gemini-3.1-flash-image-preview'
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
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

        if base_image.mode in ('RGBA', 'P') and file.filename.lower().endswith(('.jpg', '.jpeg')):
            base_image = base_image.convert('RGB')

        # Scale up để Gemini nhìn rõ chữ nhỏ
        orig_size = base_image.size
        w, h = orig_size
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
                    raise Exception("Phản hồi trống hoặc không hợp lệ từ model")
            except Exception as e:
                print(f"Lần thử {attempt + 1}/{MAX_RETRIES} thất bại: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    return jsonify({"error": f"Gemini xử lý thất bại sau {MAX_RETRIES} lần thử. Lỗi: {e}"}), 500

        part = response.candidates[0].content.parts[0]

        if hasattr(part, 'image') and part.image:
            result_pil_img = part.image
        elif hasattr(part, 'inline_data') and part.inline_data:
            result_pil_img = Image.open(io.BytesIO(part.inline_data.data))
        else:
            return jsonify({"error": "Gemini không trả về ảnh hợp lệ."}), 500

        # Scale về kích thước gốc
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
        return jsonify({"error": f"Lỗi máy chủ: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
