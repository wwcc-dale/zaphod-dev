# File Layout

> Reference guide for Zaphod course directory structure.

---

## Simple Overview

```text
curriculum-workshop/
├─ courses/
│  ├─ _all_courses/             # Shared across all courses
│  │  └─ shared/
│  │     ├─ variables.yaml      # Global variables
│  │     └─ academic-integrity.md  # Global includes
│  │ 
│  ├─ my-first-course/          # A single course (Canvas Shell) 
│  │  ├─ _course_metadata/      # Housekeeping for Zaphod
│  │  │  
│  │  ├─ assets/                # Images, videos, and media
│  │  ├─ content/               # Pages, assignments, quizzes
│  │  ├─ exports/               # Exported IMSCC files
│  │  ├─ modules/               # Module ordering
│  │  ├─ outcomes/              # Learning outcomes
│  │  ├─ question-banks/            # Question banks
│  │  ├─ rubrics/               # Shared rubrics
│  │  ├─ shared/                # Variables and includes
│  │  └─ zaphod.yaml            # Course configuration
│  │ 
│  └─ another-course/           # Another course...
│   
└─ zaphod/                      # Zaphod scripts (ignore)
```

---

## Key Directories

### content/ (or pages/)

Your course content lives here. The `content/` folder is preferred, but `pages/` is still supported for backward compatibility.

```text
content/
├─ 01-Getting Started.module/       # Module folder (sorted by prefix)
│  ├─ welcome.page/
│  │  └─ index.md
│  └─ first-assignment.assignment/
│     ├─ index.md
│     └─ rubric.yaml
│
├─ 02-Week 1.module/
│  ├─ readings.page/
│  │  └─ index.md
│  └─ week-1-quiz.quiz/
│     └─ index.md
│
└─ standalone-page.page/            # Not in a module
   └─ index.md
```

**Folder extensions:**
- `.page/` — Canvas pages
- `.assignment/` — Canvas assignments  
- `.quiz/` — Canvas quizzes
- `.link/` — External URLs
- `.file/` — File references

**Module folders:**
- `##-Name.module/` — Module with sort prefix (e.g., `01-Week 1.module/`)
- `Name.module/` — Module without prefix
- `module-Name/` — Legacy format (still supported)

### shared/

Contains variables and include files.

```text
shared/
├─ variables.yaml       # Course-wide variables
├─ contact_info.md      # Include file
├─ late_policy.md       # Include file
└─ academic_integrity.md
```

### question-banks/

Question banks for quizzes.

```text
question-banks/
├─ unit-1.bank.md       # New format (recommended)
├─ midterm.bank.md
└─ final.bank.md
```

### rubrics/

Shared rubrics and reusable row snippets.

```text
rubrics/
├─ essay_rubric.yaml
├─ presentation_rubric.yaml
└─ rows/
   ├─ writing_clarity.yaml
   └─ thesis.yaml
```

### modules/

Module ordering configuration.

```text
modules/
└─ module_order.yaml
```

### outcomes/

Learning outcome definitions.

```text
outcomes/
└─ outcomes.yaml
```

### assets/

Media files for your course.

```text
assets/
├─ images/
│  ├─ diagram.png
│  └─ photo.jpg
└─ videos/
   └─ intro.mp4
```

### _course_metadata/

Internal state managed by Zaphod. Don't edit manually.

```text
_course_metadata/
├─ upload_cache.json    # Tracks uploaded files
├─ watch_state.json     # Watch mode state
└─ defaults.json        # Course defaults (course_id)
```

---

## Complete Example

```text
my-course/
├─ _course_metadata/
│  ├─ defaults.json
│  ├─ upload_cache.json
│  └─ watch_state.json
│
├─ assets/
│  ├─ images/
│  │  └─ course-banner.png
│  └─ videos/
│     └─ welcome.mp4
│
├─ content/
│  ├─ 01-Start Here.module/
│  │  ├─ welcome.page/
│  │  │  └─ index.md
│  │  └─ syllabus.page/
│  │     └─ index.md
│  │
│  ├─ 02-Week 1.module/
│  │  ├─ readings.page/
│  │  │  └─ index.md
│  │  ├─ homework-1.assignment/
│  │  │  ├─ index.md
│  │  │  └─ rubric.yaml
│  │  └─ quiz-1.quiz/
│  │     └─ index.md
│  │
│  └─ 03-Week 2.module/
│     └─ ...
│
├─ exports/
│  └─ my-course_export.imscc
│
├─ modules/
│  └─ module_order.yaml
│
├─ outcomes/
│  └─ outcomes.yaml
│
├─ question-banks/
│  ├─ week-1.bank.md
│  └─ final.bank.md
│
├─ rubrics/
│  ├─ essay.yaml
│  └─ rows/
│     └─ writing.yaml
│
├─ shared/
│  ├─ variables.yaml
│  ├─ contact_info.md
│  └─ late_policy.md
│
├─ .gitignore
└─ zaphod.yaml
```

---

## Legacy Support

Zaphod maintains backward compatibility with older folder names:

| New (Preferred) | Legacy (Still Works) |
|-----------------|---------------------|
| `content/` | `pages/` |
| `shared/` | `includes/` |
| `Name.module/` | `module-Name/` |

If both exist, Zaphod prefers the new names.

---

## Next Steps

- [Overview](00-overview.md) — Getting started
- [Pipeline](10-pipeline.md) — How sync works
