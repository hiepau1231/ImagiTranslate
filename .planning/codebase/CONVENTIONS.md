# Code Conventions & Patterns

**Project:** ImagiTranslate
**Date:** 2026-03-29
**Status:** Active (no linter, formatter, or CI/CD)

---

## 1. Python Conventions (app.py, image_translator.py, test_api.py)

### 1.1 Code Organization

**File Structure Pattern:**
- **Imports** at top (stdlib → third-party → local)
- **Constants** (uppercase with underscores) immediately after imports
- **Classes/Functions** defined after constants
- **Main entry point** in `if __name__ == "__main__"` block

**Example from `app.py`:**
```python
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
```

**Example from `image_translator.py`:**
```python
import os
import io
import time
import argparse
from pathlib import Path
from PIL import Image
from google import genai

GEMINI_MODEL = 'gemini-3.1-flash-image-preview'
MAX_RETRIES = 3
# ... then functions, then if __name__ == "__main__"
```

### 1.2 Constants Definition

**Location:** Top of each file after imports
**Convention:** ALL_CAPS with underscores
**Scope:** Module-level (not class-level)

**Shared Constants (defined in both files):**
```python
GEMINI_MODEL = 'gemini-3.1-flash-image-preview'
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
UPSCALE_FACTOR = 2
UPSCALE_MAX_DIMENSION = 3000
```

**Unique Constants:**
- `app.py`: `MAX_FILE_SIZE_MB = 10`
- `image_translator.py`: `VALID_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}`

### 1.3 Function Naming

**Pattern:** `snake_case`
**Convention:** Imperative verbs for clear intent

**Conventions observed:**
- `get_client(api_key)` — returns client or None
- `translate_images(input_dir, output_dir, source_lang, target_lang)` — performs batch operation
- `handleFiles(files)` — JS pattern (camelCase in frontend)
- `updateGalleryUI()` — UI update functions use this pattern

### 1.4 Variable Naming

**Scope-based convention:**
```
Global constants        → CONSTANT_NAME
Module-level vars       → variable_name (rare in this codebase)
Loop counters           → i, attempt (short for iteration)
Config/state vars       → descriptive_name
DOM/API references      → descriptive_name (e.g., baseImage, origSize)
```

**Examples from code:**
```python
# app.py - Retry loop
retry_delay = RETRY_DELAY_SECONDS
for attempt in range(MAX_RETRIES):  # attempt = loop counter

# image_translator.py - Image processing
base_image = Image.open(img_file)
orig_size = base_image.size  # preserved size state
w, h = orig_size  # tuple unpacking for readability

# Flask route
img_bytes = file.read()
base_image = Image.open(io.BytesIO(img_bytes))
```

### 1.5 Docstrings

**Convention:** Function-level docstring in Vietnamese (project language)
**Format:** Single-line for simple functions

**Example from `image_translator.py`:**
```python
def translate_images(input_dir: str, output_dir: str, source_lang: str, target_lang: str):
    """Dịch văn bản trong ảnh từ ngôn ngữ nguồn sang ngôn ngữ đích dùng Gemini."""
    ...
```

**Observation:** Complex functions like `translate_image()` in `app.py` (39 lines) don't have docstrings — rely on inline comments instead.

### 1.6 Comments

**Language:** Mixed Vietnamese-English
- Vietnamese for business logic explanation
- English for technical details

**Pattern:**
```python
# Lưu kích thước gốc trước mọi xử lý — output sẽ được normalize về size này
orig_size = base_image.size

# Chỉ break khi có ít nhất 1 part là ảnh (inline_data hoặc image)
if has_image:
    break
```

**Section comments:** Marked with `# -----` or `# ----- Tên Section -----`
```python
# --- Constants ---
# ----- Gestione File Upload -----
# ----- Utils -----
```

### 1.7 Error Handling

**Pattern 1: Try-Except with Logging (Retry Logic)**
```python
for attempt in range(MAX_RETRIES):
    try:
        response = client.models.generate_content(...)
        # Validation
        if not has_image:
            raise Exception("Phản hồi không chứa ảnh")
        break
    except Exception as e:
        print(f"Lần thử {attempt + 1}/{MAX_RETRIES} thất bại: {e}")
        if attempt < MAX_RETRIES - 1:
            time.sleep(retry_delay)
            retry_delay *= 2
        else:
            # Final error handler (HTTP 500 or skip in CLI)
            ...
```

**Pattern 2: Validation with Early Return (Flask)**
```python
if not api_key:
    return None

if not target_lang:
    return jsonify({"error": "Ngôn ngữ đích là bắt buộc."}), 400

if 'image' not in request.files:
    return jsonify({"error": "Không có ảnh nào được cung cấp."}), 400
```

**Pattern 3: File Processing with Graceful Skip (CLI)**
```python
try:
    # Process file
    result_image.save(out_file_path)
    print(f"[+] Đã lưu thành công: {out_file_path}")
except Exception as e:
    print(f"[!] Lỗi khi xử lý {img_file.name}: {e}")
    # Continue to next file (no exception raised)
```

### 1.8 Image Processing Patterns

**RGBA Conversion — Asymmetric Design:**
- **`app.py`**: Convert RGBA→RGB on **input** (before sending to Gemini)
  ```python
  if base_image.mode in ('RGBA', 'P') and file.filename.lower().endswith(('.jpg', '.jpeg')):
      base_image = base_image.convert('RGB')
  ```
- **`image_translator.py`**: Convert RGBA→RGB on **output** (before saving)
  ```python
  if img_file.suffix.lower() in {'.jpg', '.jpeg'} and result_image.mode in ('RGBA', 'P'):
      result_image = result_image.convert('RGB')
  ```

**Upscaling Pattern (Both files):**
```python
orig_size = base_image.size
w, h = orig_size
if max(w, h) * UPSCALE_FACTOR <= UPSCALE_MAX_DIMENSION:
    base_image = base_image.resize(
        (w * UPSCALE_FACTOR, h * UPSCALE_FACTOR),
        Image.LANCZOS
    )
```

**Output Normalization Pattern:**
```python
result_pil_img = result_pil_img.resize(orig_size, Image.LANCZOS)
```

### 1.9 API Client Initialization

**Web (Flask) - Per-Request Client:**
```python
def get_client(api_key):
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        print(f"Lỗi khởi tạo Gemini client: {e}")
        return None
```

**CLI - Environment-Based Client:**
```python
if not os.environ.get("GEMINI_API_KEY"):
    print("Lỗi: Biến môi trường GEMINI_API_KEY chưa được thiết lập.")
    return

client = genai.Client()  # Reads GEMINI_API_KEY automatically
```

### 1.10 Response Handling — Dual Format

**Pattern (both files):**
```python
part = response.candidates[0].content.parts[0]

if hasattr(part, 'image') and part.image:
    result_image = part.image
elif hasattr(part, 'inline_data') and part.inline_data:
    result_image = Image.open(io.BytesIO(part.inline_data.data))
else:
    # Error: no valid image
    ...
```

**Rationale:** Gemini SDK returns images in different formats depending on version.

---

## 2. Frontend Conventions (JavaScript & CSS)

### 2.1 JavaScript Patterns

**File Organization:**
```javascript
document.addEventListener('DOMContentLoaded', () => {
    // DOM Element References (top)
    // State variables
    // Event listeners setup
    // Helper functions (at bottom)
});
```

**DOM Reference Convention:**
```javascript
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const browseBtn = document.getElementById('browse-btn');
// ... one per feature/component
```

**Naming Convention (camelCase):**
- Event listeners: `handleFiles()`, `updateGalleryUI()`, `enableTranslateBtn()`
- State: `currentFiles[]`, `successCount`
- Helper: `preventDefaults()`, `showError()`, `appendResultBox()`

**Event Listener Pattern:**
```javascript
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, preventDefaults, false);
});
```

**FileReader for Preview:**
```javascript
const reader = new FileReader();
reader.onload = (e) => {
    const item = document.createElement('div');
    item.className = 'gallery-item';
    item.innerHTML = `<img src="${e.target.result}" alt="preview">`;
    imageGallery.appendChild(item);
};
reader.readAsDataURL(file);
```

**Async Fetch Pattern (Sequential):**
```javascript
for (let i = 0; i < currentFiles.length; i++) {
    const formData = new FormData();
    formData.append('image', currentFile);

    try {
        const response = await fetch('/translate', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (response.ok && data.success) {
            successCount++;
        }
    } catch (error) {
        console.error("Errore di traduzione:", error);
    }
}
```

**Note:** Sequential (not parallel) by design — Flask dev server + rate limiting.

### 2.2 CSS Conventions

**Custom Properties (CSS Variables):**
```css
:root {
    --primary: #9d4edd;
    --primary-hover: #7b2cbf;
    --secondary: #ff9e00;
    --bg-color: #0d0b14;
    --glass-bg: rgba(255, 255, 255, 0.05);
    --glass-border: rgba(255, 255, 255, 0.1);
    --text-main: #f8f9fa;
    --text-muted: #adb5bd;
    --danger: #ff4d4f;
    --shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
}
```

**Class Naming (BEM-inspired):**
```
.glass-container      /* Block: main container */
.glass-bg             /* Variant modifier */
.gallery-item         /* Block: item in gallery */
.gallery-item img     /* Child element */
.remove-btn           /* Block: button in gallery */
.input-group          /* Block: form group */
.upload-section       /* Block: upload area */
.upload-content       /* Child: content inside */
.btn-primary          /* Block: primary button */
.btn-primary:hover    /* State: hover */
.btn-primary:disabled /* State: disabled */
.badge               /* Block: badge label */
.badge.highlight     /* Modifier: highlighted badge */
.img-box             /* Block: image container */
.image-comparison    /* Block: comparison layout */
.toast               /* Block: notification */
.toast.show          /* State: visible */
```

**Layout Patterns:**

1. **Flexbox layout:**
   ```css
   .glass-container {
       display: flex;
       flex-direction: column;
       gap: 2rem;
   }
   ```

2. **Glassmorphism (backdrop blur):**
   ```css
   .glass-container {
       background: var(--glass-bg);
       backdrop-filter: blur(16px);
       -webkit-backdrop-filter: blur(16px);
       border: 1px solid var(--glass-border);
   }
   ```

3. **Gradient text:**
   ```css
   h1 {
       background: linear-gradient(135deg, var(--text-main), var(--primary));
       -webkit-background-clip: text;
       -webkit-text-fill-color: transparent;
   }
   ```

4. **Responsive design:**
   ```css
   @media (max-width: 768px) {
       .controls-section { flex-direction: column; }
       .arrow-icon { transform: rotate(90deg); }
   }
   ```

### 2.3 Animation Patterns

**Keyframe-based animations:**
```css
@keyframes pulse {
    0% { transform: scale(1); }
    100% { transform: scale(1.1); }
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
```

**Transition states:**
```css
.glass-input {
    transition: all 0.3s ease;
}

.btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(157, 78, 221, 0.6);
}
```

---

## 3. HTML Conventions (index.html)

### 3.1 Structure

**Semantic sections:**
```html
<header>                    <!-- Title + tagline -->
<section class="controls-section">    <!-- Language pickers -->
<section class="api-section">         <!-- API key input -->
<section class="upload-section">      <!-- Drag-drop area -->
<section class="action-section">      <!-- Translate button -->
<section class="result-section">      <!-- Results display -->
```

**ID Naming (camelCase):**
```html
id="drop-zone"               <!-- Main upload area -->
id="file-input"              <!-- Hidden file input -->
id="browse-btn"              <!-- Browse button -->
id="image-gallery"           <!-- Preview gallery -->
id="source-lang"             <!-- Source language select -->
id="target-lang"             <!-- Target language select -->
id="api-key"                 <!-- API key input -->
id="translate-btn"           <!-- Translate button -->
id="result-container"        <!-- Results wrapper -->
id="results-gallery"         <!-- Results display area -->
id="error-message"           <!-- Error toast -->
id="batch-progress"          <!-- Progress indicator -->
```

### 3.2 Accessibility & Meta

```html
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Image Translator | Nano Banana 2</title>

<html lang="vi">            <!-- Language attribute -->
<select> <option>           <!-- Semantic form controls -->
<label for="source-lang">   <!-- Label association -->
```

---

## 4. Project-Specific Patterns

### 4.1 Multilingual Support (Vietnamese Primary)

**Code comments & messages in Vietnamese:**
- Error messages: `"Lỗi khởi tạo Gemini client: {e}"`
- Prompts: `"Bắt đầu dịch hàng loạt..."`
- UI labels: `"Từ:", "Sang:", "Dịch Ảnh"`

**UI language:** Vietnamese (vi locale in HTML)
**Language selection:** 14 languages supported in dropdowns

### 4.2 Batch Processing

**CLI approach (image_translator.py):**
- Sequential file processing
- Per-file error handling
- Progress indicators with `[*]`, `[+]`, `[-]` prefixes

**Web approach (script.js):**
- Sequential `fetch()` loops (intentional — no parallelism)
- Real-time progress updates
- Side-by-side comparison UI

### 4.3 Output Formats

**Web endpoint `/translate`:**
- Input: multipart form (image file + lang + api_key)
- Output: JSON with base64-encoded JPEG
  ```json
  {
    "success": true,
    "image": "data:image/jpeg;base64,..."
  }
```

**CLI tool:**
- Input: directory of images
- Output: same directory with translated images (preserve filename & extension)

### 4.4 Flask Configuration

```python
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE_MB * 1024 * 1024
app.run(debug=False, host='0.0.0.0', port=5000)
```

- **Debug mode:** OFF (production-safe)
- **Host:** 0.0.0.0 (accessible from any interface)
- **Port:** 5000 (Flask default)

### 4.5 Import Statements by Purpose

**Common top 4 imports (both Python files):**
```python
import os              # Environment variables (API_KEY)
import io             # BytesIO for image data
import time           # sleep() for retry backoff
from PIL import Image # Image processing
from google import genai  # Gemini API client
```

**Web-specific:**
```python
from flask import Flask, render_template, request, jsonify
import base64          # Encode image to base64
```

**CLI-specific:**
```python
import argparse        # CLI argument parsing
from pathlib import Path  # Modern path handling
```

---

## 5. Testing & Quality (Current State)

### 5.1 No Automated Testing Infrastructure

- **Test framework:** None
- **Linter:** None (no style enforcement)
- **Formatter:** None (manual formatting)
- **CI/CD:** None (no automated checks)

### 5.2 Manual Testing

**smoke test (`test_api.py`):**
- Creates dummy 100x100 red image
- Sends to Gemini with simple prompt
- Prints success/error to console
- Purpose: Verify API key and SDK connectivity

**Unused imports detected:**
```python
from google.genai import types  # Imported but never used
```

---

## 6. Known Inconsistencies & Patterns

### 6.1 Comment Language Mix

Files contain mixed languages:
- **script.js:** Italian comments alongside Vietnamese/English
  - `// Referenze Dom Elements` (Italian)
  - `// Gestione File Upload` (Italian)
  - `// Purtroppo la maggior parte dei server Flask...` (Italian explanation)
- **style.css:** Minimal comments, mostly English/Italian descriptors

**Status:** Legacy from initial Italian implementation; partial Vietnamization in progress.

### 6.2 Asymmetric RGBA Handling

By design (documented in CLAUDE.md):
- `app.py`: RGBA→RGB conversion on **input** (only JPEG files)
- `image_translator.py`: RGBA→RGB conversion on **output** (only JPEG files)
- PNG with alpha channel: Passed as-is (no conversion)

### 6.3 Prompt Template Reuse

Both files use identical prompt template:
```python
prompt = (
    f"This image may contain many small icons and UI elements with text. "
    f"Translate EVERY SINGLE piece of text from {source_lang} to {target_lang}. "
    # ... (6 more lines)
)
```

Located in:
- `app.py` lines 73-81
- `image_translator.py` lines 43-51

---

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

---

## 8. Code Quality Observations

### Strengths
✓ Consistent retry logic pattern across both Python entry points
✓ Clear section organization with marked comments
✓ Defensive programming (validation before processing)
✓ Proper error propagation and user-facing messages
✓ DRY principle: shared prompt template, reused response parsing
✓ Modern Python patterns: pathlib, f-strings, type hints (limited)

### Areas for Improvement
⚠ No type hints in function signatures (Python files)
⚠ Mixed language comments (Italian → Vietnamese transition)
⚠ No docstrings for complex functions (>20 lines)
⚠ Unused imports in test_api.py
⚠ No logging framework (print-based debugging only)
⚠ No input validation schema (Flask routes)

