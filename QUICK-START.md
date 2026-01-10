# Zaphod Quick Start

Get up and running with Zaphod in 15 minutes.

---

## What You'll Do

1. ✅ Install Python dependencies
2. ✅ Set up Canvas API credentials  
3. ✅ Create your first course
4. ✅ Make a page and sync it to Canvas
5. ✅ See it update automatically

Let's go!

---

## Step 1: Install Python (if needed)

Zaphod needs Python 3.9 or later.

**Check if you have it:**
```bash
python3 --version
```

**If not installed:**
- **Mac**: `brew install python3`
- **Windows**: Download from [python.org](https://python.org)
- **Linux**: `sudo apt install python3` or `sudo yum install python3`

---

## Step 2: Set Up Zaphod

### Get the code
```bash
# Clone or download Zaphod
cd ~/projects
git clone https://github.com/yourusername/zaphod.git
cd zaphod

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Install the CLI (optional but recommended)
```bash
# From the zaphod directory
pip install -e .

# Now you can use "zaphod" command anywhere
zaphod --help
```

---

## Step 3: Get Canvas API Token

You need an API token so Zaphod can talk to Canvas.

### In Canvas:
1. Log into Canvas
2. Click **Account** → **Settings**
3. Scroll to **Approved Integrations**
4. Click **+ New Access Token**
5. Purpose: "Zaphod course authoring"
6. Expiration: (choose a date or leave blank)
7. Click **Generate Token**
8. **Copy the token** (you won't see it again!)

### Save credentials locally:
```bash
# Create credentials directory
mkdir -p ~/.canvas

# Create credentials file
nano ~/.canvas/credentials.txt
```

**Put this in the file:**
```python
API_KEY = "paste_your_token_here"
API_URL = "https://canvas.yourinstitution.edu"
```

Replace:
- `paste_your_token_here` with your actual token
- `canvas.yourinstitution.edu` with your Canvas URL

**Save and close** (Ctrl+X, then Y, then Enter)

---

## Step 4: Create Your First Course

### Find your Canvas course ID:
1. Open your Canvas course
2. Look at the URL: `https://canvas.edu/courses/123456`
3. The number is your course ID (example: `123456`)

### Initialize a Zaphod course:
```bash
# Create course directory
mkdir -p ~/courses/my-first-course
cd ~/courses/my-first-course

# Initialize course structure
zaphod init --course-id 123456
```

(Replace `123456` with your actual course ID)

**What this creates:**
```
my-first-course/
├── pages/               # Your content goes here
├── assets/              # Images, PDFs, videos
├── quiz-banks/          # Quiz files
├── outcomes/            # Learning outcomes
├── modules/             # Module ordering
├── _course_metadata/    # Internal state
└── zaphod.yaml          # Configuration
```

---

## Step 5: Create Your First Page

### Option A: Use the CLI
```bash
zaphod new --type page --name "Welcome to the Course"
```

### Option B: Create manually
```bash
# Create page folder
mkdir -p pages/welcome.page

# Create page content
cat > pages/welcome.page/index.md << 'EOF'
---
name: "Welcome to the Course"
type: "page"
modules:
  - "Module 0: Start Here"
published: true
---

# Welcome!

This is your first Zaphod page.

## What You'll Learn

In this course, you will:
- Learn cool stuff
- Do amazing things  
- Have a great time

## Getting Help

If you need help, email your instructor.
EOF
```

---

## Step 6: Sync to Canvas

### Sync once:
```bash
zaphod sync
```

**What happens:**
1. Zaphod reads your page
2. Creates/updates it in Canvas
3. Adds it to "Module 0: Start Here"
4. Makes it visible to students

### Check Canvas:
Open your Canvas course and look for "Welcome to the Course" in Module 0!

---

## Step 7: Enable Watch Mode (Auto-Sync)

Instead of manually running sync every time, let Zaphod watch for changes:
```bash
# Start the watcher
zaphod sync --watch
```

**Leave this running in a terminal window.**

Now, whenever you save a file, Zaphod automatically syncs it to Canvas!

### Test it:
1. Open `pages/welcome.page/index.md`
2. Change "Welcome!" to "Welcome, everyone!"
3. Save the file
4. Wait 5 seconds
5. Refresh Canvas

Your change should appear!

---

## What You Just Did

✅ **Set up Zaphod** with Canvas credentials  
✅ **Created a course** with proper structure  
✅ **Made a page** using frontmatter + markdown  
✅ **Synced to Canvas** with one command  
✅ **Enabled watch mode** for automatic updates  

You're ready to build!

---

## What's Next?

### Create more content:
```bash
# Create an assignment
zaphod new --type assignment --name "First Essay" --module "Module 1"

# Create a link
zaphod new --type link --name "Course Resources"
```

### Add media:
1. Put images/videos in `assets/`
2. Reference them in markdown: `![My Image](../assets/image.jpg)`
3. Zaphod uploads them automatically

### Use variables:
```markdown
---
name: "Syllabus"
instructor_name: "Ada Lovelace"
---

Your instructor is {{var:instructor_name}}.
```

### Use includes:
```markdown
# In pages/includes/footer.md:
For help, contact support@example.edu

# In any page:
{{include:footer}}
```

---

## Common Commands
```bash
# Sync once
zaphod sync

# Auto-sync on changes
zaphod sync --watch

# List all content
zaphod list

# Check for problems
zaphod validate

# Show course info
zaphod info

# Preview what would be deleted
zaphod prune --dry-run

# Get help
zaphod --help
```

---

## Tips for Success

### ✅ Do This:
- **Edit locally only** (never in Canvas)
- **Sync to sandbox first** (test before going live)
- **Use Git** for version control
- **Keep watch mode running** while working
- **Use dry-run** before destructive operations

### ❌ Don't Do This:
- Don't edit in Canvas (changes will be overwritten)
- Don't share API tokens (keep them private)
- Don't delete cache files unless you know why
- Don't run multiple sync processes simultaneously

---

## Troubleshooting

### "Command not found: zaphod"
**Fix:** Activate virtual environment:
```bash
cd ~/projects/zaphod
source .venv/bin/activate
```

### "COURSE_ID not set"
**Fix:** Make sure you ran `zaphod init --course-id YOUR_ID`

Or set it manually:
```bash
export COURSE_ID=123456
```

### "Canvas API credentials not found"
**Fix:** Check `~/.canvas/credentials.txt` exists and has correct format

### "Page not showing up in Canvas"
**Check:**
1. Did sync complete without errors?
2. Is `published: true` in frontmatter?
3. Is the module name spelled correctly?
4. Try refreshing Canvas (Ctrl+Shift+R)

### "Watch mode not detecting changes"
**Fix:**
1. Make sure watcher is actually running
2. Check you're saving files (not just editing)
3. Wait a few seconds (debouncing delay)
4. Check terminal for errors

---

## Getting Help

### Documentation:
- **README.md** - Full overview
- **01-pages.md** through **10-pipeline.md** - Feature guides
- **ARCHITECTURE.md** - How it works
- **GLOSSARY.md** - Term definitions
- **KNOWN-ISSUES.md** - Common problems

### Common Questions:

**Q: Can I edit in Canvas?**  
A: No! Always edit locally. Canvas edits will be overwritten.

**Q: How do I add images?**  
A: Put them in `assets/` or the content folder, reference with `![](path)`

**Q: How do I make a quiz?**  
A: Create `quiz-banks/myquiz.quiz.txt` (see 09-quizzes.md)

**Q: How do I share text across pages?**  
A: Use includes: Create `pages/includes/snippet.md`, then use `{{include:snippet}}`

**Q: Can I undo a sync?**  
A: Use Git to roll back files, then sync again. Or manually fix in Canvas.

**Q: Why is syncing slow?**  
A: First sync is always slower. Watch mode uses incremental sync (much faster).

---

## Next Steps

### Learn the basics:
1. Read [01-pages.md](01-pages.md) - How pages work
2. Read [02-assignments.md](02-assignments.md) - How assignments work
3. Read [03-variables.md](03-variables.md) - Using variables
4. Read [04-includes.md](04-includes.md) - Reusing content

### Try advanced features:
1. [06-rubrics.md](06-rubrics.md) - Grading rubrics
2. [07-outcomes.md](07-outcomes.md) - Learning outcomes
3. [09-quizzes.md](09-quizzes.md) - Plain-text quizzes
4. [10-pipeline.md](10-pipeline.md) - Understanding the sync process

### Set up your workflow:
1. Create a Git repository (`git init`)
2. Commit your course (`git add . && git commit -m "Initial course"`)
3. Create a sandbox course in Canvas for testing
4. Keep watch mode running while you work
5. Sync to sandbox first, live second

---

## You're Ready!

You now know how to:
- ✅ Set up Zaphod
- ✅ Create content
- ✅ Sync to Canvas
- ✅ Use watch mode

The rest is just learning features as you need them.

**Happy course building!** 🚀