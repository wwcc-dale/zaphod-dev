## Assets in Zaphod

The assets folder is where you keep reusable files for your course—things like images, PDFs, slides, datasets, and videos that show up in more than one page or assignment. Instead of uploading these separately through the Canvas interface every time, you keep them in one place in your course repo, and Zaphod takes care of getting them into Canvas and wiring up the links.

### Where assets live

You can organize `assets/` however you like—flat or with subdirectories:

```text
example-course/
  assets/
    syllabus.pdf
    images/
      intro-image.jpg
      diagrams/
        flowchart.svg
    videos/
      week1-video.mp4
    datasets/
      sample-data.csv
```

You can also keep page-specific files in the same folder as that page or assignment if they're only used once:

```text
pages/
  intro.page/
    index.md
    instructor-photo.jpg
    welcome-handout.pdf
```

In practice:

- Use `assets/` for files that are shared across multiple places in the course.
- Use page/assignment folders for very local, one-off files.
- Use subdirectories within `assets/` to stay organized as your course grows.

Zaphod will treat all of these locations as valid sources when it looks for files to upload and link.

### Referencing assets in your content

From your perspective, you work with assets as if everything is local. In your `index.md` you just use normal markdown links and image references.

**Simple references** — just use the filename and Zaphod finds it:

```markdown
![Course overview diagram](intro-image.jpg)

[Download syllabus](syllabus.pdf)
```

Zaphod automatically searches your content folder and all of `assets/` (including subdirectories) to find the file.

**Explicit paths** — useful when you have files with the same name in different folders:

```markdown
![Flowchart](../assets/images/diagrams/flowchart.svg)

[Week 1 Data](../assets/datasets/sample-data.csv)
```

**Page-local files** — for files in the same folder as your content:

```markdown
![Your instructor](instructor-photo.jpg)

[Week 1 Handout](welcome-handout.pdf)
```

### Handling duplicate filenames

If you have the same filename in multiple places (e.g., `assets/week1/logo.png` and `assets/week2/logo.png`), Zaphod will warn you and require an explicit path:

```
[assets:warn] Multiple files named 'logo.png' found:
              - assets/week1/logo.png
              - assets/week2/logo.png
              Use explicit path, e.g., ../assets/week1/logo.png
```

This prevents accidentally linking to the wrong file.

### How publishing works

When you run the publish step, Zaphod:

- Finds any referenced files in the assignment/page folder or anywhere in `assets/`.
- Uploads them to Canvas if they are not already there.
- Caches upload information so it doesn't keep re-uploading the same file.
- Ensures the rendered Canvas page or assignment points to the uploaded versions, while you continue to edit simple local paths in your repo.

Note that Canvas flattens all files into its own storage system—your local subdirectory structure is purely for your organization and won't be preserved in Canvas.

This lets you manage course files the way you manage any other project files, and rely on Zaphod to bridge the gap between your local folder structure and Canvas's file storage.
