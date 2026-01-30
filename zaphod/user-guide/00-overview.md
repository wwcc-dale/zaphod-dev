# Zaphod User Guide

> Welcome! This guide will help you create and manage Canvas courses using Zaphod.

---

## What is Zaphod?

Zaphod is a tool that lets you write your Canvas course content in simple text files instead of using the Canvas web editor. Think of it like writing a document in Word versus using a complicated online form — the text file approach is often faster, easier to organize, and gives you a backup of everything.

**The basic idea:**
1. You create text files on your computer
2. Zaphod reads those files and creates the matching content in Canvas
3. When you make changes, Zaphod updates Canvas to match

---

## Why Use Zaphod?

### It's faster

Instead of clicking through Canvas menus and waiting for pages to load, you can write your content in any text editor. Most instructors find this much quicker, especially for longer pages or courses with lots of similar content.

### It keeps everything organized

All your course content lives in one folder on your computer. You can see everything at a glance, organize it however makes sense to you, and use familiar tools to search and edit.

### It's safer

Every change is saved in your files. If something goes wrong in Canvas, you can always re-sync from your files. You can even use version control (like Git) to track every change you've ever made.

### It allows collaboration

You can easily share your course with other instructors and build it together. If you publish it on gihub you can both work on it and not overwrite eachother's work.  

### It's reusable

Want to copy a module to a new course? Just copy the folder. Want to use the same assignment description across multiple sections? Just copy the file. No more recreating content from scratch.

---

## Getting Started

### What you need

1. **Python** installed on your computer
2. **A Canvas API token** (get this from Canvas → Account → Settings → New Access Token)
3. **Your course ID** (the number in the URL when you view your course)

### Setting up

1. Create a folder for your course:
   ```
   my-course/
   └── zaphod.yaml
   ```

2. Add your course ID to `zaphod.yaml`:
   ```yaml
   course_id: 12345
   ```

3. Set up your Canvas credentials in `~/.canvas/credentials.txt`:
   ```
   API_KEY = "your-token-here"
   API_URL = "https://canvas.youruniversity.edu"
   ```

4. Create a `pages/` folder and start adding content!

---

## How Content is Organized

Everything lives in the `pages/` folder. Each piece of content is its own folder with an `index.md` file inside:

```
my-course/
├── zaphod.yaml
└── pages/
    ├── welcome.page/
    │   └── index.md          ← This becomes a Canvas Page
    ├── essay-1.assignment/
    │   └── index.md          ← This becomes an Assignment
    └── week-1-quiz.quiz/
        └── index.md          ← This becomes a Quiz
```

The folder name ending tells Zaphod what kind of content to create:
- `.page` → Canvas Page
- `.assignment` → Canvas Assignment
- `.quiz` → Canvas Quiz
- `.link` → External Link
- `.file` → Downloadable File

---

## Writing Your First Page

Create a folder called `welcome.page/` and inside it, create a file called `index.md`:

```markdown
---
name: "Welcome to the Course"
modules:
  - "Start Here"
published: true
---

# Welcome!

This is your first page. You can write anything here using **Markdown**.

## What You'll Learn

- How to use this course
- What to expect each week
- How to get help
```

The part between the `---` lines is called "frontmatter" — it tells Zaphod the settings for this content. The rest is your actual content, written in Markdown.

Now run:
```bash
zaphod sync
```

And your page appears in Canvas!

---

## Organizing with Modules

You probably want your content organized into modules (like "Week 1", "Week 2", etc.). Zaphod makes this easy with special folder names:

```
pages/
├── 01-Getting Started.module/
│   ├── 01-welcome.page/
│   │   └── index.md
│   └── 02-syllabus.page/
│       └── index.md
├── 02-Week 1.module/
│   ├── 01-lecture.page/
│   │   └── index.md
│   └── 02-homework.assignment/
│       └── index.md
```

**How it works:**
- Folders ending in `.module` become Canvas modules
- The number prefix (01-, 02-) sets the order
- Content inside each module folder automatically goes into that module
- Items are also ordered by their number prefix

So `01-Getting Started.module/` becomes a module called "Getting Started" (the number is stripped), and it appears first in your course.

---

## The Basic Workflow

1. **Edit your files** in any text editor
2. **Run `zaphod sync`** to push changes to Canvas
3. **Check Canvas** to make sure everything looks right

That's it! For day-to-day work, it's really that simple.

### Watch Mode

If you're making lots of changes, you can have Zaphod watch for file changes and automatically sync:

```bash
zaphod sync --watch
```

Now every time you save a file, it updates in Canvas within seconds.

---

## Preview Before You Publish

Worried about making mistakes? Use dry-run mode to see what would happen without actually changing Canvas:

```bash
zaphod sync --dry-run
```

This shows you exactly what Zaphod would create, update, or delete — but doesn't do anything yet.

---

## What's Next?

This overview covered the basics. The rest of this guide goes deeper into each topic:

| Guide | What You'll Learn |
|-------|-------------------|
| [Pages](01-pages.md) | Creating and formatting pages |
| [Assignments](02-assignments.md) | Assignments, due dates, and submission types |
| [Variables](03-variables.md) | Reusing content with variables |
| [Includes](04-includes.md) | Sharing content blocks |
| [Modules](05-modules.md) | Organizing your course |
| [Rubrics](06-rubrics.md) | Creating grading rubrics |
| [Outcomes](07-outcomes.md) | Learning outcomes |
| [Assets](08-assets.md) | Images, videos, and files |
| [Quizzes](09-quizzes.md) | Creating quizzes and question banks |
| [Pipeline](10-pipeline.md) | How syncing works |
| [File Layout](15-file-layout.md) | Complete directory reference |

---

## Getting Help

### Common Commands

```bash
zaphod info          # See course status
zaphod list          # See all your content
zaphod validate      # Check for problems
zaphod prune --dry-run  # See what would be cleaned up
```

### Something Went Wrong?

1. Run `zaphod validate` to check for issues
2. Try `zaphod sync --dry-run` to see what Zaphod thinks it should do
3. Check that your frontmatter YAML is valid (no typos, proper indentation)
4. Make sure your Canvas credentials are working

### Tips for Success

- **Start small:** Create one page, sync it, make sure it works
- **Use watch mode:** `zaphod sync --watch` for faster feedback
- **Preview first:** `--dry-run` before big changes
- **Keep backups:** Use Git or copy your folder before major changes

---

Happy course building! 🎓
