## Assignments in Zaphod

Assignments in Zaphod look and feel a lot like pages, but with extra information for grading and submission. You still write the student‑facing instructions in markdown, and Zaphod turns them into real Canvas Assignments with the right settings attached.[1][2]

### Where assignments live

Assignments live under the same `pages/` folder as pages, but each assignment folder ends in `.assignment`:[1]

```text
example-course/
  pages/
    essay-1.assignment/
      index.md
    project-plan.assignment/
      index.md
```

- Each `.assignment` folder represents one Canvas Assignment.  
- As with pages, the folder name is mainly for your convenience; Canvas uses the `name` in `index.md` as the official title.[1]

### The `index.md` file

Inside each `.assignment` folder, you edit a single `index.md` file. It has:

1. **Frontmatter** with assignment settings.  
2. **Body content** with the instructions students see.

A simple assignment:

```markdown
---
name: "Essay 1: Personal Narrative"
type: "Assignment"
modules:
  - "Module 2: Narratives"
published: true
points_possible: 50
submission_types:
  - "online_upload"
allowed_extensions:
  - "pdf"
  - "docx"
due_at: "2026-02-15T23:59:00"
---

# Essay 1: Personal Narrative

Write a 3–4 page narrative about a meaningful experience in your life.

Your essay should:

- Have a clear beginning, middle, and end
- Include specific details and examples
- Be carefully proofread before submission
```

When you run Zaphod, this becomes a Canvas Assignment with the title, points, submission type, allowed file types, due date, and description taken from this file.[2][1]

### Frontmatter: common assignment settings

You can start with just a few key fields and add more as needed.[1]

```yaml
---
name: "Example Assignment"
type: "Assignment"
modules:
  - "Module 1: Getting Started"
published: true
points_possible: 30
submission_types:
  - "online_upload"
allowed_extensions:
  - "pdf"
  - "docx"
due_at: "2026-01-20T23:59:00"
---
```

Common fields:

- `name`: Assignment title in Canvas.  
- `type`: `"Assignment"` for assignments.  
- `modules`: Which Canvas modules this assignment appears in.  
- `published`: Whether students can see the assignment.  
- `points_possible`: Total points for the assignment.  
- `submission_types`: How students submit (for example `online_upload`, `online_text_entry`, `on_paper`).  
- `allowed_extensions`: File types Canvas should accept for uploads.  
- `due_at`: Optional due date/time in Canvas’s ISO format.[2][1]

You can leave some of these out and add them later; Zaphod will keep Canvas in sync whenever you update the frontmatter and rerun the pipeline.

### Writing assignment instructions

The body of `index.md` is the assignment description students see in Canvas. You can include headings, lists, examples, and links just as you would on a page:[1]

```markdown
# Example Assignment

In this activity, you will:

- Practice using the course discussion tools
- Introduce yourself to your classmates
- Reflect on your goals for the term

## What to do

1. Write a short paragraph introducing yourself.
2. Share one learning goal you have for this course.
3. Upload your document as a PDF or Word file.
```

Because it’s plain markdown, you can easily copy, reorganize, or reuse assignment descriptions across courses.

### Page‑local files for assignments

Assignments can also have their own local files—templates, starter code, sample answers—stored right in the `.assignment` folder:[1]

```text
pages/
  essay-1.assignment/
    index.md
    rubric.yaml
    sample-essay.pdf
    outline-template.docx
```

You can link to these files in the assignment body:

```markdown
You may find these resources helpful:

- [Sample Essay](sample-essay.pdf)
- [Outline Template](outline-template.docx)
```

Zaphod can upload these files to Canvas and keep the links working, while you continue to reference them by simple relative paths in your markdown.[1]

### Rubrics for assignments

If you use a rubric, you keep it right next to the assignment in a separate file (for example `rubric.yaml`). The assignment’s `index.md` stays focused on what students need to do, while the rubric file defines how you will grade it. When the rubric sync runs, Zaphod creates or updates the rubric in Canvas and attaches it to this assignment.[3][4]

### Adding the assignment to your course

Once you create or edit an assignment:

- Save `index.md` (and any related files like `rubric.yaml`).  
- Run your usual Zaphod pipeline or let the watcher detect the change.  

Zaphod will:

- Create or update the Canvas Assignment with the settings from the frontmatter.  
- Use the markdown body as the assignment description.  
- Place the assignment into the modules you listed.  

From then on, treat the `.assignment` folder as the single source of truth: adjust settings and instructions in `index.md`, and let Zaphod keep Canvas up to date.