# The Sync Pipeline

> Understanding how Zaphod processes your files and syncs them to Canvas.

---

## Overview

When you run `zaphod sync`, several scripts run in sequence to transform your local files into Canvas content. Think of it as an assembly line where each step has a specific job.

---

## Pipeline Steps

```
zaphod sync
    │
    ├── 1. frontmatter_to_meta.py   → Parse index.md files
    │
    ├── 2. publish_all.py           → Create/update Canvas content
    │
    ├── 3. sync_banks.py            → Import question banks
    │
    ├── 4. sync_quizzes.py          → Create/update quizzes
    │
    ├── 5. sync_modules.py          → Organize into modules
    │
    ├── 6. sync_clo_via_csv.py      → Import outcomes
    │
    ├── 7. sync_rubrics.py          → Create/attach rubrics
    │
    └── 8. prune_canvas_content.py  → Clean up orphaned content
```

---

## Step 1: frontmatter_to_meta.py

**Purpose:** Parse your `index.md` files and prepare them for publishing.

**What it does:**
1. Reads each `index.md` file
2. Extracts YAML frontmatter (name, modules, etc.)
3. Expands `{{var:...}}` variables
4. Expands `{{include:...}}` blocks
5. Infers type from folder extension (`.page` → page)
6. Infers module from folder structure (`.module` folders)
7. Writes `meta.json` (metadata) and `source.md` (processed content)

**Input:**
```
pages/welcome.page/index.md
```

**Output:**
```
pages/welcome.page/
├── index.md      (unchanged)
├── meta.json     (generated metadata)
└── source.md     (processed content)
```

---

## Step 2: publish_all.py

**Purpose:** Create or update content in Canvas.

**What it does:**
1. Reads `meta.json` and `source.md` for each content folder
2. Replaces `{{video:...}}` with Canvas media iframes
3. Uploads any local assets referenced in the content
4. Creates or updates Canvas pages, assignments, files, and links

**Caching:**
- Uses `_course_metadata/upload_cache.json` to avoid re-uploading unchanged files
- Cache key includes content hash, so changed files are re-uploaded

---

## Step 3: sync_banks.py

**Purpose:** Import question banks from `.bank.md` files.

**What it does:**
1. Reads `question-banks/*.bank.md` files
2. Parses questions (multiple choice, true/false, etc.)
3. Converts to QTI format
4. Imports to Canvas via Content Migration API
5. Waits for migration to complete

**Caching:**
- Uses `_course_metadata/bank_cache.json`
- Only re-imports banks that have changed

---

## Step 4: sync_quizzes.py

**Purpose:** Create quizzes from `.quiz` folders.

**What it does:**
1. Reads `pages/**/*.quiz/index.md`
2. Creates Canvas quizzes
3. Links question groups to banks (by bank_id)
4. Handles inline questions if present

---

## Step 5: sync_modules.py

**Purpose:** Organize content into Canvas modules.

**What it does:**
1. Reads module assignments from `meta.json` files
2. Creates modules that don't exist
3. Adds items to their assigned modules
4. Orders items within modules (by position or folder prefix)
5. Reorders modules according to `module_order.yaml` or folder prefixes

---

## Step 6: sync_clo_via_csv.py

**Purpose:** Import course learning outcomes.

**What it does:**
1. Reads `outcomes/outcomes.yaml`
2. Generates `outcomes/outcomes_import.csv` in Canvas format
3. Imports via Canvas Outcomes API

**Incremental:**
- Only runs when `outcomes.yaml` has changed

---

## Step 7: sync_rubrics.py

**Purpose:** Create rubrics and attach them to assignments.

**What it does:**
1. Finds `rubric.yaml` files in `.assignment` folders
2. Expands shared rubrics (`use_rubric:`)
3. Expands reusable rows (`{{rubric_row:...}}`)
4. Creates rubric via Canvas Rubrics API
5. Associates rubric with the assignment

---

## Step 8: prune_canvas_content.py

**Purpose:** Clean up orphaned content.

**What it does:**
1. Compares local content to Canvas content
2. Deletes Canvas pages not in local files
3. Deletes Canvas assignments not in local files (optional)
4. Removes module items that shouldn't be there
5. Deletes empty modules (unless protected)
6. Cleans up work files (`meta.json`, `source.md`)

**Safety:**
- Protected modules (from `module_order.yaml` or `.module` folders) are not deleted
- Use `--dry-run` to preview what would be deleted

---

## Incremental Mode

Zaphod supports incremental syncing for faster updates:

### Full Sync

```bash
zaphod sync
```

Processes everything. Takes longer but ensures consistency.

### Watch Mode (Incremental)

```bash
zaphod sync --watch
```

- Monitors files for changes
- Only processes changed files
- Much faster for small edits (seconds vs minutes)

### How Incremental Works

1. `watch_and_publish.py` detects file changes
2. Sets `ZAPHOD_CHANGED_FILES` environment variable
3. Each script checks this variable
4. Only processes folders containing changed files

---

## Dry Run Mode

Preview what would happen without making changes:

```bash
zaphod sync --dry-run
```

**What you see:**
- What content would be published
- What banks would be imported
- What quizzes would be created
- What would be pruned

**What doesn't run:**
- Module sync (requires content to exist first)
- Rubric sync (requires assignments to exist)
- CLO sync (depends on previous steps)

---

## Skipping Prune

If you don't want to clean up orphaned content:

```bash
zaphod sync --no-prune
```

Useful when:
- You have content in Canvas you want to keep
- You're debugging and don't want deletions
- You're doing partial updates

---

## Common Workflows

### Daily Editing

```bash
zaphod sync --watch
# Edit files, they sync automatically
# Ctrl+C when done
```

### Publishing Updates

```bash
zaphod sync --dry-run    # Preview
zaphod sync              # Apply
```

### Before Semester Start

```bash
zaphod sync              # Full sync
# Check Canvas manually
zaphod prune --dry-run   # See what would be cleaned
zaphod prune             # Clean up
```

---

## Troubleshooting

### Something Didn't Sync

1. Check for errors in the output
2. Make sure `meta.json` was generated (step 1)
3. Try running the specific script directly:
   ```bash
   python zaphod/publish_all.py
   ```

### Content Out of Order

1. Check folder prefixes (01-, 02-)
2. Check `module_order.yaml`
3. Check `position:` in frontmatter

### Stale Cache

Clear caches and re-sync:

```bash
rm _course_metadata/*.json
zaphod sync
```

### Watch Mode Not Detecting Changes

1. Make sure you're in the course root
2. Check that the file is in a watched location
3. Try saving the file again
4. Restart watch mode

---

## Next Steps

- [Modules](05-modules.md) — Module organization
- [Assets](08-assets.md) — File handling
- [Manifest & Hydrate](11-manifest-hydrate.md) — Large file management
