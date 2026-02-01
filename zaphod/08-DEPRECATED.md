# Deprecated Scripts & Features

> This file documents scripts and features that are no longer actively maintained or have been superseded by newer implementations.

---

## Deprecated Scripts

### sync_quiz_banks.py

**Status:** DEPRECATED (January 2026)
**Replaced by:** `sync_banks.py` + `sync_quizzes.py`

**What it did:**
- Read `question-banks/*.quiz.txt` files
- Created Classic Quizzes directly via Canvas API
- Combined bank and quiz creation in one step

**Why deprecated:**
- The two-layer model (banks vs quizzes) is cleaner
- New `sync_banks.py` handles question bank import via QTI
- New `sync_quizzes.py` handles quiz folders as first-class content
- Better caching and incremental sync support

**Migration:**
1. Convert `.quiz.txt` files to `.bank.md` format for question banks
2. Create `.quiz/` folders for deployable quizzes
3. Use the new pipeline: `zaphod sync`

---

### import_quiz_bank.py

**Status:** DEPRECATED (January 2026)
**Replaced by:** `sync_banks.py`

**What it did:**
- Imported a single quiz bank file to Canvas
- Used QTI format conversion
- Standalone import utility

**Why deprecated:**
- Functionality absorbed into `sync_banks.py`
- Better content-hash caching
- Integrated into unified pipeline

**Migration:**
- Use `sync_banks.py` or `zaphod sync` instead

---

### prune_quizzes.py

**Status:** PARTIALLY DEPRECATED (January 2026)
**May be replaced by:** Enhanced `prune_canvas_content.py`

**What it did:**
- Delete Classic quizzes with zero questions
- Delete question banks not matching local files

**Current status:**
- NOT in the main CLI pipeline
- Quiz awareness added to `prune_canvas_content.py`
- May still be useful as standalone maintenance tool

**Recommendation:**
- Use `zaphod prune` for routine cleanup
- Consider this script for deep quiz cleanup if needed

---

## Deprecated File Formats

### *.quiz.txt (Question Banks)

**Status:** LEGACY (still supported)
**Preferred:** `*.bank.md`

The `.quiz.txt` format is still parsed but `.bank.md` is recommended:
- Cleaner separation of banks vs quizzes
- Consistent markdown format
- Better frontmatter support

**Example migration:**
```
# Old: question-banks/chapter1.quiz.txt
# New: question-banks/chapter1.bank.md
```

---

### module- prefix (Module Folders)

**Status:** LEGACY (still supported)
**Preferred:** `.module` suffix

Both patterns work for module organization:

```
# LEGACY (still works):
pages/module-Week 1/intro.page/

# PREFERRED (new pattern):
pages/01-Week 1.module/intro.page/
```

Benefits of `.module` suffix:
- Numeric prefix for ordering
- Cleaner directory names
- Consistent with content type naming

---

## Deprecated Dependencies

### markdown2canvas

**Status:** BEING PHASED OUT
**Replaced by:** Native `canvas_publish.py`

The external `markdown2canvas` library is being replaced with native Zaphod publishing code for:
- Better control over Canvas API interactions
- Reduced external dependencies
- Easier maintenance

**Current status:**
- Some code paths still use markdown2canvas
- Native publishing handles most cases
- Full transition in progress

---

## Deprecated Configuration

### _course_metadata/defaults.json (for course_id)

**Status:** LEGACY (still supported)
**Preferred:** `zaphod.yaml`

```yaml
# PREFERRED: zaphod.yaml in course root
course_id: 12345

# LEGACY: _course_metadata/defaults.json
{"course_id": "12345"}
```

---

## Cleanup Recommendations

If you're maintaining an older Zaphod installation:

1. **Convert quiz files:**
   - Move questions to `*.bank.md` files
   - Create `*.quiz/` folders for deployable quizzes

2. **Update module structure:**
   - Rename `module-Name/` to `01-Name.module/`
   - Add numeric prefixes for ordering

3. **Update configuration:**
   - Create `zaphod.yaml` with `course_id`
   - Can remove `defaults.json` after migration

4. **Clear old caches:**
   ```bash
   rm _course_metadata/quiz_cache.json
   rm _course_metadata/bank_cache.json
   zaphod sync --force
   ```

---

## Script Status Summary

| Script | Status | Replacement |
|--------|--------|-------------|
| `sync_quiz_banks.py` | DEPRECATED | `sync_banks.py` + `sync_quizzes.py` |
| `import_quiz_bank.py` | DEPRECATED | `sync_banks.py` |
| `prune_quizzes.py` | PARTIAL | `prune_canvas_content.py` |
| `test_quiz_parsing.py` | TEST ONLY | N/A (dev utility) |

---

*Last updated: January 2026*
