# CLI Reference

> Complete reference for all Zaphod command-line commands.

---

## Quick Reference

```bash
# Course Setup
zaphod init [--course-id ID]              # Initialize new course
zaphod info                               # Show course status
zaphod validate [-v]                      # Check for errors

# Content
zaphod list [--type TYPE]                 # List content
zaphod new --type TYPE --name NAME        # Create content

# Syncing
zaphod sync [--watch] [--dry-run]         # Sync to Canvas
zaphod prune [--dry-run]                  # Clean up orphans

# Media
zaphod manifest                           # Build media manifest
zaphod hydrate --source PATH              # Download media

# Export
zaphod export [-o FILE]                   # Export course

# Other
zaphod version                            # Show version
```

---

## Command Details

### zaphod init

Initialize a new Zaphod course structure.

```bash
zaphod init [--course-id ID] [--force]
```

**Options:**
- `--course-id ID` — Set the Canvas course ID
- `--force` — Overwrite existing template files

**What it creates:**
```
my-course/
├── pages/                  # Content folders
│   ├── welcome.page/
│   └── sample-assignment.assignment/
├── assets/                 # Shared media
├── question-banks/             # Question banks
│   └── sample.bank.md
├── modules/                # Module ordering
│   └── module_order.yaml
├── outcomes/               # Learning outcomes
│   └── outcomes.yaml
├── rubrics/                # Shared rubrics
│   ├── essay_rubric.yaml
│   └── rows/
├── _course_metadata/       # Internal state
└── zaphod.yaml             # Configuration
```

**Examples:**
```bash
# Initialize with prompts
zaphod init

# Set course ID during init
zaphod init --course-id 12345

# Overwrite existing templates
zaphod init --force
```

---

### zaphod sync

Sync local content to Canvas.

```bash
zaphod sync [--watch] [--course-id ID] [--dry-run] [--no-prune] [--assets-only]
```

**Options:**
- `--watch` — Watch for changes and auto-sync
- `--course-id ID` — Override the course ID
- `--dry-run, -n` — Preview changes without making them
- `--no-prune` — Skip the cleanup step
- `--assets-only` — Only upload media files

**Pipeline steps:**
1. Process frontmatter from index.md files
2. Publish pages, assignments, links, files
3. Import question banks
4. Sync quizzes
5. Organize content into modules
6. Import learning outcomes
7. Sync rubrics to assignments
8. Clean up orphaned content (unless --no-prune)

**Examples:**
```bash
# Sync once
zaphod sync

# Auto-sync on file changes
zaphod sync --watch

# Preview what would happen
zaphod sync --dry-run

# Sync without cleaning up
zaphod sync --no-prune
```

---

### zaphod list

List course content.

```bash
zaphod list [--type TYPE] [--module MODULE] [--json]
```

**Options:**
- `--type TYPE` — Filter by type: `page`, `assignment`, `quiz`, `link`, `file`, `all`
- `--module MODULE` — Filter by module name
- `--json` — Output as JSON

**Examples:**
```bash
# List everything
zaphod list

# Only assignments
zaphod list --type assignment

# Only quizzes
zaphod list --type quiz

# Content in a specific module
zaphod list --module "Week 1"

# JSON output for scripting
zaphod list --json
```

---

### zaphod new

Create a new content item.

```bash
zaphod new --type TYPE --name NAME [--module MODULE]
```

**Options:**
- `--type TYPE` — Required. One of: `page`, `assignment`, `quiz`, `link`
- `--name NAME` — Required. Display name for the content
- `--module MODULE` — Module(s) to add content to (can be repeated)

**Examples:**
```bash
# Create a page
zaphod new --type page --name "Welcome"

# Create an assignment in a module
zaphod new --type assignment --name "Essay 1" --module "Week 2"

# Create a quiz in multiple modules
zaphod new --type quiz --name "Midterm" --module "Week 5" --module "Exams"
```

---

### zaphod validate

Validate course content before syncing.

```bash
zaphod validate [--verbose]
```

**Options:**
- `--verbose, -v` — Show detailed output

**What it checks:**
- Required frontmatter fields
- Valid YAML syntax
- Missing include files
- Quiz questions without correct answers
- Rubric configuration errors
- Undefined module references

**Examples:**
```bash
# Quick check
zaphod validate

# Detailed output
zaphod validate -v
```

---

### zaphod prune

Remove orphaned Canvas content.

```bash
zaphod prune [--dry-run] [--assignments]
```

**Options:**
- `--dry-run` — Show what would be deleted without deleting
- `--assignments` — Include assignments in pruning

**What it removes:**
- Pages not in any .page folder
- Assignments not in any .assignment folder (with --assignments)
- Empty modules (except protected ones)
- Module items in wrong modules

**Examples:**
```bash
# Preview what would be deleted
zaphod prune --dry-run

# Actually delete orphaned content
zaphod prune

# Include assignments
zaphod prune --assignments
```

---

### zaphod manifest

Build a media manifest for large files.

```bash
zaphod manifest
```

**What it does:**
1. Scans the course for large media files (videos, audio)
2. Computes SHA256 checksums
3. Creates `_course_metadata/media_manifest.json`

**Tracked file types:**
- Video: .mp4, .mov, .avi, .mkv, .webm, .m4v, .wmv, .flv
- Audio: .mp3, .wav, .flac, .m4a, .ogg, .aac, .wma

**Use case:** For team workflows where large files are stored on a shared drive and not in Git.

---

### zaphod hydrate

Download missing media files from a shared source.

```bash
zaphod hydrate --source PATH [--verify/--no-verify] [--dry-run]
```

**Options:**
- `--source PATH` — Required. Source location (local path, SMB path, or HTTP URL)
- `--no-verify` — Skip checksum verification
- `--dry-run` — Show what would be downloaded

**Supported sources:**
- Local paths: `/mnt/shared/courses/CS101`
- SMB paths: `\\server\courses\CS101`
- HTTP URLs: `https://media.example.com/courses/CS101`

**Examples:**
```bash
# From network share
zaphod hydrate --source "\\\\fileserver\\courses\\CS101"

# From local path
zaphod hydrate --source /mnt/shared/courses/CS101

# Preview downloads
zaphod hydrate --source /path/to/source --dry-run
```

---

### zaphod export

Export course to Common Cartridge format.

```bash
zaphod export [--output FILE] [--title TITLE] [--format FORMAT]
```

**Options:**
- `--output, -o FILE` — Output file path
- `--title, -t TITLE` — Course title
- `--format FORMAT` — Export format: `cartridge` (default) or `qti`

**Examples:**
```bash
# Export full course
zaphod export

# Custom output path
zaphod export --output my-course.imscc

# Override title
zaphod export --title "Introduction to Biology"
```

---

### zaphod info

Show course information and status.

```bash
zaphod info
```

**Displays:**
- Course ID and root directory
- Last sync time
- Content statistics (pages, assignments, quizzes, etc.)
- Configuration status
- Quick health check

---

### zaphod version

Show version information.

```bash
zaphod version
```

---

### zaphod ui

Launch the web UI (experimental).

```bash
zaphod ui [--port PORT] [--no-browser]
```

**Options:**
- `--port PORT` — Port number (default: 8000)
- `--no-browser` — Don't open browser automatically

**Note:** The web UI is not yet fully implemented.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `COURSE_ID` | Canvas course ID (overrides zaphod.yaml) |
| `CANVAS_API_KEY` | Canvas API token |
| `CANVAS_API_URL` | Canvas instance URL |
| `CANVAS_CREDENTIAL_FILE` | Path to credentials file (default: ~/.canvas/credentials.txt) |
| `ZAPHOD_CHANGED_FILES` | For incremental sync (set by watch mode) |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (check output for details) |

---

## Tips

**Preview first:**
```bash
zaphod sync --dry-run
zaphod prune --dry-run
```

**Watch mode for development:**
```bash
zaphod sync --watch
```

**Check before syncing:**
```bash
zaphod validate && zaphod sync
```

---

## Getting Help

```bash
# General help
zaphod --help

# Command-specific help
zaphod sync --help
zaphod new --help
```
