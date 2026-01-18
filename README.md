# Zaphod
##### A course authoring workspace that makes Canvas faster, safer, and easier to reuse than editing directly in the browser.

Zaphod lets you build a Canvas course from a folder of plain-text files instead of clicking around the Canvas editor. You write pages, assignments, quizzes, rubrics, and outcomes in simple text files, and Zaphod takes care of turning them into real Canvas content.

Each course lives in its own folder and acts as the “source of truth” for one Canvas shell. When you’re ready, Zaphod publishes everything to Canvas in a consistent, repeatable way.

Quizzes are written in a compact plain-text format (based on the NYIT Canvas Exam Converter), then turned into Classic quiz banks and quizzes automatically.

***

## Key Benefits

Working from plain text files gives you control and safety that are hard to get when you edit directly in the Canvas UI.

#### Collaboration and version control

- All course content is stored in a shared folder (usually in Git), so you can see what changed, when it changed, and who changed it.
- Multiple instructors or designers can work on the same course without overwriting each other, and you can always roll back to a previous version if needed.

#### Faster editing and reuse

- Writing in markdown is often faster than fighting a rich-text editor, especially for longer pages, code examples, or repeated patterns.
- You can copy and reuse modules, pages, assignments, quizzes, and rubrics across terms or courses by copying files instead of rebuilding them by hand in Canvas.

#### Automation and consistency

- Course wide changes (for example a new support link or an updated footer) can be made once and applied everywhere in your course the next time you publish.
- Text that will be reused multiple times in multiple pages and courses can easily be set as variables at the page, course, or all-courses level, e.g., `animal: cat` can be repeated consistently throughout a page or pages where needed by using  `{{var:animal}}` 
- Entire sections of content can also be consitently resused at the page, course or all-course level with includes using `{{include:myInclude}}`  
- Zaphod’s scripts keep names, modules, outcomes, and other details consistent across the whole course, which reduces tedious clicking and the chance of small mistakes.

#### Portability and longevity

- Because content is stored as plain text instead of locked inside Canvas, it’s easier to adapt to another LMS, a static website, or other formats in the future.
- The folder structure (pages, outcomes, quiz banks) makes the course design visible, so one repository can drive multiple Canvas shells or sandboxes.

#### Testing and safety

- You can publish to a test or sandbox course first, review everything, and only then publish to a live section.
- An automatic “watch and publish” script can monitor your files and run the full pipeline for you, reducing the chances of missing a page or leaving something half-updated.

---


## 1. File Layout

A typical course directory looks like this:

```text
courses_root/
└─ example-course/                 # one Canvas course
   ├─ pages/                       # all Canvas items (pages, assignments, files, links)
   |  ├─ intro.page/               # Canvas Page + page-local media
   |  |  ├─ index.md
   |  |  ├─ intro-image.jpg        # image used only on this page (or symlink from assets/)
   |  |  └─ intro-handout.pdf      # page-specific handout (or symlink)
   |  ├─ example.assignment/       # Canvas Assignment + media
   |  |  ├─ index.md
   |  |  ├─ rubric.yaml            # optional rubric spec
   |  |  ├─ sample-output.png      # assignment-specific image (or symlink)
   |  |  └─ starter-files.zip      # assignment resources (or symlink)
   |  ├─ syllabus.page/
   |  |  └─ index.md
   |  ├─ resources.link/           # external link item
   |  |  └─ index.md
   |  └─ handout.file/             # file item
   |     └─ index.md
   |
   ├─ quiz-banks/                  # Classic quiz definitions (NYIT-style)
   |  ├─ week1.quiz.txt
   |  └─ midterm.quiz.txt
   |
   ├─ outcomes/                    # course-level learning outcomes
   |  ├─ outcomes.yaml
   |  └─ outcomes_import.csv       # generated for Canvas Outcomes import
   |
   ├─ modules/                     # optional module ordering & protection
   |  └─ module_order.yaml
   |
   ├─ assets/                      # flat pool of course assets
   |  ├─ intro-image.jpg
   |  ├─ intro-handout.pdf
   |  ├─ sample-output.png
   |  ├─ starter-files.zip
   |  └─ week1-video.mp4
   |
   ├─ _course_metadata/            # internal course-level state/config
   |  ├─ defaults.json             # defaults (e.g. course_id)
   |  ├─ upload_cache.json         # Canvas file ID cache
   |  └─ watch_state.json          # watcher bookkeeping
   |
   ├─ zaphod/                      # Zaphod scripts for this repo
   |  ├─ frontmatter_to_meta.py
   |  ├─ publish_all.py
   |  ├─ sync_modules.py
   |  ├─ sync_clo_via_csv.py
   |  ├─ sync_rubrics.py
   |  ├─ sync_quiz_banks.py
   |  ├─ prune_canvas_content.py
   |  ├─ prune_quizzes.py
   |  └─ watch_and_publish.py
   |
   └─ .venv/                       # optional Python virtualenv
```
- `pages/*.page` and `pages/*.assignment` hold Canvas Pages and Assignments; `*.file` and `*.link` folders represent file/link items.
- `quiz-banks/*.quiz.txt` holds Classic quiz definitions, one quiz per file.
- `outcomes/outcomes.yaml` defines course-level CLOs; `outcomes_import.csv` is generated for Canvas Outcomes import.
- `modules/module_order.yaml` optionally defines the desired ordering and “protected” modules.
- `assets/` contains course-wide media and document assets that can be bulk-uploaded to Canvas.
- `_course_metadata` centralizes defaults, upload cache, and watcher state.

***

## 2. Authoring pages and assignments

### 2.1 `index.md` frontmatter

Zaphod treats each folder under `pages/` ending in `.page`, `.assignment`, `.file`, or `.link` as one Canvas object.

**Page example:**

```markdown
---
name: "Course Introduction"
type: "Page"
modules:
  - "Module 1: Getting Started"
published: true
---

# Course Introduction

Welcome to the course.
```

**Assignment example:**

```markdown
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
---

# Example Assignment

Instructions for the assignment go here.
```

Required fields are `name` and `type`; `modules`, `published`, and assignment settings are optional but recommended.

Frontmatter can also include Zaphod-specific keys such as:

- `modules`: list of Canvas module names to place this item into.
- `indent`: indentation level for module items.
- `external_url` and `new_tab` for `.link` folders.
- Arbitrary metadata used by your own tooling.

### 2.2 Generated work files: `meta.json` and `source.md`

`frontmatter_to_meta.py` turns `index.md` into two work files:[7]

- `meta.json` - JSON metadata derived from frontmatter.
- `source.md` - the body content only (with frontmatter removed), after variable and include expansion.

Example `meta.json`:

```json
{
  "name": "Course Introduction",
  "type": "Page",
  "modules": ["Module 1: Getting Started"],
  "published": true
}
```

On subsequent runs, if a folder already has `meta.json` and `source.md` and `index.md` is unchanged or missing, Zaphod can reuse the existing files.

***

## 3. Includes, variables, and templates

Zaphod provides its own light templating system via special tokens in `index.md` and includes in shared directories.

### 3.1 `{{var:key}}` metadata interpolation

In `frontmatter_to_meta.py`, any `{{var:key}}` placeholders in the body are replaced with the corresponding frontmatter value if present.

Example:

```markdown
---
name: "Syllabus"
type: "Page"
instructor_name: "Ada Lovelace"
---

Welcome to {{var:course_code}}.

Your instructor is {{var:instructor_name}}.
```

If `course_code` is defined at a higher level or injected later, you can also treat these as simple tokens for custom replacement logic.

### 3.2 `{{include:name}}` includes

`{{include:name}}` pulls in the contents of a shared markdown file, with search precedence:[7]

1. `pages/includes/name.md`
2. `includes/name.md`
3. `<courses_root_parent>/_all_courses/includes/name.md`

Includes themselves are processed recursively: Zaphod applies `{{var:...}}` to the include content and expands nested `{{include:...}}` markers as well.

This replaces the older `_styles` concept with a more explicit `includes`/templates model that you control directly in the repo.

***

## 4. Environment and Canvas configuration

From `/path/to/courses/example-course`:

```bash
cd /path/to/courses/example-course
python -m venv .venv
source .venv/bin/activate
pip install canvasapi watchdog python-frontmatter emoji markdown beautifulsoup4 lxml pyyaml
# plus markdown2canvas if you are still using its publish layer
```


Canvas credentials:

```bash
mkdir -p ~/.canvas
nano ~/.canvas/credentials.txt
```

```python
API_KEY = "YOUR_CANVAS_API_TOKEN_HERE"
API_URL = "https://yourcanvas.institution.edu/"
```

Environment variables:

```bash
export CANVAS_CREDENTIAL_FILE=$HOME/.canvas/credentials.txt
export COURSE_ID=123456
```

Scripts and `canvasapi` use these to connect to Canvas and the correct course.

Zaphod also uses `_course_metadata/defaults.json` to store per-course defaults (including `course_id` if `COURSE_ID` is not set):[10]

```json
{
  "course_id": 123456
}
```

***

## 5. Core scripts and pipeline

Zaphod is designed around a repeatable pipeline that can run on demand or automatically when files change.

### 5.1 `frontmatter_to_meta.py`

- Walks `pages/` for content folders ending in `.page`, `.assignment`, `.file`, `.link`.
- For each folder:
  - Parses `index.md` YAML frontmatter with `python-frontmatter`.
  - Writes `meta.json` and `source.md` after applying `{{var:...}}` and `{{include:...}}`.
- Supports incremental mode:
  - If `ZAPHOD_CHANGED_FILES` is set, only processes folders whose `index.md` changed.

### 5.2 `publish_all.py`

Publishes pages, assignments, files, and external links to Canvas, and manages asset uploads.

- Discovers all content folders under `pages/` ending in `.page`, `.assignment`, `.file`, `.link` or a subset inferred from `ZAPHOD_CHANGED_FILES`.
- Uses `markdown2canvas` (for now) to construct `Page`, `Assignment`, `Link`, and `File` objects from each folder and call `.publish(course, overwrite=True)`.
- Before publishing:
  - For Pages and Assignments, reads `source.md`, replaces `{{video:...}}` placeholders by:
    - Locating the referenced file in `assets/` or in the content folder.
    - Uploading it to Canvas (or reusing cached IDs).
    - Injecting `<iframe src="{CANVAS_BASE_URL}/media_attachments_iframe/{file_id}">` markup.
  - Writes the modified `source.md` back to disk.
- Provides `--assets-only` mode to bulk upload all asset files under `assets/` using a shared `_course_metadata/upload_cache.json` to avoid re-uploads.

Over time, Zaphod is moving toward inlining this publish logic (replacing markdown2canvas) while keeping the same `meta.json`/`source.md` contract.

### 5.3 `sync_modules.py`

Ensures Canvas modules reflect the `modules` lists in `meta.json`.

- Reads `ZAPHOD_CHANGED_FILES` and narrows work to content affected by changes, or processes all content if unset.
- For each Page/Assignment/File/Link folder:
  - Loads `meta.json` and reads `name`/`filename`/`external_url`, `modules`, `indent`.
  - Finds or creates each module via `course.create_module`.
  - Adds the appropriate module item (Page, Assignment, File, or ExternalUrl) if it is not already present, avoiding duplicates.
- Module ordering is later reconciled by `prune_canvas_content.py` using `modules/module_order.yaml`.

### 5.4 `sync_clo_via_csv.py`

Synchronizes course-level learning outcomes (CLOs) from YAML into Canvas Outcomes via CSV import.

- Reads `outcomes/outcomes.yaml`, expecting a top-level mapping with `course_outcomes` list.
- Builds `outcomes/outcomes_import.csv` following Canvas Outcomes CSV format, encoding rating levels as alternating `points,description` cells after a `ratings` header.
- Uses `Course.import_outcome()` to import/update all course outcomes in one batch.
- Honors incremental mode:
  - If `ZAPHOD_CHANGED_FILES` is set and `outcomes.yaml` is not among changed paths, skips work.

### 5.5 `sync_rubrics.py`

Creates/updates Canvas rubrics from specs in `.assignment` folders and associates them with assignments.

- Scans `pages/**/.assignment` for `rubric.yaml`, `rubric.yml`, or `rubric.json`.
- Uses `meta.json["name"]` to locate the Canvas assignment.
- Loads rubric spec (title, criteria, ratings) and builds a payload for `POST /api/v1/courses/:course_id/rubrics`, including:
  - Criteria descriptions, points, ranges, and rating levels.
  - Rubric association fields linking it to the assignment and marking it as used for grading.
- Uses raw HTTP with credentials from `CANVAS_CREDENTIAL_FILE`.

### 5.6 `sync_quiz_banks.py`

Converts `quiz-banks/*.quiz.txt` into Classic quizzes and questions.

- Each `.quiz.txt` file:
  - May start with YAML frontmatter specifying quiz metadata (title, points_per_question, shuffle_answers, published, etc.).
  - Contains a NYIT Canvas Exam Converter-style question body (multiple-choice, multiple-answer, short answer, essay, file upload, true/false).
- `sync_quiz_banks.py`:
  - In incremental mode: only processes `.quiz.txt` files listed in `ZAPHOD_CHANGED_FILES`; otherwise processes all under `quiz-banks/`.
  - Parses each file into `ParsedQuestion` objects, then creates a Classic Quiz via `course.create_quiz`.
  - Adds each question via `quiz.create_question` with the appropriate `question_type`, `answers`, and `points_possible`.

### 5.7 `prune_canvas_content.py`

Reconciles Canvas content/modules with the current repo and removes stale items.

- Builds local sets:
  - Page names and assignment names from `pages/**/index.md` frontmatter.
  - Module memberships for pages/assignments/files/links from `pages/**/meta.json`.
- Builds Canvas sets:
  - Existing pages, assignments, files, modules, and module items.
- Content pruning:
  - Deletes Canvas pages whose titles are not present locally.
  - Optionally deletes assignments not present locally (controlled by env/flags).
- Module-item pruning:
  - For each module item, keeps only those whose module name appears in the local `modules` list for that object type; removes extra module items but leaves the underlying content.
- Empty module pruning:
  - Deletes any modules with no items **except** those listed in `modules/module_order.yaml`.
- Work-file cleanup:
  - Removes generated work files under `pages/` such as `styled_source.md`, `extra_styled_source.*`, `result.html`, and `source.md` to keep the repo clean after publishing.

### 5.8 `prune_quizzes.py`

Cleans up Canvas quizzes and banks.

- Deletes Classic quizzes with zero questions.
- Deletes question banks whose names do not match any `quiz-banks/*.quiz.txt` filename stem.
- Controlled by `ZAPHOD_PRUNE_APPLY` (true by default); in dry-run mode logs what it would delete.

### 5.9 `watch_and_publish.py`

Long-running watchdog that drives the pipeline.

- Must be run from the course root (where `pages/` lives); exits if `pages/` is missing.
- Watches for changes to:
  - `pages/**/index.md`
  - `outcomes/outcomes.yaml`
  - `modules/module_order.yaml`
  - `quiz-banks/*.quiz.txt`
  - `rubric.{yaml,yml,json}`.
- Maintains `_course_metadata/watch_state.json` with:
  - `last_run_ts`, `run_count`, `last_run_datetime`, `watch_stopped`.
- On change (debounced):
  - Computes changed files since last run.
  - Exports `ZAPHOD_CHANGED_FILES` (newline-separated absolute paths) to child processes.
  - Runs, in order:
    1. `frontmatter_to_meta.py`
    2. `publish_all.py`
    3. `sync_modules.py`
    4. `sync_clo_via_csv.py`
    5. `sync_rubrics.py`
    6. `sync_quiz_banks.py`
    7. `prune_canvas_content.py` (optional)
    8. `prune_quizzes.py`.
- Prevents overlapping runs and provides clear phase fences in the log.

***

## 5.10 `export_cartridge.py`

Exports the entire course to IMS Common Cartridge 1.3 format for importing into other LMS platforms.

- Creates a complete `.imscc` package containing:
  - All pages as HTML web content
  - Assignments with rubrics (CC extension format)
  - Quizzes as QTI 1.2 assessments
  - Learning outcomes
  - Module structure
  - Media assets

- Usage:
  ```bash
  # Via CLI
  zaphod export                           # Export full course
  zaphod export --output course.imscc     # Custom output path
  zaphod export --title "My Course"       # Set course title
  
  # Direct script
  python export_cartridge.py --output my-course.imscc
  ```

- The export can be imported into:
  - Canvas LMS
  - Moodle
  - Blackboard
  - Brightspace (D2L)
  - Sakai
  - Any CC 1.3 compliant LMS

This enables course portability and migration without needing Canvas API access.

***

## 6. Credits

Zaphod builds on ideas and tooling from:

- The original [markdown2canvas](https://github.com/ofloveandhate/markdown2canvas) project by Silviana Amethyst et al.
- The NYIT [CanvasExam Converter](https://site.nyit.edu/its/canvas_exam_converter) for its quiz text format.
- GPT-4o assistance via [Perplexity](https://www.perplexity.ai/) during design and refactoring.

Together, these move Zaphod toward a curriculum-level pipeline where outcomes, topics, content, quizzes, and rubrics live in a coherent, version-controlled text representation synchronized to Canvas.

---
## 7. License

&copy; 2026 Dale Chapman
Zaphod is open-source under the MIT License.
See the `LICENSE` file in the repo root for full terms.