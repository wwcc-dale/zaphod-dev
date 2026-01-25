#!/usr/bin/env python3

"""
scaffold_course.py (Zaphod)

Create a minimal Zaphod-ready course skeleton in the current directory.

- Creates pages/, modules/, outcomes/, quiz-banks/, assets/, _course_metadata/,
  rubrics/, rubrics/rows/
- Seeds example content folders with index.md and frontmatter
- Seeds a shared rubric and a reusable rubric row snippet
- Writes modules/module_order.yaml and outcomes/outcomes.yaml
- Does not touch existing files unless --force is specified for some writes
"""

from __future__ import annotations

import argparse
from pathlib import Path
import textwrap


COURSE_ROOT = Path.cwd()

PAGES_DIR = COURSE_ROOT / "pages"
MODULES_DIR = COURSE_ROOT / "modules"
OUTCOMES_DIR = COURSE_ROOT / "outcomes"
QUIZ_BANKS_DIR = COURSE_ROOT / "quiz-banks"
ASSETS_DIR = COURSE_ROOT / "assets"
METADATA_DIR = COURSE_ROOT / "_course_metadata"
RUBRICS_DIR = COURSE_ROOT / "rubrics"
RUBRIC_ROWS_DIR = RUBRICS_DIR / "rows"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_file(path: Path, content: str, force: bool = False) -> None:
    if path.exists() and not force:
        print(f"[scaffold] SKIP existing file: {path.relative_to(COURSE_ROOT)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"[scaffold] WROTE {path.relative_to(COURSE_ROOT)}")


PAGES_WELCOME = textwrap.dedent(
    """\
    ---
    type: page
    name: Welcome
    modules:
      - Start Here
    indent: 0
    ---
    
    # Welcome to the course
    
    This is your first Zaphod-managed Canvas page.
    
    You can edit this file at `pages/welcome.page/index.md`.
    """
)

PAGES_SAMPLE_ASSIGNMENT = textwrap.dedent(
    """\
    ---
    type: assignment
    name: Sample Assignment
    points_possible: 10
    submission_types:
      - online_upload
    modules:
      - Week 1
    indent: 0
    ---
    
    # Sample assignment
    
    Replace this content with your own assignment instructions.
    """
)

# Assignment-local rubric wrapper that uses a shared rubric
PAGES_SAMPLE_RUBRIC = textwrap.dedent(
    """\
    # This assignment uses the shared course-level rubric defined at rubrics/essay_rubric.yaml.
    use_rubric: "essay_rubric"
    """
)

MODULE_ORDER_YAML = textwrap.dedent(
    """\
    # Order of modules as they should appear in Canvas
    # Add, remove, or reorder as needed.
    - Start Here
    - Week 1
    - Week 2
    """
)

OUTCOMES_YAML = textwrap.dedent(
    """\
    # Course learning outcomes for this course
    # See sync_clo_via_csv.py for how these are imported into Canvas.
    course_outcomes:
      - code: CLO1
        title: Example outcome
        description: Students can describe how to work with a text-to-Canvas workflow.
        vendor_guid: CLO1
        mastery_points: 3
        ratings:
          - points: 3
            description: Exceeds expectations
          - points: 2
            description: Meets expectations
          - points: 1
            description: Below expectations
    """
)

DEFAULTS_JSON = textwrap.dedent(
    """\
    {
      "course_id": "REPLACE_ME"
    }
    """
)

QUIZ_SAMPLE_BANK = textwrap.dedent(
    """\
    ---
    name: Sample Question Bank
    points_per_question: 1
    ---
    
    1. Example multiple choice question
    a) Wrong answer
    *b) Correct answer (marked with *)
    c) Distractor
    d) Distractor
    
    1. Another question (markdown-style numbering - all can be "1.")
    Select all prime numbers:
    [*] 2
    [*] 3
    [ ] 4
    [*] 5
    
    1. Short answer question
    * correct answer
    * alternate correct answer
    
    1. Essay question
    Write a paragraph about your learning goals.
    ####
    """
)

QUIZ_SAMPLE_QUIZ = textwrap.dedent(
    """\
    ---
    name: Sample Quiz
    type: quiz
    quiz_type: assignment
    time_limit: null
    shuffle_answers: true
    allowed_attempts: 1
    modules:
      - Week 1
    published: false
    
    # Pull questions from banks
    banks:
      - name: "sample.bank"
        pick: 2
    ---
    
    # Sample Quiz
    
    This quiz pulls questions from the sample question bank.
    
    You can also add inline questions below:
    
    1. What is the capital of France?
    a) London
    *b) Paris
    c) Berlin
    d) Madrid
    """
)

# Shared course-level rubric (rubrics/essay_rubric.yaml)
RUBRIC_SHARED_ESSAY = textwrap.dedent(
    """\
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

      - "{{rubric_row:writing_clarity}}"
    """
)

# Shared row snippet (rubrics/rows/writing_clarity.yaml)
RUBRIC_ROW_WRITING_CLARITY = textwrap.dedent(
    """\
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
    """
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scaffold a Zaphod course in the current directory"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing template files where present",
    )
    args = parser.parse_args()

    print(f"[scaffold] COURSE_ROOT = {COURSE_ROOT}")

    # Directories (now including rubrics and rubric rows)
    for d in [
        PAGES_DIR,
        MODULES_DIR,
        OUTCOMES_DIR,
        QUIZ_BANKS_DIR,
        ASSETS_DIR,
        METADATA_DIR,
        RUBRICS_DIR,
        RUBRIC_ROWS_DIR,
    ]:
        ensure_dir(d)

    # Example page and assignment
    write_file(PAGES_DIR / "welcome.page" / "index.md", PAGES_WELCOME, force=args.force)
    write_file(
        PAGES_DIR / "sample-assignment.assignment" / "index.md",
        PAGES_SAMPLE_ASSIGNMENT,
        force=args.force,
    )

    # Sample assignment rubric wrapper, pointing at shared rubric
    write_file(
        PAGES_DIR / "sample-assignment.assignment" / "rubric.yaml",
        PAGES_SAMPLE_RUBRIC,
        force=args.force,
    )

    # Module order
    write_file(MODULES_DIR / "module_order.yaml", MODULE_ORDER_YAML, force=args.force)

    # Outcomes
    write_file(OUTCOMES_DIR / "outcomes.yaml", OUTCOMES_YAML, force=args.force)

    # Metadata defaults (never overwrite, to avoid clobbering course_id)
    write_file(METADATA_DIR / "defaults.json", DEFAULTS_JSON, force=False)

    # Sample question bank (new .bank.md format)
    write_file(QUIZ_BANKS_DIR / "sample.bank.md", QUIZ_SAMPLE_BANK, force=args.force)

    # Sample quiz (uses question bank)
    write_file(PAGES_DIR / "sample-quiz.quiz" / "index.md", QUIZ_SAMPLE_QUIZ, force=args.force)

    # Shared rubric and row snippet
    write_file(RUBRICS_DIR / "essay_rubric.yaml", RUBRIC_SHARED_ESSAY, force=args.force)
    write_file(
        RUBRIC_ROWS_DIR / "writing_clarity.yaml",
        RUBRIC_ROW_WRITING_CLARITY,
        force=args.force,
    )

    print("[scaffold] Done. You can now edit the scaffolded files and run watch_and_publish.py.")


if __name__ == "__main__":
    main()
