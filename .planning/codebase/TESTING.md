# Testing Strategy & Patterns

**Project:** ImagiTranslate
**Date:** 2026-03-29
**Test Framework Status:** None (manual smoke testing only)

---

## 1. Current Testing State

### 1.1 No Testing Infrastructure

**Framework:** None
- No pytest, unittest, or any test runner
- No assertions or test discovery
- No test fixtures or mocking capabilities
- No code coverage tools

**Type Checking:** None
- No mypy, pyright, or similar
- Limited type hints in code
- Runtime errors not caught by static analysis

**Linting & Formatting:** None
- No Black, autopep8, or similar
- No ESLint for JavaScript
- No Prettier for CSS
- Manual style enforcement only

**CI/CD:** None
- No GitHub Actions, GitLab CI, or similar
- No pre-commit hooks
- No automated test on push

---

## 2. Existing Test File: test_api.py

### 2.1 File Structure

```python
import os
import io
from PIL import Image
from google import genai
from google.genai import types  # ← UNUSED IMPORT

def test():
    # 1. Environment check
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Set GEMINI_API_KEY")
        return

    # 2. Client initialization
    client = genai.Client(api_key=api_key)

    # 3. Test data creation
    img = Image.new('RGB', (100, 100), color = 'red')

    # 4. API call
    prompt = "Translate text from Italian to English"
    try:
        response = client.models.generate_content(
            model='gemini-3.1-flash-image-preview',
            contents=[img, prompt]
        )
        print("GENERATE CONTENT SUCCESS!")
        print(response)
    except Exception as e:
        print(f"GENERATE CONTENT ERROR: {e}")

if __name__ == "__main__":
    test()
```

### 2.2 Test Type: Smoke Test

**Purpose:** Verify Gemini API connectivity and SDK integration
**Scope:** Integration test (calls external API)
**Execution:** Manual — `python test_api.py`
**Prerequisites:** `GEMINI_API_KEY` environment variable set

**Test Flow:**
1. ✓ Environment variable validation
2. ✓ Client initialization
3. ✓ Simple image creation (100×100 red)
4. ✓ API call with basic prompt
5. ✓ Response validation (success/failure print)

### 2.3 Issues Identified

**Issue 1: Unused Import**
```python
from google.genai import types  # Never referenced
```
**Impact:** Minor (no functional impact)
**Fix:** Remove this import

**Issue 2: No Assertions**
```python
# Current output: just prints result
print("GENERATE CONTENT SUCCESS!")
print(response)

# Should validate:
assert response is not None
assert response.candidates is not None
assert len(response.candidates) > 0
```

**Issue 3: No Test Framework Structure**
- Not discoverable by pytest/unittest
- Can't be integrated into CI/CD
- No test metrics or reporting
- Function named `test()` but not recognized as test

**Issue 4: Minimal Coverage**
- Only tests basic API connectivity
- Doesn't test:
  - Image processing (upscaling, RGBA conversion)
  - Batch processing
  - Error handling (retry logic)
  - Output format validation

---

## 3. Manual Testing Patterns Observed

### 3.1 Web Testing (Implicit Flow)

**User-facing smoke test flow in script.js:**
```javascript
// 1. Upload image
handleFiles(files)
↓
// 2. Click "Dịch Ảnh" button
fetch('/translate', { method: 'POST', body: formData })
↓
// 3. Validation occurs:
if (response.ok && data.success) {
    successCount++
    appendResultBox(...)
} else {
    throw new Error(data.error)
    appendErrorBox(...)
}
```

**Test criteria (implicit):**
- Form validation (required fields, file size <10MB)
- File type validation (image/*)
- API key provided
- Response parseable as JSON
- Image renders correctly in browser

### 3.2 CLI Testing (Implicit Flow)

**Usage for manual testing:**
```bash
export GEMINI_API_KEY='your-key-here'
python image_translator.py -i ./input -o ./output -t "Vietnamese"
```

**Output indicators (from script.js/image_translator.py):**
```
[*] Đang xử lý: image.png ...
[+] Đã lưu thành công: ./output/image.png
[-] Thất bại sau 3 lần thử cho image.png
[!] Lỗi khi xử lý image.png: {error}
```

**Test criteria (implicit):**
- Directory scanning works
- Each file processed in sequence
- Retry logic triggers on failure
- Output files created with same name/extension
- Error messages informative

---

## 4. Backend Testing Approach

### 4.1 Flask Route Testing (Would Be)

**Route to test:** `POST /translate`

**Input validation tests:**
```python
# Missing API key
POST /translate {
    'image': file,
    'target_lang': 'Vietnamese'
}
→ 401 {"error": "API Key Gemini không hợp lệ..."}

# Missing target language
POST /translate {
    'api_key': 'key',
    'image': file
}
→ 400 {"error": "Ngôn ngữ đích là bắt buộc."}

# No file uploaded
POST /translate {
    'api_key': 'key',
    'target_lang': 'Vietnamese'
}
→ 400 {"error": "Không có ảnh nào được cung cấp."}

# File size > 10MB
POST /translate {large_file}
→ 413 (Flask enforces via MAX_CONTENT_LENGTH)
```

**Successful flow:**
```python
POST /translate {
    'api_key': 'valid-key',
    'image': test_image.jpg,
    'source_lang': 'auto-detect',
    'target_lang': 'Vietnamese'
}
→ 200 {
    "success": true,
    "image": "data:image/jpeg;base64,..."
}
```

### 4.2 Image Processing Testing (Would Be)

**RGBA Conversion (app.py input stage):**
```python
# JPEG with RGBA → should convert to RGB
input_img = Image.new('RGBA', (100, 100))
assert input_img.mode == 'RGBA'
→ process → output mode should be 'RGB'

# PNG with RGBA → should NOT convert
input_img = Image.new('RGBA', (100, 100))
file.filename = 'test.png'
→ process → output mode should remain 'RGBA'
```

**Upscaling Logic:**
```python
# Small image → should upscale
orig_size = (500, 500)
UPSCALE_FACTOR = 2
UPSCALE_MAX_DIMENSION = 3000
# 500 * 2 = 1000 <= 3000 → UPSCALE
→ resized to (1000, 1000)

# Large image → should NOT upscale
orig_size = (2000, 2000)
# 2000 * 2 = 4000 > 3000 → NO UPSCALE
→ remains (2000, 2000)
```

**Output Normalization:**
```python
# Gemini might return different size
gemini_output_size = (800, 600)
orig_size = (500, 500)
→ normalized to (500, 500)
assert result.size == orig_size
```

### 4.3 Retry Logic Testing (Would Be)

**Pattern to test (both files):**
```python
# Attempt 1: failure
→ wait 2s
# Attempt 2: failure
→ wait 4s
# Attempt 3: failure
→ return error

# Mock Example:
mock_client = Mock()
mock_client.models.generate_content.side_effect = [
    Exception("timeout"),
    Exception("timeout"),
    Response(with_image)  # Success on 3rd
]
→ verify 3 attempts made
→ verify sleep called with [2, 4]
→ verify response returned
```

### 4.4 CLI Batch Processing Testing (Would Be)

**Test: Directory scanning**
```python
input_dir = "./test_images"
├── image1.jpg       (10MB)
├── image2.png       (5MB)
├── image3.gif       (unsupported)
└── document.pdf     (unsupported)

→ scan result: [image1.jpg, image2.png]
assert len(images_found) == 2
```

**Test: Sequential processing**
```python
Process 3 images:
  [*] Đang xử lý: image1.jpg ...
  [+] Đã lưu thành công: ./output/image1.jpg

  [*] Đang xử lý: image2.png ...
  [!] Lỗi khi xử lý image2.png: timeout

  [*] Đang xử lý: image3.jpg ...
  [+] Đã lưu thành công: ./output/image3.jpg

Results:
  success: 2/3
  failed: 1/3 (error logged but continued)
```

---

## 5. Frontend Testing Approach

### 5.1 JavaScript Unit Tests (Would Be)

**Test framework:** Jest or Mocha
**Test scope:** Behavior, not rendering

**Example: File validation**
```javascript
describe('handleFiles', () => {
    test('rejects non-image files', () => {
        const mockFile = new File([], 'test.txt', { type: 'text/plain' });
        handleFiles([mockFile]);
        expect(currentFiles).toHaveLength(0);
        expect(showError).toHaveBeenCalledWith(expect.stringContaining('không phải là ảnh'));
    });

    test('rejects files > 10MB', () => {
        const mockFile = new File(['x'.repeat(11 * 1024 * 1024)], 'large.jpg', { type: 'image/jpeg' });
        handleFiles([mockFile]);
        expect(currentFiles).toHaveLength(0);
    });

    test('accepts valid image files', () => {
        const mockFile = new File([], 'valid.jpg', { type: 'image/jpeg' });
        handleFiles([mockFile]);
        expect(currentFiles).toHaveLength(1);
    });

    test('prevents duplicates', () => {
        const mockFile = new File([], 'image.jpg', { type: 'image/jpeg' });
        handleFiles([mockFile]);
        handleFiles([mockFile]); // Same name + size
        expect(currentFiles).toHaveLength(1);
    });
});
```

**Test framework code:** Mocking example
```javascript
// Mock fetch
global.fetch = jest.fn(() =>
    Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ success: true, image: 'data:...' })
    })
);

// Test translate button click
test('handleTranslateClick sends batch of files sequentially', async () => {
    const files = [file1, file2, file3];
    currentFiles = files;

    await triggerTranslateClick();

    expect(fetch).toHaveBeenCalledTimes(3);
    expect(fetch).toHaveBeenNthCalledWith(1, '/translate', expect.objectContaining({ body: expect.any(FormData) }));
});
```

### 5.2 Integration Tests (Would Be)

**Test: End-to-end web flow**
```javascript
describe('Full translation workflow', () => {
    test('upload → translate → download works', async () => {
        // 1. User uploads image
        const file = new File(['image-data'], 'test.jpg', { type: 'image/jpeg' });

        // 2. Gallery updates
        handleFiles([file]);
        expect(document.querySelectorAll('.gallery-item')).toHaveLength(1);

        // 3. Translate button enabled
        apiKeyInput.value = 'test-key';
        targetLangSel.value = 'Vietnamese';
        expect(translateBtn.disabled).toBe(false);

        // 4. Click translate
        translateBtn.click();
        await waitForFetch();

        // 5. Results appear
        expect(document.querySelectorAll('.image-comparison')).toHaveLength(1);
        expect(document.querySelector('.download-btn-dynamic')).toBeInTheDocument();
    });
});
```

### 5.3 E2E Testing (Would Be)

**Tool:** Playwright or Cypress
**Environment:** Local Flask dev server running

```javascript
// cypress/e2e/translation.cy.js
describe('Image translation E2E', () => {
    beforeEach(() => {
        cy.visit('http://localhost:5000');
        cy.get('#api-key').type(Cypress.env('GEMINI_API_KEY'));
    });

    it('translates single image from English to Vietnamese', () => {
        // Upload
        cy.fixture('english-ui.png').then(fileContent => {
            cy.get('#file-input').attachFile('english-ui.png');
        });

        // Check preview
        cy.get('.gallery-item').should('have.length', 1);

        // Select language
        cy.get('#target-lang').select('Vietnamese');

        // Translate
        cy.get('#translate-btn').click();

        // Wait for result
        cy.get('.image-comparison', { timeout: 60000 }).should('be.visible');
        cy.get('[alt="Ảnh đã dịch"]').should('be.visible');

        // Download
        cy.get('.download-btn-dynamic').click();
        cy.readFile(`cypress/downloads/DaDich_english-ui.png`).should('exist');
    });

    it('shows error for invalid API key', () => {
        cy.get('#api-key').clear().type('invalid-key');
        cy.get('#file-input').attachFile('english-ui.png');
        cy.get('#translate-btn').click();

        cy.get('#error-message').should('have.class', 'show');
        cy.get('#error-message').should('contain', 'API Key');
    });
});
```

---

## 6. Testing Patterns by Feature

### 6.1 API Key Validation

**Current location:** `get_client()` in app.py, implicit in image_translator.py
**Test needed:**
```python
def test_invalid_api_key():
    response = client.post('/translate', data={
        'api_key': 'invalid-key',
        'target_lang': 'Vietnamese',
        'image': (open('test.jpg', 'rb'), 'test.jpg')
    })
    assert response.status_code == 401
    assert 'không hợp lệ' in response.json['error']
```

### 6.2 File Upload Validation

**Current location:** Implicit in script.js (client-side), form in app.py (server-side)
**Test needed:**
```python
def test_file_size_limit():
    # Create 11MB file
    large_file = io.BytesIO(b'x' * (11 * 1024 * 1024))

    response = client.post('/translate', data={
        'api_key': 'valid-key',
        'target_lang': 'Vietnamese',
        'image': (large_file, 'large.jpg')
    })
    assert response.status_code == 413  # Payload Too Large
```

### 6.3 RGBA Conversion

**Current location:** app.py line 63-64 (input), image_translator.py line 116-117 (output)
**Test needed:**
```python
def test_rgba_jpeg_converted_to_rgb_on_input():
    rgba_img = Image.new('RGBA', (100, 100))
    io_buffer = io.BytesIO()
    rgba_img.save(io_buffer, format='PNG')  # Save as PNG (supports RGBA)
    io_buffer.seek(0)

    response = app.test_client().post('/translate', data={
        'api_key': 'key',
        'target_lang': 'Vietnamese',
        'image': (io_buffer, 'test.jpg')  # But claim it's JPEG
    })

    # Verify that RGBA was converted before sending to Gemini
    assert mock_gemini_call.called
    sent_image = mock_gemini_call.call_args[0][0]  # First arg
    assert sent_image.mode == 'RGB'
```

### 6.4 Upscaling Logic

**Current location:** Both files, lines 63-71 (app.py) and 63-67 (image_translator.py)
**Test needed:**
```python
def test_upscale_small_image():
    small_img = Image.new('RGB', (100, 100))

    # Mock the upscaling behavior
    # Should resize to (200, 200)

    # After processing, original size should be preserved
    result = process_image(small_img)
    assert result.size == (100, 100)  # Normalized back to original

def test_no_upscale_large_image():
    large_img = Image.new('RGB', (2000, 2000))

    # 2000 * 2 = 4000 > 3000, so no upscaling
    result = process_image(large_img)
    assert result.size == (2000, 2000)
```

### 6.5 Retry Logic

**Current location:** Both files, lines 86-111 (app.py) and 72-99 (image_translator.py)
**Test needed:**
```python
def test_retry_exponential_backoff():
    mock_client = Mock()
    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("timeout")
        return Response(with_image=True)

    mock_client.models.generate_content.side_effect = side_effect

    with patch('time.sleep') as mock_sleep:
        result = translate_with_retry(mock_client, image, prompt)

        assert call_count == 3
        mock_sleep.assert_has_calls([call(2), call(4)])  # 2s, then 4s
        assert result is not None
```

### 6.6 Batch Processing Sequential Order

**Current location:** image_translator.py lines 53-126, script.js lines 161-196
**Test needed:**
```python
def test_cli_batch_sequential_order():
    input_dir = Path('./test_input')
    input_dir.mkdir()

    # Create 3 test images
    for i in range(3):
        img = Image.new('RGB', (100, 100))
        img.save(input_dir / f'image_{i:02d}.jpg')

    call_order = []
    mock_client.models.generate_content.side_effect = lambda **kw: (
        call_order.append('image_' + kw['contents'][0].filename),
        Response(image=Image.new('RGB', (100, 100)))
    )

    translate_images(str(input_dir), './test_output', 'English', 'Vietnamese')

    # Verify processing order is deterministic
    assert call_order == ['image_00.jpg', 'image_01.jpg', 'image_02.jpg']
```

---

## 7. Testing Best Practices to Adopt

### 7.1 Immediate Actions (No Framework Required)

1. **Enhance test_api.py:**
   ```python
   # Add assertions
   assert response is not None, "Response is None"
   assert response.candidates, "No candidates in response"

   # Remove unused imports
   # from google.genai import types  ← DELETE
   ```

2. **Add error case to test_api.py:**
   ```python
   def test_with_invalid_key():
       client = genai.Client(api_key='invalid')
       try:
           # Should raise authentication error
       except Exception as e:
           assert 'authentication' in str(e).lower()
   ```

3. **Add CLI batch test script:**
   ```bash
   #!/bin/bash
   mkdir -p test_batch_input

   # Create test images
   python -c "from PIL import Image; Image.new('RGB', (100, 100)).save('test_batch_input/test1.jpg')"

   # Run CLI
   export GEMINI_API_KEY='test-key'
   python image_translator.py -i test_batch_input -o test_batch_output -t Vietnamese

   # Verify output
   ls test_batch_output/*.jpg
   ```

### 7.2 Medium Term (With Test Framework)

1. **Adopt pytest:**
   ```
   pip install pytest pytest-flask pytest-mock
   ```

2. **Create test structure:**
   ```
   tests/
   ├── conftest.py          # Fixtures, mocks
   ├── unit/
   │   ├── test_image_processing.py
   │   ├── test_retry_logic.py
   │   └── test_validation.py
   ├── integration/
   │   ├── test_flask_routes.py
   │   └── test_cli.py
   └── fixtures/
       ├── test_images/
       └── mock_responses.json
   ```

3. **Write pytest tests:**
   ```python
   # tests/unit/test_image_processing.py
   import pytest
   from PIL import Image
   from app import translate_image

   @pytest.fixture
   def test_image():
       return Image.new('RGB', (100, 100))

   def test_upscale_small_image(test_image):
       # Test implementation
       pass
   ```

### 7.3 Long Term (With CI/CD)

1. **Set up GitHub Actions:**
   ```yaml
   name: Tests
   on: [push, pull_request]
   jobs:
     test:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v2
         - uses: actions/setup-python@v2
         - run: pip install -r requirements.txt
         - run: pytest tests/ --cov --cov-report=xml
         - run: npm install && npm run lint
   ```

2. **Add pre-commit hooks:**
   ```yaml
   # .pre-commit-config.yaml
   repos:
     - repo: https://github.com/psf/black
       rev: 23.3.0
       hooks:
         - id: black
     - repo: https://github.com/PyCQA/flake8
       rev: 6.0.0
       hooks:
         - id: flake8
   ```

---

## 8. Coverage Gaps Analysis

### 8.1 Not Tested (Current)

| Component | Type | Impact |
|-----------|------|--------|
| `get_client()` | Unit | Medium (API key handling) |
| RGBA conversion logic | Unit | High (output quality) |
| Upscaling logic | Unit | Medium (OCR accuracy) |
| Retry backoff timing | Unit | Medium (reliability) |
| Batch sequential order | Integration | Low (consistency) |
| Flask error routes | Integration | High (user experience) |
| Image normalization | Unit | Medium (consistency) |
| Dual response format handling | Integration | High (robustness) |
| File validation (size, type) | Unit | High (security) |
| Duplicate prevention | Unit | Low (UI polish) |

### 8.2 Critical Paths to Test First

**Priority 1 (High risk if broken):**
1. Image format detection and conversion
2. Retry logic (timeout resilience)
3. API key validation
4. File size limit enforcement

**Priority 2 (Medium risk):**
1. Batch processing sequencing
2. Output format normalization
3. Flask error responses

**Priority 3 (Nice to have):**
1. UI gallery updates
2. Download functionality
3. Toast notifications

---

## 9. Mock Data for Testing

### 9.1 Test Images

**Needed types:**
- Small JPEG (100×100)
- Large PNG (2000×2000, RGBA)
- WebP with text
- Invalid format (GIF)
- Corrupt file

**Generation script:**
```python
from PIL import Image, ImageDraw

def create_test_images():
    # 1. Small JPEG
    img = Image.new('RGB', (100, 100), color=(255, 0, 0))
    img.save('tests/fixtures/small.jpg')

    # 2. Large PNG with RGBA
    img = Image.new('RGBA', (2000, 2000), color=(255, 0, 0, 128))
    img.save('tests/fixtures/large.png')

    # 3. PNG with text (for translation test)
    img = Image.new('RGB', (400, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "Hello World", fill=(0, 0, 0))
    img.save('tests/fixtures/with_text.png')

    # 4. WebP
    img = Image.new('RGB', (100, 100))
    img.save('tests/fixtures/test.webp')
```

### 9.2 Mock API Responses

**Gemini API success response:**
```python
class MockResponse:
    class Candidate:
        class Content:
            class Part:
                image = Image.new('RGB', (100, 100))
                inline_data = None
            parts = [Part()]
        content = Content()
    candidates = [Candidate()]
```

**Gemini API error responses:**
```python
# Authentication error
raise google.api_core.exceptions.Unauthenticated("Invalid API key")

# Rate limit error
raise google.api_core.exceptions.ResourceExhausted("Rate limit exceeded")

# Server error
raise google.api_core.exceptions.InternalServerError("Internal server error")
```

---

## 10. Summary: Testing Roadmap

| Phase | Timeline | Action |
|-------|----------|--------|
| **Now** | Immediate | Fix test_api.py (remove unused import, add assertions) |
| **Sprint 1** | Week 1 | Create manual test script for CLI batch |
| **Sprint 2** | Week 2-3 | Set up pytest, write unit tests for image processing |
| **Sprint 3** | Week 4-5 | Add Flask integration tests, E2E tests with Playwright |
| **Sprint 4+** | Ongoing | Add GitHub Actions CI/CD, pre-commit hooks |

---

## 11. Key Takeaways

### Current State
- ✓ **Ad-hoc manual testing** happens during development
- ✓ **Simple smoke test** (test_api.py) validates API connectivity
- ✗ **No automated testing** for new features
- ✗ **No regression prevention** between commits
- ✗ **No code coverage** metrics
- ✗ **No CI/CD pipeline**

### Recommendations
1. **Short term:** Enhance existing test_api.py, create manual CLI test scripts
2. **Medium term:** Integrate pytest for unit/integration testing
3. **Long term:** Set up GitHub Actions with full E2E pipeline

### Quality Impact
- Without testing infrastructure: **Risk of silent regressions, API failures caught only by users**
- With pytest: **70% coverage reachable in 2 weeks**
- With CI/CD: **Prevention of broken deployments, confidence in refactoring**

