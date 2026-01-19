## Rubrics in Zaphod

Rubrics in Zaphod are plain‑text descriptions of how you grade an assignment. Instead of clicking around in the Canvas rubric editor, you define the rows, points, and rating levels in plain text. It can be as simple as one small file that lives next to the assignment.

When the rubric sync runs, Zaphod builds or updates the Canvas rubric for you and attaches it to the right assignment.

You can store rubrics you'd like to reuse in multiple places in a `rubrics` folder **assignment‑local** rubrics and **course‑level** shared rubrics/rows, but the basic mental model stays the same: you author everything in plain text and Zaphod wires Canvas up for you.[3]

## Where rubric files live

Each assignment can still have its own rubric file next to `index.md`:

```text
example-course/
  pages/
    essay-1.assignment/
      index.md
      rubric.yaml
    project-plan.assignment/
      index.md
      rubric.yaml
```

- The `.assignment` folder is the assignment itself.  
- `rubric.yaml` (or `rubric.yml` / `rubric.json`) in that folder describes the rubric for that assignment.[3]
- If there is no rubric file, Zaphod leaves the Canvas assignment rubric‑free.[3]

In addition, a course can define **shared rubrics and reusable rows** at the top level:

```text
example-course/
  rubrics/
    essay_rubric.yaml        # full shared rubric
    rows/
      writing_clarity.yaml   # reusable row snippet
```

- `rubrics/*.yaml` are full rubric specs that multiple assignments can reuse.  
- `rubrics/rows/*.yaml` are one‑or‑more full rows (criteria) that can be included inside any rubric.[3]

## Basic Rubrics

Simple per‑assignment rubrics look like this:

```yaml
# pages/essay-1.assignment/rubric.yaml
title: Essay 1 Rubric
criteria:
  - description: Thesis and focus
    long_description: Clarity and strength of the main argument.
    points: 10
    ratings:
      - description: Excellent
        long_description: Clear, original thesis; fully focused throughout.
        points: 10
      - description: Satisfactory
        long_description: Thesis is present but may be vague or unevenly supported.
        points: 8
      - description: Needs improvement
        long_description: Thesis is missing, unclear, or not supported.
        points: 5

  - description: Organization
    long_description: Logical structure, paragraphing, and flow.
    points: 10
    ratings:
      - description: Excellent
        long_description: Clear structure, smooth transitions, easy to follow.
        points: 10
      - description: Satisfactory
        long_description: Mostly organized; some awkward transitions or jumps.
        points: 8
      - description: Needs improvement
        long_description: Hard to follow; ideas feel scattered.
        points: 5
```

Zaphod turns this into a Canvas rubric with that title, two rows, the given point values, and rating levels.

## Course‑level shared rubrics

Instead of defining a full rubric in every assignment folder, you can define a **shared** rubric once and point assignments at it.

Shared rubrics look like any other rubric:

```yaml
# rubrics/essay_rubric.yaml
title: "Essay Rubric"
free_form_criterion_comments: false

criteria:
  - description: "Thesis and focus"
    long_description: "Clarity and strength of the main argument."
    points: 10
    ratings:
      - description: "Excellent"
        long_description: "Clear, original thesis; fully focused throughout."
        points: 10
      - description: "Satisfactory"
        long_description: "Thesis is present but may be vague or unevenly supported."
        points: 8
      - description: "Needs improvement"
        long_description: "Thesis is missing, unclear, or not supported."
        points: 5

  - description: "Organization"
    long_description: "Logical structure, paragraphing, and flow."
    points: 10
    ratings:
      - description: "Excellent"
        long_description: "Clear structure, smooth transitions, easy to follow."
        points: 10
      - description: "Satisfactory"
        long_description: "Mostly organized; some awkward transitions or jumps."
        points: 8
      - description: "Needs improvement"
        long_description: "Hard to follow; ideas feel scattered."
        points: 5
```

Assignment that **uses** this shared rubric has the following in it's rubric file:

```yaml
# pages/sample-assignment.assignment/rubric.yaml
use_rubric: "essay_rubric"
```

`use_rubric: "essay_rubric"` tells Zaphod to ignore local details and instead load `rubrics/essay_rubric.yaml` as the spec.

## Reusable rubric rows

For rows you repeat often (for example, writing clarity, professionalism), you can store them once in the `rubrics/rows` folder and include them by reference.

A Rubric Row:

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
      long_description: "Generally clear; minor errors do not impede understanding."
      points: 8
    - description: "Major issues"
      long_description: "Frequent errors or disorganization impede understanding."
      points: 5
```

Rubric that **includes** that reusable row:

```yaml
title: "Essay 2 Rubric"
free_form_criterion_comments: false

criteria:
  - description: "Use of sources"
    long_description: "Quality and integration of sources."
    points: 10
    ratings:
      - description: "Excellent"
        points: 10
      - description: "Adequate"
        points: 8
      - description: "Weak"
        points: 5
# The row below is shared
  - "{{rubric_row:writing_clarity}}"

association:
  purpose: "grading"
  use_for_grading: true
```

- Any `criteria` entry that is exactly a string like `{{rubric_row:writing_clarity}}` is expanded before sending to Canvas: Zaphod loads `rubrics/rows/writing_clarity.yaml` and inlines all of its criteria rows in that position.
- Those rows can be aligned or unaligned; any extra fields (such as `outcome_code`) travel with the row and are preserved in the Canvas payload.

## Connecting rubrics to outcomes (optional)

Outcome‑aligned rows still use the same shape, with an extra field such as `outcome_code`:

```yaml
criteria:
  - description: "Thesis and focus"
    points: 10
    outcome_code: CLO1
    ratings:
      - description: "Exceeds expectations"
        points: 10
      - description: "Meets expectations"
        points: 8
      - description: "Developing"
        points: 6
      - description: "Beginning"
        points: 4
```

You can place `outcome_code` either directly in the assignment rubric or inside a shared rubric/row snippet; Zaphod reads the expanded criteria list and then constructs the Canvas form fields from each criterion.

## How rubrics get into Canvas

The sync behavior is unchanged at a high level:

1. In each `.assignment` folder, Zaphod looks for `rubric.yaml` / `rubric.yml` / `rubric.json`.[3]
2. If that file has `use_rubric: NAME`, it loads `rubrics/NAME.(yaml|yml|json)`; otherwise it uses the rubric as defined in the file.  
3. It expands any `{{rubric_row:identifier}}` entries using `rubrics/rows/identifier.(yaml|yml|json)`.  
4. It builds the Canvas rubric payload from the final `title` + `criteria` and POSTs it to the course rubrics endpoint, associating it with the assignment and marking it for grading unless you override that.

### Don't repeat yourself

- You can keep authoring per‑assignment rubrics right next to `index.md`.  
- You can centralize common rubrics and rows under `rubrics/` and `rubrics/rows/` and reference them from assignments to avoid duplication.