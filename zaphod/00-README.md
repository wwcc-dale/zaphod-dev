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
├── content/                    # All content lives here
├── templates/                  # Header/footer wrappers
│   ├── default/
│   │   ├── header.html
│   │   ├── header.md
│   │   ├── footer.md
│   │   └── footer.html
│   └── fancy/                  # Alternative template sets
│       └── ...
├── pages/                      # All content lives here
│   ├── 01-Getting Started.module/
│   │   ├── 01-welcome.page/
│   │   │   ├── my-image.jpg
│   │   │   ├── my-movie.mp4
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
├── shared/
│   ├── variables.yaml
│   └── my-include.md
├── templates/
│   ├── footer.html
│   ├── footer.md
│   ├── header.html
│   └── header.md
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

## Extracting Canvas IDs

Canvas question bank IDs and outcome IDs are not accessible via the API and must be extracted manually.

### Question Bank IDs

**Why needed:** Quizzes need `bank_id` in frontmatter to link to Canvas question banks.

**Workflow:**

1. **Sync banks to Canvas**
   ```bash
   python3 zaphod/sync_banks.py
   ```

2. **Save HTML from Canvas**
   - Go to: Canvas > Quizzes > Manage Question Banks
   - Save page source as `banks.html`

3. **Extract IDs**
   ```bash
   python3 zaphod/utilities/bank_scrape.py banks.html
   ```
   - Generates `question-banks/bank-mappings.yaml`

4. **Apply to quizzes**
   ```bash
   python3 zaphod/utilities/apply_bank_ids.py
   ```
   - Updates quiz frontmatter with `bank_id` fields

5. **Sync quizzes**
   ```bash
   zaphod sync
   ```

### Outcome IDs

**Why needed:** For linking assignments/quizzes to learning outcomes.

**Workflow:**

1. **Save HTML from Canvas**
   - Go to: Canvas > Outcomes
   - Save page source as `outcomes.html`

2. **Extract IDs**
   ```bash
   python3 zaphod/utilities/outcome_scrape.py outcomes.html
   ```
   - Generates `outcomes/outcome-mappings.yaml`

3. **Use in content**
   - Reference outcome IDs in assignment/quiz frontmatter

**Note:** Canvas does not expose bank/outcome IDs via API or exports. HTML scraping is the only reliable method for authenticated content.

---

## Module Organization

Zaphod automatically organizes content into Canvas modules based on folder structure:

```
content/
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

## Templates - Automatic Headers & Footers

Apply consistent headers and footers to all pages automatically.

### Template Sets

Create reusable template sets in `templates/` directory:

```
templates/
├── default/              # Applied to all pages by default
│   ├── header.html
│   ├── header.md
│   ├── footer.md
│   └── footer.html
├── fancy/                # Alternative template set
│   ├── header.html
│   ├── header.md
│   ├── footer.md
│   └── footer.html
└── minimal/              # Minimal styling
    └── footer.md
```

### Application Order

Templates wrap content in this order:
1. `header.html`
2. `header.md` (converted to HTML)
3. **Your page content**
4. `footer.md` (converted to HTML)
5. `footer.html`

### Using Templates

**Default behavior** - uses `templates/default/`:
```yaml
---
name: "My Page"
# Automatically uses templates/default/
---
```

**Choose different template set:**
```yaml
---
name: "Special Page"
template: "fancy"         # Uses templates/fancy/
---
```

**Skip templates for a page:**
```yaml
---
name: "Plain Page"
template: null            # No template wrapping
---
```

### Example Template Files

**templates/default/header.md:**
```markdown
# Course Header

**Important:** All assignments due by midnight.
```

**templates/default/footer.md:**
```markdown
---

Questions? Email your instructor.
```

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
