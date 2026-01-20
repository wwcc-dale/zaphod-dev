#!/usr/bin/env python3
"""
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

sync_quizzes.py

Syncs quiz folders (*.quiz/) to Canvas as first-class content items.

Quiz folders live alongside pages and assignments in the content directory:

    pages/                              # (or content/)
    ├── module-01-intro/
    │   ├── 01-welcome.page/
    │   │   └── index.md
    │   ├── 02-homework.assignment/
    │   │   └── index.md
    │   └── 03-pretest.quiz/           # ← Quiz as first-class citizen
    │       └── index.md
    │
    quiz-banks/                         # Source pools (not deployed directly)
    ├── chapter1.bank.md
    └── chapter2.bank.md

Quiz index.md format:

    ---
    name: "Week 1 Quiz"
    time_limit: 30                      # Optional, minutes
    shuffle_answers: true               # Default: true
    published: false
    
    # Option A: Draw from question banks
    question_groups:
      - bank: "chapter1.bank"           # References quiz-banks/chapter1.bank.md
        pick: 5                         # Pick 5 random questions
        points_per_question: 2
      - bank: "chapter2.bank"
        pick: 5
        points_per_question: 2
    
    # Option B: Inline questions (set this flag)
    # inline_questions: true
    ---
    
    Optional description/instructions shown at top of quiz.
    
    # If inline_questions: true, questions follow the description:
    
    1. What is 2+2?
    *a) 4
    b) 5

Features:
- Module inference from directory structure (module-*/path/quiz.quiz/)
- Bank references by name (resolves to Canvas bank ID)
- Inline questions for simple quizzes
- Supports fenced code blocks in questions

Incremental behavior:
- If ZAPHOD_CHANGED_FILES is set, only changed quiz folders are processed
- Otherwise, all *.quiz/ folders are processed
"""

from __future__ import annotations

import html
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

import requests
import yaml
from canvasapi import Canvas

from zaphod.config_utils import get_course_id


# ============================================================================
# Constants and Paths
# ============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
COURSE_ROOT = Path.cwd()
PAGES_DIR = COURSE_ROOT / "pages"
CONTENT_DIR = COURSE_ROOT / "content"  # Alternative name
QUIZ_BANKS_DIR = COURSE_ROOT / "quiz-banks"


# ============================================================================
# Data Classes
# ============================================================================

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


@dataclass
class QuestionGroup:
    """A group of questions drawn from a bank"""
    bank_name: Optional[str]  # Name for display/lookup
    bank_id: Optional[int]    # Direct Canvas bank ID (preferred)
    pick: int
    points_per_question: float


@dataclass
class QuizFolder:
    """Represents a quiz folder with its configuration"""
    folder_path: Path
    name: str
    description: str
    meta: Dict[str, Any]
    question_groups: List[QuestionGroup]
    inline_questions: List[ParsedQuestion]
    module: Optional[str] = None


# ============================================================================
# Canvas Client Setup
# ============================================================================

def load_canvas() -> Tuple[Canvas, str, str]:
    """Load Canvas API client and return (canvas, api_url, api_key)."""
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

    return Canvas(api_url, api_key), api_url.rstrip("/"), api_key


# ============================================================================
# Question Parsing (for inline questions)
# ============================================================================

QUESTION_HEADER_RE = re.compile(r"^\s*(\d+)\.\s+(.*\S)\s*$")
MC_OPTION_RE = re.compile(r"^\s*([a-z])\)\s+(.*\S)\s*$")
MC_OPTION_CORRECT_RE = re.compile(r"^\s*\*([a-z])\)\s+(.*\S)\s*$")
MULTI_ANSWER_RE = re.compile(r"^\s*\[(\*|\s)\]\s*(.*\S)\s*$")
SHORT_ANSWER_RE = re.compile(r"^\s*\*\s+(.+\S)\s*$")
TF_TRUE_RE = re.compile(r"^\s*\*a\)\s*True\s*$", re.IGNORECASE)
TF_FALSE_RE = re.compile(r"^\s*\*b\)\s*False\s*$", re.IGNORECASE)
INLINE_CODE_RE = re.compile(r"`([^`]+)`")


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return html.escape(text, quote=True)


def stem_to_html(stem: str) -> str:
    """Convert question stem to HTML with code block support."""
    lines = stem.split('\n')
    result_parts = []
    current_para = []
    in_code_block = False
    code_block_lines = []
    code_lang = ""
    
    def flush_paragraph():
        nonlocal current_para
        if current_para:
            text = ' '.join(current_para)
            parts = []
            last_end = 0
            for match in INLINE_CODE_RE.finditer(text):
                parts.append(escape_html(text[last_end:match.start()]))
                parts.append(f'<code>{escape_html(match.group(1))}</code>')
                last_end = match.end()
            parts.append(escape_html(text[last_end:]))
            text = ''.join(parts)
            result_parts.append(f"<p>{text}</p>")
            current_para = []
    
    for line in lines:
        stripped = line.strip()
        
        if stripped.startswith("```") or stripped.startswith("~~~"):
            if not in_code_block:
                flush_paragraph()
                in_code_block = True
                code_lang = stripped[3:].strip()
                code_block_lines = []
            else:
                in_code_block = False
                code_content = escape_html('\n'.join(code_block_lines))
                if code_lang:
                    result_parts.append(
                        f'<pre><code class="language-{escape_html(code_lang)}">{code_content}</code></pre>'
                    )
                else:
                    result_parts.append(f'<pre><code>{code_content}</code></pre>')
                code_block_lines = []
                code_lang = ""
        elif in_code_block:
            code_block_lines.append(line)
        elif not stripped:
            flush_paragraph()
        else:
            current_para.append(line)
    
    flush_paragraph()
    
    if in_code_block and code_block_lines:
        code_content = escape_html('\n'.join(code_block_lines))
        result_parts.append(f'<pre><code>{code_content}</code></pre>')
    
    return '\n'.join(result_parts)


def answer_to_html(text: str) -> str:
    """Convert answer text to HTML."""
    parts = []
    last_end = 0
    for match in INLINE_CODE_RE.finditer(text):
        parts.append(escape_html(text[last_end:match.start()]))
        parts.append(f'<code>{escape_html(match.group(1))}</code>')
        last_end = match.end()
    parts.append(escape_html(text[last_end:]))
    return ''.join(parts)


def split_questions(raw: str) -> List[List[str]]:
    """Split text into question blocks, preserving code blocks."""
    lines = raw.splitlines()
    blocks: List[List[str]] = []
    cur: List[str] = []
    in_code_block = False

    def push():
        nonlocal cur, blocks
        if cur and any(line.strip() for line in cur):
            blocks.append(cur)
        cur = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            cur.append(line)
        elif not line.strip() and not in_code_block:
            push()
        else:
            cur.append(line)
    push()
    return blocks


def detect_qtype(block: List[str]) -> str:
    """Detect question type from block content."""
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


def parse_question_block(block: List[str], default_points: float) -> Optional[ParsedQuestion]:
    """Parse a single question block."""
    if not block:
        return None

    m = QUESTION_HEADER_RE.match(block[0])
    if not m:
        return None

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
                    answers.append(AnswerOption(text=m_corr.group(2).strip(), is_correct=True))
                else:
                    m_opt = MC_OPTION_RE.match(line)
                    if m_opt:
                        answers.append(AnswerOption(text=m_opt.group(2).strip(), is_correct=False))
            else:
                if not in_opts:
                    stem_lines.append(line)

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

    elif qtype == "short_answer":
        for line in rest:
            m_sa = SHORT_ANSWER_RE.match(line)
            if m_sa:
                answers.append(AnswerOption(text=m_sa.group(1).strip(), is_correct=True))
            else:
                stem_lines.append(line)

    elif qtype == "essay":
        for line in rest:
            if line.strip() != "####":
                stem_lines.append(line)

    elif qtype == "file_upload":
        for line in rest:
            if line.strip() != "^^^^":
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
            return None
        answers = [
            AnswerOption(text="True", is_correct=bool(correct_is_true)),
            AnswerOption(text="False", is_correct=not bool(correct_is_true)),
        ]

    stem = "\n".join(line for line in stem_lines)
    return ParsedQuestion(number=number, stem=stem, qtype=qtype, answers=answers, points=default_points)


def parse_inline_questions(body: str, default_points: float) -> List[ParsedQuestion]:
    """Parse inline questions from body text."""
    blocks = split_questions(body)
    questions: List[ParsedQuestion] = []
    
    for block in blocks:
        q = parse_question_block(block, default_points)
        if q:
            questions.append(q)
    
    return questions


# ============================================================================
# Quiz Folder Parsing
# ============================================================================

def infer_module_from_path(folder_path: Path) -> Optional[str]:
    """Infer module from directory structure (module-* pattern)."""
    try:
        rel_path = folder_path.relative_to(PAGES_DIR)
    except ValueError:
        try:
            rel_path = folder_path.relative_to(CONTENT_DIR)
        except ValueError:
            return None
    
    for part in rel_path.parts:
        if part.startswith("module-"):
            # Extract module name: "module-01-intro" -> "01-intro"
            return part[7:]  # Remove "module-" prefix
    
    return None


def parse_quiz_folder(folder_path: Path) -> Optional[QuizFolder]:
    """Parse a .quiz/ folder and return QuizFolder."""
    index_path = folder_path / "index.md"
    
    if not index_path.is_file():
        print(f"[quiz:warn] No index.md in {folder_path}")
        return None
    
    raw = index_path.read_text(encoding="utf-8")
    
    # Parse frontmatter
    lines = raw.splitlines()
    if not lines or not lines[0].strip().startswith("---"):
        meta = {}
        body = raw
    else:
        end_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip().startswith("---"):
                end_idx = i
                break
        
        if end_idx is None:
            meta = {}
            body = raw
        else:
            fm_text = "\n".join(lines[1:end_idx])
            body = "\n".join(lines[end_idx + 1:])
            meta = yaml.safe_load(fm_text) or {}
            if not isinstance(meta, dict):
                meta = {}
    
    # Extract quiz name
    name = meta.get("name") or meta.get("title") or folder_path.stem.replace(".quiz", "")
    
    # Parse question groups
    question_groups: List[QuestionGroup] = []
    for group_meta in meta.get("question_groups", []):
        bank_name = group_meta.get("bank")
        bank_id = group_meta.get("bank_id")  # Direct Canvas bank ID
        
        if bank_name or bank_id:
            question_groups.append(QuestionGroup(
                bank_name=bank_name,
                bank_id=int(bank_id) if bank_id else None,
                pick=int(group_meta.get("pick", 1)),
                points_per_question=float(group_meta.get("points_per_question", 1.0)),
            ))
    
    # Parse inline questions - check for numbered questions in body
    inline_questions: List[ParsedQuestion] = []
    if body.strip():
        # Always try to parse inline questions if body has content
        default_points = float(meta.get("points_per_question", 1.0))
        inline_questions = parse_inline_questions(body, default_points)
    
    # Description is any body text before the first question
    description = ""
    if body.strip():
        # Extract description (text before first numbered question)
        desc_lines = []
        for line in body.splitlines():
            if QUESTION_HEADER_RE.match(line):
                break
            desc_lines.append(line)
        description = "\n".join(desc_lines).strip()
    
    # Infer module from path
    module = infer_module_from_path(folder_path)
    if not module and meta.get("module"):
        module = meta["module"]
    
    return QuizFolder(
        folder_path=folder_path,
        name=name,
        description=description,
        meta=meta,
        question_groups=question_groups,
        inline_questions=inline_questions,
        module=module,
    )


# ============================================================================
# Canvas Quiz Creation
# ============================================================================

def get_question_banks(course_id: int, api_url: str, api_key: str) -> Dict[str, int]:
    """Get all question banks and return {name: id} mapping."""
    url = f"{api_url}/api/v1/courses/{course_id}/question_banks"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    banks = {}
    try:
        # Paginate through all banks
        page_url = url
        while page_url:
            resp = requests.get(page_url, headers=headers, params={"per_page": 100})
            
            if resp.status_code != 200:
                print(f"[quiz:warn] Failed to fetch question banks (HTTP {resp.status_code})")
                print(f"[quiz:warn]   Response: {resp.text[:200]}")
                break
            
            data = resp.json()
            if not isinstance(data, list):
                print(f"[quiz:warn] Unexpected response format for question banks")
                break
            
            for bank in data:
                # Canvas uses "title" for question banks
                title = bank.get("title", "")
                bank_id = bank.get("id")
                if title and bank_id:
                    banks[title] = bank_id
            
            # Check for next page in Link header
            page_url = None
            link_header = resp.headers.get("Link", "")
            for link in link_header.split(","):
                if 'rel="next"' in link:
                    page_url = link.split(";")[0].strip("<> ")
                    break
                    
    except Exception as e:
        print(f"[quiz:warn] Could not fetch question banks: {e}")
    
    return banks


def get_existing_quizzes(course) -> Dict[str, Any]:
    """Get all existing quizzes and return {title: quiz} mapping."""
    quizzes = {}
    try:
        for quiz in course.get_quizzes():
            quizzes[quiz.title] = quiz
    except Exception as e:
        print(f"[quiz:warn] Could not fetch existing quizzes: {e}")
    return quizzes


def delete_quiz_questions(quiz, api_url: str, api_key: str, course_id: int):
    """Delete all questions from a quiz."""
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # Get all questions
    questions_url = f"{api_url}/api/v1/courses/{course_id}/quizzes/{quiz.id}/questions"
    try:
        resp = requests.get(questions_url, headers=headers, params={"per_page": 100})
        if resp.status_code == 200:
            questions = resp.json()
            for q in questions:
                q_id = q.get("id")
                if q_id:
                    del_url = f"{questions_url}/{q_id}"
                    requests.delete(del_url, headers=headers)
    except Exception as e:
        print(f"[quiz:warn] Error deleting questions: {e}")
    
    # Delete question groups
    groups_url = f"{api_url}/api/v1/courses/{course_id}/quizzes/{quiz.id}/groups"
    try:
        resp = requests.get(groups_url, headers=headers)
        if resp.status_code == 200:
            groups = resp.json()
            for g in groups:
                g_id = g.get("id")
                if g_id:
                    del_url = f"{groups_url}/{g_id}"
                    requests.delete(del_url, headers=headers)
    except Exception as e:
        print(f"[quiz:warn] Error deleting question groups: {e}")


def to_canvas_question_payload(pq: ParsedQuestion) -> Dict[str, Any]:
    """Convert ParsedQuestion to Canvas API payload."""
    qtext_html = stem_to_html(pq.stem)
    name_text = pq.stem.split('\n')[0][:80]

    if pq.qtype == "multiple_choice":
        answers = []
        for i, ans in enumerate(pq.answers):
            answers.append({
                "answer_html": answer_to_html(ans.text),
                "answer_text": ans.text,
                "answer_weight": 100 if ans.is_correct else 0,
                "answer_position": i + 1,
            })
        return {
            "question_name": name_text,
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
            answers.append({
                "answer_html": answer_to_html(ans.text),
                "answer_text": ans.text,
                "answer_weight": weight,
                "answer_position": i + 1,
            })
        return {
            "question_name": name_text,
            "question_text": qtext_html,
            "question_type": "multiple_answers_question",
            "points_possible": pq.points,
            "answers": answers,
        }

    if pq.qtype == "short_answer":
        answers = [{"answer_text": ans.text, "answer_weight": 100, "answer_position": i + 1}
                   for i, ans in enumerate(pq.answers)]
        return {
            "question_name": name_text,
            "question_text": qtext_html,
            "question_type": "short_answer_question",
            "points_possible": pq.points,
            "answers": answers,
        }

    if pq.qtype == "essay":
        return {
            "question_name": name_text,
            "question_text": qtext_html,
            "question_type": "essay_question",
            "points_possible": pq.points,
        }

    if pq.qtype == "file_upload":
        return {
            "question_name": name_text,
            "question_text": qtext_html,
            "question_type": "file_upload_question",
            "points_possible": pq.points,
        }

    if pq.qtype == "true_false":
        answers = [{"answer_text": ans.text, "answer_weight": 100 if ans.is_correct else 0, "answer_position": i + 1}
                   for i, ans in enumerate(pq.answers)]
        return {
            "question_name": name_text,
            "question_text": qtext_html,
            "question_type": "true_false_question",
            "points_possible": pq.points,
            "answers": answers,
        }

    raise ValueError(f"Unsupported question type: {pq.qtype}")


def create_canvas_quiz(
    course,
    quiz_folder: QuizFolder,
    bank_map: Dict[str, int],
    existing_quizzes: Dict[str, Any],
    api_url: str,
    api_key: str,
    course_id: int,
) -> Optional[Any]:
    """Create or update a Canvas quiz from a QuizFolder."""
    
    # Check if quiz already exists
    existing_quiz = existing_quizzes.get(quiz_folder.name)
    
    # Build quiz parameters
    quiz_params: Dict[str, Any] = {
        "title": quiz_folder.name,
        "description": quiz_folder.description,
        "quiz_type": quiz_folder.meta.get("quiz_type", "assignment"),
        "published": bool(quiz_folder.meta.get("published", False)),
        "shuffle_answers": bool(quiz_folder.meta.get("shuffle_answers", True)),
    }
    
    if quiz_folder.meta.get("time_limit"):
        quiz_params["time_limit"] = int(quiz_folder.meta["time_limit"])
    
    if quiz_folder.meta.get("allowed_attempts"):
        quiz_params["allowed_attempts"] = int(quiz_folder.meta["allowed_attempts"])
    
    if existing_quiz:
        # Update existing quiz
        print(f"[quiz] Updating existing quiz '{existing_quiz.title}' (id={existing_quiz.id})")
        
        # Update quiz settings
        existing_quiz.edit(quiz=quiz_params)
        
        # Delete old questions and groups
        delete_quiz_questions(existing_quiz, api_url, api_key, course_id)
        print(f"[quiz]   Cleared existing questions")
        
        quiz = existing_quiz
    else:
        # Create new quiz
        quiz = course.create_quiz(quiz=quiz_params)
        print(f"[quiz] Created quiz '{quiz.title}' (id={quiz.id})")
    
    # Add question groups (bank references)
    if quiz_folder.question_groups:
        headers = {"Authorization": f"Bearer {api_key}"}
        groups_url = f"{api_url}/api/v1/courses/{course_id}/quizzes/{quiz.id}/groups"
        
        for group in quiz_folder.question_groups:
            # Use bank_id directly if provided, otherwise try to resolve by name
            resolved_bank_id = group.bank_id
            bank_name = group.bank_name  # Could be None
            
            if not resolved_bank_id and bank_name:
                # Try to resolve bank name to ID (will likely fail without API access)
                resolved_bank_id = bank_map.get(bank_name)
                
                if not resolved_bank_id and bank_name.endswith(".md"):
                    bank_name_no_ext = bank_name[:-3]
                    resolved_bank_id = bank_map.get(bank_name_no_ext)
                
                if not resolved_bank_id:
                    base_name = bank_name.replace(".bank.md", "").replace(".bank", "")
                    for canvas_name, cid in bank_map.items():
                        if canvas_name.startswith(base_name):
                            resolved_bank_id = cid
                            break
            
            if not resolved_bank_id:
                display_name = bank_name or f"bank_id={group.bank_id}"
                print(f"[quiz:warn] Bank '{display_name}' not found, skipping group")
                print(f"[quiz:hint] Use 'bank_id: <id>' in frontmatter. Find IDs in Canvas UI:")
                print(f"[quiz:hint]   Course > Settings > Question Banks > click bank > ID in URL")
                continue
            
            group_name = bank_name or f"Bank {resolved_bank_id}"
            
            group_payload = {
                "quiz_groups": [{
                    "name": f"Questions from {group_name}",
                    "pick_count": group.pick,
                    "question_points": group.points_per_question,
                    "assessment_question_bank_id": resolved_bank_id,
                }]
            }
            
            resp = requests.post(groups_url, headers=headers, json=group_payload)
            if resp.status_code in (200, 201):
                print(f"[quiz:group] Added group: pick {group.pick} from '{group_name}' (bank_id={resolved_bank_id}) @ {group.points_per_question} pts each")
            else:
                print(f"[quiz:warn] Failed to create group for bank '{group.bank_name}'")
    
    # Add inline questions
    if quiz_folder.inline_questions:
        for pq in quiz_folder.inline_questions:
            payload = to_canvas_question_payload(pq)
            quiz.create_question(question=payload)
            print(f"[quiz:q] added {payload.get('question_type')}: {payload.get('question_name', '')[:50]}...")
    
    return quiz


# ============================================================================
# File Discovery
# ============================================================================

def get_changed_files() -> List[Path]:
    """Get list of changed files from environment."""
    raw = os.environ.get("ZAPHOD_CHANGED_FILES", "").strip()
    if not raw:
        return []
    return [Path(p) for p in raw.splitlines() if p.strip()]


def get_content_root() -> Path:
    """Get the content root directory (pages/ or content/)."""
    if CONTENT_DIR.exists():
        return CONTENT_DIR
    return PAGES_DIR


def iter_quiz_folders_full() -> List[Path]:
    """Get all .quiz/ folders."""
    content_root = get_content_root()
    if not content_root.exists():
        return []
    
    folders = []
    for folder in content_root.rglob("*.quiz"):
        if folder.is_dir() and (folder / "index.md").is_file():
            folders.append(folder)
    
    return sorted(folders)


def iter_quiz_folders_incremental(changed_files: List[Path]) -> List[Path]:
    """Get quiz folders affected by changed files."""
    content_root = get_content_root()
    folders: set[Path] = set()
    
    for p in changed_files:
        # Check if this file is inside a .quiz/ folder
        for parent in [p] + list(p.parents):
            if parent.name.endswith(".quiz") and parent.is_dir():
                folders.add(parent)
                break
    
    return sorted(folders)


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Sync quiz folders (*.quiz/) to Canvas"
    )
    parser.add_argument(
        "--folder", "-f",
        type=Path,
        help="Sync a specific quiz folder"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Parse folders but don't create quizzes in Canvas"
    )
    args = parser.parse_args()
    
    course_id = get_course_id()
    if not course_id:
        raise SystemExit("COURSE_ID is not set")
    
    course_id_int = int(course_id)
    canvas, api_url, api_key = load_canvas()
    course = canvas.get_course(course_id_int)
    
    # Determine which folders to process
    if args.folder:
        quiz_folders = [args.folder]
    else:
        changed_files = get_changed_files()
        if changed_files:
            quiz_folders = iter_quiz_folders_incremental(changed_files)
            if not quiz_folders:
                print(f"[quiz] No changed quiz folders; nothing to do.")
                return
        else:
            quiz_folders = iter_quiz_folders_full()
            if not quiz_folders:
                print(f"[quiz] No quiz folders (*.quiz/) found")
                return
    
    print(f"[quiz] Processing {len(quiz_folders)} quiz folder(s)")
    print(f"[quiz] Course ID: {course_id_int}")
    print()
    
    # Load question banks for group references
    bank_map = get_question_banks(course_id_int, api_url, api_key)
    if bank_map:
        print(f"[quiz] Found {len(bank_map)} question bank(s) in Canvas")
    else:
        print(f"[quiz] No question banks found (bank references will fail)")
    
    # Load existing quizzes for upsert
    existing_quizzes = get_existing_quizzes(course)
    if existing_quizzes:
        print(f"[quiz] Found {len(existing_quizzes)} existing quiz(es) in Canvas")
    
    success_count = 0
    for folder in quiz_folders:
        print(f"[quiz] === {folder.name} ===")
        
        quiz_data = parse_quiz_folder(folder)
        if not quiz_data:
            print(f"[quiz:warn] Could not parse {folder.name}")
            continue
        
        print(f"[quiz]   Name: {quiz_data.name}")
        if quiz_data.module:
            print(f"[quiz]   Module: {quiz_data.module}")
        if quiz_data.question_groups:
            print(f"[quiz]   Question groups: {len(quiz_data.question_groups)}")
            for g in quiz_data.question_groups:
                if g.bank_id:
                    print(f"[quiz]     - bank_id={g.bank_id}: pick {g.pick} @ {g.points_per_question} pts")
                else:
                    print(f"[quiz]     - {g.bank_name}: pick {g.pick} @ {g.points_per_question} pts")
        if quiz_data.inline_questions:
            print(f"[quiz]   Inline questions: {len(quiz_data.inline_questions)}")
        
        if args.dry_run:
            if quiz_data.name in existing_quizzes:
                print(f"[quiz]   (dry-run) Would update existing quiz '{quiz_data.name}'")
            else:
                print(f"[quiz]   (dry-run) Would create quiz '{quiz_data.name}'")
            success_count += 1
        else:
            quiz = create_canvas_quiz(course, quiz_data, bank_map, existing_quizzes, api_url, api_key, course_id_int)
            if quiz:
                success_count += 1
        
        print()
    
    print(f"[quiz] Completed: {success_count}/{len(quiz_folders)} quiz(es)")


if __name__ == "__main__":
    main()
