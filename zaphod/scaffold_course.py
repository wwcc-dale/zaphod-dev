#!/usr/bin/env python3

"""
scaffold_course.py (Zaphod)

Create a minimal Zaphod-ready course skeleton in the current directory.

Creates:
- content/           Content folders (.page, .assignment, .quiz, etc.)
- shared/            Shared variables and includes
- modules/           Module ordering configuration
- outcomes/          Learning outcomes definitions
- quiz-banks/        Question bank files
- assets/            Shared media files
- rubrics/           Shared rubrics and reusable rows
- _course_metadata/  Internal state and cache files

Seeds example content with index.md and frontmatter.
Does not touch existing files unless --force is specified.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import textwrap


COURSE_ROOT = Path.cwd()

# NEW: Use content/ instead of pages/
CONTENT_DIR = COURSE_ROOT / "content"
SHARED_DIR = COURSE_ROOT / "shared"
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


# =============================================================================
# Sample Content
# =============================================================================

WELCOME_PAGE = textwrap.dedent(
    """\
    ---
    type: page
    name: Welcome
    modules:
      - Start Here
    indent: 0
    ---
    
    # Welcome to {{var:course_code}}
    
    Welcome to **{{var:course_title}}**, taught by {{var:instructor_name}}.
    
    This is your first Zaphod-managed Canvas page.
    
    ## Contact Information
    
    {{include:contact_info}}
    
    ## Getting Help
    
    If you have questions, please email {{var:instructor_email}}.
    """
)

SAMPLE_ASSIGNMENT = textwrap.dedent(
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
    
    # Sample Assignment
    
    Replace this content with your own assignment instructions.
    
    ## Late Policy
    
    {{include:late_policy}}
    """
)

# Assignment-local rubric wrapper that uses a shared rubric
SAMPLE_RUBRIC = textwrap.dedent(
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

# =============================================================================
# NEW: Shared folder content
# =============================================================================

SHARED_VARIABLES = textwrap.dedent(
    """\
    # Course-wide variables
    # These are available in all pages using {{var:variable_name}}
    # Page frontmatter can override any of these values.
    
    # Course information
    course_code: "CS 101"
    course_title: "Introduction to Computer Science"
    semester: "Spring 2026"
    
    # Instructor information
    instructor_name: "Dr. Ada Lovelace"
    instructor_email: "lovelace@university.edu"
    instructor_office: "Engineering Building, Room 142"
    office_hours: "Tuesday/Thursday 2-4pm"
    
    # TA information (optional)
    # ta_name: "Charles Babbage"
    # ta_email: "babbage@university.edu"
    
    # Common phrases
    late_penalty: "10% per day, up to 3 days"
    """
)

SHARED_CONTACT_INFO = textwrap.dedent(
    """\
    **Instructor:** {{var:instructor_name}}  
    **Email:** {{var:instructor_email}}  
    **Office:** {{var:instructor_office}}  
    **Office Hours:** {{var:office_hours}}
    """
)

SHARED_LATE_POLICY = textwrap.dedent(
    """\
    Late submissions will receive a penalty of {{var:late_penalty}}. 
    After 3 days, late submissions will not be accepted without prior arrangement.
    
    If you need an extension, please contact the instructor **before** the due date.
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
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Use legacy folder names (pages/ instead of content/)",
    )
    args = parser.parse_args()

    print(f"[scaffold] COURSE_ROOT = {COURSE_ROOT}")

    # Determine content directory name
    content_dir = COURSE_ROOT / "pages" if args.legacy else CONTENT_DIR
    content_name = "pages" if args.legacy else "content"
    print(f"[scaffold] Using {content_name}/ for content")

    # Create directories
    for d in [
        content_dir,
        SHARED_DIR,
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
    write_file(content_dir / "welcome.page" / "index.md", WELCOME_PAGE, force=args.force)
    write_file(
        content_dir / "sample-assignment.assignment" / "index.md",
        SAMPLE_ASSIGNMENT,
        force=args.force,
    )

    # Sample assignment rubric wrapper, pointing at shared rubric
    write_file(
        content_dir / "sample-assignment.assignment" / "rubric.yaml",
        SAMPLE_RUBRIC,
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
    write_file(content_dir / "sample-quiz.quiz" / "index.md", QUIZ_SAMPLE_QUIZ, force=args.force)

    # Shared rubric and row snippet
    write_file(RUBRICS_DIR / "essay_rubric.yaml", RUBRIC_SHARED_ESSAY, force=args.force)
    write_file(
        RUBRIC_ROWS_DIR / "writing_clarity.yaml",
        RUBRIC_ROW_WRITING_CLARITY,
        force=args.force,
    )

    # NEW: Shared variables and includes
    write_file(SHARED_DIR / "variables.yaml", SHARED_VARIABLES, force=args.force)
    write_file(SHARED_DIR / "contact_info.md", SHARED_CONTACT_INFO, force=args.force)
    write_file(SHARED_DIR / "late_policy.md", SHARED_LATE_POLICY, force=args.force)

    print()
    print("[scaffold] Done!")
    print()
    print("Next steps:")
    print("  1. Edit shared/variables.yaml with your course details")
    print("  2. Edit the sample content in content/")
    print("  3. Run: zaphod sync --dry-run")
    print("  4. Run: zaphod sync")


if __name__ == "__main__":
    main()
