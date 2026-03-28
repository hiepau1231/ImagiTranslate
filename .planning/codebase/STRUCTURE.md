# ImagiTranslate Directory Structure

## Project Root Layout

```
d:/_Dev/GoodFirstIsuuses/ImagiTranslate/
├── .git/                          # Git repository metadata
├── .gitignore                      # Ignored patterns (*.pyc, __pycache__, .env, etc.)
├── .planning/
│   └── codebase/                   # Architecture documentation (generated)
│       ├── ARCHITECTURE.md         # System design, data flow, patterns
│       └── STRUCTURE.md            # This file
├── CLAUDE.md                       # Project guidelines for Claude Code
├── README.md                       # User-facing documentation
├── LICENSE                         # License file (Apache 2.0 or similar)
│
├── app.py                          # Flask web server (Flask entry point)
├── image_translator.py             # CLI batch tool (Command-line entry point)
├── test_api.py                     # Smoke test for Gemini API connectivity
├── requirements.txt                # Python dependencies
│
├── static/                         # Frontend assets (served by Flask)
│   ├── script.js                   # Client-side batch upload & translation logic
│   └── style.css                   # Glassmorphism UI styles
│
├── templates/                      # Jinja2 HTML templates
│   └── index.html                  # Single-page application template
│
├── docs/                           # Additional documentation (empty or future use)
├── output_test/                    # Example output directory (test runs)
└── main_atlas.png                  # Example image asset

```

---

## Core Entry Points

### 1. **app.py** (Flask Web Server)
**Purpose**: Serve web UI and handle image translation via HTTP POST

**Location**: `d:/_Dev/GoodFirstIsuuses/ImagiTranslate/app.py`
**Lines**: 142 lines total

**Key Components**:
- **Lines 11-17**: Constants
  - `GEMINI_MODEL`: Model identifier
  - `MAX_RETRIES`, `RETRY_DELAY_SECONDS`: Retry configuration
  - `UPSCALE_FACTOR`, `UPSCALE_MAX_DIMENSION`: Scaling limits
  - `MAX_FILE_SIZE_MB`: Upload limit (10 MB)

- **Lines 21-28**: `get_client(api_key)` function
  - Validates and initializes Gemini client
  - Returns `None` if key is invalid

- **Line 30-32**: Route `GET /`
  - Renders `templates/index.html`

- **Lines 34-138**: Route `POST /translate`
  - Parses form fields: `image`, `api_key`, `source_lang`, `target_lang`
  - Validates API key (401 on failure)
  - Loads image via PIL
  - Converts RGBA→RGB for JPEG files (line 63)
  - Scales image up 2x if small (lines 67-71)
  - Calls Gemini with retry loop (lines 83-111)
  - Normalizes output to original dimensions (line 123)
  - Encodes result as base64 JPEG
  - Returns JSON response

- **Lines 140-141**: Flask app startup
  - Debug mode disabled (production-safe)
  - Listens on `0.0.0.0:5000`

**Dependencies**:
- `flask` — web framework
- `google.genai` — Gemini SDK
- `PIL` (pillow) — image processing

---

### 2. **image_translator.py** (CLI Batch Tool)
**Purpose**: Batch translate all images in a directory via command line

**Location**: `d:/_Dev/GoodFirstIsuuses/ImagiTranslate/image_translator.py`
**Lines**: 141 lines total

**Key Components**:
- **Lines 9-14**: Constants
  - `GEMINI_MODEL`: Model identifier
  - `MAX_RETRIES`, `RETRY_DELAY_SECONDS`: Retry configuration
  - `UPSCALE_FACTOR`, `UPSCALE_MAX_DIMENSION`: Scaling limits
  - `VALID_EXTENSIONS`: Supported image formats

- **Lines 16-127**: `translate_images()` function
  - **Lines 18-27**: Reads `GEMINI_API_KEY` env var; initializes client
  - **Lines 29-38**: Discovers images in input directory
  - **Lines 43-51**: Constructs translation prompt
  - **Lines 53-125**: Main loop per image
    - Load image, scale up (lines 57-67)
    - Retry loop with exponential backoff (lines 72-99)
    - Extract image from response (lines 101-111)
    - Normalize dimensions (line 114)
    - Convert RGBA→RGB for JPEG (line 116-117)
    - Save to output directory (line 119)
    - Print status messages (lines 120-125)

- **Lines 129-140**: Argument parser
  - `-i, --input`: Input directory (default: `./input`)
  - `-o, --output`: Output directory (default: `./output`)
  - `-s, --source-lang`: Source language (default: `auto-detect`)
  - `-t, --target-lang`: Target language (required)

**Dependencies**:
- `google.genai` — Gemini SDK
- `PIL` (pillow) — image processing
- `pathlib` — cross-platform path handling
- `argparse` — CLI argument parsing

---

### 3. **test_api.py** (Smoke Test)
**Purpose**: Validate Gemini API credentials and connectivity

**Location**: `d:/_Dev/GoodFirstIsuuses/ImagiTranslate/test_api.py`
**Lines**: 30 lines total

**Key Components**:
- **Lines 7-26**: `test()` function
  - Reads `GEMINI_API_KEY` env var
  - Creates dummy 100×100 red image
  - Sends to Gemini with simple translation prompt
  - Prints success/error response

**Usage**: `GEMINI_API_KEY=xxx python test_api.py`

**Note**: Unused import `from google.genai import types` (line 5)

---

## Frontend Assets

### **static/script.js** (Client-Side Logic)
**Location**: `d:/_Dev/GoodFirstIsuuses/ImagiTranslate/static/script.js`
**Lines**: 280 lines total

**Responsibility**: Batch image upload, translation orchestration, results display

**Key Sections**:
- **Lines 1-20**: DOM element caching
  - Drop zone, file input, language selectors, translate button, toast notifications

- **Lines 22**: `currentFiles[]` array
  - In-memory store for selected images (not persisted)

- **Lines 24-92**: File upload handling
  - **Lines 27-30**: Browse button click → open file picker
  - **Lines 32-36**: Drop zone click → open file picker
  - **Lines 39-41**: File input change → process files
  - **Lines 44-65**: Drag-and-drop event handlers
  - **Lines 68-92**: `handleFiles()` — validate, deduplicate, update UI
    - Checks: MIME type is image/* (line 72)
    - Checks: File size ≤ 10 MB (line 77)
    - Deduplicates by name+size (line 83)
    - Adds to `currentFiles[]`
    - Updates gallery preview

- **Lines 94-126**: Gallery preview (`updateGalleryUI()`)
  - Shows thumbnail grid of selected images
  - Generates data URLs for each image
  - Attaches remove buttons per image

- **Lines 128-134**: Button state (`enableTranslateBtn()`)
  - Enables translate button if:
    - Images selected AND
    - Target language chosen AND
    - API key entered

- **Lines 141-203**: Translation orchestration (`translateBtn.addEventListener`)
  - Sequential loop through `currentFiles[]`
  - Per file: build FormData, POST to `/translate`
  - Parse JSON response
  - Display result (or error box)
  - Update progress badge
  - Handle failures gracefully (skip file, continue)

- **Lines 205-265**: Result display
  - **Lines 205-252**: `appendResultBox()` — side-by-side comparison
    - Original image (left)
    - Translated image (right)
    - Download button
  - **Lines 254-265**: `appendErrorBox()` — error box

- **Lines 269-276**: Utility `showError()` — toast notification

**Comments**: Italian language comments (legacy code being Vietnamized)

---

### **static/style.css** (Glassmorphism UI)
**Location**: `d:/_Dev/GoodFirstIsuuses/ImagiTranslate/static/style.css`
**Lines**: 454 lines total

**Design System**:
- **Lines 1-12**: CSS variables
  - Primary: purple (#9d4edd)
  - Secondary: orange (#ff9e00)
  - Background: dark (#0d0b14)
  - Glass morphism: semi-transparent whites with blur

**Sections**:
- **Lines 14-31**: Reset + body base
- **Lines 33-50**: Animated background (radial gradient + pulse animation)
- **Lines 52-66**: Main container (glassmorphism: blur + semi-transparent)
- **Lines 68-91**: Header (gradient text, branding)
- **Lines 93-162**: Language controls section (dropdown styling)
- **Lines 164-175**: API key section
- **Lines 177-196**: Upload zone (drag-drop target)
- **Lines 198-281**: File gallery preview (thumbnails with remove buttons)
- **Lines 283-353**: Button styles (primary, secondary, spinner animation)
- **Lines 355-414**: Result section (side-by-side comparison, badges)
- **Lines 416-436**: Toast notifications (error messages)
- **Lines 438-453**: Mobile responsive (max-width: 768px)

---

### **templates/index.html** (Single-Page Application)
**Location**: `d:/_Dev/GoodFirstIsuuses/ImagiTranslate/templates/index.html`
**Lines**: 115 lines total

**Structure**:
- **Lines 1-11**: HTML head
  - Charset, viewport, title
  - Google Fonts (Outfit, Inter)
  - CSS link to `static/style.css`

- **Lines 12-114**: Body content
  - Background animation div (visual effect)

  - **Lines 15-19**: Main container `.glass-container` (Jinja2: `url_for()` for static assets)
    - **Lines 16-18**: Header with title "ImagiTranslate"

    - **Lines 21-67**: Language selection controls
      - Source language dropdown (line 24-39)
      - Arrow icon (line 42-46)
      - Target language dropdown (line 50-66)

    - **Lines 69-75**: API key input section
      - Password input field
      - Help text (not stored locally)

    - **Lines 77-90**: Upload zone
      - File input (hidden, triggered by JS)
      - Drop zone content (upload icon, instructions, browse button)
      - Image gallery preview (populated by JS)

    - **Lines 92-97**: Translate button
      - Primary action button
      - Spinner loader (hidden until processing)

    - **Lines 99-107**: Results section (hidden until translation)
      - Batch progress badge
      - Side-by-side comparison gallery
      - Instructions for downloads

    - **Lines 109**: Error toast container

    - **Lines 112**: Script link to `static/script.js`

**Template Language**: Jinja2 (minimal — just `url_for()` for Flask static asset routing)

---

## Configuration & Metadata

### **requirements.txt**
**Location**: `d:/_Dev/GoodFirstIsuuses/ImagiTranslate/requirements.txt`

```
google-genai>=0.2.2      # Gemini API client
pillow>=10.2.0           # Image processing
flask>=3.0.0             # Web framework
werkzeug>=3.0.0          # WSGI utilities
```

### **CLAUDE.md** (Project Guidelines)
**Location**: `d:/_Dev/GoodFirstIsuuses/ImagiTranslate/CLAUDE.md`

Instructions for Claude Code:
- When to use codebase retrieval (MCP Auggie) vs manual tools
- Development commands (pip install, run app/CLI, test)
- Architecture summary (dual entry points, shared Gemini integration)
- Key patterns (retry logic, dual image format handling, RGBA conversion)
- Constants (model, retry config, file limits)
- API key management
- Design philosophy (sequential processing, no parallelism)

---

## Data & Output Directories

### **input/** (CLI Input)
**Purpose**: Source images for CLI batch processing

**Convention**:
- Not checked into repo (gitignored)
- User creates and populates before running CLI
- Example usage: `python image_translator.py -i ./input -o ./output`

### **output/** (CLI Output)
**Purpose**: Translated images from CLI batch processing

**Convention**:
- Not checked into repo (gitignored)
- Created by CLI if doesn't exist
- Files preserve original extension and name

### **output_test/**
**Purpose**: Example output directory (test run artifacts)

---

## Documentation

### **README.md**
**Location**: `d:/_Dev/GoodFirstIsuuses/ImagiTranslate/README.md`

User-facing documentation:
- Project description
- Installation instructions
- Usage examples (web, CLI)
- Feature list
- Limitations
- License

### **CLAUDE.md**
**Location**: `d:/_Dev/GoodFirstIsuuses/ImagiTranslate/CLAUDE.md`

Developer guidelines for Claude Code:
- Codebase search strategy
- Development commands
- Architecture overview
- Key code patterns
- Constants and configuration
- Notes on implementation

### **docs/**
**Location**: `d:/_Dev/GoodFirstIsuuses/ImagiTranslate/docs/`

Directory for additional technical documentation (currently empty or placeholder)

---

## Key Naming Conventions

### Python Files
- Entry points: `app.py` (web), `image_translator.py` (CLI)
- Test utilities: `test_api.py`
- All lowercase, no prefix

### Frontend Files
- Scripts: `static/script.js` (camelCase, one file)
- Styles: `static/style.css` (kebab-case for CSS class names)
- Templates: `templates/index.html` (single entry point)

### Python Functions
- Main loop: `translate_images()` (verb+plural for batch operations)
- Utilities: `get_client()` (verb + object)
- Handlers: `handleFiles()` (camelCase in JavaScript, snake_case in Python)

### Python Variables & Constants
- Constants: `GEMINI_MODEL`, `MAX_RETRIES`, `RETRY_DELAY_SECONDS` (UPPER_SNAKE_CASE)
- Module variables: `currentFiles[]` (camelCase in JS), `images_found` (snake_case in Python)

### CSS Classes & IDs
- Containers: `.glass-container`, `.upload-section`
- Components: `.btn-primary`, `.img-box`, `.badge`
- States: `.dragover`, `.show`, `.highlight`
- Utilities: `.text-btn`, `.help-text`

---

## Project Metadata

| Aspect | Value |
|--------|-------|
| **Language** (Backend) | Python 3.8+ |
| **Language** (Frontend) | HTML5 / CSS3 / vanilla JavaScript (ES6+) |
| **Framework** (Web) | Flask 3.0+ |
| **Framework** (AI) | Google Gemini SDK (google-genai) |
| **Image Library** | Pillow (PIL) 10.2+ |
| **Model** | `gemini-3.1-flash-image-preview` |
| **Input Formats** | PNG, JPEG, WebP |
| **Output Formats** | JPEG (web), original format (CLI) |
| **Max File Size** | 10 MB |
| **Supported Languages** | Any language Gemini supports (13+ in UI) |
| **Deployment** | Flask dev server (local); WSGI compatible (production) |
| **License** | Apache 2.0 (or stated in LICENSE file) |

---

## Module Dependencies (Call Graph)

```
app.py
  ├─ flask (routes, templates)
  ├─ google.genai (Gemini API)
  ├─ PIL (Image processing)
  └─ Standard: os, io, time, base64

image_translator.py
  ├─ google.genai (Gemini API)
  ├─ PIL (Image processing)
  ├─ pathlib (Path handling)
  ├─ argparse (CLI parsing)
  └─ Standard: os, io, time

test_api.py
  ├─ google.genai (Gemini API)
  ├─ PIL (Image processing)
  └─ Standard: os, io

static/script.js
  ├─ Fetch API (XHR to /translate)
  ├─ FileReader API (local image preview)
  ├─ DOM APIs (querySelector, event listeners)
  └─ Standard: no external libs

static/style.css
  └─ Pure CSS3 (no preprocessor)

templates/index.html
  └─ Jinja2 (Flask template engine for url_for())
```

---

## File Locations Summary

| File | Purpose | Lines | Type |
|------|---------|-------|------|
| app.py | Flask web server | 142 | Python |
| image_translator.py | CLI batch tool | 141 | Python |
| test_api.py | Smoke test | 30 | Python |
| static/script.js | Client-side logic | 280 | JavaScript |
| static/style.css | UI styling | 454 | CSS |
| templates/index.html | HTML template | 115 | HTML |
| requirements.txt | Dependencies | 5 | Text |
| CLAUDE.md | Project guidelines | 120 | Markdown |
| README.md | User documentation | ~100 | Markdown |
| LICENSE | License | - | Text |

**Total lines of code**: ~1,287 (Python + JS + HTML)
