## Pipeline and watcher in Zaphod

The pipeline and watcher are what turn your text files into a live Canvas course without a lot of manual effort. The pipeline is a series of scripts that publish and update everything; the watcher is a small program that notices when you save a file and runs the pipeline for you.[1][2]

### The pipeline: what happens when you “sync”

In a typical course, the pipeline runs a set of steps in order whenever you decide to sync:

1. Read and process `index.md` files to prepare internal metadata and clean markdown.  
2. Publish or update pages, assignments, files, and links in Canvas.  
3. Make sure those items appear in the correct modules.  
4. Import or update course outcomes from your outcomes file.  
5. Create or update rubrics from `rubric.yaml` files and attach them to assignments.  
6. Create or update quizzes from `.quiz.txt` files.  
7. Optionally prune outdated content or module items that no longer exist in the repo.[3][1]

Each step focuses on one part of the course, but together they make sure that Canvas always reflects the current state of your Zaphod course folder.

From your perspective, you usually think of this as “run the sync” or “run the publish command”: after it finishes, Canvas is up to date with your latest file edits.

### The watcher: automatic updates on save

Instead of manually running all the steps every time you change a file, you can use the watcher—a long‑running script that monitors your course folder for changes:

- You start the watcher once from the course root in a terminal.  
- It watches for changes to key files such as `pages/**/index.md`, your outcomes file, quiz files, and rubric files.  
- When it sees a change, it waits briefly (to avoid double‑running on quick saves) and then runs the pipeline.[2][4]

In practice, this makes Zaphod feel very natural:

- You edit a page, assignment, rubric, or quiz in your editor.  
- You hit save.  
- A few moments later, the corresponding Canvas content updates automatically.

The watcher also keeps track of which files changed, so the pipeline can focus on just the affected pieces when possible. For instructors, this means less time thinking about scripts and more time treating Zaphod like a “local Canvas” that stays in sync with the real one in the background.