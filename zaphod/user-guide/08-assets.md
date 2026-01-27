# Assets

> Assets are the images, videos, PDFs, and other files you include in your course. Zaphod handles uploading them to Canvas and keeping track of them.

---

## Where to Put Assets

You have two options:

### 1. Shared Assets Folder

For files used on multiple pages:

```
my-course/
└── assets/
    ├── course-logo.png
    ├── syllabus.pdf
    └── videos/
        └── intro.mp4
```

### 2. Content Folder

For files used only on one page:

```
pages/
└── welcome.page/
    ├── index.md
    └── welcome-banner.png    # Only used here
```

**Note:** When files are uploaded to Canvas, they all go into the course's Files area. Subfolder structure in your local `assets/` folder is not preserved in Canvas — it's just for your local organization.

---

## Using Images

### Basic Image

```markdown
![Description](image-name.png)
```

Zaphod looks for the image in:
1. The same folder as `index.md`
2. The `assets/` folder (including subfolders)

### From Assets Folder

```markdown
![Course Logo](course-logo.png)
```

Zaphod finds it in `assets/course-logo.png` (or any subfolder).

### Auto-Discovery

If you have a file anywhere in `assets/` or its subfolders, just use the filename:

```markdown
![Chart](figure1.png)
```

Zaphod searches `assets/` recursively to find `figure1.png`.

### Explicit Path (When Needed)

If you have multiple files with the same name:

```markdown
![Banner](../assets/images/banner.png)
```

Use explicit relative paths to avoid ambiguity.

---

## Handling Duplicate Filenames

If you have files with the same name in different locations (e.g., `assets/logo.png` and `pages/welcome.page/logo.png`):

1. Zaphod uses **content-hash caching** — different files with the same name are tracked separately
2. Each unique file content gets its own Canvas upload
3. To avoid confusion, use explicit paths or unique filenames

---

## Using Videos

### Video Placeholder

For videos that should become Canvas media players:

```markdown
{{video:lecture1.mp4}}
```

**What happens:**
1. Zaphod finds `lecture1.mp4` in assets or content folder
2. Uploads it to Canvas (with caching)
3. Replaces the placeholder with a Canvas media iframe

### Result in Canvas

The video appears as an embedded player, not a download link.

---

## File Downloads

### Link to a File

```markdown
Download the [worksheet](worksheet.pdf).
```

Zaphod uploads `worksheet.pdf` and converts the link.

### Dedicated File Item

For important downloads, create a `.file` folder:

```
pages/
└── syllabus.file/
    ├── index.md
    └── CS101-Syllabus-Spring2026.pdf
```

**index.md:**
```yaml
---
name: "Course Syllabus"
filename: "CS101-Syllabus-Spring2026.pdf"
modules:
  - "Course Resources"
---
```

This creates a dedicated file item in Canvas that students can download.

---

## Asset Organization

### Recommended Structure

```
assets/
├── images/
│   ├── diagrams/
│   ├── photos/
│   └── icons/
├── documents/
│   ├── handouts/
│   └── templates/
├── videos/
│   ├── lectures/
│   └── tutorials/
└── data/
    └── datasets/
```

### Flat Structure (Also Fine)

```
assets/
├── logo.png
├── syllabus.pdf
├── lecture1.mp4
└── dataset.csv
```

---

## Caching

Zaphod caches uploaded files to avoid re-uploading:

**Cache location:** `_course_metadata/upload_cache.json`

**Cache key:** `{course_id}:{filename}:{content_hash}`

**This means:**
- Same file, same content → skip upload (uses cache)
- Same filename, different content → re-upload
- Different course → upload again

### Clearing the Cache

If you need to force re-upload:

```bash
rm _course_metadata/upload_cache.json
zaphod sync
```

---

## Large Media Files

For very large files (videos over 100MB, high-resolution media), Zaphod provides a **media manifest system** to keep them out of your version-controlled files.

### Why Use the Manifest System?

Large video files cause problems:
- Slow clones and pushes
- Repository size bloat
- Difficult collaboration

The manifest system lets you:
1. Track large files by checksum (not content)
2. Store originals on a shared drive or server
3. Download ("hydrate") them when needed

### Setting Up

1. **Ignore large files in version control:**
   ```
   # .gitignore
   assets/*.mp4
   assets/*.mov
   assets/*.avi
   assets/videos/
   ```

2. **Build a manifest:**
   ```bash
   zaphod manifest
   ```
   
   This scans your assets and creates `_course_metadata/media_manifest.json` with checksums.

3. **Store originals on a shared location:**
   - Network drive: `\\server\courses\CS101\assets`
   - Local shared folder: `/mnt/shared/courses/CS101`
   - Web server: `https://media.university.edu/CS101`

4. **Team members download when needed:**
   ```bash
   zaphod hydrate --source "\\server\courses\CS101"
   ```

### Workflow Example

```bash
# Course author: create course with videos
zaphod manifest                    # Generate checksums
git add _course_metadata/          # Commit manifest (small)
# Copy videos to shared drive

# Collaborator: clone and hydrate
git clone ...
zaphod hydrate --source /mnt/shared/courses/CS101
zaphod sync
```

See [Manifest & Hydrate](11-manifest-hydrate.md) for complete details.

---

## Supported File Types

### Images
- `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.svg`

### Videos
- `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`

### Documents
- `.pdf`, `.doc`, `.docx`, `.ppt`, `.pptx`, `.xls`, `.xlsx`

### Data
- `.csv`, `.json`, `.xml`

### Archives
- `.zip`, `.tar`, `.gz`

---

## Troubleshooting

### Image Not Showing

1. Check the filename matches exactly (case-sensitive)
2. Make sure the file exists in assets or content folder
3. Run `zaphod sync --dry-run` to see what Zaphod finds

### Video Not Playing

1. Check the file format is supported (.mp4 works best)
2. Make sure you're using `{{video:...}}` not regular markdown
3. Check the upload completed (look for messages during sync)

### Duplicate Filenames

If Zaphod warns about multiple files with the same name:
- Use explicit paths to specify which one: `../assets/images/logo.png`
- Or rename one of the files to be unique

---

## Tips

✅ **Use descriptive filenames** — `week1-diagram.png` not `image1.png`

✅ **Organize in subfolders** — Easier to find things

✅ **Keep originals** — Store high-res versions outside assets

✅ **Use .mp4 for video** — Best Canvas compatibility

✅ **Check file sizes** — Compress large images before adding

---

## Next Steps

- [Pages](01-pages.md) — Using assets in pages
- [Manifest & Hydrate](11-manifest-hydrate.md) — Managing large files
