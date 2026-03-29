# Plan B: Constants Migration

```yaml
wave: 2
depends_on:
  - PLAN-A-grid-module
files_modified:
  - app.py
  - image_translator.py
files_read:
  - grid_translator.py
  - app.py
  - image_translator.py
  - .planning/phases/01-grid-module-core/01-CONTEXT.md
  - .planning/phases/01-grid-module-core/01-RESEARCH.md
  - .planning/REQUIREMENTS.md
  - .planning/codebase/CONVENTIONS.md
requirements_addressed:
  - GRID-05
autonomous: true
```

---

## Goal

Migrate shared constants (`GEMINI_MODEL`, `MAX_RETRIES`, `RETRY_DELAY_SECONDS`) out of `app.py` and `image_translator.py` — both files import from `grid_translator.py` as single source of truth. No duplicate definitions remain. No other changes to these files.

---

## Tasks

### Task 1: Update `app.py` — replace constant definitions with import from `grid_translator`

<read_first>
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/app.py (full file — especially lines 1-17 for imports and constants, and lines 83-111 for where constants are used)
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/grid_translator.py (verify constants exist and values match)
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/.planning/phases/01-grid-module-core/01-RESEARCH.md (Finding 5 for which constants move and which stay)
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/.planning/codebase/CONVENTIONS.md (section 1.1 for import ordering: stdlib → third-party → local)
</read_first>

<action>
In `app.py`, make these exact changes:

1. **Add import** — after the `from google import genai` line (line 7), add:
   ```python
   from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS
   ```
   This follows the convention: stdlib → third-party (flask, PIL, google) → local (grid_translator).

2. **Remove three constant definitions** — delete these exact lines from the `# --- Constants ---` section:
   ```python
   GEMINI_MODEL = 'gemini-3.1-flash-image-preview'
   MAX_RETRIES = 3
   RETRY_DELAY_SECONDS = 2
   ```

3. **Keep these constants in place** — do NOT remove or modify:
   ```python
   MAX_FILE_SIZE_MB = 10
   UPSCALE_FACTOR = 2
   UPSCALE_MAX_DIMENSION = 3000
   ```

4. **Keep the `# --- Constants ---` section comment** — it still applies to the remaining constants.

The resulting imports + constants section should look like:

```python
import os
import io
import time
import base64
from flask import Flask, render_template, request, jsonify
from PIL import Image
from google import genai
from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS

app = Flask(__name__)

# --- Constants ---
MAX_FILE_SIZE_MB = 10
UPSCALE_FACTOR = 2
UPSCALE_MAX_DIMENSION = 3000
```

No other lines in `app.py` change. The constants are still used by name in lines 83-111 — they now resolve via the import.
</action>

<acceptance_criteria>
- `app.py` contains `from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS`
- `app.py` does NOT contain `GEMINI_MODEL = 'gemini-3.1-flash-image-preview'` (no inline definition)
- `app.py` does NOT contain `MAX_RETRIES = 3` as a standalone assignment (no inline definition)
- `app.py` does NOT contain `RETRY_DELAY_SECONDS = 2` as a standalone assignment (no inline definition)
- `app.py` still contains `MAX_FILE_SIZE_MB = 10`
- `app.py` still contains `UPSCALE_FACTOR = 2`
- `app.py` still contains `UPSCALE_MAX_DIMENSION = 3000`
- `app.py` still contains `# --- Constants ---`
- `app.py` still contains `model=GEMINI_MODEL` (usage unchanged, line ~89)
- `app.py` still contains `retry_delay = RETRY_DELAY_SECONDS` (usage unchanged, line ~83)
- `app.py` still contains `for attempt in range(MAX_RETRIES):` (usage unchanged, line ~86)
- Running `python -c "import app"` does not raise ImportError (verify import chain works)
</acceptance_criteria>

---

### Task 2: Update `image_translator.py` — replace constant definitions with import from `grid_translator`

<read_first>
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/image_translator.py (full file — especially lines 1-14 for imports and constants, and lines 69-99 for where constants are used)
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/grid_translator.py (verify constants exist and values match)
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/.planning/phases/01-grid-module-core/01-RESEARCH.md (Finding 5 for which constants move and which stay)
- d:/_Dev/GoodFirstIsuuses/ImagiTranslate/.planning/codebase/CONVENTIONS.md (section 1.1 for import ordering)
</read_first>

<action>
In `image_translator.py`, make these exact changes:

1. **Add import** — after the `from google import genai` line (line 7), add:
   ```python
   from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS
   ```

2. **Remove three constant definitions** — delete these exact lines:
   ```python
   GEMINI_MODEL = 'gemini-3.1-flash-image-preview'
   MAX_RETRIES = 3
   RETRY_DELAY_SECONDS = 2
   ```

3. **Keep these constants in place** — do NOT remove or modify:
   ```python
   VALID_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
   UPSCALE_FACTOR = 2
   UPSCALE_MAX_DIMENSION = 3000
   ```

The resulting imports + constants section should look like:

```python
import os
import io
import time
import argparse
from pathlib import Path
from PIL import Image
from google import genai
from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS

VALID_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
UPSCALE_FACTOR = 2
UPSCALE_MAX_DIMENSION = 3000
```

No other lines in `image_translator.py` change. The constants are still used by name in lines 69-99 — they now resolve via the import.
</action>

<acceptance_criteria>
- `image_translator.py` contains `from grid_translator import GEMINI_MODEL, MAX_RETRIES, RETRY_DELAY_SECONDS`
- `image_translator.py` does NOT contain `GEMINI_MODEL = 'gemini-3.1-flash-image-preview'` (no inline definition)
- `image_translator.py` does NOT contain `MAX_RETRIES = 3` as a standalone assignment (no inline definition)
- `image_translator.py` does NOT contain `RETRY_DELAY_SECONDS = 2` as a standalone assignment (no inline definition)
- `image_translator.py` still contains `VALID_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}`
- `image_translator.py` still contains `UPSCALE_FACTOR = 2`
- `image_translator.py` still contains `UPSCALE_MAX_DIMENSION = 3000`
- `image_translator.py` still contains `model=GEMINI_MODEL` (usage unchanged, line ~74)
- `image_translator.py` still contains `retry_delay = RETRY_DELAY_SECONDS` (usage unchanged, line ~69)
- `image_translator.py` still contains `for attempt in range(MAX_RETRIES):` (usage unchanged, line ~72)
- Running `python -c "from image_translator import translate_images"` does not raise ImportError
</acceptance_criteria>

---

## Verification

After all tasks are complete, verify:

```bash
# 1. Both files import from grid_translator
python -c "
import ast

for fname in ['app.py', 'image_translator.py']:
    tree = ast.parse(open(fname).read())
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == 'grid_translator':
            names = [a.name for a in node.names]
            assert 'GEMINI_MODEL' in names, f'{fname}: missing GEMINI_MODEL import'
            assert 'MAX_RETRIES' in names, f'{fname}: missing MAX_RETRIES import'
            assert 'RETRY_DELAY_SECONDS' in names, f'{fname}: missing RETRY_DELAY_SECONDS import'
            found = True
    assert found, f'{fname}: no import from grid_translator found'
    print(f'{fname}: imports OK')
"

# 2. No duplicate definitions in either file
python -c "
for fname in ['app.py', 'image_translator.py']:
    content = open(fname).read()
    assert \"GEMINI_MODEL = '\" not in content, f'{fname} still defines GEMINI_MODEL'
    assert 'MAX_RETRIES = 3' not in content.replace('from grid_translator import', ''), f'{fname} still defines MAX_RETRIES'
    assert 'RETRY_DELAY_SECONDS = 2' not in content.replace('from grid_translator import', ''), f'{fname} still defines RETRY_DELAY_SECONDS'
    print(f'{fname}: no duplicates OK')
"

# 3. Constants are still used (not accidentally deleted references)
python -c "
for fname in ['app.py', 'image_translator.py']:
    content = open(fname).read()
    assert 'GEMINI_MODEL' in content, f'{fname}: GEMINI_MODEL reference missing'
    assert 'MAX_RETRIES' in content, f'{fname}: MAX_RETRIES reference missing'
    assert 'RETRY_DELAY_SECONDS' in content, f'{fname}: RETRY_DELAY_SECONDS reference missing'
    print(f'{fname}: usages intact OK')
"

# 4. Remaining constants untouched
python -c "
app = open('app.py').read()
assert 'MAX_FILE_SIZE_MB = 10' in app
assert 'UPSCALE_FACTOR = 2' in app

cli = open('image_translator.py').read()
assert \"VALID_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}\" in cli
assert 'UPSCALE_FACTOR = 2' in cli
print('Remaining constants OK')
"
```

---

## must_haves

- [ ] `app.py` imports `GEMINI_MODEL`, `MAX_RETRIES`, `RETRY_DELAY_SECONDS` from `grid_translator`
- [ ] `image_translator.py` imports `GEMINI_MODEL`, `MAX_RETRIES`, `RETRY_DELAY_SECONDS` from `grid_translator`
- [ ] Neither `app.py` nor `image_translator.py` contains inline constant definitions for these three values
- [ ] `app.py` still contains `MAX_FILE_SIZE_MB`, `UPSCALE_FACTOR`, `UPSCALE_MAX_DIMENSION` as local definitions
- [ ] `image_translator.py` still contains `VALID_EXTENSIONS`, `UPSCALE_FACTOR`, `UPSCALE_MAX_DIMENSION` as local definitions
- [ ] All existing usages of `GEMINI_MODEL`, `MAX_RETRIES`, `RETRY_DELAY_SECONDS` in both files remain unchanged
