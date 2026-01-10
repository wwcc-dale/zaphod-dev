## Assets in Zaphod

The assets folder is where you keep reusable files for your course—things like images, PDFs, slides, datasets, and videos that show up in more than one page or assignment. Instead of uploading these separately through the Canvas interface every time, you keep them in one place in your course repo, and Zaphod takes care of getting them into Canvas and wiring up the links.

### Where assets live

A typical course has a single, flat `assets/` folder:

```text
example-course/
  assets/
    intro-image.jpg
    syllabus.pdf
    sample-output.png
    starter-files.zip
    week1-video.mp4
```

You can also keep page‑specific files in the same folder as that page or assignment if they’re only used once:

```text
pages/
  intro.page/
    index.md
    instructor-photo.jpg
    welcome-handout.pdf
```

In practice:

- Use `assets/` for files that are shared across multiple places in the course.
- Use page/assignment folders for very local, one‑off files.

Zaphod will treat both locations as valid sources when it looks for files to upload and link.

### Referencing assets in your content

From your perspective, you work with assets as if everything is local. In your `index.md` you just use normal markdown links and image references:

```markdown
![Course overview diagram](../assets/intro-image.jpg)

You can download the full syllabus here:
[Download syllabus](../assets/syllabus.pdf)
```

or, for page‑local files:

```markdown
![Your instructor](instructor-photo.jpg)

Download the Week 1 handout:
[Week 1 Handout](welcome-handout.pdf)
```

When you run the publish step, Zaphod:

- Finds any referenced files in the assignment/page folder or in `assets/`.  
- Uploads them to Canvas if they are not already there.  
- Caches upload information so it doesn’t keep re‑uploading the same file.  
- Ensures the rendered Canvas page or assignment points to the uploaded versions, while you continue to edit simple local paths in your repo.

This lets you manage course files the way you manage any other project files, and rely on Zaphod to bridge the gap between your local folder structure and Canvas’s file storage.