# ImagiTranslate Architecture

## System Overview

**ImagiTranslate** is a dual-entry image translation system that uses Google Gemini's image generation model to re-render images with translated text. It does NOT perform OCR+overlay; instead, Gemini regenerates the entire image with translated text while preserving layout, colors, and visual style.

Two independent entry points share the same Gemini integration:
- **Web**: Flask REST API for interactive batch processing via browser
- **CLI**: Command-line batch tool for server-side automation

---

## Core Architecture

### Shared Model Layer
Both entry points use the **same underlying API and retry logic**:

```
Input Image (PIL)
    ↓
[Scale up by 2x if small (max 3000px)]
    ↓
Client.models.generate_content(
    model='gemini-3.1-flash-image-preview',
    contents=[pil_image, prompt]
)
    ↓
Parse response (image from part.image or part.inline_data)
    ↓
Resize to original dimensions (Gemini may return different size)
    ↓
Output (JPEG web / preserve format CLI)
```

### Entry Points

#### 1. **Web Application** (`app.py`)
- **Framework**: Flask 3.0+
- **Routes**:
  - `GET /` → Render `templates/index.html`
  - `POST /translate` → Accept form data (image + metadata), return JSON
- **Request Format**: Multipart form
  - `image` (File): PNG, JPEG, WebP, 10 MB max
  - `api_key` (String): Gemini API key passed per-request
  - `source_lang` (String): Auto-detect or specific language
  - `target_lang` (String): Required
- **Response Format**: JSON
  ```json
  {
    "success": true,
    "image": "data:image/jpeg;base64,..."
  }
  ```
- **Error Handling**: HTTP 500 on Gemini failure (after 3 retries)

#### 2. **CLI Application** (`image_translator.py`)
- **Invocation**: `python image_translator.py -i INPUT -o OUTPUT -s SOURCE -t TARGET`
- **Arguments**:
  - `-i, --input`: Input directory (default: `./input`)
  - `-o, --output`: Output directory (default: `./output`)
  - `-s, --source-lang`: Source language (default: `auto-detect`)
  - `-t, --target-lang`: Target language (required)
- **API Auth**: Reads `GEMINI_API_KEY` environment variable
- **Behavior**:
  - Discovers all `.png`, `.jpg`, `.jpeg`, `.webp` files in input directory
  - Processes sequentially (not parallel for stability + rate limits)
  - Preserves original filename and extension
  - Skips failed files, continues with rest

---

## Key Technical Patterns

### Dual Image Response Format (Gemini SDK Variance)
The Gemini SDK can return images in two formats depending on version. Code checks **both**:

```python
if hasattr(part, 'image') and part.image:
    result = part.image  # PIL Image object directly
elif hasattr(part, 'inline_data') and part.inline_data:
    result = Image.open(io.BytesIO(part.inline_data.data))  # Bytes wrapper
```

**Both files implement this identically** — mandatory for compatibility.

### Retry Strategy with Exponential Backoff
Identical in both entry points:

```python
retry_delay = RETRY_DELAY_SECONDS  # = 2 seconds
for attempt in range(MAX_RETRIES):  # = 3
    try:
        response = client.models.generate_content(...)
        # Validate response has an image
        parts = response.candidates[0].content.parts
        has_image = any(
            (hasattr(p, 'image') and p.image) or
            (hasattr(p, 'inline_data') and p.inline_data)
            for p in parts
        )
        if has_image:
            break
        else:
            raise Exception("Response missing image")
    except Exception as e:
        if attempt < MAX_RETRIES - 1:
            time.sleep(retry_delay)
            retry_delay *= 2  # 2s → 4s → 8s
        else:
            # Final failure: return error
```

**Empty/text-only responses are treated as retryable errors.**

### RGBA→RGB Conversion (Asymmetric)
Handling differs between web and CLI to align with output format:

- **Web** (`app.py`):
  - **Timing**: On input (before sending to Gemini)
  - **Trigger**: File is JPEG format AND image mode is RGBA/P
  - **Reason**: Web always outputs JPEG; preserve alpha elsewhere

- **CLI** (`image_translator.py`):
  - **Timing**: On output (after receiving from Gemini)
  - **Trigger**: File is JPEG format AND result mode is RGBA/P
  - **Reason**: Preserve format during transmission; normalize at save

**PNG with alpha channel**: Both pass through unchanged (no conversion).

### Image Dimension Handling
**Upscaling (Input)**:
- Applied to both entry points identically
- Factor: 2x (multiply width and height)
- Condition: `max(w, h) * UPSCALE_FACTOR ≤ 3000` (skip if already large)
- Purpose: Helps Gemini recognize small text

**Normalization (Output)**:
- Applied to both entry points identically
- Resize result back to original input dimensions using LANCZOS filter
- Handles: Gemini may return different size than input

---

## Data Flow Diagram

### Web Flow (Request → Response)
```
User Browser
    ↓ (drag-drop or upload)
JS: static/script.js
    ├─ Validate: image type, size (10MB)
    ├─ Build FormData: image + langs + api_key
    └─ Sequential fetch() loop for each file
        ↓
Flask: POST /translate
    ├─ Parse form (api_key, langs, file)
    ├─ Load PIL Image from bytes
    ├─ RGBA→RGB conversion (if JPEG + alpha)
    ├─ Scale up 2x (if small)
    └─ Call Gemini API (with retry)
        ↓
Gemini: generate_content
    └─ Returns re-rendered image with translated text
        ↓
Flask: Normalize size + encode base64 → JSON
    ↓
JS: Display side-by-side comparison (before/after)
    └─ Download button per image
```

### CLI Flow (File System → File System)
```
Command line:
python image_translator.py -i ./input -o ./output -s English -t Vietnamese

    ↓ (read GEMINI_API_KEY env var)
Main: translate_images()
    ├─ List files: *.png, *.jpg, *.jpeg, *.webp
    └─ For each file (sequential):
        ├─ Load PIL Image
        ├─ Scale up 2x (if small)
        └─ Call Gemini API (with retry)
            ↓
        Gemini: generate_content
            └─ Returns re-rendered image
            ↓
        Normalize size + RGBA→RGB (if JPEG)
        ↓
        Save to output directory (same filename/extension)
        └─ Print status: success or error
```

---

## Constants (Version Configuration)

### Shared Across Both Entry Points
```python
GEMINI_MODEL = 'gemini-3.1-flash-image-preview'  # Model name
MAX_RETRIES = 3                                    # Retry attempts
RETRY_DELAY_SECONDS = 2                            # Initial backoff (exponential)
UPSCALE_FACTOR = 2                                 # Pre-translation scale
UPSCALE_MAX_DIMENSION = 3000                       # Scale limit
```

### Web-Only (`app.py`)
```python
MAX_FILE_SIZE_MB = 10           # File upload limit
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE_MB * 1024 * 1024
```

### CLI-Only (`image_translator.py`)
```python
VALID_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}  # Supported formats
```

---

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

---

## Prompt Pattern

Both entry points use the **identical prompt structure**:

```python
prompt = (
    f"This image may contain many small icons and UI elements with text. "
    f"Translate EVERY SINGLE piece of text from {source_lang} to {target_lang}. "
    "IMPORTANT: Do NOT skip any text, no matter how small, faint, or densely packed. "
    "This includes small labels under icons, tiny button text, corner labels, and any "
    "characters no matter how small they appear. "
    "Strictly preserve the exact original layout, colors, icon graphics, and visual style. "
    "Only the text characters should change — everything else must remain pixel-perfect."
)
```

**Why this prompt?**
- Emphasizes completeness (no skipped text)
- Warns against text-in-icons edge cases
- Enforces layout/color preservation (critical for UI/design assets)
- Targets Gemini's image regeneration capability

---

## Client Dependencies

### Core
- **google-genai** (≥0.2.2): Gemini API client
- **pillow** (≥10.2.0): Image processing (open, resize, convert)
- **flask** (≥3.0.0): Web framework [web only]
- **werkzeug** (≥3.0.0): WSGI utilities [web only]

### No External Utility Dependencies
- No OCR library (Gemini handles)
- No image concatenation (static/script.js handles UI comparison)
- No database (stateless)
- No cache (fresh generation per request)

---

## Processing Characteristics

### Image Generation Model
- **Model**: `gemini-3.1-flash-image-preview` (Nano Banana 2)
- **Behavior**: **Re-renders entire image**, not OCR+overlay
- **Implication**:
  - Regenerates all visual content
  - May alter anti-aliasing, font rendering slightly
  - Preserves overall design intent, not pixel-perfect accuracy
  - Great for icons/UI; less ideal for photographs

### Batch Processing Philosophy
- **Web**: Sequential `fetch()` calls by JS (no parallelism)
- **CLI**: Sequential loop in Python (no thread pool)
- **Reason**: Flask dev server stability + Gemini API rate limits

### Output Format Asymmetry
- **Web**: Always JPEG (even if input PNG) → loses alpha channel
- **CLI**: Preserves original extension and format

---

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

---

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

Both share:
- Gemini model API
- Retry logic + backoff
- Image upscaling
- Dimension normalization
- RGBA→RGB handling pattern
- Prompt structure

---

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
