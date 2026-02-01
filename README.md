# Zaphod

> A course authoring workspace that makes Canvas faster, safer, and easier to reuse than editing directly in the browser.

Zaphod lets you build a Canvas course from a folder of plain-text files instead of clicking around the Canvas editor. You write pages, assignments, quizzes, rubrics, and outcomes in simple text files, and Zaphod takes care of turning them into real Canvas content.

Each course lives in its own folder and acts as the "source of truth" for one Canvas shell. When you're ready, Zaphod publishes everything to Canvas in a consistent, repeatable way.

---

## Quick Start

```bash
# Navigate to your course folder
cd ~/courses/my-course

# Sync everything to Canvas
zaphod sync

# Or watch for changes and auto-sync
zaphod sync --watch
```

See [05-QUICK-START.md](05-QUICK-START.md) for detailed setup instructions.

---

## Key Benefits

### 🔄 Version Control & Collaboration

- All content stored in Git-friendly plain text
- See what changed, when it changed, who changed it
- Multiple instructors can work without conflicts
- Roll back to any previous version

### ⚡ Speed & Reuse

- Write in markdown (faster than Canvas editor)
- Copy modules, pages, quizzes across terms by copying files
- Variables and includes for consistent content
- Incremental sync: only changed content uploads

### 🛡️ Safety & Consistency

- Test in sandbox, then publish to live
- Preview changes with `--dry-run`
- Automatic cleanup of orphaned content
- Course-wide updates with one change

### 📦 Portability

- Content isn't locked in Canvas
- Export to Common Cartridge for any LMS
- Plain text survives platform migrations

---

## What Can Zaphod Manage?

| Content Type | Extension | Description |
|--------------|-----------|-------------|
| Pages | `.page/` | Informational content |
| Assignments | `.assignment/` | Gradable submissions with optional rubrics |
| Quizzes | `.quiz/` | Classic quizzes with question banks |
| Links | `.link/` | External URLs |
| Files | `.file/` | Downloadable files |
| Question Banks | `.bank.md` | Pools of questions for quizzes |
| Rubrics | `rubric.yaml` | Grading criteria |
| Outcomes | `outcomes.yaml` | Course learning objectives |
| Modules | `.module/` folders | Canvas module organization |

---

## Directory Structure

```
my-course/
├── zaphod.yaml                 # Course config (course_id)
├── pages/                      # All content lives here
│   ├── 01-Getting Started.module/
│   │   ├── 01-welcome.page/
│   │   │   └── index.md
│   │   ├── 02-first-assignment.assignment/
│   │   │   ├── index.md
│   │   │   └── rubric.yaml
│   │   └── 03-quiz.quiz/
│   │       └── index.md
│   └── 02-Week 1.module/
│       └── ...
├── question-banks/
│   ├── chapter1.bank.md
│   └── chapter2.bank.md
├── assets/
│   ├── images/
│   └── videos/
├── outcomes/
│   └── outcomes.yaml
├── modules/
│   └── module_order.yaml       # Optional explicit ordering
└── rubrics/
    ├── my-shared-rubric.yaml
    └── rows/
        ├── my-rubric-row.yaml
        └── another-rubric-row.yaml
```

---

## CLI Commands

```bash
# Sync content to Canvas
zaphod sync                    # Full sync
zaphod sync --watch            # Watch mode (auto-sync on changes)
zaphod sync --dry-run          # Preview what would happen
zaphod sync --no-prune         # Don't clean up orphaned content

# Content management
zaphod list                    # List all content
zaphod list --type quiz        # List quizzes only
zaphod new --type page --name "Welcome"  # Create new content

# Maintenance
zaphod prune                   # Remove orphaned Canvas content
zaphod prune --dry-run         # Preview deletions
zaphod validate                # Check for issues

# Information
zaphod info                    # Course status and stats

# Export
zaphod export                  # Export to Common Cartridge
zaphod export --output my.imscc
```

---

## Writing Content

### Pages

```markdown
---
name: "Course Introduction"
modules:
  - "Getting Started"
published: true
---

# Welcome to the Course

Your content here in **Markdown**.
```

### Assignments

```markdown
---
name: "Essay 1"
type: assignment
modules:
  - "Week 1"
points_possible: 100
submission_types:
  - online_upload
allowed_extensions:
  - pdf
  - docx
---

# Essay Assignment

Write a 500-word essay on...
```

### Quizzes

```markdown
---
name: "Week 1 Quiz"
quiz_type: assignment
time_limit: 30
question_groups:
  - bank_id: 12345
    pick: 5
    points_per_question: 2
---

Instructions for the quiz.
```

---

## Module Organization

Zaphod automatically organizes content into Canvas modules based on folder structure:

```
pages/
├── 01-Introduction.module/     # → Module "Introduction" (position 1)
│   ├── 01-welcome.page/        # → First item in module
│   └── 02-overview.page/       # → Second item
├── 02-Week 1.module/           # → Module "Week 1" (position 2)
│   └── ...
```

- Folders ending in `.module` define modules
- Numeric prefixes (01-, 02-) set the order
- The prefix is stripped from the module name
- Items within modules are also ordered by prefix

---

## Variables & Includes

### Variables

Define once, use everywhere:

```yaml
# In frontmatter:
instructor: "Dr. Smith"
email: "smith@university.edu"
---
Contact {{var:instructor}} at {{var:email}}.
```

### Includes

Share content blocks:

```markdown
# In your page:
{{include:late_policy}}

# Pulls from includes/late_policy.md
```

---

## Credits

Zaphod builds on ideas from:

- [markdown2canvas](https://github.com/ofloveandhate/markdown2canvas) by Silviana Amethyst et al.
- NYIT [Canvas Exam Converter](https://site.nyit.edu/its/canvas_exam_converter) for quiz format

---

## License

© 2026 Dale Chapman  
Zaphod is open-source under the MIT License.

---

## Documentation

- [Quick Start Guide](05-QUICK-START.md)
- [Architecture](01-ARCHITECTURE.md)
- [User Guide](00-overview.md) (detailed documentation)
- [Known Issues](04-KNOWN-ISSUES.md)
- [Security](99-SECURITY.md)
