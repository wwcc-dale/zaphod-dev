# Outcomes

> Outcomes (also called Learning Objectives or CLOs) define what students should know or be able to do after completing your course. Zaphod can sync these to Canvas.

---

## Creating Outcomes

Create an `outcomes/outcomes.yaml` file in your course:

```
my-course/
└── outcomes/
    └── outcomes.yaml
```

---

## Basic Structure

```yaml
# outcomes/outcomes.yaml
course_outcomes:
  - code: "CLO-1"
    title: "Critical Thinking"
    description: "Students will analyze problems using logical reasoning"
    mastery_points: 3
    ratings:
      - points: 4
        description: "Exceeds Expectations"
      - points: 3
        description: "Meets Expectations"
      - points: 2
        description: "Approaching Expectations"
      - points: 1
        description: "Below Expectations"
      - points: 0
        description: "No Evidence"

  - code: "CLO-2"
    title: "Communication"
    description: "Students will communicate ideas clearly in writing"
    mastery_points: 3
    ratings:
      - points: 4
        description: "Exceeds Expectations"
      - points: 3
        description: "Meets Expectations"
      - points: 2
        description: "Approaching Expectations"
      - points: 1
        description: "Below Expectations"
      - points: 0
        description: "No Evidence"
```

---

## Outcome Fields

| Field | Required | Description |
|-------|----------|-------------|
| `code` | Yes | Short identifier (CLO-1, ILO-COMM) |
| `title` | Yes | Outcome name |
| `description` | No | Detailed description |
| `vendor_guid` | No | Unique identifier (defaults to code if omitted) |
| `mastery_points` | No | Points needed for mastery |
| `ratings` | No | Proficiency scale |

**Note:** `vendor_guid` is used by Canvas to prevent duplicates. If you don't provide one, Zaphod uses the `code` value automatically.

---

## Rating Scales

Ratings define proficiency levels. List from highest to lowest points:

```yaml
ratings:
  - points: 4
    description: "Exemplary"
  - points: 3
    description: "Proficient"
  - points: 2
    description: "Developing"
  - points: 1
    description: "Beginning"
  - points: 0
    description: "Not Demonstrated"
```

**Common scales:**
- 4-point (0-4)
- 5-point (0-4 or 1-5)
- Custom institutional scales

---

## Complete Example

```yaml
# outcomes/outcomes.yaml
course_outcomes:
  # Program Learning Outcomes
  - code: "PLO-1"
    title: "Problem Solving"
    description: "Apply systematic approaches to solve complex problems"
    vendor_guid: "PLO-1"
    mastery_points: 3
    ratings:
      - points: 4
        description: "Exceeds - Solves complex, novel problems independently"
      - points: 3
        description: "Meets - Applies appropriate problem-solving strategies"
      - points: 2
        description: "Approaching - Applies strategies with guidance"
      - points: 1
        description: "Beginning - Limited problem-solving ability"
      - points: 0
        description: "No Evidence"

  - code: "PLO-2"
    title: "Technical Skills"
    description: "Demonstrate proficiency with industry-standard tools"
    vendor_guid: "PLO-2"
    mastery_points: 3
    ratings:
      - points: 4
        description: "Exceeds - Expert-level tool proficiency"
      - points: 3
        description: "Meets - Competent use of required tools"
      - points: 2
        description: "Approaching - Basic tool usage with some errors"
      - points: 1
        description: "Beginning - Minimal tool proficiency"
      - points: 0
        description: "No Evidence"

  # Course-Specific Outcomes
  - code: "CLO-1"
    title: "Data Analysis"
    description: "Analyze datasets using statistical methods"
    vendor_guid: "CLO-DATA-1"
    mastery_points: 3
    ratings:
      - points: 4
        description: "Exceeds Expectations"
      - points: 3
        description: "Meets Expectations"
      - points: 2
        description: "Approaching"
      - points: 1
        description: "Below Expectations"
      - points: 0
        description: "Not Demonstrated"
```

---

## How Syncing Works

When you run `zaphod sync`:

1. Zaphod reads `outcomes/outcomes.yaml`
2. Generates `outcomes/outcomes_import.csv` (Canvas format)
3. Imports the CSV into Canvas via the Outcomes API

**Note:** Outcomes sync is incremental — it only runs when `outcomes.yaml` has changed.

---

## Linking Outcomes to Assignments

Canvas allows you to align rubric criteria with outcomes. This is currently done in Canvas directly after outcomes are imported.

**Future feature:** Zaphod may support outcome alignment in rubric YAML.

---

## Tips

✅ **Use consistent codes** — CLO-1, CLO-2 or ILO-COMM-1

✅ **Keep descriptions brief** — Canvas has display limits

✅ **Match institutional scales** — Use your school's proficiency levels

✅ **Use vendor_guid for uniqueness** — Prevents duplicates on re-import

---

## Troubleshooting

### Outcomes Not Appearing

1. Check that `outcomes/outcomes.yaml` exists
2. Make sure the YAML is valid (proper indentation)
3. Run `zaphod sync` and look for outcome messages
4. Check Canvas → Outcomes to see if they were imported

### Duplicate Outcomes

If you see duplicates:
1. Delete outcomes in Canvas
2. Make sure each `vendor_guid` is unique
3. Re-run `zaphod sync`

---

## Next Steps

- [Rubrics](06-rubrics.md) — Align rubrics with outcomes
- [Assignments](02-assignments.md) — Create gradable content
