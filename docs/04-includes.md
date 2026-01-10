## Includes in Zaphod

Includes are reusable content snippets you can drop into many pages or assignments without copying and pasting. They are perfect for standard pieces of text you repeat often—like a late‑work policy, technical support info, or a course footer.[1]

### Where includes live

Includes are kept in shared folders so any page or assignment can use them:

```text
example-course/
  pages/
    includes/
      footer.md
      late-work-policy.md
  includes/
    accessibility-note.md
```

Zaphod looks for an include in a few places (in this order):

1. `pages/includes/` inside the course  
2. `includes/` inside the course  
3. A shared `_all_courses/includes/` above your course root (if you have one)[1]

This lets you have:

- Course‑specific includes (like a unique project policy).  
- Shared includes across multiple courses (like institutional support links).

### Using an include in a page or assignment

To use an include, you add a simple marker to the body of `index.md`:

```markdown
# Week 1 Overview

Here’s what we’ll do this week...

{{include:late-work-policy}}

{{include:footer}}
```

When Zaphod processes this file, it replaces each `{{include:...}}` marker with the full content of the corresponding `.md` file.[1]

For example, if `pages/includes/late-work-policy.md` contains:

```markdown
## Late Work Policy

Assignments submitted up to 48 hours late may receive partial credit at the instructor’s discretion.
```

that entire section will appear wherever you wrote `{{include:late-work-policy}}`.

### Updating shared content once

The main benefit of includes is that you only update shared text in one place:

- If your school changes its accessibility statement, you update the `accessibility-note.md` include.  
- The next time you run the pipeline, every page or assignment that includes it will show the new wording.  

This keeps your course consistent, reduces copy‑paste errors, and makes global policy updates much less painful.