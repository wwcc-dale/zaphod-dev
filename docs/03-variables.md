## Variables in Zaphod

Variables let you avoid repeating the same small pieces of information across many pages and assignments. Instead of hard‑coding details like the course code, instructor name, or support email in dozens of places, you define them once and then drop in simple placeholders. When Zaphod processes your files, it fills in the real values for you.[1]

### Where variables come from

Most variables start in frontmatter or in a shared configuration file. For example, a page might define a few values at the top of `index.md`:

```markdown
---
name: "Syllabus"
type: "Page"
course_code: "ENGL& 101"
instructor_name: "Ada Lovelace"
support_email: "support@example.edu"
---
```

You can also keep common values in a shared config file that Zaphod reads during processing (for example, a per‑course defaults file), so you don’t have to repeat them in every page’s frontmatter.[1]

### Using variables in your content

Inside the body of your page or assignment, you use a placeholder to reference these values:

```markdown
# Syllabus for {{var:course_code}}

Welcome to {{var:course_code}}.

Your instructor is {{var:instructor_name}}.

If you have technical problems, email {{var:support_email}}.
```

When Zaphod processes this file, it:

- Looks up each `{{var:key}}` placeholder.  
- Substitutes the value from frontmatter or shared config.  

So the rendered content might become:

```markdown
# Syllabus for ENGL& 101

Welcome to ENGL& 101.

Your instructor is Ada Lovelace.

If you have technical problems, email support@example.edu.
```

The key idea is that you only define `course_code`, `instructor_name`, or `support_email` once, and every place that uses them stays in sync automatically.[1]

### Why variables are helpful

Variables are especially handy when:

- You teach multiple sections with slightly different details (like meeting times or instructor names).  
- You want to reuse a course shell for a new term and only change a few key values.  
- You want to ensure contact information and course identifiers are consistent everywhere.

Instead of hunting through dozens of pages to update a term or email address, you change the value in one place and let Zaphod update every page and assignment that uses that variable the next time you run the pipeline.