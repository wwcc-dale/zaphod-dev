# Zaphod Architecture

> Last updated: January 2026

## What Zaphod Does

Zaphod is a **local-first course authoring workspace** that makes Canvas LMS course management faster, safer, and more reusable than editing directly in the browser.

**Core Concept:** Plain-text files on disk are the single source of truth → Zaphod syncs them to Canvas.

---

## System Overview

### Directory Structure

```
course/
├── zaphod.yaml                 # Course configuration (course_id, settings)
├── pages/                      # All content items
│   ├── 01-Intro.module/        # Module folder (NEW: .module suffix)
│   │   ├── 01-welcome.page/    # Canvas Page
│   │   │   └── index.md
│   │   ├── 02-homework.assignment/  # Canvas Assignment
│   │   │   ├── index.md
│   │   │   └── rubric.yaml     # Optional rubric
│   │   └── 03-quiz.quiz/       # Canvas Quiz (NEW)
│   │       └── index.md
│   ├── module-Legacy.../       # LEGACY: module- prefix still supported
│   ├── resources.link/         # External link
│   └── handout.file/           # File download
├── question-banks/                 # Question bank sources
│   ├── chapter1.bank.md        # NEW: .bank.md format
│   └── legacy.quiz.txt         # LEGACY: .quiz.txt still supported
├── assets/                     # Shared media (images, videos, PDFs)
│   └── subfolders/supported/
├── outcomes/                   # Learning outcomes
│   └── outcomes.yaml
├── modules/                    # Module ordering
│   └── module_order.yaml       # Optional explicit ordering
├── rubrics/                    # Shared rubrics
│   ├── shared_rubric.yaml
│   └── rows/                   # Reusable criteria rows
│       └── writing_clarity.yaml
├── includes/                   # Shared content snippets
│   └── late_policy.md
└── _course_metadata/           # Generated state (gitignore this)
    ├── defaults.json           # Legacy course_id storage
    ├── upload_cache.json       # Canvas file ID cache
    ├── bank_cache.json         # Question bank hash cache
    ├── quiz_cache.json         # Quiz hash cache
    └── watch_state.json        # Incremental sync state
```

### Content Types

| Extension | Canvas Type | Description |
|-----------|-------------|-------------|
| `.page/` | Page | Informational content |
| `.assignment/` | Assignment | Gradable submissions |
| `.quiz/` | Quiz | Classic quizzes (NEW) |
| `.link/` | External URL | Link to external site |
| `.file/` | File | Downloadable file |
| `.bank.md` | Question Bank | Pool of questions for quizzes |

### Module Organization

**NEW Pattern (recommended):** `.module` suffix
```
pages/
├── 01-Week 1.module/          # → Module "Week 1" (position 1)
├── 02-Week 2.module/          # → Module "Week 2" (position 2)
└── 10-Final.module/           # → Module "Final" (position 3)
```

**LEGACY Pattern (still supported):** `module-` prefix
```
pages/
└── module-Week 1/             # → Module "Week 1"
```

**Module order inference:**
1. Explicit `modules/module_order.yaml` (highest priority)
2. Directory prefixes (numeric sort from `.module` folders)
3. Content order within modules from folder prefixes (01-, 02-, etc.)

---

## Processing Pipeline

### Unified CLI Entry Point

```bash
zaphod sync [--watch] [--dry-run] [--no-prune]
zaphod validate
zaphod prune [--dry-run]
zaphod list [--type TYPE]
zaphod new --type TYPE --name NAME
zaphod info
zaphod export [--output FILE]
```

### Pipeline Steps (in order)

| Step | Script | Purpose |
|------|--------|---------|
| 1 | `frontmatter_to_meta.py` | Parse index.md → meta.json + source.md |
| 2 | `publish_all.py` | Create/update pages, assignments, files, links |
| 3 | `sync_banks.py` | Import question banks (QTI migration) |
| 4 | `sync_quizzes.py` | Create/update quiz folders |
| 5 | `sync_modules.py` | Organize content into modules |
| 6 | `sync_clo_via_csv.py` | Import learning outcomes |
| 7 | `sync_rubrics.py` | Create/update rubrics |
| 8 | `prune_canvas_content.py` | Remove orphaned content, clean work files |

### 1. frontmatter_to_meta.py

**Input:** `pages/**/index.md` with YAML frontmatter
**Output:** `meta.json` (metadata) + `source.md` (processed body)

**Features:**
- Parses YAML frontmatter
- Expands `{{var:key}}` variables
- Expands `{{include:name}}` blocks (recursive)
- Infers type from folder extension
- Infers module from `.module` directory structure

### 2. publish_all.py

**Input:** `meta.json` + `source.md`
**Output:** Canvas pages, assignments, files, links

**Features:**
- Replaces `{{video:filename}}` with Canvas iframe
- Uploads local assets (with content-hash caching)
- Supports `--dry-run` for preview
- Supports `--assets-only` for bulk asset upload

### 3. sync_banks.py

**Input:** `question-banks/*.bank.md` or `*.quiz.txt`
**Output:** Canvas question banks via QTI migration

**Features:**
- Content-hash caching (avoids re-upload)
- Supports `bank_name` frontmatter override
- Tracks migration status with timeout handling
- Warns about duplicates on `--force`

### 4. sync_quizzes.py

**Input:** `pages/**/*.quiz/index.md`
**Output:** Canvas Classic quizzes

**Features:**
- Quiz as first-class content (alongside pages/assignments)
- References question banks by `bank_id` or bank name
- Supports inline questions
- Content-hash caching
- Module inference from directory structure

### 5. sync_modules.py

**Input:** `meta.json` files with `modules` lists
**Output:** Canvas modules with ordered items

**Features:**
- Creates modules on demand
- Orders items by folder prefix (01-, 02-)
- Supports `position` frontmatter override
- Applies `module_order.yaml` sequencing

### 6. sync_clo_via_csv.py

**Input:** `outcomes/outcomes.yaml`
**Output:** Canvas outcomes via CSV import

### 7. sync_rubrics.py

**Input:** `rubric.yaml` in `.assignment` folders
**Output:** Canvas rubrics attached to assignments

**Features:**
- Supports `use_rubric: name` for shared rubrics
- Supports `{{rubric_row:name}}` expansion
- Creates rubric and associates with assignment

### 8. prune_canvas_content.py

**Purpose:** Clean up orphaned content

**What it prunes:**
- Canvas pages not in local `.page` folders
- Assignments not in local `.assignment` folders (optional)
- Quizzes not in local `.quiz` folders
- Module items not in `modules` lists
- Empty modules (except those in config)
- Work files: `meta.json`, `source.md`, etc.

---

## Quiz Architecture

### Two-Layer Model

```
┌─────────────────────────────────────────────────────┐
│  question-banks/*.bank.md                               │
│  (Question Pools - Canvas Question Banks)           │
│  ├── chapter1.bank.md  →  "Chapter 1 Questions"    │
│  └── chapter2.bank.md  →  "Chapter 2 Questions"    │
└─────────────────────────────────────────────────────┘
                       ▼
        ┌─────────────────────────────────────────────┐
        │  pages/**/*.quiz/                           │
        │  (Deployable Quizzes - Canvas Quizzes)      │
        │  ├── week1.quiz/index.md  →  "Week 1 Quiz" │
        │  │     question_groups:                     │
        │  │       - bank_id: 12345                   │
        │  │         pick: 5                          │
        │  └── midterm.quiz/index.md → "Midterm"     │
        │          (inline questions)                 │
        └─────────────────────────────────────────────┘
```

### Bank File Format (.bank.md)

```markdown
---
bank_name: "Chapter 1 Questions"
---

1. What is 2+2?
a) 3
*b) 4
c) 5

2. Select all prime numbers:
[*] 2
[*] 3
[ ] 4
[*] 5
```

### Quiz Folder Format (.quiz/)

```markdown
---
name: "Week 1 Quiz"
quiz_type: assignment
time_limit: 30
shuffle_answers: true
question_groups:
  - bank_id: 12345
    pick: 5
    points_per_question: 2
---

Instructions for the quiz go here.
```

---

## Templating System

### Variables

```yaml
# In frontmatter:
instructor: "Dr. Smith"
---
Contact {{var:instructor}} for help.
```

**Resolution order:**
1. Same-file frontmatter
2. Course `variables.yaml`
3. Shared `_all_courses/variables.yaml`

### Includes

```markdown
{{include:late_policy}}
```

**Search order:**
1. `pages/includes/late_policy.md`
2. `includes/late_policy.md`
3. `_all_courses/includes/late_policy.md`

### Video Embedding

```markdown
{{video:lecture1.mp4}}
```

Converted to Canvas media iframe after upload.

---

## Caching System

### Content-Hash Caching

All upload operations use content hashing to avoid redundant uploads:

```
Cache key: {course_id}:{filename}:{content_hash}
```

**Benefits:**
- Same filename, different content → re-upload
- Same content, same name → skip
- Works across courses

**Cache files:**
- `upload_cache.json` - Media/asset uploads
- `bank_cache.json` - Question bank imports
- `quiz_cache.json` - Quiz syncs

---

## Configuration

### zaphod.yaml (recommended)

```yaml
course_id: 12345
# Optional overrides
api_url: https://canvas.institution.edu
```

### Environment Variables

```bash
COURSE_ID=12345
CANVAS_API_KEY=token
CANVAS_API_URL=https://canvas.institution.edu
CANVAS_CREDENTIAL_FILE=~/.canvas/credentials.txt
```

### Credentials File

```python
# ~/.canvas/credentials.txt
API_KEY = "your_token"
API_URL = "https://canvas.institution.edu"
```

**Priority:** Environment variables → zaphod.yaml → defaults.json → credentials file

---

## Security Features

- **Safe credential parsing** (no `exec()`)
- **Environment variable support** for CI/CD
- **Path traversal protection** in CLI
- **File permission warnings** for credentials
- **Request timeouts** on all API calls
- **Content validation** via YAML safe_load

---

## Export Capability

### Common Cartridge Export

```bash
zaphod export --output course.imscc
```

**Exports:**
- Pages as HTML
- Assignments with rubrics
- Quizzes as QTI 1.2
- Learning outcomes
- Module structure
- Media assets

**Compatible with:** Canvas, Moodle, Blackboard, Brightspace, Sakai

---

## Incremental Processing

When `ZAPHOD_CHANGED_FILES` is set:
- Only changed folders are processed
- Watch mode sets this automatically
- Full sync: 5+ minutes → Incremental: 10-30 seconds

---

## Data Flow Example

```
User edits: pages/01-Intro.module/essay.assignment/index.md
     ↓
frontmatter_to_meta.py → meta.json + source.md
     ↓
publish_all.py → Creates/updates Canvas Assignment
     ↓
sync_rubrics.py → Attaches rubric from rubric.yaml
     ↓
sync_modules.py → Adds to "Intro" module
     ↓
prune_canvas_content.py → Removes orphaned items, cleans work files
     ↓
Canvas reflects latest local state
```
