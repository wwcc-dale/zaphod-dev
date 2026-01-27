# Includes

> Includes let you share larger blocks of content across multiple pages. Write it once, use it everywhere.

---

## Why Use Includes?

Some content appears on many pages:
- Late work policies
- Academic integrity statements
- Office hours information
- Assignment submission instructions

Instead of copying this text to every page (and updating 20 files when it changes), create an include and reference it:

```markdown
{{include:late_policy}}
```

---

## Basic Usage

### 1. Create an Include File

Create a markdown file in your `shared/` folder:

```
my-course/
└── shared/
    ├── variables.yaml
    └── late_policy.md       # Include file
```

**shared/late_policy.md:**
```markdown
## Late Work Policy

Assignments submitted late will receive a {{var:late_penalty}} penalty.
After 3 days, late submissions will not be accepted without prior arrangement.

If you need an extension, please contact the instructor **before** the due date.
```

### 2. Use It in Your Pages

```markdown
---
name: "Essay 1"
---

# Essay 1

Write a 500-word essay...

{{include:late_policy}}
```

### 3. Result

The `{{include:late_policy}}` is replaced with the entire contents of `late_policy.md`, with any `{{var:...}}` placeholders filled in.

---

## Include Syntax

```
{{include:name}}
```

- `name` corresponds to `shared/name.md`
- Names can contain letters, numbers, underscores, and hyphens
- The `.md` extension is added automatically

---

## Where Include Files Are Found

Includes are searched in this order (first match wins):

### 1. Course Shared Folder (highest priority)

```
my-course/
└── shared/
    └── late_policy.md
```

### 2. Global Shared Folder

```
courses/
├── _all_courses/
│   └── shared/
│       └── academic_integrity.md    # Available to all courses
└── my-course/
```

### 3. Legacy Locations (backward compatibility)

For existing courses using older folder names:
- `<course>/content/includes/name.md` (or `pages/includes/`)
- `<course>/includes/name.md`
- `_all_courses/includes/name.md`

---

## Variables in Includes

Includes can use variables! This makes them dynamic templates.

**shared/contact_info.md:**
```markdown
## Contact Information

- **Instructor:** {{var:instructor_name}}
- **Email:** {{var:instructor_email}}
- **Office Hours:** {{var:office_hours}}
- **Office:** {{var:instructor_office}}
```

**shared/variables.yaml:**
```yaml
instructor_name: "Dr. Smith"
instructor_email: "smith@university.edu"
office_hours: "MW 2-4pm"
instructor_office: "Room 301"
```

**Your page:**
```markdown
---
name: "Syllabus"
---

# Syllabus

{{include:contact_info}}

## Course Description
...
```

**Result:**
```markdown
# Syllabus

## Contact Information

- **Instructor:** Dr. Smith
- **Email:** smith@university.edu
- **Office Hours:** MW 2-4pm
- **Office:** Room 301

## Course Description
...
```

---

## Override Variables Per Page

Page frontmatter can override variables used by includes:

**shared/contact_info.md:**
```markdown
Today's instructor: {{var:instructor_name}}
```

**Guest lecture page:**
```yaml
---
name: "Guest Lecture"
instructor_name: "Dr. Jones"    # Override for this page
---

{{include:contact_info}}
```

**Result:** "Today's instructor: Dr. Jones"

---

## Nested Includes

Includes can contain other includes:

**shared/footer.md:**
```markdown
---

{{include:contact_info}}

{{include:academic_integrity}}
```

Zaphod expands them recursively.

---

## Common Includes

### Contact Information
```markdown
<!-- shared/contact_info.md -->
**Instructor:** {{var:instructor_name}}  
**Email:** {{var:instructor_email}}  
**Office:** {{var:instructor_office}}  
**Office Hours:** {{var:office_hours}}
```

### Late Policy
```markdown
<!-- shared/late_policy.md -->
## Late Work

Late submissions receive a penalty of {{var:late_penalty}}.
After 3 days, late submissions will not be accepted without prior arrangement.

If you need an extension, contact the instructor **before** the due date.
```

### Academic Integrity
```markdown
<!-- shared/academic_integrity.md -->
## Academic Integrity

All work must be your own. See the {{var:academic_integrity_link}} for details.
Violations will be reported to the Dean of Students.
```

### Submission Instructions
```markdown
<!-- shared/submit_instructions.md -->
## How to Submit

1. Save your work as a PDF
2. Go to the assignment page in Canvas
3. Click "Submit Assignment"
4. Upload your PDF file
5. Click "Submit"

You can resubmit until the deadline.
```

---

## Sharing Across Courses

For content shared across multiple courses, use the global shared folder:

```
courses/
├── _all_courses/
│   └── shared/
│       ├── variables.yaml           # Global variables
│       ├── academic_integrity.md    # Used by all courses
│       └── university_resources.md
├── CS101/
│   └── shared/
│       └── variables.yaml           # Course-specific variables
└── CS102/
```

Global includes use the course's variables, so they can still be customized per course.

---

## Tips

✅ **Name includes descriptively** — `late_policy` not `policy1`

✅ **Use variables for customization** — Make includes flexible

✅ **Keep includes focused** — One topic per file

✅ **Use the shared/ folder** — Keeps everything organized

✅ **Check for typos** — `{{include:late_polcy}}` won't work

---

## Troubleshooting

### Include Not Found

```
[frontmatter:warn] essay.assignment: include 'late_policy' not found
```

1. Check the filename matches: `shared/late_policy.md`
2. Check the include name: `{{include:late_policy}}` (no .md extension)
3. Make sure the file exists

### Variables Not Replaced in Include

1. Check the variable is defined in `shared/variables.yaml` or page frontmatter
2. Check for typos in variable names
3. Make sure PyYAML is installed

---

## Next Steps

- [Variables](03-variables.md) — Define reusable values
- [Pages](01-pages.md) — Create content pages
