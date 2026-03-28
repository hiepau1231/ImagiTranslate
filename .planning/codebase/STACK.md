# Technology Stack

## Language & Runtime

- **Python 3.x** — Server-side language (Flask backend, CLI tools)
- **JavaScript (ES6+)** — Client-side (browser batch processing, file handling)
- **HTML5 / CSS3** — Template markup and styling

## Backend Framework

### Flask 3.0.0+
- **Purpose**: Lightweight WSGI web application framework
- **Usage**: RESTful HTTP API for image translation
  - `GET /` — Serves `index.html` template
  - `POST /translate` — Accepts multipart form-data (image, API key, language options)
- **Configuration**:
  - `MAX_CONTENT_LENGTH` = 10 MB (file upload limit)
  - Debug mode: OFF in production (`debug=False`)
  - Binds to `0.0.0.0:5000` for network access

### Werkzeug 3.0.0+
- **Purpose**: WSGI utilities library (dependency of Flask)
- **Usage**: HTTP exception handling, request/response processing, file upload security

## Image Processing

### Pillow (PIL) 10.2.0+
- **Purpose**: Python Imaging Library for image manipulation
- **Usage**:
  - `Image.open()` — Load images from file uploads or byte streams
  - `.resize()` — Upscale (2x) before Gemini processing for text clarity; normalize output back to original dimensions
  - `.convert()` — RGBA ↔ RGB conversion (asymmetric: input in web, output in CLI)
  - `.save()` — Export JPEG/PNG/WebP with format preservation
  - Supported formats: PNG, JPG/JPEG, WebP (CLI); JPEG output only (Web)
- **Image Processing Pipeline**:
  - Load original → Save original dimensions → Upscale 2x (if under 3000px max dimension)
  - Send to Gemini → Retrieve response → Normalize to original size
  - Convert color mode if needed (RGBA→RGB for JPEG output)

## External API Client

### google-genai 0.2.2+
- **Purpose**: Google Generative AI SDK (Gemini integration)
- **Usage**:
  - `genai.Client(api_key=...)` — Web: per-request client initialization from form field
  - `genai.Client()` — CLI: auto-reads `GEMINI_API_KEY` environment variable
  - `client.models.generate_content()` — Send PIL Image + text prompt to Gemini 3.1 Flash
- **Model**: `gemini-3.1-flash-image-preview` (Nano Banana 2 — image generation model, not OCR)
- **Response Handling**:
  - Check `response.candidates[0].content.parts[0]` for image
  - Handle dual response formats:
    - `part.image` — Direct PIL Image object
    - `part.inline_data.data` — Byte stream → wrap in `BytesIO()` → `Image.open()`
- **Retry Logic**:
  - MAX_RETRIES = 3, RETRY_DELAY_SECONDS = 2 (exponential backoff: 2s → 4s → 8s)
  - Retryable conditions: empty response, text-only response (no image)

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
  - Drag-and-drop file upload
  - Client-side validation (file type, size ≤ 10 MB)
  - Batch processing: sequential `fetch()` loop (not parallel — intentional for API rate limits)
  - Image preview gallery (before translation)
  - Results comparison UI (before ↔ after side-by-side)
  - Base64 encoding for JPEG response display
- **State Management**: `currentFiles[]` array, results accumulation

## CLI Tool

### argparse (Python stdlib)
- **Purpose**: Command-line argument parser
- **Options**:
  - `-i, --input` — Source directory (default: `./input`)
  - `-o, --output` — Output directory (default: `./output`)
  - `-s, --source-lang` — Source language (default: `auto-detect`)
  - `-t, --target-lang` — Target language (required)
- **Behavior**: Sequential processing loop over all images in input directory

### pathlib.Path (Python stdlib)
- **Purpose**: Cross-platform file system operations
- **Usage**: Directory traversal, file iteration, path validation

## Environment Variables

- **`GEMINI_API_KEY`** (CLI only)
  - Required for `image_translator.py` execution
  - Read via `os.environ.get("GEMINI_API_KEY")`
  - Web app: API key sourced from form POST field instead

## Testing & Validation

### test_api.py (Smoke Test)
- **Purpose**: Verify Gemini API connectivity
- **Execution**: `python test_api.py` (requires `GEMINI_API_KEY`)
- **Process**:
  - Create dummy red 100×100 RGB image
  - Send to Gemini with translation prompt
  - Print response (validation only, no output file)
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
