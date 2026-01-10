#!/usr/bin/env python3
"""
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

sync_quiz_banks.py (Zaphod v0.2+)

For the *current* course (cwd):

- Reads all *.quiz.txt files under quiz-banks/
- Optional YAML frontmatter at top (between --- lines) defines quiz metadata:
    ---
    title: "Week 1 Reading Quiz"
    points_per_question: 2
    shuffle_answers: true
    published: false
    topics: ["TOPIC-ARG-1"]
    outcomes: ["ILO-COMM-1"]
    ---

- Body uses NYIT Canvas Exam Converter-style text format:
    * Multiple choice: a) / *c) for correct
    * Multiple answers: [ ] / [*]
    * Short answer: * answer
    * Essay: ####
    * File-upload: ^^^^
    * True/False: *a) True / b) False

- Creates a Classic Quiz per file via /courses/:course_id/quizzes
- Adds each parsed question via Quiz Questions API.

Incremental behavior:
- If ZAPHOD_CHANGED_FILES is set, only *.quiz.txt files listed there
  (under quiz-banks/) are processed.
- If ZAPHOD_CHANGED_FILES is unset/empty, all *.quiz.txt files are processed
  (existing full behavior).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from config_utils import get_course_id
import yaml  # pip install pyyaml
from canvasapi import Canvas
from errors import (
    quiz_parsing_error,
    ContentValidationError,
)


# Shared layout paths
SCRIPT_DIR = Path(__file__).resolve().parent          # .../courses/zaphod
SHARED_ROOT = SCRIPT_DIR.parent                       # .../courses/zaphod
COURSES_ROOT = SHARED_ROOT.parent                     # .../courses
COURSE_ROOT = Path.cwd()                              # current course, e.g. .../courses/test
QUIZ_BANKS_DIR = COURSE_ROOT / "quiz-banks"


# ---------- Canvas helpers ----------

def load_canvas() -> Canvas:
    cred_path = os.environ.get("CANVAS_CREDENTIAL_FILE")
    if not cred_path:
        raise SystemExit("CANVAS_CREDENTIAL_FILE is not set")

    cred_file = Path(cred_path)
    if not cred_file.is_file():
        raise SystemExit(f"CANVAS_CREDENTIAL_FILE does not exist: {cred_file}")

    ns: Dict[str, Any] = {}
    exec(cred_file.read_text(encoding="utf-8"), ns)
    try:
        api_key = ns["API_KEY"]
        api_url = ns["API_URL"]
    except KeyError as e:
        raise SystemExit(f"Credentials file must define API_KEY and API_URL. Missing: {e}")

    return Canvas(api_url, api_key)


def create_quiz(course, title: str, meta: Dict[str, Any]):
    """
    Create a Classic Quiz using metadata + sensible defaults.
    """
    description = meta.get("description", "")
    quiz_type = meta.get("quiz_type", "assignment")  # graded quiz
    published = bool(meta.get("published", False))
    shuffle_answers = bool(meta.get("shuffle_answers", True))
    time_limit = meta.get("time_limit")  # optional minutes

    quiz_params: Dict[str, Any] = {
        "title": title,
        "description": description,
        "quiz_type": quiz_type,
        "published": published,
        "shuffle_answers": shuffle_answers,
    }
    if time_limit is not None:
        quiz_params["time_limit"] = int(time_limit)

    quiz = course.create_quiz(quiz=quiz_params)
    print(f"[quiz] Created quiz '{quiz.title}' (id={quiz.id})")
    return quiz


def add_question(course_id: int, quiz, question_payload: Dict[str, Any], canvas: Canvas):
    resp = quiz.create_question(question=question_payload)
    print(f"[quiz:q] added {question_payload.get('question_type')}: {question_payload.get('question_name')}")
    return resp


# ---------- Frontmatter handling ----------

def split_frontmatter_and_body(raw: str) -> Tuple[Dict[str, Any], str]:
    """
    If file starts with YAML frontmatter (--- ... ---), parse it.
    Otherwise return empty meta and whole text as body.
    """
    lines = raw.splitlines()
    if not lines or not lines[0].strip().startswith("---"):
        return {}, raw

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip().startswith("---"):
            end_idx = i
            break

    if end_idx is None:
        return {}, raw

    fm_text = "\n".join(lines[1:end_idx])
    body_text = "\n".join(lines[end_idx + 1 :])

    meta = yaml.safe_load(fm_text) or {}
    if not isinstance(meta, dict):
        meta = {}

    return meta, body_text


# ---------- NYIT-style quiz parsing ----------

@dataclass
class AnswerOption:
    text: str
    is_correct: bool = False


@dataclass
class ParsedQuestion:
    number: int
    stem: str
    qtype: str
    answers: List[AnswerOption] = field(default_factory=list)
    points: float = 1.0


QUESTION_HEADER_RE = re.compile(r"^\s*(\d+)\.\s+(.*\S)\s*$")
MC_OPTION_RE = re.compile(r"^\s*([a-z])\)\s+(.*\S)\s*$")
MC_OPTION_CORRECT_RE = re.compile(r"^\s*\*([a-z])\)\s+(.*\S)\s*$")
MULTI_ANSWER_RE = re.compile(r"^\s*\[(\*|\s)\]\s*(.*\S)\s*$")
SHORT_ANSWER_RE = re.compile(r"^\s*\*\s+(.+\S)\s*$")
TF_TRUE_RE = re.compile(r"^\s*\*a\)\s*True\s*$", re.IGNORECASE)
TF_FALSE_RE = re.compile(r"^\s*\*b\)\s*False\s*$", re.IGNORECASE)


def split_questions(raw: str) -> List[List[str]]:
    """
    Split quiz text into question blocks, separated by blank line(s).
    """
    lines = raw.splitlines()
    blocks: List[List[str]] = []
    cur: List[str] = []

    def push():
        nonlocal cur, blocks
        if cur and any(line.strip() for line in cur):
            blocks.append(cur)
        cur = []

    for line in lines:
        if not line.strip():
            push()
        else:
            cur.append(line)
    push()
    return blocks


def detect_qtype(block: List[str]) -> str:
    body = "\n".join(block)
    if "####" in body:
        return "essay"
    if "^^^^" in body:
        return "file_upload"

    for line in block:
        if MULTI_ANSWER_RE.match(line):
            return "multiple_answers"

    if any(SHORT_ANSWER_RE.match(line) for line in block):
        return "short_answer"

    has_true = any(re.search(r"a\)\s*True", line, re.IGNORECASE) for line in block)
    has_false = any(re.search(r"b\)\s*False", line, re.IGNORECASE) for line in block)
    if has_true and has_false:
        return "true_false"

    return "multiple_choice"


def parse_question_block(block: List[str], default_points: float) -> ParsedQuestion:
    if not block:
        raise ContentValidationError(
            message="Empty question block encountered",
            suggestion="Check quiz file for blank sections between questions"
        )

    m = QUESTION_HEADER_RE.match(block[0])
    if not m:
        # BETTER ERROR: Show the problematic line
        raise quiz_parsing_error(
            quiz_file=Path("current_quiz.txt"),  # Would be passed in
            line_number=1,
            line_content=block[0],
            cause=ValueError("Question must start with number and period, e.g., '1. Question text'")
        )
    
    number = int(m.group(1))
    stem_first_line = m.group(2).strip()
    rest = block[1:]

    qtype = detect_qtype(block)
    stem_lines: List[str] = [stem_first_line]
    answers: List[AnswerOption] = []

    if qtype == "multiple_choice":
        in_opts = False
        for line in rest:
            if MC_OPTION_CORRECT_RE.match(line) or MC_OPTION_RE.match(line):
                in_opts = True
                m_corr = MC_OPTION_CORRECT_RE.match(line)
                if m_corr:
                    _, text = m_corr.groups()
                    answers.append(AnswerOption(text=text.strip(), is_correct=True))
                else:
                    m_opt = MC_OPTION_RE.match(line)
                    if m_opt:
                        _, text = m_opt.groups()
                        answers.append(AnswerOption(text=text.strip(), is_correct=False))
            else:
                if not in_opts:
                    stem_lines.append(line)

        if not any(ans.is_correct for ans in answers):
            # BETTER ERROR: Specific validation failure
            raise ContentValidationError(
                message=f"Question {number}: No correct answer marked",
                suggestion=(
                    "Mark the correct answer with an asterisk:\n"
                    "  *b) Correct answer\n\n"
                    "Question text:\n"
                    f"  {stem_first_line}"
                ),
                context={
                    "question_number": number,
                    "question_type": "multiple_choice",
                    "answers_found": len(answers)
                }
            )

        
    elif qtype == "multiple_answers":
        in_opts = False
        for line in rest:
            mm = MULTI_ANSWER_RE.match(line)
            if mm:
                in_opts = True
                star, text = mm.groups()
                answers.append(AnswerOption(text=text.strip(), is_correct=(star == "*")))
            else:
                if not in_opts:
                    stem_lines.append(line)
        if not any(ans.is_correct for ans in answers):
            raise ValueError(f"Multiple-answers question {number} has no [*] options")
    elif qtype == "short_answer":
        for line in rest:
            m_sa = SHORT_ANSWER_RE.match(line)
            if m_sa:
                answers.append(AnswerOption(text=m_sa.group(1).strip(), is_correct=True))
            else:
                stem_lines.append(line)
        if not answers:
            raise ValueError(f"Short-answer question {number} has no '* answer' lines")
    elif qtype == "essay":
        for line in rest:
            if line.strip() == "####":
                continue
            stem_lines.append(line)
    elif qtype == "file_upload":
        for line in rest:
            if line.strip() == "^^^^":
                continue
            stem_lines.append(line)
    elif qtype == "true_false":
        correct_is_true: Optional[bool] = None
        for line in rest:
            if TF_TRUE_RE.match(line):
                correct_is_true = True
            elif TF_FALSE_RE.match(line):
                correct_is_true = False
            else:
                stem_lines.append(line)
        if correct_is_true is None:
            raise ValueError(f"True/False question {number} has no '*a) True' or '*b) False'")
        answers = [
            AnswerOption(text="True", is_correct=bool(correct_is_true)),
            AnswerOption(text="False", is_correct=not bool(correct_is_true)),
        ]
    else:
        raise ValueError(f"Unsupported question type: {qtype}")

    stem = "\n".join(line.strip() for line in stem_lines if line.strip())
    return ParsedQuestion(number=number, stem=stem, qtype=qtype, answers=answers, points=default_points)


def parse_quiz_text(raw: str, default_points: float) -> List[ParsedQuestion]:
    blocks = split_questions(raw)
    questions: List[ParsedQuestion] = []
    for block in blocks:
        try:
            q = parse_question_block(block, default_points=default_points)
            questions.append(q)
        except Exception as e:
            print(f"[quiz:err] Failed to parse question block: {e}")
    return questions


# ---------- Map parsed questions to Canvas payloads ----------

def to_canvas_question_payload(pq: ParsedQuestion) -> Dict[str, Any]:
    qtext_html = f"<p>{pq.stem}</p>"

    if pq.qtype == "multiple_choice":
        answers = []
        for i, ans in enumerate(pq.answers):
            answers.append(
                {
                    "answer_text": ans.text,
                    "answer_weight": 100 if ans.is_correct else 0,
                    "answer_position": i + 1,
                }
            )
        return {
            "question_name": f"{pq.stem}",
            "question_text": qtext_html,
            "question_type": "multiple_choice_question",
            "points_possible": pq.points,
            "answers": answers,
        }

    if pq.qtype == "multiple_answers":
        correct_count = max(1, sum(1 for a in pq.answers if a.is_correct))
        per_correct = 100.0 / correct_count
        answers = []
        for i, ans in enumerate(pq.answers):
            weight = per_correct if ans.is_correct else 0.0
            answers.append(
                {
                    "answer_text": ans.text,
                    "answer_weight": weight,
                    "answer_position": i + 1,
                }
            )
        return {
            "question_name": f"{pq.stem}",
            "question_text": qtext_html,
            "question_type": "multiple_answers_question",
            "points_possible": pq.points,
            "answers": answers,
        }

    if pq.qtype == "short_answer":
        answers = []
        for i, ans in enumerate(pq.answers):
            answers.append(
                {
                    "answer_text": ans.text,
                    "answer_weight": 100,
                    "answer_position": i + 1,
                }
            )
        return {
            "question_name": f"{pq.stem}",
            "question_text": qtext_html,
            "question_type": "short_answer_question",
            "points_possible": pq.points,
            "answers": answers,
        }

    if pq.qtype == "essay":
        return {
            "question_name": f"{pq.stem}",
            "question_text": qtext_html,
            "question_type": "essay_question",
            "points_possible": pq.points,
        }

    if pq.qtype == "file_upload":
        return {
            "question_name": f"{pq.stem}",
            "question_text": qtext_html,
            "question_type": "file_upload_question",
            "points_possible": pq.points,
        }

    if pq.qtype == "true_false":
        answers = []
        for i, ans in enumerate(pq.answers):
            answers.append(
                {
                    "answer_text": ans.text,
                    "answer_weight": 100 if ans.is_correct else 0,
                    "answer_position": i + 1,
                }
            )
        return {
            "question_name": f"{pq.stem}",
            "question_text": qtext_html,
            "question_type": "true_false_question",
            "points_possible": pq.points,
            "answers": answers,
        }

    raise ValueError(f"Unsupported question type for payload: {pq.qtype}")


# ---------- Incremental helpers ----------

def get_changed_files() -> List[Path]:
    raw = os.environ.get("ZAPHOD_CHANGED_FILES", "").strip()
    if not raw:
        return []
    return [Path(p) for p in raw.splitlines() if p.strip()]


def iter_quiz_files_full() -> List[Path]:
    if not QUIZ_BANKS_DIR.exists():
        return []
    return sorted(QUIZ_BANKS_DIR.glob("*.quiz.txt"))


def iter_quiz_files_incremental(changed_files: List[Path]) -> List[Path]:
    """
    From the changed files list, return the *.quiz.txt files under quiz-banks/
    that should be processed.
    """
    result: List[Path] = []
    seen: set[Path] = set()

    for p in changed_files:
        if p.suffix != ".txt" or not str(p).endswith(".quiz.txt"):
            continue
        try:
            rel = p.relative_to(COURSE_ROOT)
        except ValueError:
            continue
        if not rel.parts or rel.parts[0] != "quiz-banks":
            continue
        # Normalize to the actual path on disk (in case of case differences)
        path = QUIZ_BANKS_DIR / rel.name if rel.parent == Path("quiz-banks") else COURSE_ROOT / rel
        if path.is_file() and path not in seen:
            seen.add(path)
            result.append(path)

    return sorted(result)


# ---------- Main workflow ----------

def process_quiz_file(course, canvas: Canvas, path: Path, course_id: int):
    print(f"[quiz:file] {path.name}")
    raw = path.read_text(encoding="utf-8")

    meta, body = split_frontmatter_and_body(raw)
    default_points = float(meta.get("points_per_question", 1.0))

    questions = parse_quiz_text(body, default_points=default_points)
    if not questions:
        print(f"[quiz:warn] No questions parsed from {path.name}")
        return

    title = meta.get("title") or path.stem
    quiz = create_quiz(course, title=title, meta=meta)

    for pq in questions:
        payload = to_canvas_question_payload(pq)
        add_question(course_id, quiz, payload, canvas)


def main():
    course_id = get_course_id()
    if not course_id:
        raise SystemExit("COURSE_ID is not set")

    course_id_int = int(course_id)
    canvas = load_canvas()
    course = canvas.get_course(course_id_int)

    changed_files = get_changed_files()
    if changed_files:
        quiz_files = iter_quiz_files_incremental(changed_files)
        if not quiz_files:
            print(f"[quiz] No changed *.quiz.txt files under {QUIZ_BANKS_DIR}; nothing to do.")
            return
    else:
        quiz_files = iter_quiz_files_full()
        if not quiz_files:
            print(f"[quiz] No *.quiz.txt files under {QUIZ_BANKS_DIR}")
            return

    for path in quiz_files:
        process_quiz_file(course, canvas, path, course_id_int)
        print()


if __name__ == "__main__":
    main()
