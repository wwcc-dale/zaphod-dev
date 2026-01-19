# Zaphod
Zaphod is a **course** authoring workspace that makes Canvas faster, safer, and easier to reuse than editing directly in the browser. It lets you build a complete Canvas course from a folder of plain‑text files (pages, assignments, quizzes, rubrics, outcomes, modules, and files) all without working in the Canvas editor.

Each course lives in its own folder and acts as the single “source of truth” for one or more Canvas shells. When you are ready, you run a publish command that pushes updates to pages, files, modules, outcomes, rubrics, and quizzes in a consistent, repeatable way. An optional watcher can keep an eye on your course folder while you work and run the pipeline automatically when you save, so a sandbox course updates a few moments after each edit and larger courses can sync just the pieces that changed.

Quizzes are written in a compact plain‑text format (based on the NYIT Canvas Exam Converter style), then turned into reusable Classic quiz banks and quizzes automatically, so the same quiz files can support multiple sections or shells. Outcomes and rubrics live in simple text formats too, and Zaphod keeps them attached to the right assignments from term to term, which makes it easier to maintain alignment without re‑wiring everything every time you copy a course.

***  

## Key benefits  

Working from plain text gives you a calm, predictable way to build a course that is hard to achieve when editing directly in the Canvas UI. The same files you see in your course folder are the ones that drive what students see in each Canvas shell that folder serves.

### Collaboration and version control  

- All course content can live in a shared folder (often in Git), so you can see what changed, when it changed, and who changed it.  
- Multiple instructors or designers can work on the same course without overwriting each other’s edits, and you can always roll back to an earlier version if something goes wrong.  

### Faster editing and reuse  

- Writing in markdown is often faster and less frustrating than working in a rich‑text editor, especially for longer pages, code samples, or repeated layouts.  
- You can copy and reuse modules, pages, assignments, quizzes, and rubrics across terms or courses simply by copying folders and files, instead of rebuilding them by hand in Canvas.  
- A single repository can drive multiple Canvas shells and sandboxes, so you can maintain one master course and publish it wherever you need it.  

### Automation and consistency  

- Course‑wide changes—such as a new support link, an updated policy, or a shared footer—can be updated once and applied everywhere the next time you publish.  
- Text that appears in many places can be stored as a variable at the page, course, or all‑courses level (for example `animal: cat`) and reused wherever you need it with a simple placeholder like `{{var:animal}}`.  
- Larger shared sections, such as a late‑work policy or accessibility statement, can be defined once and reused with includes like `{{include:myInclude}}`, keeping wording consistent across the course (or across many courses).  
- Zaphod’s scripts keep titles, module memberships, outcomes, rubrics, and other details in sync across the whole course, reducing tedious clicking and the risk of small, hard‑to‑spot errors.  

### Portability and longevity  

- Because your course content lives in plain text instead of being locked inside Canvas, it is easier to adapt to another LMS, a static website, or other formats in the future.  
- The folder structure (pages, modules, outcomes, quiz banks, and so on) makes the course design visible at a glance, so a single repository can drive many Canvas shells or future versions of the course.  

### Testing and safety  

- You can publish to a test or sandbox course first, review everything, and then run the same pipeline against a live section once you are satisfied.  
- A “watch and publish” process can monitor your files while you work and run the pipeline when it detects changes, so you are less likely to miss a page or leave something half‑updated in Canvas, even in larger and more complex courses.
---
## Zaphod's Elements

### [Pages](01-pages.md)

Pages are the basic building blocks of a Zaphod course. Each page lives in its own folder and has a single `index.md` file that holds both its settings (at the top) and its content (below). You write the page just like you would any other markdown document: headings, paragraphs, lists, images, and links. The page you see in Canvas is simply the published version of what you wrote in `index.md`.

When you run Zaphod, each of these page folders becomes a real Canvas Page with the same title and body text. This means you rarely need to touch the Canvas page editor; your local text files stay as the source of truth for what students see.

- [How Pages Work ►](01-pages.md)

### [Assignments](02-assignments.md)

Assignments work almost exactly like pages, but with a few extra details for grading. Each assignment lives in its own folder with an `index.md` file, and you write the instructions for students in markdown, just as you do for pages.

At the top of `index.md`, the frontmatter can describe grading settings such as points possible, how students submit (for example file upload), and which modules the assignment belongs to. When Zaphod runs, it reads those settings and creates or updates the corresponding Canvas Assignment so its title, description, points, and basic options stay in sync with your text file.

- [How Assignments Work ►](02-assignments.md)

### [Variables](03-variables.md)

Variables let you fill in small pieces of information automatically so you don’t have to repeat them everywhere. You define key values, such as the course code, support email, or instructor name, in the frontmatter or in a shared configuration.

In your page or assignment body you use a placeholder that refers to that key instead of hard‑coding the text. When Zaphod processes the file, it substitutes the actual value wherever the placeholder appears, making it easy to change details like term labels or contact information in one place and have the updates flow into every affected page and assignment.

- [How Variables Work ►](03-variables.md)

### [Includes](04-includes.md)

Includes are reusable content snippets you can drop into multiple pages or assignments without copying and pasting. You keep shared blocks—such as a standard course footer, a late‑work policy, or a recurring assignment tip—in separate markdown files in one of the include directories.

Inside any `index.md`, you insert a short marker that names the include you want. When Zaphod processes the page or assignment, it replaces that marker with the full text of the shared snippet, so updating the include file automatically updates every page or assignment that uses it.

- [How Includes Work ►](04-includes.md)


### [Modules](05-modules.md)

Modules describe how your pages, assignments, quizzes, and files are grouped and ordered for students inside Canvas. Instead of dragging items around in the Canvas interface, you describe module membership in each item’s frontmatter and, if you like, keep a small file that outlines the overall module order and which modules should never be removed.

During a sync, Zaphod reads those settings and ensures that Canvas modules reflect what you’ve described in your text files. This keeps your course structure consistent and makes it easy to rearrange or reuse modules just by editing or copying configuration in your repo.

- [How Modules Work ►](05-modules.md)


### [Rubrics](06-rubrics.md)

Rubrics live alongside their assignments so everything stays together. For any assignment folder, you can add a rubric file that describes the criteria, point values, and rating levels in plain language instead of building the rubric by clicking around in Canvas.

When Zaphod syncs rubrics, it reads those definitions and builds the matching rubric in Canvas, then attaches it to the correct assignment. If you later refine the wording or adjust point values in the rubric file, running the sync again will update the Canvas rubric to match your latest version.

- [How Rubrics Work ►](06-rubrics.md)

### [Outcomes](07-outcomes.md)

Outcomes are defined at the course level rather than per assignment. Zaphod keeps them in a shared outcomes file where each outcome has a short code, a title, a description, and a set of rating levels, all under version control so they can be reused across multiple assignments.

When you run the outcome sync, Zaphod imports or updates all of those outcomes in Canvas in one batch. Rubrics can then point to these outcome codes, which allows Canvas to track student performance against those outcomes whenever you grade using an aligned rubric.

- [Outcomes Work ►](07-outcomes.md)

### [Assets folder](08-assets.md)

The assets folder is where you keep files that are reused across pages and assignments, such as images, handouts, videos, and other downloadable resources. Instead of uploading these files manually through Canvas every time, you place them in the assets folder once.

Zaphod can then upload them to Canvas for you and remember which files have already been uploaded. In your markdown, you reference these assets like ordinary local files, and the publish step takes care of making sure they are available inside Canvas and linked correctly from your pages and assignments.
### [How the Assets Folder Works ►](08-assets.md)


### [Quizzes](09-quizzes.md)

Quizzes in Zaphod are defined in simple text files rather than built one question at a time in Canvas. Each quiz file contains a short header with basic information (such as a title and default points) followed by a body of questions written in a compact, easy‑to‑read shorthand.

You list the question text, possible answers, and correct answer markers in that file, which makes it straightforward to edit or duplicate. When you run the quiz sync script, Zaphod reads these files, creates Classic quizzes in Canvas, and adds the questions with the correct types and answers. This makes it easy to share or update quizzes across courses by working entirely with text.

- [How Quizzes Work ►](09-quizzes.md)

### [Pipeline and watcher](pipeline.md)

The pipeline is the automated sequence that turns your text files into a live Canvas course: it prepares internal metadata, publishes content, updates modules, synchronizes outcomes, syncs rubrics and quizzes, and can optionally clean up stale items. You can run this pipeline when you choose, or let a long‑running “watcher” take care of it.

The watcher monitors your course folder for changes—such as edits to `index.md`, outcomes, or quiz files—and triggers the pipeline when something changes. In practice, this makes the experience feel like “edit files on your computer, and Canvas quietly updates in the background,” without repeatedly clicking through the Canvas interface.

- [How the Pipeline & Watcher Works ►](pipeline.md)

---
## Zaphod File Layout
Everything exists in flat files in a very logical directory structure. Think of this of all of the ingredients for your Canvas shell.

Here is an example of a typical zaphod file layout

```text
courses_root/
└─ example-course/                 # one Canvas course
   ├─ pages/                       # all Canvas items (pages, assignments, files, links)
   │  ├─ intro.page/               # Canvas Page + page-local media
   │  │  ├─ index.md
   │  │  ├─ intro-image.jpg        # image used only on this page (or symlink from assets/)
   │  │  └─ intro-handout.pdf      # page-specific handout (or symlink)
   │  ├─ example.assignment/       # Canvas Assignment + media
   │  │  ├─ index.md
   │  │  ├─ rubric.yaml            # optional rubric spec
   │  │  ├─ sample-output.png      # assignment-specific image (or symlink)
   │  │  └─ starter-files.zip      # assignment resources (or symlink)
   │  ├─ syllabus.page/
   │     └─ index.md
   │
   ├─ quiz-banks/                  # Classic quiz definitions (NYIT-style)
   │  ├─ week1.quiz.txt
   │  └─ midterm.quiz.txt
   │
   ├─ outcomes/                    # course-level learning outcomes
   │  ├─ outcome_map.yaml
   │  ├─ outcomes.yaml
   │  └─ outcomes_import.csv       # generated for Canvas Outcomes import
   │
   ├─ modules/                     # optional module ordering & protection
   │  └─ module_order.yaml
   │
   ├─ assets/                      # flat pool of course assets
   │  ├─ intro-image.jpg
   │  ├─ intro-handout.pdf
   │  ├─ sample-output.png
   │  ├─ starter-files.zip
   │  └─ week1-video.mp4
   │
   ├─ _course_metadata/            # internal course-level state/config
   │  ├─ defaults.json             # defaults (e.g. course_id)
   │  ├─ upload_cache.json         # Canvas file ID cache
   │  └─ watch_state.json          # watcher bookkeeping
   │
   ├─ zaphod/                      # Zaphod scripts for this repo
   │  ├─ frontmatter_to_meta.py
   │  ├─ publish_all.py
   │  ├─ sync_modules.py
   │  ├─ sync_clo_via_csv.py
   │  ├─ sync_rubrics.py
   │  ├─ sync_quiz_banks.py
   │  ├─ prune_canvas_content.py
   │  ├─ prune_quizzes.py
   │  └─ watch_and_publish.py
   │
   └─ .venv/                       # optional Python virtualenv
```
