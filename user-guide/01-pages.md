## Pages in Zaphod

Pages are where most of your course “story” lives: weekly overviews, readings, examples, how‑tos, and any other rich content you’d normally build in the Canvas Page editor. In Zaphod, each page is just a folder with a single markdown file, which makes it easy to see, edit, and version alongside the rest of your course.[1]

### Where pages live

All pages live under the `pages/` folder for your course. Each page has its own subfolder ending in `.page`:[1]

```text
example-course/
  pages/
    intro.page/
      index.md
    week1-overview.page/
      index.md
    resources.page/
      index.md
```

- The folder name (like `intro.page`) is mainly for you; Canvas will use the human‑readable title inside `index.md`.  
- Keeping “one folder per page” lets you add page‑specific files later (images, PDFs) without cluttering the rest of the course.[1]

### The `index.md` file

Inside each `.page` folder, `index.md` is the only file you need to edit. It has two parts:[1]

1. **Frontmatter** at the top (between `---` lines) where you set page settings.  
2. **Body content** underneath, written in normal markdown.

A simple page:

```markdown
---
name: "Course Introduction"
type: "Page"
modules:
  - "Module 1: Getting Started"
published: true
---

# Welcome to the course

This page gives you a quick overview of what to expect this term.

- How the course is organized
- What tools we’ll use
- Where to ask for help
```

When Zaphod runs, it reads this `index.md` and turns it into a Canvas Page with the same title and body text, and places it into the listed modules.[2][1]

### Frontmatter: common fields

You don’t need to remember every possible setting; most pages only use a few fields. Common ones include:[1]

```yaml
---
name: "Week 1 Overview"        # Page title in Canvas
type: "Page"                   # Always "Page" for pages
modules:                       # Optional: which modules to place this page in
  - "Module 1: Getting Started"
published: true                # true = visible to students, false = hidden
indent: 1                      # Optional: indent level inside the module
---
```

- `name`: The title students see in Canvas.  
- `type`: For pages, this should be `"Page"`.  
- `modules`: A list of Canvas module names where this page should appear.  
- `published`: Whether the page is visible to students once synced.  
- `indent`: Optional visual indentation inside the module (for grouping).[2][1]

If you leave out `modules`, Zaphod will still create the page in Canvas; it just won’t be placed in any module until you add them.

### Writing page content

Below the frontmatter, you can write the page body in regular markdown: headings, paragraphs, lists, images, code blocks, and so on.[1]

```markdown
# Week 1 Overview

In Week 1, you will:

- Get oriented to the course structure
- Meet your classmates
- Complete a short “tech check” activity

## To do this week

1. Read the **Syllabus** page.
2. Post an introduction in the Week 1 discussion.
3. Complete the “Tech Check” quiz.
```

Zaphod converts this markdown into HTML for Canvas, so what you write here is what students see (formatted with Canvas’s usual styles).[1]

### Using images and other page‑local files

If a page uses an image or a PDF that’s specific to that page, you can keep those files in the same folder as `index.md`:

```text
pages/
  intro.page/
    index.md
    instructor-photo.jpg
    welcome-handout.pdf
```

Then reference them in the markdown:

```markdown
![Your instructor](instructor-photo.jpg)

You can download the Week 1 handout here: [Week 1 Handout](welcome-handout.pdf).
```

During publish, Zaphod can upload these files to Canvas and update the links so they work inside the course, while you continue to work with simple relative links in your files.[1]

### Adding the page to your course

Once you’ve created or edited a page:

- Save `index.md`.  
- Run your usual Zaphod pipeline (or let the watcher pick up the change).  

Zaphod will:

- Create or update the Canvas Page with the title from `name`.  
- Update the page body from the markdown content.  
- Place the page into any modules listed in `modules` (creating modules if needed).