# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Codebase Search

**Luôn dùng MCP Auggie (`codebase-retrieval`) làm công cụ đầu tiên** khi cần tìm kiếm hoặc hiểu code. Auggie duy trì index real-time, chính xác hơn Grep/Glob/Read thủ công.

- Dùng Auggie khi: tìm function, hiểu luồng xử lý, tìm file liên quan, hỏi về cấu trúc
- Chỉ dùng Read/Grep/Glob khi: đọc file cụ thể đã biết path, hoặc Auggie không đủ chi tiết

## Development Commands

```bash
# Cài dependencies
pip install -r requirements.txt

# Chạy web app (http://localhost:5000)
python app.py

# CLI batch tool (dịch cả thư mục ảnh)
python image_translator.py --target-lang "Vietnamese"
python image_translator.py -i ./input -o ./output -s "English" -t "Vietnamese"

# Smoke test API (cần GEMINI_API_KEY env var)
python test_api.py

# Test OCR detector (offline, không cần API key)
python test_ocr.py
python test_ocr.py --integration
```

Không có test framework, linter, formatter, hay CI/CD.

## Architecture

Hai entry point độc lập dùng chung Gemini model:

```
Web (app.py)                          CLI (image_translator.py)
─────────────────────                 ─────────────────────────
POST /translate (multipart form)      GEMINI_API_KEY env var
  api_key từ form field                 genai.Client() auto-reads env
  genai.Client(api_key=key)
        │                                       │
        └──────────────┬────────────────────────┘
                       ▼
         PIL Image.open() + prompt string
         client.models.generate_content(
             model=GEMINI_MODEL,
             contents=[prompt, pil_image],   # prompt TRƯỚC ảnh — bắt buộc
             config=GenerateContentConfig(
                 response_modalities=['IMAGE', 'TEXT']
             )
         )
         [retry 3 lần, exponential backoff: 2s → 4s]
                       │
         response.candidates[0].content.parts[0]
           ├─ part.image        → PIL Image trực tiếp
           └─ part.inline_data  → Image.open(BytesIO(data))
                       │
         Web: save JPEG → base64 → JSON response
         CLI: save file giữ nguyên tên gốc
```

**Web routes:** `GET /` → index.html | `POST /translate` → JSON

**Frontend batch flow:** Files lưu trong `currentFiles[]` → sequential `fetch()` loop (không parallel — cố ý vì Flask dev server + rate limit) → side-by-side comparison UI.

## Key Patterns

### Gemini Image Generation — Gotchas Đã Xác Nhận

**⚠️ Thứ tự `contents` là bắt buộc: prompt TRƯỚC ảnh**
```python
# ✅ ĐÚNG — Gemini generate image
contents=[prompt, pil_image]

# ❌ SAI — Gemini trả về text mô tả (FinishReason.STOP, 1 text part)
contents=[pil_image, prompt]
```

**⚠️ `response_modalities` phải là `['IMAGE', 'TEXT']` (không phải `['IMAGE']`)**
```python
# ✅ ĐÚNG
response_modalities=['IMAGE', 'TEXT']

# ❌ SAI — Gemini trả FinishReason.NO_IMAGE, content=None
response_modalities=['IMAGE']
```

**⚠️ Prompt phải có explicit image output instruction**
- Thêm vào cuối prompt: `"Output the result as an image."`
- Không có câu này, Gemini dễ interpret task là "mô tả bản dịch" (text response)

**⚠️ `content` có thể là `None`**
- Khi `finish_reason=NO_IMAGE`, `candidate.content` là `None` (không có `.parts`)
- Luôn guard: `cand.content.parts if cand.content else []`

**Symptom table:**
| `contents` order | `response_modalities` | Kết quả |
|---|---|---|
| `[image, prompt]` | `['IMAGE', 'TEXT']` | Text description (STOP) — Gemini mô tả bản dịch |
| `[image, prompt]` | `['IMAGE']` | NO_IMAGE, content=None |
| `[prompt, image]` | `['IMAGE', 'TEXT']` | ✅ Image trả về qua `inline_data` |

### Retry Logic (giống nhau ở cả 2 file)
```python
retry_delay = RETRY_DELAY_SECONDS  # = 2
for attempt in range(MAX_RETRIES):  # = 3
    try:
        response = client.models.generate_content(...)
        if not (response and response.candidates and ...parts):
            raise Exception("empty response")  # empty = retryable
        break
    except Exception as e:
        if attempt < MAX_RETRIES - 1:
            time.sleep(retry_delay)
            retry_delay *= 2  # backoff: 2s → 4s
        else:
            # Web: return HTTP 500; CLI: response = None, skip file
```

### Dual Image Response Format
Gemini SDK trả image theo 2 format khác nhau tùy version — luôn kiểm tra cả hai:
```python
if hasattr(part, 'image') and part.image:
    result = part.image
elif hasattr(part, 'inline_data') and part.inline_data:
    result = Image.open(io.BytesIO(part.inline_data.data))
```

### RGBA Conversion — Bất đối xứng
- **`app.py`**: convert RGBA→RGB trên **input** (trước khi gửi Gemini), chỉ khi file là JPEG
- **`image_translator.py`**: convert RGBA→RGB trên **output** (trước khi lưu), chỉ khi file là JPEG
- PNG với alpha channel được gửi nguyên trạng — không convert

### API Key
- **Web**: gửi qua form POST field `api_key`, tạo `genai.Client(api_key=...)` mới mỗi request
- **CLI**: đọc từ `GEMINI_API_KEY` env var, dùng `genai.Client()` không argument

### Output Format
- **Web**: luôn xuất JPEG (kể cả input là PNG/WebP — mất alpha channel)
- **CLI**: giữ nguyên extension và tên file gốc

### File Upload Limit
10 MB/file — enforce cả server-side (`app.config['MAX_CONTENT_LENGTH']`) lẫn client-side JS.

## Constants (định nghĩa ở đầu mỗi file)
```python
GEMINI_MODEL = 'gemini-3.1-flash-image-preview'
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
MAX_FILE_SIZE_MB = 10        # chỉ app.py
VALID_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}  # chỉ image_translator.py
```

## Codebase Notes

- Model `gemini-3.1-flash-image-preview` (nickname: *Nano Banana 2*) là image generation model — **re-renders lại ảnh** với text đã dịch, không phải OCR + overlay
- **Quan trọng:** Model này yêu cầu prompt đứng trước ảnh trong `contents` và `response_modalities=['IMAGE', 'TEXT']` để trả về ảnh (xem "Gemini Image Generation — Gotchas" ở trên)
- Code ban đầu viết bằng tiếng Ý, đang được Việt hóa — một số comment cũ tiếng Ý còn sót trong `static/script.js` và `static/style.css`
- `test_api.py` có `from google.genai import types` nhưng không dùng (unused import)
- Batch processing cố ý sequential (không parallel) vì Flask dev server + API rate limits

### PaddleOCR (verify_and_patch)

`verify_and_patch()` trong `grid_translator.py` dùng **PaddleOCR** (local, offline) để detect chữ Chinese ideograph còn sót sau khi dịch — thay cho Gemini TEXT-only detection trước đây.

- Module: `ocr_detector.py` — expose `detect_cjk_bboxes(pil_image) → list[dict]`
- PaddleOCR lazy init lần đầu gọi (~200MB model, cache tại `~/.paddleocr/`)
- Chỉ detect Chinese ideograph (U+4E00–U+9FFF, U+3400–U+4DBF, U+F900–U+FAFF) — không detect kana/hangul
- Confidence threshold: `CJK_CONFIDENCE_THRESHOLD = 0.5`
- **Giới hạn đã xác nhận:** PaddleOCR miss chữ nghệ thuật/embossed 3D trên nền phức tạp (game icon artwork). Với sprite atlas, đây là hành vi bình thường — chỉ clean UI text mới detect được.

### Grid size recommendation

`--grid NxN` ảnh hưởng trực tiếp đến chất lượng dịch:

| Grid | Tile size (ảnh 1024×1024) | Phù hợp |
|------|--------------------------|---------|
| mặc định (1×1) | 1024×1024 | Ảnh đơn giản, ít text |
| `2x2` | 512×512 | Ảnh thông thường |
| `3x3` | 341×341 | Game UI screenshot |
| `4x4` | 256×256 | **Sprite atlas, ảnh text dày đặc** — recommended |

**Thực nghiệm trên `main_atlas.png` (1024×1024):**
- `1×1`: còn 2 vùng Chinese sau verify, nhiều icon text bị miss do Gemini xử lý toàn ảnh
- `4×4`: 0 vùng Chinese còn sót — Gemini dịch tốt hơn nhiều ở tile nhỏ 256×256px

<!-- GSD:project-start source:PROJECT.md -->
## Project

**ImagiTranslate**

ImagiTranslate là công cụ dịch thuật hình ảnh dùng Gemini AI để re-render lại ảnh với text đã được dịch — không phải OCR+overlay thông thường. Có hai entry point: web app (Flask) để dịch từng ảnh qua browser, và CLI tool để batch dịch cả thư mục. Mục tiêu chính là dịch ảnh game UI/screenshot đang bị bỏ sót chữ do Gemini không xử lý được hết text trong ảnh phức tạp.

**Core Value:** Mọi chữ trong ảnh phải được dịch — không bỏ sót, đặc biệt với game UI có nhiều text nhỏ, icon label, và các phần tử UI dày đặc.

### Constraints

- **Model**: Dùng `gemini-3.1-flash-image-preview` — không thay đổi model
- **Processing**: Sequential (không parallel) — Flask dev server + API rate limit
- **Output**: Web luôn xuất JPEG; CLI giữ nguyên extension gốc
- **File size**: Max 10MB/file
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Language & Runtime
- **Python 3.x** — Server-side language (Flask backend, CLI tools)
- **JavaScript (ES6+)** — Client-side (browser batch processing, file handling)
- **HTML5 / CSS3** — Template markup and styling
## Backend Framework
### Flask 3.0.0+
- **Purpose**: Lightweight WSGI web application framework
- **Usage**: RESTful HTTP API for image translation
- **Configuration**:
### Werkzeug 3.0.0+
- **Purpose**: WSGI utilities library (dependency of Flask)
- **Usage**: HTTP exception handling, request/response processing, file upload security
## Image Processing
### Pillow (PIL) 10.2.0+
- **Purpose**: Python Imaging Library for image manipulation
- **Usage**:
- **Image Processing Pipeline**:
## External API Client
### google-genai 0.2.2+
- **Purpose**: Google Generative AI SDK (Gemini integration)
- **Usage**:
- **Model**: `gemini-3.1-flash-image-preview` (Nano Banana 2 — image generation model, not OCR)
- **Response Handling**:
- **Retry Logic**:
## Frontend (Browser)
### HTML5 Document Structure
- **Bootstrap**: Semantic layout with glass-morphism design
- **Language support**: Vietnamese (localized UI)
- **Accessibility**: Form labels, ARIA roles implicit in semantic HTML
- **File input**: Accept MIME types `image/png`, `image/jpeg`, `image/webp`; multiple uploads enabled
### CSS3 Styling (`static/style.css`)
- **Design system**: Glass-morphism cards, gradient backgrounds, smooth animations
- **Fonts**: Google Fonts — Outfit (headings), Inter (body text)
- **Layout**: Flexbox + Grid for responsive design
- **Dark mode**: CSS variables for theming (`--bg-*`, `--text-*`, `--accent-*`)
- **Responsive**: Mobile-first, viewport meta tag
### JavaScript Runtime (`static/script.js`)
- **Environment**: Browser (Chrome, Firefox, Safari, Edge modern versions)
- **DOM API**: Standard event listeners, `querySelector`, `fetch()`
- **Features**:
- **State Management**: `currentFiles[]` array, results accumulation
## CLI Tool
### argparse (Python stdlib)
- **Purpose**: Command-line argument parser
- **Options**:
- **Behavior**: Sequential processing loop over all images in input directory
### pathlib.Path (Python stdlib)
- **Purpose**: Cross-platform file system operations
- **Usage**: Directory traversal, file iteration, path validation
## Environment Variables
- **`GEMINI_API_KEY`** (CLI only)
## Testing & Validation
### test_api.py (Smoke Test)
- **Purpose**: Verify Gemini API connectivity
- **Execution**: `python test_api.py` (requires `GEMINI_API_KEY`)
- **Process**:
- **Unused import**: `from google.genai import types` (legacy code)
## Development Server
- **Framework**: Flask development server
- **Address**: `http://0.0.0.0:5000` (accessible from any network interface)
- **Debug Mode**: Disabled (`debug=False`)
- **WSGI Server**: Built-in Werkzeug WSGI server (suitable for development only)
## Configuration Files
- **`requirements.txt`** — Python dependencies (pip format)
- **`.gitignore`** — Git version control exclusions
- **`CLAUDE.md`** — Developer guidelines (code patterns, retry logic, asymmetric RGBA conversion notes)
## Summary Table
| Layer | Component | Version | Purpose |
|-------|-----------|---------|---------|
| Runtime | Python | 3.x | Server-side runtime |
| Backend | Flask | 3.0.0+ | Web framework |
| Backend | Werkzeug | 3.0.0+ | WSGI utilities |
| Image | Pillow | 10.2.0+ | Image I/O & manipulation |
| API | google-genai | 0.2.2+ | Gemini SDK |
| Frontend | HTML/CSS/JS | ES6+ | Browser UI |
| CLI | argparse | stdlib | CLI argument parsing |
| CLI | pathlib | stdlib | File operations |
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## 1. Python Conventions (app.py, image_translator.py, test_api.py)
### 1.1 Code Organization
- **Imports** at top (stdlib → third-party → local)
- **Constants** (uppercase with underscores) immediately after imports
- **Classes/Functions** defined after constants
- **Main entry point** in `if __name__ == "__main__"` block
### 1.2 Constants Definition
- `app.py`: `MAX_FILE_SIZE_MB = 10`
- `image_translator.py`: `VALID_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}`
### 1.3 Function Naming
- `get_client(api_key)` — returns client or None
- `translate_images(input_dir, output_dir, source_lang, target_lang)` — performs batch operation
- `handleFiles(files)` — JS pattern (camelCase in frontend)
- `updateGalleryUI()` — UI update functions use this pattern
### 1.4 Variable Naming
### 1.5 Docstrings
### 1.6 Comments
- Vietnamese for business logic explanation
- English for technical details
### 1.7 Error Handling
### 1.8 Image Processing Patterns
- **`app.py`**: Convert RGBA→RGB on **input** (before sending to Gemini)
- **`image_translator.py`**: Convert RGBA→RGB on **output** (before saving)
### 1.9 API Client Initialization
### 1.10 Response Handling — Dual Format
## 2. Frontend Conventions (JavaScript & CSS)
### 2.1 JavaScript Patterns
- Event listeners: `handleFiles()`, `updateGalleryUI()`, `enableTranslateBtn()`
- State: `currentFiles[]`, `successCount`
- Helper: `preventDefaults()`, `showError()`, `appendResultBox()`
### 2.2 CSS Conventions
### 2.3 Animation Patterns
## 3. HTML Conventions (index.html)
### 3.1 Structure
### 3.2 Accessibility & Meta
## 4. Project-Specific Patterns
### 4.1 Multilingual Support (Vietnamese Primary)
- Error messages: `"Lỗi khởi tạo Gemini client: {e}"`
- Prompts: `"Bắt đầu dịch hàng loạt..."`
- UI labels: `"Từ:", "Sang:", "Dịch Ảnh"`
### 4.2 Batch Processing
- Sequential file processing
- Per-file error handling
- Progress indicators with `[*]`, `[+]`, `[-]` prefixes
- Sequential `fetch()` loops (intentional — no parallelism)
- Real-time progress updates
- Side-by-side comparison UI
### 4.3 Output Formats
- Input: multipart form (image file + lang + api_key)
- Output: JSON with base64-encoded JPEG
- Input: directory of images
- Output: same directory with translated images (preserve filename & extension)
### 4.4 Flask Configuration
- **Debug mode:** OFF (production-safe)
- **Host:** 0.0.0.0 (accessible from any interface)
- **Port:** 5000 (Flask default)
### 4.5 Import Statements by Purpose
## 5. Testing & Quality (Current State)
### 5.1 No Automated Testing Infrastructure
- **Test framework:** None
- **Linter:** None (no style enforcement)
- **Formatter:** None (manual formatting)
- **CI/CD:** None (no automated checks)
### 5.2 Manual Testing
- Creates dummy 100x100 red image
- Sends to Gemini with simple prompt
- Prints success/error to console
- Purpose: Verify API key and SDK connectivity
## 6. Known Inconsistencies & Patterns
### 6.1 Comment Language Mix
- **script.js:** Italian comments alongside Vietnamese/English
- **style.css:** Minimal comments, mostly English/Italian descriptors
### 6.2 Asymmetric RGBA Handling
- `app.py`: RGBA→RGB conversion on **input** (only JPEG files)
- `image_translator.py`: RGBA→RGB conversion on **output** (only JPEG files)
- PNG with alpha channel: Passed as-is (no conversion)
### 6.3 Prompt Template Reuse
- `app.py` lines 73-81
- `image_translator.py` lines 43-51
## 7. Summary Table
| Aspect | Convention | Location |
|--------|-----------|----------|
| **Constants** | ALL_CAPS, module-level | Top of file after imports |
| **Functions** | snake_case, imperative | After constants |
| **Variables** | snake_case, descriptive | Scope-appropriate |
| **Comments** | Vietnamese primary, section-marked | Inline or above code |
| **Docstrings** | Single-line Vietnamese | Function definitions |
| **Error handling** | Try-except with retry logic | Retry loops & request handlers |
| **DOM elements** | camelCase IDs, class-based | HTML elements |
| **CSS classes** | kebab-case, BEM-inspired | Style sheets |
| **Images** | Base64 web, native CLI | Output format-specific |
| **Batch processing** | Sequential, intentional | Both web & CLI |
| **API keys** | Per-request (web), env (CLI) | Client initialization |
## 8. Code Quality Observations
### Strengths
### Areas for Improvement
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## System Overview
- **Web**: Flask REST API for interactive batch processing via browser
- **CLI**: Command-line batch tool for server-side automation
## Core Architecture
### Shared Model Layer
```
```
### Entry Points
#### 1. **Web Application** (`app.py`)
- **Framework**: Flask 3.0+
- **Routes**:
- **Request Format**: Multipart form
- **Response Format**: JSON
- **Error Handling**: HTTP 500 on Gemini failure (after 3 retries)
#### 2. **CLI Application** (`image_translator.py`)
- **Invocation**: `python image_translator.py -i INPUT -o OUTPUT -s SOURCE -t TARGET`
- **Arguments**:
- **API Auth**: Reads `GEMINI_API_KEY` environment variable
- **Behavior**:
## Key Technical Patterns
### Dual Image Response Format (Gemini SDK Variance)
```python
```
### Retry Strategy with Exponential Backoff
```python
```
### RGBA→RGB Conversion (Asymmetric)
- **Web** (`app.py`):
- **CLI** (`image_translator.py`):
### Image Dimension Handling
- Applied to both entry points identically
- Factor: 2x (multiply width and height)
- Condition: `max(w, h) * UPSCALE_FACTOR ≤ 3000` (skip if already large)
- Purpose: Helps Gemini recognize small text
- Applied to both entry points identically
- Resize result back to original input dimensions using LANCZOS filter
- Handles: Gemini may return different size than input
## Data Flow Diagram
### Web Flow (Request → Response)
```
```
### CLI Flow (File System → File System)
```
```
## Constants (Version Configuration)
### Shared Across Both Entry Points
```python
```
### Web-Only (`app.py`)
```python
```
### CLI-Only (`image_translator.py`)
```python
```
## API Key Management
### Web (`app.py`)
- **Per-request**: User provides API key via form field
- **Scope**: Single translation request
- **Security**: Key transmitted in POST body; not stored
- **Client creation**: `genai.Client(api_key=key)` per request
### CLI (`image_translator.py`)
- **Environment variable**: `GEMINI_API_KEY`
- **Scope**: All files in batch
- **Security**: Read from OS environment
- **Client creation**: `genai.Client()` reads env auto
## Prompt Pattern
```python
```
- Emphasizes completeness (no skipped text)
- Warns against text-in-icons edge cases
- Enforces layout/color preservation (critical for UI/design assets)
- Targets Gemini's image regeneration capability
## Client Dependencies
### Core
- **google-genai** (≥0.2.2): Gemini API client
- **pillow** (≥10.2.0): Image processing (open, resize, convert)
- **flask** (≥3.0.0): Web framework [web only]
- **werkzeug** (≥3.0.0): WSGI utilities [web only]
### No External Utility Dependencies
- No image concatenation (static/script.js handles UI comparison)
- No database (stateless)
- No cache (fresh generation per request)
## Processing Characteristics
### Image Generation Model
- **Model**: `gemini-3.1-flash-image-preview` (Nano Banana 2)
- **Behavior**: **Re-renders entire image**, not OCR+overlay
- **Implication**:
### Batch Processing Philosophy
- **Web**: Sequential `fetch()` calls by JS (no parallelism)
- **CLI**: Sequential loop in Python (no thread pool)
- **Reason**: Flask dev server stability + Gemini API rate limits
### Output Format Asymmetry
- **Web**: Always JPEG (even if input PNG) → loses alpha channel
- **CLI**: Preserves original extension and format
## Error Handling
### Web (`app.py`)
- **Invalid API key**: HTTP 401
- **Missing/invalid parameters**: HTTP 400
- **Gemini failure (after retries)**: HTTP 500 with error message
- **All errors**: Return JSON with `"error"` field
### CLI (`image_translator.py`)
- **Missing `GEMINI_API_KEY`**: Print error + exit
- **File processing error**: Print to stdout, skip file, continue
- **Gemini failure (after retries)**: Skip file, continue
- **All files failed**: Print summary, exit gracefully
## Architecture Summary
| Aspect | Web | CLI |
|--------|-----|-----|
| **Entry** | POST /translate | Command line |
| **Auth** | Form field per-request | GEMINI_API_KEY env |
| **Input** | Single/multiple via form | Directory scan |
| **Output Format** | Base64 JSON | File system |
| **Parallelism** | None (sequential fetch) | None (sequential loop) |
| **Output Format** | Always JPEG | Preserve extension |
| **Error Recovery** | HTTP response | Skip file + continue |
- Gemini model API
- Retry logic + backoff
- Image upscaling
- Dimension normalization
- RGBA→RGB handling pattern
- Prompt structure
## Testing / Debugging
### Smoke Test (`test_api.py`)
- Creates dummy 100×100 red image
- Attempts `generate_content()` with test prompt
- Validates API connectivity and model availability
- Requires `GEMINI_API_KEY` env var
### Development
- Web: `python app.py` (Flask debug mode disabled for stability)
- CLI: `python image_translator.py -t Vietnamese` (requires input directory)
- Both: Set `GEMINI_API_KEY` before running
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
