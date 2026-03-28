# External Integrations

## Primary API Integration: Google Gemini 3.1 Flash

### Overview
- **API**: Google Generative AI (Cloud)
- **Model**: `gemini-3.1-flash-image-preview` (Nano Banana 2)
- **Type**: Image generation model (re-renders with translated text, not OCR)
- **Region**: Global (Google Cloud Endpoints)

### Authentication

#### Web Application (app.py)
- **Method**: Per-request API key from user
- **Flow**:
  1. User submits POST form to `/translate` with `api_key` field
  2. Backend: `genai.Client(api_key=request.form.get('api_key'))`
  3. Each request creates new client instance
  4. Key validation: Returns 401 if invalid or missing
- **Security**:
  - API key transmitted via HTTPS (enforced by Flask app server in production)
  - Key not persisted or logged (used once per request)
  - Error response: Generic message if auth fails (no key leakage)

#### CLI Tool (image_translator.py)
- **Method**: Environment variable
- **Flow**:
  1. Read `GEMINI_API_KEY` from OS environment: `os.environ.get("GEMINI_API_KEY")`
  2. Initialize: `genai.Client()` (auto-reads env var)
  3. Single client instance for batch processing
- **Setup**: User runs `export GEMINI_API_KEY='sk-...'` before execution

### Request/Response Protocol

#### Request
```python
client.models.generate_content(
    model='gemini-3.1-flash-image-preview',
    contents=[pil_image, prompt_string]  # Image + text in single request
)
```
- **Input**: PIL Image object + English language prompt (hardcoded template)
- **Prompt Template** (both web & CLI identical):
  ```
  "This image may contain many small icons and UI elements with text.
   Translate EVERY SINGLE piece of text from {source_lang} to {target_lang}.
   IMPORTANT: Do NOT skip any text, no matter how small, faint, or densely packed.
   This includes small labels under icons, tiny button text, corner labels, and any
   characters no matter how small they appear.
   Strictly preserve the exact original layout, colors, icon graphics, and visual style.
   Only the text characters should change — everything else must remain pixel-perfect."
  ```
- **Image Preprocessing**:
  - Upscale 2x (if original dimensions × 2 ≤ 3000 px max)
  - Reason: Improve Gemini's OCR/text recognition on small UI elements
  - RGBA→RGB conversion: Only for JPEG input in web (asymmetric)

#### Response
```python
response.candidates[0].content.parts[0]  # First part of first candidate
```
- **Format 1** (newer SDK versions): `part.image` — Direct PIL Image object
- **Format 2** (older SDK versions): `part.inline_data.data` — Raw bytes → wrap in `BytesIO()` → `Image.open()`
- **Format Selection**: Code checks both using `hasattr(part, 'image')` and `hasattr(part, 'inline_data')`
- **Output**: Translated image (re-rendered, not overlay)
- **Post-processing**: Normalize to original dimensions using LANCZOS resampling

### Error Handling & Retry Logic

**Max Retries**: 3 attempts with exponential backoff
**Retry Delays**: 2 seconds → 4 seconds → 8 seconds

**Retryable Conditions**:
- Empty response (`response == None` or no candidates)
- Text-only response (no image in parts)
- Exception during `generate_content()` call

**Non-Retryable (Fail Immediately)**:
- Authentication error (401)
- Invalid API key format
- Model not found

**Web Behavior on Failure**:
- HTTP 500 response with error message in JSON
- Example: `{"error": "Gemini xử lý thất bại sau 3 lần thử..."}`

**CLI Behavior on Failure**:
- Print error message to stdout
- Skip file (continue to next image)
- No retry for that file

### Rate Limiting & Quotas

**Observed Behavior**:
- Backend enforces sequential processing (not parallel) to respect API rate limits
- Frontend batch processing: sequential `fetch()` calls per image
- Flask dev server inherent limitation also prevents parallel requests

**Recommended Usage**:
- Free tier: Limited daily quota (test with 1-2 images first)
- Paid tier: Check Google Cloud Console for current quota

### Cost Model

- **Billing**: Per API call (or per request/token in newer models)
- **Input Cost**: Per image processed
- **Output Cost**: Per generated image returned
- **No persistent storage**: Images not retained by Google (per terms)

---

## Secondary Integration Points

### Google Fonts API

#### Usage
- **Endpoint**: `https://fonts.googleapis.com` (stylesheet delivery)
- **Fonts**:
  - Outfit (weights: 300, 400, 600, 800) — Headings
  - Inter (weights: 400, 500, 600) — Body text
- **Method**: `<link>` tags in HTML with preconnect hints
- **Security**: CORS allowed, preconnect optimization

### No Database Integration

- **Architecture**: Stateless request-response model
- **Data Persistence**: None (images processed in-memory, not stored)
- **Session Management**: None (each API request independent)

### No Authentication Provider

- **User Accounts**: Not implemented
- **OAuth/SSO**: Not used
- **Key Management**: User responsible for API key (passed per-request in web)

### No Webhook Integration

- **Callbacks**: None
- **Notifications**: None
- **Async Processing**: None (synchronous request-response only)

---

## API Consumption Patterns

### Web Application Flow
```
User Upload (form multipart)
  ↓
Flask POST /translate handler
  ↓
Extract: api_key, source_lang, target_lang, image file
  ↓
[1] Validate API key → genai.Client(api_key=...)
  ↓
[2] Image preprocessing (upscale, RGBA→RGB if needed)
  ↓
[3] Call: client.models.generate_content(model, contents=[img, prompt])
    └─ Retry logic: 3 attempts, exponential backoff
  ↓
[4] Extract image from response (handle dual format)
  ↓
[5] Post-processing (normalize size, color mode)
  ↓
[6] Encode JPEG to base64
  ↓
JSON Response: {"success": true, "image": "data:image/jpeg;base64,..."}
  ↓
Browser decodes & displays
```

### CLI Tool Flow
```
Parse arguments: input dir, output dir, source_lang, target_lang
  ↓
[1] Validate GEMINI_API_KEY env var
  ↓
[2] Scan input directory for images (.png, .jpg, .jpeg, .webp)
  ↓
For each image:
  ├─ Load file via PIL
  ├─ Preprocess (upscale, preserve orig size)
  ├─ Call: client.models.generate_content(model, contents=[img, prompt])
  │   └─ Retry logic: 3 attempts, exponential backoff
  ├─ Post-process (normalize size, RGBA→RGB if JPEG)
  ├─ Save to output directory (same filename & extension)
  └─ Log result (success or error)
  ↓
Print summary: "Batch processing complete"
```

---

## Integration Reliability

### Fault Tolerance
- **Retry Strategy**: Exponential backoff for transient failures
- **Graceful Degradation**: CLI skips failed files, web returns error to user
- **Timeouts**: Not explicitly set (inherits from google-genai SDK defaults)

### Known Limitations
- **Small Text**: Upscaling to 2x helps but no guarantee for < 8pt fonts
- **Compressed Artifacts**: JPEG artifacts may confuse translation model
- **Complex Layouts**: Dense icons/text may result in hallucinated translations
- **Languages**: Model may perform better on common languages (English, Spanish, etc.)

### Testing

**Smoke Test** (`test_api.py`):
- Requires `GEMINI_API_KEY` environment variable
- Creates dummy red image + translation prompt
- Validates API connectivity (no output file saved)
- Run: `python test_api.py`

---

## Security Considerations

### API Key Exposure

**Web App**:
- User provides key in browser (transmit over HTTPS in production)
- Server doesn't store key (per-request only)
- Error messages sanitized (no key in response)

**CLI**:
- Key stored in shell environment (visible to `env`, `printenv` commands)
- Best practice: Use separate service account key, rotate regularly

### Image Privacy

- **Web**: Images uploaded to Gemini API (not stored by app)
- **CLI**: Local processing only (images stay on user's machine)
- **Both**: Assume Google Cloud retains images per API ToS

### Rate Limit Bypass

- **Sequence Processing**: Prevents accidental DoS via parallel requests
- **Client-Side Validation**: 10 MB file size limit (enforced both client & server)
- **Server Limit**: `app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024`

---

## Future Integration Opportunities

1. **Cloud Storage** (Google Cloud Storage, AWS S3)
   - Store processed images for user retrieval
   - CDN distribution for downloads

2. **Authentication & Authorization**
   - User accounts (Firebase, Cognito)
   - Per-user API key management
   - Usage quota tracking

3. **Database** (Firestore, PostgreSQL)
   - Track translation history
   - Store processed images metadata
   - User preferences

4. **Task Queue** (Cloud Tasks, Celery)
   - Async batch processing
   - Job status webhooks
   - Priority queues for large batches

5. **Webhooks & Notifications**
   - Email when batch completes
   - Slack integration for team collaboration
   - Discord bot for image translation commands

6. **Alternative Image Models**
   - Claude Vision API (Anthropic)
   - GPT-4V (OpenAI)
   - Model selection UI dropdown

---

## Integration Status Summary

| Integration | Type | Status | Required |
|-------------|------|--------|----------|
| Google Gemini 3.1 Flash | API | ✅ Active | Yes |
| Google Fonts API | CDN | ✅ Active | No (cosmetic) |
| GEMINI_API_KEY (CLI) | Env Var | ✅ Active | Yes (CLI) |
| API Key Form (Web) | User Input | ✅ Active | Yes (Web) |
| Database | N/A | ❌ Not Implemented | No |
| Authentication | N/A | ❌ Not Implemented | No |
| Webhooks | N/A | ❌ Not Implemented | No |
| Cloud Storage | N/A | ❌ Not Implemented | No |
