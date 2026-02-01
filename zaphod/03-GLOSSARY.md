# Zaphod Glossary

> Quick reference for terms, concepts, and jargon used in Zaphod.

---

## Canvas LMS Terms

### Canvas
The Learning Management System (LMS) that Zaphod syncs to. Think of it as the website students see and where they submit work.

### Canvas Page
A content page in Canvas (like a syllabus or weekly overview). Not the same as a web page—it's Canvas-specific.

### Canvas Assignment
A gradeable item in Canvas where students submit work. Has points, due dates, submission types.

### Module
Canvas's way of organizing content into sections or weeks. Modules appear in the sidebar and contain pages, assignments, quizzes, etc.

### Module Item
An individual piece of content inside a module (a page, assignment, file, etc.).

### Classic Quiz
The original Canvas quiz system. Zaphod only supports Classic Quizzes (not New Quizzes).

### Question Bank
Canvas storage for quiz questions that can be reused across quizzes. Zaphod creates these from `.bank.md` files.

### Outcome
A learning goal or objective. Canvas can track student performance against outcomes across assignments.

### Rubric
A grading guide that breaks an assignment into criteria with point values and rating levels.

### Canvas Shell
A single instance of a Canvas course (one course ID). One Zaphod course folder can sync to multiple shells.

---

## Zaphod Concepts

### Source of Truth
The authoritative version of something. In Zaphod, **local files are the source of truth** and Canvas reflects them.

### Content Folder
A folder under `pages/` that represents one Canvas item. Ends in `.page`, `.assignment`, `.file`, `.link`, or `.quiz`.

Example: `pages/welcome.page/` is a content folder.

### Module Folder
A folder ending in `.module` that groups content items into a Canvas module.

Example: `pages/01-Week 1.module/` creates a module named "Week 1".

### Frontmatter
YAML metadata at the top of an `index.md` file, between `---` lines. Contains settings like title, type, modules, points.
```markdown
---
name: "Welcome"
type: "page"
published: true
---
```

### Body Content
The markdown content below the frontmatter in `index.md`. This becomes the actual page/assignment description.

### Work Files
Generated files that Zaphod creates during processing:
- `meta.json` - Parsed metadata from frontmatter
- `source.md` - Processed body content (after variables/includes)

You don't edit these directly—they're regenerated from `index.md` and cleaned up by prune.

---

## Templating System

### Variable
A placeholder that gets filled in with a value from frontmatter or config.
```markdown
instructor_name: "Ada Lovelace"
---
Contact {{var:instructor_name}} for help.
→ Contact Ada Lovelace for help.
```

### Include
A reusable content snippet stored in a shared location.
```markdown
{{include:late-work-policy}}
→ Inserts content from late-work-policy.md
```

### Video Placeholder
A special placeholder for Canvas video embedding.
```markdown
{{video:lecture.mp4}}
→ Becomes a Canvas media iframe after upload
```

### Interpolation
The process of replacing variables and includes with their actual content.

---

## File Structure Terms

### Course Root
The top-level directory for a Zaphod course. Contains `pages/`, `assets/`, etc.

Example: `/Users/ada/courses/intro-to-design/`

### Pages Directory
The `pages/` folder where all content items live (pages, assignments, quizzes, files, links).

### Assets Folder
The `assets/` folder where shared media files live (images, videos, PDFs).

### Question Banks Directory
The `question-banks/` folder where `.bank.md` files live (question pools).

### Course Metadata
The `_course_metadata/` folder where Zaphod stores internal state (cache, config, watch state).

---

## Pipeline Terms

### Pipeline
The sequence of scripts that process local files and sync them to Canvas.

Steps: parse → publish → banks → quizzes → modules → outcomes → rubrics → prune

### Sync
Running the pipeline to make Canvas match your local files. "Syncing" = "making Canvas up to date."

### Incremental Mode
Only processing files that changed since the last sync (faster than full mode).

### Full Mode
Processing all files in the course (slower, but thorough).

### Watcher
A long-running script that monitors files for changes and automatically runs the pipeline.

### Debounce
Waiting a few seconds after a change before running the pipeline (prevents running on every keystroke).

### Dry Run
Show what would happen without actually doing it (for testing).

---

## Content Types

### Page
A Canvas Page (informational content, no submission). Folder ends in `.page`.

### Assignment
A Canvas Assignment (students submit, gets graded). Folder ends in `.assignment`.

### Quiz
A Canvas Classic Quiz. Folder ends in `.quiz`.

### File Item
A downloadable file in Canvas (PDF, zip, etc.). Folder ends in `.file`.

### Link Item
An external link in Canvas (to a website, video, tool). Folder ends in `.link`.

---

## Quiz Terms

### Bank File
A `.bank.md` file in `question-banks/` that defines questions for a question bank.

### Quiz Folder
A `.quiz/` folder under `pages/` that defines a deployable quiz.

### Two-Layer Model
Zaphod's quiz architecture:
1. **Banks** (`.bank.md`) → Question pools
2. **Quizzes** (`.quiz/`) → Deployed quizzes that pull from banks

### Question Group
A set of questions pulled from a bank into a quiz (with pick count and points).

### NYIT Format
The plain-text quiz format Zaphod uses (borrowed from NYIT Canvas Exam Converter).

Example:
```
1. What is 2+2?
a) 3
*b) 4   ← asterisk marks correct answer
c) 5
```

### Question Types
Types of quiz questions Zaphod supports:
- **Multiple choice** - One correct answer (`*a)`)
- **Multiple answers** - Multiple correct answers (`[*]`)
- **True/False** - Two options
- **Short answer** - Text input (`* answer`)
- **Essay** - Long text response (`####`)
- **File upload** - Student uploads file (`^^^^`)

---

## Rubric Terms

### Criterion (plural: Criteria)
One row in a rubric. Describes one aspect of the assignment (like "Organization" or "Clarity").

### Rating
One column in a rubric criterion. Describes one level of performance (like "Excellent" or "Needs Improvement").

### Points Possible
Maximum points for a criterion or assignment.

### Mastery Points
The point threshold that indicates satisfactory performance (for outcomes).

### Shared Rubric
A rubric defined once in `rubrics/` and reused via `use_rubric:` in assignments.

### Rubric Row
A reusable criterion in `rubrics/rows/` included via `{{rubric_row:name}}`.

---

## Outcome Terms

### CLO (Course Learning Outcome)
A learning goal for the entire course. Example: "Students will write clear, organized essays."

### Outcome Code
A short identifier for an outcome (like `CLO1`, `CLO2`). Used in frontmatter references.

### Outcome Ratings
Proficiency levels for an outcome (e.g., "Exceeds", "Meets", "Approaching", "Below").

---

## Caching Terms

### Content Hash
A fingerprint of file contents used to detect changes. Same content = same hash.

### Upload Cache
`_course_metadata/upload_cache.json` - Tracks uploaded files to avoid re-uploading.

### Bank Cache
`_course_metadata/bank_cache.json` - Tracks imported question banks.

### Quiz Cache
`_course_metadata/quiz_cache.json` - Tracks synced quizzes.

---

## Module Organization

### Numeric Prefix
A number at the start of a folder name used for ordering.
```
01-Introduction.module/   ← Position 1
02-Week 1.module/         ← Position 2
```

### Module Order YAML
`modules/module_order.yaml` - Explicit module ordering and protection.

### Protected Module
A module that won't be deleted even when empty (listed in module_order.yaml or has a `.module` folder).

### Item Position
The `position:` frontmatter field that controls where an item appears in a module.

---

## Git Terms (Common in Zaphod Workflows)

### Repository (Repo)
A folder tracked by Git. Your Zaphod course folder is typically a Git repo.

### Commit
A saved snapshot of your files in Git. Records who changed what, when.

### Branch
A parallel version of your course (like "spring-2026" or "draft-changes").

---

## Technical Terms

### API (Application Programming Interface)
How Zaphod talks to Canvas programmatically (without clicking in the browser).

### Canvas API Token
A secret key that lets Zaphod authenticate with Canvas on your behalf.

### Environment Variable
A configuration value stored in your shell (like `COURSE_ID=123456`).

### Credentials File
`~/.canvas/credentials.txt` - Contains your Canvas API token and URL.

### QTI (Question and Test Interoperability)
A standard format for quiz content. Zaphod uses QTI to import question banks.

### Common Cartridge
A standard format for course content portability. Zaphod can export to CC format.

---

## Operation Terms

### Publish
Make content visible to students in Canvas (`published: true`).

### Unpublish
Hide content from students (`published: false`).

### Prune
Delete Canvas content that doesn't exist in local files (cleanup operation).

### Watch Mode
Automatic syncing when files change (the watcher runs in the background).

### Assets Only Mode
Only upload assets without publishing content (`--assets-only`).

---

## CLI Commands Reference

```bash
# Sync everything
zaphod sync

# Sync with watch mode
zaphod sync --watch

# Preview changes
zaphod sync --dry-run

# Skip cleanup
zaphod sync --no-prune

# List content
zaphod list
zaphod list --type quiz

# Create new content
zaphod new --type page --name "Week 1"

# Preview deletions
zaphod prune --dry-run

# Check for problems
zaphod validate

# Show course info
zaphod info

# Export course
zaphod export
```

---

## File Extension Quick Reference

| Extension | Type |
|-----------|------|
| `.md` | Markdown file (editable content) |
| `.json` | JSON data (machine-readable) |
| `.yaml` / `.yml` | YAML config (human-readable) |
| `.page/` | Canvas Page folder |
| `.assignment/` | Canvas Assignment folder |
| `.quiz/` | Canvas Quiz folder |
| `.link/` | External link folder |
| `.file/` | File download folder |
| `.module/` | Module grouping folder |
| `.bank.md` | Question bank file |

---

## Common Phrases

**"Did you sync?"**
→ Did you run the pipeline to update Canvas?

**"It's in watch mode"**
→ The watcher is running, changes auto-sync

**"Check your frontmatter"**
→ Look at the YAML settings at the top of `index.md`

**"That's in the cache"**
→ Already uploaded to Canvas, won't re-upload

**"Canvas is the reflection"**
→ Local files are authoritative, Canvas mirrors them

**"It's a work file"**
→ Generated file (`meta.json`, `source.md`), don't edit directly

**"Two-layer model"**
→ Banks (question pools) + Quizzes (deployed tests)

---

*Last updated: January 2026*
