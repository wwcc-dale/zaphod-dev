# Rubrics

> Rubrics let you define grading criteria once and apply them to assignments. Zaphod supports per-assignment rubrics, shared rubrics, reusable rows, and outcome alignment.

---

## Quick Start

Create a rubric file in your assignment folder:

```yaml
# content/essay.assignment/rubric.yaml
title: "Essay Rubric"

criteria:
  - description: "Thesis and focus"
    points: 10
    ratings:
      - description: "Excellent"
        points: 10
      - description: "Satisfactory"
        points: 8
      - description: "Needs improvement"
        points: 5

  - description: "Organization"
    points: 10
    ratings:
      - description: "Excellent"
        points: 10
      - description: "Satisfactory"
        points: 8
      - description: "Needs improvement"
        points: 5
```

Run `zaphod sync rubrics` to push it to Canvas.

---

## Rubric Structure

Every rubric needs:
- `title` — Name shown in Canvas
- `criteria` — List of grading criteria (rows)

Each criterion needs:
- `description` — What's being evaluated
- `points` — Maximum points for this criterion
- `ratings` — List of performance levels

Each rating needs:
- `description` — Performance level name
- `points` — Points awarded for this level

Optional fields:
- `long_description` — Extended description (on criteria or ratings)
- `use_range` — Allow partial points between rating levels
- `outcome_code` — Link criterion to a learning outcome (see below)
- `free_form_criterion_comments` — Allow free-form comments

---

## Shared Rubrics

Instead of copying rubrics between assignments, define them once in `rubrics/`:

**Create the shared rubric:**
```yaml
# rubrics/essay_rubric.yaml
title: "Essay Rubric"
criteria:
  - description: "Thesis and focus"
    points: 10
    ratings:
      - description: "Excellent"
        points: 10
      - description: "Satisfactory"
        points: 8
      - description: "Needs improvement"
        points: 5
```

**Reference it from assignments:**
```yaml
# content/essay-1.assignment/rubric.yaml
use_rubric: "essay_rubric"
```

Changes to the shared rubric automatically apply to all assignments using it.

---

## Reusable Rubric Rows

For criteria you use in multiple rubrics (like "Writing Clarity"), create row snippets:

**Create the row:**
```yaml
# rubrics/rows/writing_clarity.yaml
- description: "Writing clarity and mechanics"
  long_description: "Grammar, syntax, and organization support readability."
  points: 10
  ratings:
    - description: "Excellent"
      long_description: "Clear, fluent writing; virtually no errors."
      points: 10
    - description: "Minor issues"
      long_description: "Generally clear; minor errors."
      points: 8
    - description: "Major issues"
      long_description: "Errors impede understanding."
      points: 5
```

**Include it in rubrics:**
```yaml
# rubrics/essay_rubric.yaml
title: "Essay Rubric"
criteria:
  - description: "Thesis and focus"
    points: 10
    ratings:
      - description: "Excellent"
        points: 10
      - description: "Satisfactory"
        points: 8

  - "{{rubric_row:writing_clarity}}"   # Expanded from rows/
```

---

## Outcome Alignment

Link rubric criteria to course learning outcomes for Canvas outcome reporting.

### Step 1: Create outcomes (if not already done)

```yaml
# outcomes/outcomes.yaml
course_outcomes:
  - code: CLO1
    title: "Write clear essays"
    description: "Students can write clear, organized essays."
    mastery_points: 8
    ratings:
      - description: "Exceeds expectations"
        points: 10
      - description: "Meets expectations"
        points: 8
```

Run `zaphod sync outcomes` to import them to Canvas.

### Step 2: Create the outcome map

After outcomes are in Canvas, you need to map your codes to Canvas IDs. Look up the IDs in Canvas (Outcomes area) and create:

```json
// _course_metadata/outcome_map.json
{
  "CLO1": 12345,
  "CLO2": 12346,
  "CLO3": 12347
}
```

### Step 3: Add outcome_code to rubric criteria

```yaml
# rubrics/essay_rubric.yaml
title: "Essay Rubric"
criteria:
  - description: "Thesis and focus"
    points: 10
    outcome_code: CLO1    # Links to CLO1 outcome
    ratings:
      - description: "Excellent"
        points: 10
      - description: "Meets expectations"
        points: 8
      - description: "Developing"
        points: 6

  - description: "Organization"
    points: 10
    outcome_code: CLO2    # Links to CLO2 outcome
    ratings:
      - description: "Excellent"
        points: 10
      - description: "Meets expectations"
        points: 8
```

When you grade using this rubric, Canvas will track outcome mastery automatically.

### Outcome alignment in shared rows

Outcome codes work in reusable rows too:

```yaml
# rubrics/rows/thesis_criterion.yaml
- description: "Thesis and argument"
  points: 10
  outcome_code: CLO1    # Carried through to any rubric using this row
  ratings:
    - description: "Excellent"
      points: 10
    - description: "Satisfactory"
      points: 8
```

---

## File Locations

```
my-course/
├── content/
│   └── essay.assignment/
│       ├── index.md
│       └── rubric.yaml          # Per-assignment rubric
│
├── rubrics/
│   ├── essay_rubric.yaml        # Shared rubric
│   ├── presentation_rubric.yaml
│   └── rows/
│       ├── writing_clarity.yaml # Reusable row
│       └── thesis.yaml
│
├── outcomes/
│   └── outcomes.yaml            # Outcome definitions
│
└── _course_metadata/
    └── outcome_map.json         # Outcome code -> Canvas ID
```

---

## Tips

✅ **Start simple** — Per-assignment rubrics work fine for small courses

✅ **Extract common rows** — If you copy-paste criteria, make it a shared row

✅ **Use outcome alignment** — Essential for accreditation reporting

✅ **Test with dry-run** — `zaphod sync rubrics --dry-run` shows what would change

---

## Troubleshooting

### "Outcome 'CLO1' not found in outcome_map.json"

1. Import your outcomes first: `zaphod sync outcomes`
2. Find the Canvas outcome IDs (in Canvas: Outcomes → click outcome → ID in URL)
3. Add them to `_course_metadata/outcome_map.json`

### Rubric not appearing on assignment

1. Make sure the assignment was published first: `zaphod sync`
2. Check that `rubric.yaml` is in the `.assignment/` folder
3. Run `zaphod sync rubrics`

### Changes not reflected in Canvas

Canvas rubrics that have been used for grading become locked. You may need to delete the Canvas rubric manually and re-sync.

---

## Next Steps

- [Outcomes](07-outcomes.md) — Define course learning outcomes
- [Assignments](02-assignments.md) — Create assignments
