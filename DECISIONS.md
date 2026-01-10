# Key Design Decisions

Document significant architectural choices with rationale and trade-offs.

---

## File-Based Pipeline vs API Server
**Date:** Initial design (2024)
**Status:** Current, evolving (adding API for UI)

**Context:**
Need to sync local content to Canvas. Two approaches:
1. Script pipeline that runs on demand
2. API server that's always running

**Decision:** Script-based pipeline with optional watcher

**Rationale:**
- **Simplicity:** Each script does one thing, easy to understand
- **Debugging:** Run individual steps, see exactly what happens
- **No ops:** No server to manage, restart, monitor
- **Local-first:** Matches workflow (edit files → sync)
- **Incremental adoption:** Can add API layer later

**Trade-offs:**
- ✗ State shared via files, not memory
- ✗ Harder to add web UI (now adding API layer for this)
- ✗ No concurrent user support
- ✗ Each script re-initializes Canvas API
- ✓ But: Simple, debuggable, works for single-user

**Alternatives Considered:**
- Django/Flask app with database: Too heavy, unnecessary complexity
- Pure API with no CLI: Less accessible for dev workflow

**Outcome:**
Works well. Adding FastAPI layer in 2026 for UI while keeping scripts for CLI.

---

## Frontmatter + Markdown vs Separate Config
**Date:** Initial design (2024)
**Status:** Current

**Context:**
Need to store both metadata (title, settings) and content for pages/assignments.

**Options:**
1. Frontmatter in markdown (Jekyll-style)
2. Separate JSON config + markdown content
3. All in JSON with markdown as string

**Decision:** YAML frontmatter in markdown files

**Rationale:**
- **Single file:** One source of truth, easier to manage
- **Familiar:** Common pattern (Jekyll, Hugo, Gatsby)
- **Git-friendly:** All changes in one file
- **Human-readable:** YAML is clear, markdown is clear
- **Portable:** Can be used outside Zaphod

**Trade-offs:**
- ✗ YAML syntax errors break entire file
- ✗ Can't query metadata without parsing file
- ✗ Harder to validate (need full parser)
- ✓ But: Much better editing experience

**Alternatives Considered:**
- `meta.json` + `content.md`: Two files to keep in sync, annoying
- All JSON: Markdown as string is ugly, not git-friendly

**Outcome:**
Right choice. YAML errors are rare, and single-file is much better UX.

---

## Incremental Processing
**Date:** v0.2 (2025)
**Status:** Current, working well

**Context:**
Large courses (100+ pages) took 5+ minutes for full sync. Slow dev cycle.

**Problem:**
- Watch mode ran full pipeline on every change
- Mostly wasted work (99% of content unchanged)
- Bad developer experience

**Decision:** Track changed files, only process affected folders

**Implementation:**
```python
# watch_and_publish.py exports:
ZAPHOD_CHANGED_FILES="path/to/file1.md
path/to/file2.md"

# Child scripts check:
if ZAPHOD_CHANGED_FILES:
    # Incremental mode
else:
    # Full scan (backward compatible)
```

**Rationale:**
- **Speed:** 5 minutes → 10-30 seconds for typical edits
- **Better DX:** Watch mode feels instant
- **Backward compatible:** Still works without env var
- **Simple:** Just an environment variable

**Trade-offs:**
- ✗ More complex change detection logic
- ✗ State file management (`watch_state.json`)
- ✗ Edge cases (file renames, moves)
- ✓ But: Massive speed improvement worth it

**Alternatives Considered:**
- Database tracking: Overkill, adds dependency
- Git diff: Requires git, complex
- Filesystem timestamps: Unreliable (clock changes, etc.)

**Outcome:**
Big win. Makes Zaphod practical for large courses.

---

## NYIT Quiz Format vs Custom Parser
**Date:** Initial quiz support (2024)
**Status:** Current

**Context:**
Need plain-text quiz authoring. Canvas has no bulk import format we like.

**Decision:** Use NYIT Canvas Exam Converter format

**Rationale:**
- **Proven:** NYIT tool has been used successfully
- **Compact:** Easier to read/write than verbose formats
- **Simple:** Line-based, easy to parse
- **Familiar:** For anyone who's used NYIT tool

**Format Example:**
```
1. Question text?
a) Wrong answer
*b) Correct answer
c) Wrong answer
```

**Trade-offs:**
- ✗ Custom parsing logic needed
- ✗ Limited to Classic Quizzes (not New Quizzes)
- ✗ Learning curve for new users
- ✓ But: Much faster than Canvas UI

**Alternatives Considered:**
- QTI format: Too verbose, complex
- Canvas API one-by-one: Slow, clunky
- Custom JSON/YAML: Reinventing wheel

**Outcome:**
Good choice. Users who learn it love it.

---

## Separate Assets Folder vs Per-Content Files
**Date:** Initial design (2024)
**Status:** Current, with flexibility

**Context:**
Where to put media files (images, videos, PDFs)?

**Decision:** Hybrid approach

**Structure:**
```
assets/           # Shared across course
  logo.png
  syllabus.pdf

pages/
  intro.page/     # Page-specific
    intro-bg.jpg
    index.md
```

**Rationale:**
- **Assets folder:** For reused files (branding, shared resources)
- **Content folders:** For one-off files (specific to that page)
- **Flexibility:** Author chooses based on usage

**Trade-offs:**
- ✗ Two places to look for files
- ✓ But: Clearer intent (shared vs local)

**Implementation:**
- Can symlink from content folder to assets
- Upload cache prevents re-uploads
- Both are valid sources during publish

**Outcome:**
Works well. Most courses use `assets/` for big shared stuff.

---

## Prune by Default vs Opt-In
**Date:** v0.3 (2025)
**Status:** Changed to on-by-default

**Context:**
Orphaned Canvas content accumulates over time. Should we delete automatically?

**Original:** Opt-in (must pass `--prune`)
**Changed:** Prune by default (can disable with flag)

**Rationale for Change:**
- **Expected behavior:** Local files are source of truth
- **Cleaner courses:** No stale content confusing students
- **Less surprise:** Users expect sync to mean "make Canvas match local"

**Safety Measures:**
- Dry-run available (`--dry-run`)
- Protected modules (`module_order.yaml`)
- Assignments pruning can be disabled
- Clear logging of what will be deleted

**Trade-offs:**
- ✗ Accidental deletions possible
- ✓ But: Cleaner default, safety valves available

**Outcome:**
Better default. Users can disable if needed.

---

## Module Order YAML vs Frontmatter
**Date:** v0.2 (2025)
**Status:** Current

**Context:**
Two ways to define module structure:
1. Each item lists its modules (frontmatter)
2. Central file defines all module structure

**Decision:** Hybrid approach

**Implementation:**
- Items list their modules in frontmatter: `modules: ["Module 1"]`
- Optional `module_order.yaml` defines sequence + protected modules

**Rationale:**
- **Distributed:** Each item knows where it belongs (local knowledge)
- **Centralized ordering:** One place controls overall sequence
- **Flexible:** Can work without `module_order.yaml`

**Example:**
```yaml
# modules/module_order.yaml
protected_modules:
  - "Course Resources"
module_order:
  - "Module 0: Start Here"
  - "Module 1: Week 1"
```

**Trade-offs:**
- ✗ Two sources of truth (item lists + central order)
- ✓ But: Local control + global order

**Outcome:**
Works well. Most courses use both.

---

## Why Not New Quizzes?
**Date:** Ongoing
**Status:** Current limitation

**Context:**
Canvas has two quiz systems: Classic and New Quizzes.

**Decision:** Only support Classic Quizzes

**Rationale:**
- **API availability:** Classic has full API, New Quizzes API limited
- **Plain text friendly:** Classic format maps well to text
- **Institutional support:** Many schools still use Classic
- **Time/effort:** New Quizzes would require major rewrite

**Trade-offs:**
- ✗ New Quizzes have better features (item banks, question types)
- ✗ Classic will eventually be deprecated
- ✓ But: Classic works for most use cases now

**Future:**
May add New Quizzes support when API improves.

---

## Recent Decision: CLI vs Multiple Scripts
**Date:** January 2026
**Status:** Added, but keeping both

**Context:**
Users had to remember which script to run when.

**Decision:** Add unified CLI that wraps scripts

**Implementation:**
```bash
# Old way (still works):
python zaphod/publish_all.py

# New way:
zaphod publish
```

**Rationale:**
- **Better UX:** One command, clear subcommands
- **Backward compatible:** Scripts still work
- **Discoverability:** `--help` shows all options

**Trade-offs:**
- ✗ Extra layer of indirection
- ✓ But: Much better user experience

**Outcome:**
Big improvement. New users love it.

---

## Template for Future Decisions
```markdown
## [Decision Title]
**Date:** [When decided]
**Status:** [Current/Changed/Deprecated]

**Context:**
[What problem were we solving?]

**Decision:** [What we chose]

**Rationale:**
- [Why option A]
- [Why not option B]

**Trade-offs:**
- ✗ [Downside 1]
- ✓ But: [Why acceptable]

**Alternatives Considered:**
- [Option B]: [Why rejected]
- [Option C]: [Why rejected]

**Outcome:**
[How it's working]
```