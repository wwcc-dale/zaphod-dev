# Quizzes

> Zaphod lets you create Canvas quizzes from plain text files — no more clicking through the Canvas quiz editor question by question.

---

## How Quizzes Work in Zaphod

Zaphod uses a two-layer approach to quizzes:

1. **Question Banks** — Pools of questions stored in `question-banks/`
2. **Quizzes** — The actual quizzes students take, stored in `pages/` as `.quiz/` folders

You create questions in banks, then quizzes pull from those banks. This lets you:
- Reuse questions across multiple quizzes
- Randomize which questions each student sees
- Update questions in one place

---

## Quick Example

### Step 1: Create a Question Bank

Create `question-banks/chapter1.bank.md`:

```markdown
---
bank_name: "Chapter 1 Questions"
---

1. What is 2 + 2?
a) 3
*b) 4
c) 5
d) 6

2. Which of these are prime numbers? (Select all that apply)
[*] 2
[*] 3
[ ] 4
[*] 5
[ ] 6
```

### Step 2: Create a Quiz

Create `pages/01-Week 1.module/quiz.quiz/index.md`:

```markdown
---
name: "Week 1 Quiz"
quiz_type: assignment
time_limit: 30
shuffle_answers: true
question_groups:
  - bank_id: 12345     # Get this from Canvas after syncing banks
    pick: 5
    points_per_question: 2
---

Complete this quiz to test your understanding of Chapter 1.
```

### Step 3: Sync

```bash
zaphod sync
```

---

## Question Banks

Question banks are pools of questions. Students never see banks directly — quizzes pull questions from them.

### Bank File Format

Banks live in `question-banks/` with a `.bank.md` extension:

```
question-banks/
├── chapter1.bank.md
├── chapter2.bank.md
└── midterm-pool.bank.md
```

### Bank Frontmatter

```yaml
---
bank_name: "Chapter 1 Questions"    # Name in Canvas
---
```

If you don't specify `bank_name`, Zaphod uses the filename.

### Question Types

#### Multiple Choice

The `*` marks the correct answer:

```markdown
1. What color is the sky?
a) Red
*b) Blue
c) Green
d) Yellow
```

#### Multiple Answer

Use `[*]` for correct and `[ ]` for incorrect:

```markdown
2. Which animals can fly? (Select all that apply)
[*] Eagle
[ ] Dog
[*] Bat
[ ] Fish
[*] Sparrow
```

#### True/False

```markdown
3. The Earth is flat.
*a) False
b) True
```

Or simply:

```markdown
3. The Earth is flat.
*False
```

#### Short Answer

Use `*` to mark accepted answers:

```markdown
4. What is the capital of France?
* Paris
* paris
```

Multiple variations can be correct.

#### Essay

Use `####` to indicate an essay question:

```markdown
5. Explain the significance of the Industrial Revolution.
####

Consider economic, social, and technological impacts.
```

#### File Upload

Use `^^^^` to indicate students should upload a file:

```markdown
6. Upload your completed worksheet.
^^^^
```

### Question Numbering

Questions start with a number followed by a period. You can use sequential numbering or markdown-style numbering (all "1."):

**Sequential (traditional):**
```markdown
1. First question?
*a) Correct

2. Second question?
*a) Correct
```

**Markdown-style (all "1."):**
```markdown
1. First question?
*a) Correct

1. Second question?
*a) Correct

1. Third question?
*a) Correct
```

Both work — Zaphod parses questions by their structure, not their numbers. The markdown-style is easier to maintain when adding or reordering questions.

### Points Per Question

Set in quiz frontmatter, not in the bank. Banks just store questions.

---

## Creating Quizzes

Quizzes are content items, just like pages and assignments. They live in `.quiz/` folders:

```
pages/
└── 01-Week 1.module/
    └── weekly-quiz.quiz/
        └── index.md
```

### Quiz Frontmatter

```yaml
---
name: "Week 1 Quiz"
quiz_type: assignment          # 'assignment' (graded) or 'practice_quiz'
time_limit: 30                 # Minutes (optional)
allowed_attempts: 2            # How many tries (optional)
shuffle_answers: true          # Randomize answer order
published: false               # Set true when ready
modules:
  - "Week 1"                   # Module(s) to appear in
indent: 1                      # Indentation level in module (optional)

question_groups:
  - bank_id: 12345            # Canvas bank ID
    pick: 5                    # How many questions to pull
    points_per_question: 2     # Points each
---
```

**Common options:**
| Field | Values | Default |
|-------|--------|---------|
| `quiz_type` | `assignment`, `practice_quiz`, `graded_survey`, `survey` | `assignment` |
| `time_limit` | minutes or `null` | no limit |
| `allowed_attempts` | number or `-1` for unlimited | 1 |
| `shuffle_answers` | `true`/`false` | `true` |
| `show_correct_answers` | `true`/`false` | `true` |
| `indent` | `0`, `1`, `2` | `0` |

### Finding Bank IDs

After you sync your banks, you need to find their Canvas IDs:

1. Go to your Canvas course
2. Click **Quizzes** → **⋮** menu → **Manage Question Banks**
3. Click on your bank
4. The URL will show the ID: `.../question_banks/12345`

Then add that ID to your quiz:

```yaml
question_groups:
  - bank_id: 12345
    pick: 5
```

### Multiple Question Groups

Pull from multiple banks:

```yaml
question_groups:
  - bank_id: 12345     # Chapter 1
    pick: 5
    points_per_question: 2
  - bank_id: 12346     # Chapter 2
    pick: 5
    points_per_question: 2
```

---

## Inline Questions

For simple quizzes, you can put questions directly in the quiz instead of using banks:

```markdown
---
name: "Quick Check"
quiz_type: practice_quiz
inline_questions: true
---

# Quick Knowledge Check

1. What is the main idea of this chapter?
a) Growth
*b) Change
c) Stability

2. True or false: The author agrees with the theory.
*a) True
b) False
```

This is simpler but doesn't allow randomization or question reuse.

---

## Quiz Settings Reference

| Setting | Description | Default |
|---------|-------------|---------|
| `name` | Quiz title | Required |
| `quiz_type` | `assignment` (graded) or `practice_quiz` | `assignment` |
| `time_limit` | Minutes allowed | No limit |
| `allowed_attempts` | Number of tries | 1 |
| `shuffle_answers` | Randomize answer order | `true` |
| `show_correct_answers` | Show answers after | `true` |
| `published` | Visible to students | `false` |
| `question_groups` | Banks to pull from | See below |
| `inline_questions` | Questions in body | `false` |

### Question Group Settings

```yaml
question_groups:
  - bank_id: 12345           # Required: Canvas bank ID
    pick: 5                   # Required: Questions to pull
    points_per_question: 2    # Points each (default: 1)
```

---

## Complete Example

### Bank: `question-banks/week1.bank.md`

```markdown
---
bank_name: "Week 1: Fundamentals"
---

1. What is the primary purpose of version control?
a) Making code run faster
*b) Tracking changes over time
c) Compiling programs
d) Testing software

2. Which command creates a new Git repository?
a) git clone
*b) git init
c) git pull
d) git push

3. Select all valid Git commands:
[*] git add
[*] git commit
[ ] git compile
[*] git push
[ ] git run

4. What does 'git status' show?
* current state of working directory
* the state of the repository
* modified files

5. Explain the difference between git pull and git fetch.
####

Consider what each command does and when you might use each.
```

### Quiz: `pages/01-Getting Started.module/git-quiz.quiz/index.md`

```markdown
---
name: "Git Fundamentals Quiz"
quiz_type: assignment
time_limit: 20
allowed_attempts: 2
shuffle_answers: true
published: false

question_groups:
  - bank_id: 12345
    pick: 4
    points_per_question: 5
---

# Git Fundamentals Quiz

Test your understanding of basic Git concepts.

**Time Limit:** 20 minutes
**Attempts:** 2
**Points:** 20 total

Good luck!
```

---

## Workflow

### Initial Setup

1. Create your question banks in `question-banks/`
2. Run `zaphod sync` to upload banks to Canvas
3. Note the bank IDs from Canvas
4. Create `.quiz/` folders with `bank_id` references
5. Run `zaphod sync` again to create quizzes

### Updating Questions

1. Edit the `.bank.md` file
2. Run `zaphod sync`
3. Bank is re-imported (with content-hash caching)
4. Quizzes using that bank get the updated questions

### Tips

- **Start with `published: false`** — Test before students see it
- **Use practice quizzes for self-assessment** — `quiz_type: practice_quiz`
- **Keep banks focused** — One topic per bank makes reuse easier
- **Use multiple banks** — Mix easy and hard questions from different pools

---

## Troubleshooting

### "Bank not found"

After creating a bank, you need to:
1. Run `zaphod sync` to upload it
2. Find the bank ID in Canvas
3. Add that ID to your quiz's `question_groups`

Canvas doesn't provide an API to look up banks by name, so you need the numeric ID.

### Questions Not Updating

Banks use content-hash caching. If questions aren't updating:

1. Check that you actually changed the `.bank.md` file
2. Delete `_course_metadata/bank_cache.json` and re-sync
3. Check Canvas to see if the bank has duplicate entries

### Quiz Shows Wrong Questions

Make sure:
- The `bank_id` is correct
- The bank actually contains questions
- You've synced after making changes

---

## Next Steps

- [Modules](05-modules.md) — Organize your quizzes
- [Pipeline](10-pipeline.md) — Understand the sync process
- [Assets](08-assets.md) — Add images to questions
