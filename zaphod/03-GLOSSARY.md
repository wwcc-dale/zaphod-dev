# Zaphod Glossary

Quick reference for terms, concepts, and jargon used in Zaphod.

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
A folder under `pages/` that represents one Canvas item. Ends in `.page`, `.assignment`, `.file`, or `.link`.

Example: `pages/welcome.page/` is a content folder.

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

You don't edit these directly—they're regenerated from `index.md`.

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

### Interpolation
The process of replacing variables and includes with their actual content.

---

## File Structure Terms

### Course Root
The top-level directory for a Zaphod course. Contains `pages/`, `assets/`, etc.

Example: `/Users/ada/courses/intro-to-design/`

### Pages Directory
The `pages/` folder where all content items live (pages, assignments, files, links).

### Assets Folder
The `assets/` folder where shared media files live (images, videos, PDFs).

### Quiz Banks
The `quiz-banks/` folder where `.quiz.txt` files live.

### Course Metadata
The `_course_metadata/` folder where Zaphod stores internal state (cache, config, watch state).

---

## Pipeline Terms

### Pipeline
The sequence of scripts that process local files and sync them to Canvas.

Steps: parse → publish → modules → outcomes → rubrics → quizzes → prune

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

---

## Content Types

### Page
A Canvas Page (informational content, no submission). Folder ends in `.page`.

### Assignment
A Canvas Assignment (students submit, gets graded). Folder ends in `.assignment`.

### File Item
A downloadable file in Canvas (PDF, zip, etc.). Folder ends in `.file`.

### Link Item
An external link in Canvas (to a website, video, tool). Folder ends in `.link`.

---

## Quiz Terms

### Quiz File
A `.quiz.txt` file in `quiz-banks/` that defines one quiz in plain text.

### Question Bank
Canvas storage for quiz questions (can be reused across quizzes). Zaphod creates these automatically.

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
- **Multiple choice** - One correct answer
- **Multiple answers** - Multiple correct answers
- **True/False** - Two options
- **Short answer** - Text input
- **Essay** - Long text response
- **File upload** - Student uploads file

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
A rubric defined once in `rubrics/` and reused across multiple assignments.

### Rubric Row
A reusable criterion that can be included in multiple rubrics.

---

## Outcome Terms

### CLO (Course Learning Outcome)
A learning goal for the entire course. Example: "Students will write clear, organized essays."

### Outcome Code
A short identifier for an outcome (like `CLO1`, `CLO2`). Used to reference outcomes from rubrics.

### Outcome Alignment
Connecting rubric criteria to outcomes so Canvas can track student performance.

### Outcome Map
A file mapping outcome codes to Canvas outcome IDs (needed for alignment).

---

## Git Terms (Optional but Common)

### Repository (Repo)
A folder tracked by Git. Your Zaphod course folder is typically a Git repo.

### Commit
A saved snapshot of your files in Git. Records who changed what, when.

### Branch
A parallel version of your course (like "spring-2026" or "draft-changes").

### Git History
The log of all commits (all changes over time).

---

## Technical Terms

### API (Application Programming Interface)
How Zaphod talks to Canvas programmatically (without clicking in the browser).

### Endpoint
A specific URL in the Canvas API (like `/courses/:id/pages`).

### Canvas API Token
A secret key that lets Zaphod authenticate with Canvas on your behalf.

### Environment Variable
A configuration value stored in your shell (like `COURSE_ID=123456`).

### Script
A Python program that does one part of the Zaphod pipeline (like `publish_all.py`).

### Virtual Environment (venv)
An isolated Python installation for Zaphod's dependencies (keeps your system Python clean).

---

## Operation Terms

### Publish
Make content visible to students in Canvas (`published: true`).

### Unpublish
Hide content from students (`published: false`).

### Prune
Delete Canvas content that doesn't exist in local files (cleanup operation).

### Dry Run
Show what would happen without actually doing it (for testing).

### Watch Mode
Automatic syncing when files change (the watcher runs in the background).

---

## Common Abbreviations

- **LMS** - Learning Management System (Canvas)
- **CLI** - Command Line Interface (terminal commands)
- **UI** - User Interface (visual interface)
- **API** - Application Programming Interface
- **YAML** - Yet Another Markup Language (the frontmatter format)
- **JSON** - JavaScript Object Notation (a data format)
- **CSV** - Comma-Separated Values (spreadsheet format)
- **PDF** - Portable Document Format
- **CLO** - Course Learning Outcome
- **MD** - Markdown (the `.md` file format)

---

## Zaphod-Specific Jargon

### "Sync to Canvas"
Run the pipeline to update Canvas.

### "The pipeline"
The full sequence of processing scripts.

### "Content folder"
A folder under `pages/` ending in `.page`, `.assignment`, etc.

### "Work files"
Generated `meta.json` and `source.md` files.

### "The watcher"
`watch_and_publish.py` running in the background.

### "Canvas shell"
One instance of a Canvas course (one course ID).

### "Source of truth"
Your local files (Canvas is the reflection).

---

## Command Examples with Translations
```bash
# "Run the sync"
zaphod sync

# "Start the watcher"
zaphod sync --watch

# "See what would be deleted without deleting it"
zaphod prune --dry-run

# "List all content"
zaphod list

# "Create a new page"
zaphod new --type page --name "Week 1"

# "Check for problems"
zaphod validate

# "Show course info"
zaphod info
```

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

**"The content folder"**
→ The `something.page` or `something.assignment` folder

**"Run it in dry-run mode"**
→ Preview what would happen without doing it

**"Canvas is the reflection"**
→ Local files are authoritative, Canvas mirrors them

**"It's a work file"**
→ Generated file, don't edit directly

---

## When to Use What

### Page vs Assignment
- **Page**: Informational content, no submission
- **Assignment**: Students submit work, gets graded

### Assets vs Content Folder
- **Assets**: Shared across multiple pages/assignments
- **Content folder**: Specific to one page/assignment

### Full Mode vs Incremental
- **Full**: Process everything (first sync, big changes)
- **Incremental**: Process only changed files (daily work)

### Sync vs Watch
- **Sync**: Run once, manual
- **Watch**: Run automatically, continuous

### Prune vs Publish
- **Publish**: Add/update content in Canvas
- **Prune**: Remove stale content from Canvas

---

## FAQ Translations

**Q: "Where does this page go in Canvas?"**
A: Check the `modules` list in its frontmatter.

**Q: "Why isn't my change showing up?"**
A: Did you sync? Check if watcher is running. Check Canvas cache.

**Q: "Can I edit in Canvas?"**
A: No! Edit locally. Canvas edits will be overwritten on next sync.

**Q: "How do I make a quiz?"**
A: Create a `.quiz.txt` file in `quiz-banks/`.

**Q: "How do I share content across pages?"**
A: Use includes: `{{include:snippet-name}}`

**Q: "Where do images go?"**
A: `assets/` for shared, or in the content folder for page-specific.

**Q: "What if I break something?"**
A: Use Git to roll back. Or sync to sandbox first.

---

## Symbol Reference

### In Frontmatter
- `---` - YAML delimiter (start/end frontmatter)
- `"quotes"` - String value
- `- item` - List item
- `:` - Key-value separator

### In Body
- `#` - Heading
- `*italic*` or `_italic_` - Italic text
- `**bold**` or `__bold__` - Bold text
- `[text](url)` - Link
- `![alt](image.jpg)` - Image
- `{{var:key}}` - Variable
- `{{include:name}}` - Include
- `{{video:file.mp4}}` - Video embed

### In Quiz Files
- `*` - Correct answer marker
- `[*]` - Correct answer (multiple)
- `####` - Essay question
- `^^^^` - File upload question
- `a) b) c)` - Answer options

---

## File Extension Quick Reference

- `.md` - Markdown file (editable content)
- `.json` - JSON data (machine-readable)
- `.yaml` or `.yml` - YAML config (human-readable)
- `.txt` - Plain text (quiz files use this)
- `.page` - Folder containing a Canvas Page
- `.assignment` - Folder containing a Canvas Assignment
- `.link` - Folder containing an external link item
- `.file` - Folder containing a file item

---

## Getting Help

**In this documentation:**
- README.md - Overview and getting started
- ARCHITECTURE.md - How Zaphod works internally
- DECISIONS.md - Why things are designed this way
- KNOWN-ISSUES.md - Problems and limitations
- GLOSSARY.md - You are here!

**For specific features:**
- 01-pages.md through 10-pipeline.md - Detailed guides

**When stuck:**
1. Check GLOSSARY.md (this file) for term definitions
2. Check KNOWN-ISSUES.md for known problems
3. Try `--dry-run` to preview
4. Check Git history to see what changed
5. Search documentation for the concept