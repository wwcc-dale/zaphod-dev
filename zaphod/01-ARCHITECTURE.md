# Zaphod Architecture

## What Zaphod Does

Zaphod is a **local-first course authoring workspace** that makes Canvas LMS course management faster, safer, and more reusable than editing directly in the browser.

**Core Concept:** Plain-text files on disk are the single source of truth → Zaphod scripts sync them to Canvas.

## Key Design Philosophy

### File-Based Source of Truth
- All content (pages, assignments, quizzes, rubrics, outcomes) lives in plain text
- Version control friendly (Git)
- Multiple Canvas shells can be driven from one repository
- Portability: content not locked in Canvas

### Why This Matters
- **Collaboration:** Git-based version control shows what changed, when, who
- **Reuse:** Copy files/folders instead of rebuilding in Canvas UI
- **Consistency:** Course-wide changes applied everywhere via variables/includes
- **Safety:** Test in sandbox first, then publish to live
- **Longevity:** Plain text survives LMS migrations

## System Architecture

### File Structure
```
course/
├── pages/                      # Content items
|   ├── *.page/                # Canvas Pages
|   ├── *.assignment/          # Canvas Assignments (with optional rubric.yaml)
|   ├── *.link/                # External links
|   └── *.file/                # File items
├── assets/                     # Shared media (images, PDFs, videos)
├── quiz-banks/                 # *.quiz.txt (NYIT-style plain text)
├── outcomes/                   # outcomes.yaml (course learning outcomes)
├── modules/                    # module_order.yaml (module structure)
├── rubrics/                    # Shared rubrics and reusable rows
|   ├── *.yaml                 # Full shared rubrics
|   └── rows/*.yaml            # Reusable criterion rows
├── _course_metadata/           # Generated state/config
|   ├── defaults.json          # course_id, defaults
|   ├── upload_cache.json      # Canvas file upload cache
|   └── watch_state.json       # Incremental sync state
└── zaphod/                     # Python scripts (the engine)
```

### Content Authoring Model

**Each content item = One folder with `index.md`**
```markdown
---
# Frontmatter: YAML metadata
name: "Page Title"
type: "page"
modules: ["Module 1"]
published: true
---

# Body: Markdown content
Content goes here with {{var:variables}} and {{include:snippets}}
```

**Key Pattern:** Frontmatter (settings) + Body (content) in single file

### Templating System

**Variables:** `{{var:key}}` - replaced with frontmatter values
```markdown
instructor_name: "Ada Lovelace"
---
Contact {{var:instructor_name}} for help.
```

**Includes:** `{{include:name}}` - shared content blocks
```markdown
{{include:late-work-policy}}  # Inserts pages/includes/late-work-policy.md
```

**Search precedence:**
1. `pages/includes/name.md` (course-specific)
2. `includes/name.md` (course-level)
3. `_all_courses/includes/name.md` (shared across courses)

### Media Handling

**Video Embedding:** `{{video:filename.mp4}}`
- Looks in `assets/` or content folder
- Uploads to Canvas (with caching)
- Converts to Canvas media_attachments_iframe

**Other Media:** Standard markdown `![](path)` or `[link](path)`
- Uploads to Canvas
- Caches file IDs to avoid re-upload
- Updates links in published content

## Processing Pipeline

### 1. `frontmatter_to_meta.py`
**Purpose:** Parse index.md → generate work files

**What it does:**
- Parses YAML frontmatter from `index.md`
- Applies `{{var:...}}` interpolation
- Expands `{{include:...}}` blocks (recursively)
- Writes `meta.json` (metadata) + `source.md` (processed body)

**Why:** Separates concerns - metadata vs content

### 2. `publish_all.py`
**Purpose:** Sync content to Canvas

**What it does:**
- Reads `meta.json` + `source.md`
- Replaces `{{video:...}}` with Canvas iframe markup
- Creates/updates Canvas Pages, Assignments, Files, Links
- Uploads media files (with caching)
- `--assets-only` mode for bulk asset upload

**Dependencies:** Uses `markdown2canvas` (being phased out) and `canvasapi`

### 3. `sync_modules.py`
**Purpose:** Organize content into Canvas modules

**What it does:**
- Reads `modules` list from each `meta.json`
- Creates modules if missing
- Adds items to modules (avoids duplicates)
- Applies `module_order.yaml` for sequencing
- Respects `indent` for visual grouping

### 4. `sync_clo_via_csv.py`
**Purpose:** Import course learning outcomes

**What it does:**
- Reads `outcomes/outcomes.yaml`
- Generates Canvas Outcomes CSV format
- Imports via `Course.import_outcome()` API

**Note:** Uses Canvas CSV import, not outcome-by-outcome API

### 5. `sync_rubrics.py`
**Purpose:** Create/update Canvas rubrics

**What it does:**
- Finds `rubric.yaml` in `.assignment` folders
- Supports `use_rubric: name` to reference shared rubrics
- Expands `{{rubric_row:name}}` from `rubrics/rows/`
- POSTs to `/api/v1/courses/:course_id/rubrics`
- Associates with assignment + marks for grading

**Rubric Architecture:**
- Per-assignment: `pages/foo.assignment/rubric.yaml`
- Shared rubrics: `rubrics/essay_rubric.yaml`
- Reusable rows: `rubrics/rows/writing_clarity.yaml`

### 6. `sync_quiz_banks.py`
**Purpose:** Convert text quizzes to Canvas Classic quizzes

**What it does:**
- Reads `quiz-banks/*.quiz.txt`
- Parses YAML frontmatter (quiz settings)
- Parses NYIT-style question body
- Creates Classic Quiz via `course.create_quiz()`
- Adds questions via `quiz.create_question()`

**Question Types Supported:**
- Multiple choice (`*b)` marks correct)
- Multiple answers (`[*]` marks correct)
- True/False (`*a) True`)
- Short answer (`* answer`)
- Essay (`####`)
- File upload (`^^^^`)

### 7. `prune_canvas_content.py`
**Purpose:** Remove orphaned Canvas content

**What it does:**
- **Content pruning:** Deletes Canvas pages/assignments not in local files
- **Module-item pruning:** Removes module items not in `modules` lists
- **Empty module pruning:** Deletes empty modules (except those in `module_order.yaml`)
- **Work-file cleanup:** Removes generated files (`source.md`, etc.)

**Controlled by:**
- `ZAPHOD_PRUNE_APPLY` (default true)
- `ZAPHOD_PRUNE_ASSIGNMENTS` (default true)
- `--dry-run` flag for preview

### 8. `prune_quizzes.py`
**Purpose:** Clean up quiz content

**What it does:**
- Deletes Classic quizzes with zero questions
- Deletes question banks not matching `*.quiz.txt` files

### 9. `watch_and_publish.py`
**Purpose:** Auto-run pipeline on file changes

**What it does:**
- Monitors for changes to:
  - `pages/**/index.md`
  - `outcomes/outcomes.yaml`
  - `modules/module_order.yaml`
  - `quiz-banks/*.quiz.txt`
  - `rubric.{yaml,yml,json}`
- Debounces changes (2 second window)
- Exports `ZAPHOD_CHANGED_FILES` env var
- Runs full pipeline
- Maintains `_course_metadata/watch_state.json`

**State Tracking:**
- `last_run_ts` - timestamp of last run
- `run_count` - total runs
- `last_run_datetime` - ISO timestamp

### 10. `export_cartridge.py`
**Purpose:** Export course to IMS Common Cartridge format

**What it does:**
- Creates a complete `.imscc` package for LMS portability
- Generates `imsmanifest.xml` with full course structure
- Converts pages to HTML web content
- Converts assignments to CC assignment XML with rubrics
- Converts quizzes to QTI 1.2 assessment format
- Includes learning outcomes
- Preserves module structure in organization
- Bundles all media assets

**Output Structure:**
```
course_export.imscc (ZIP file)
├── imsmanifest.xml           # Course manifest with organization
├── web_resources/            # Content items
│   ├── <item_id>/
│   │   ├── content.html      # Page/assignment HTML
│   │   ├── assignment.xml    # Assignment metadata (if applicable)
│   │   └── rubric.xml        # Rubric (if applicable)
│   └── assets/               # Media files
└── assessments/              # Quizzes
    └── <quiz_id>/
        └── assessment.xml    # QTI 1.2 format
```

**Compatible with:**
- Canvas LMS
- Moodle
- Blackboard
- Brightspace (D2L)
- Sakai
- Any CC 1.3 compliant LMS

## Incremental Processing

**Key Optimization:** Only process changed files

**How it works:**
1. `watch_and_publish.py` detects changes via watchdog
2. Computes changed files since `last_run_ts`
3. Exports `ZAPHOD_CHANGED_FILES` (newline-separated paths)
4. Child scripts check env var:
   - If set: only process affected folders
   - If unset: full scan (backward compatible)

**Benefits:**
- Large courses: 5+ minute full sync → 10-30 second incremental
- Better dev experience with watch mode

**Implementation:**
```python
def get_changed_files() -> list[Path]:
    raw = os.environ.get("ZAPHOD_CHANGED_FILES", "").strip()
    if not raw:
        return []  # Full mode
    return [Path(p) for p in raw.splitlines()]

# In each script:
changed = get_changed_files()
if changed:
    dirs = iter_changed_content_dirs(changed)  # Incremental
else:
    dirs = iter_all_content_dirs()  # Full scan
```

## Configuration

### Environment Variables
```bash
CANVAS_CREDENTIAL_FILE=$HOME/.canvas/credentials.txt
COURSE_ID=123456
ZAPHOD_PRUNE_APPLY=true
ZAPHOD_PRUNE_ASSIGNMENTS=true
```

### Credentials File
```python
# ~/.canvas/credentials.txt
API_KEY = "your_canvas_token"
API_URL = "https://canvas.yourinstitution.edu"
```

### Course Defaults
```json
// _course_metadata/defaults.json
{
  "course_id": 123456
}
```

**Resolution Order:** `COURSE_ID` env var → `defaults.json` → error

## Technology Stack

### Core Dependencies
- **canvasapi** - Canvas LMS API wrapper
- **markdown2canvas** - Markdown → Canvas HTML (being phased out)
- **python-frontmatter** - YAML frontmatter parsing
- **watchdog** - File system monitoring
- **PyYAML** - YAML parsing for configs

### Recent Additions (2026)
- **click** - CLI framework
- **pytest** - Testing
- **FastAPI** - Web UI backend (in progress)

## Critical Design Decisions

### Why Script Pipeline vs Monolithic App?
**Decision:** Multiple independent Python scripts

**Rationale:**
- Each script does one thing (Unix philosophy)
- Easy to understand and debug
- Can run steps individually
- No server management
- Good for single-user local workflows

**Trade-offs:**
- State shared via files, not memory
- Adding web UI requires API layer
- No concurrent user support

### Why Frontmatter + Markdown?
**Decision:** YAML frontmatter in markdown files

**Rationale:**
- Single file = single source of truth
- Common pattern (Jekyll, Hugo)
- Easy to edit (one file, not two)
- Git-friendly

**Trade-offs:**
- Harder to query metadata without parsing
- YAML errors can break entire file

### Why Incremental Mode?
**Decision:** Track changed files, only process those

**Rationale:**
- Courses can have 100+ pages
- Full sync takes 5+ minutes
- Incremental sync takes 10-30 seconds
- Better dev experience

**Trade-offs:**
- More complex change detection
- State file management
- Edge cases with file moves/renames

### Why NYIT Quiz Format?
**Decision:** Custom plain-text quiz format

**Rationale:**
- Faster than Canvas quiz editor
- Easy to version/review/duplicate
- Borrowed proven format from NYIT tool

**Trade-offs:**
- Custom parsing logic needed
- Limited to Classic Quizzes
- Learning curve for format

## Known Limitations

### Critical
- **No conflict resolution:** Last-write-wins when Canvas is newer
- **Cache invalidation:** Upload cache can get stale (manual delete needed)
- **No undo for prune:** Deletions are immediate

### Important
- **Module reordering:** Sometimes fails silently
- **Video cache:** Filename-based (doesn't detect content changes)
- **Single course:** One course at a time
- **Classic quizzes only:** No New Quizzes support

### By Design
- **Local-only:** No cloud sync
- **Single-user:** No concurrent editing support
- **One shell per run:** Must specify `COURSE_ID` for multi-shell

## Recent Evolution (2026)

### What We're Adding
1. **Unified CLI** (`cli.py`) - Better DX
2. **Testing** (`tests/`) - Catch regressions
3. **Better errors** (`errors.py`) - Actionable messages
4. **Web UI** (in progress) - Visual management
5. **Validation** (planned) - Pre-sync checks

### What's Unchanged
- Core pipeline architecture
- File structure
- Frontmatter format
- All existing scripts work as before

---

## Data Flow Example
```
User edits → pages/essay-1.assignment/index.md
              ↓
Watch detects change → exports ZAPHOD_CHANGED_FILES
              ↓
frontmatter_to_meta.py → essay-1.assignment/meta.json + source.md
              ↓
publish_all.py → Creates/updates Canvas Assignment
              ↓
sync_modules.py → Adds to "Module 2" in Canvas
              ↓
sync_rubrics.py → Creates rubric from rubric.yaml, attaches to assignment
              ↓
Result: Canvas reflects latest local state
```

## Success Metrics

**What makes Zaphod work well:**
- Course updates in seconds (incremental) vs minutes (Canvas UI)
- Content survives across terms/shells (just copy files)
- Changes visible in Git (who changed what, when)
- Test in sandbox, publish to live (same files)
- Variables/includes keep wording consistent

**What users value most:**
1. Speed (watch mode feels instant)
2. Reusability (copy course = copy folder)
3. Safety (Git history, sandbox testing)
4. Consistency (variables, includes)
5. Plain text (future-proof, portable)