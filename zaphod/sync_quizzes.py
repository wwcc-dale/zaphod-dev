#!/usr/bin/env python3
"""
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

sync_quizzes.py

Syncs quiz folders (*.quiz/) to Canvas as first-class content items.

Quiz folders live alongside pages and assignments in the content directory:

    pages/                              # (or content/)
    Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ 01-Intro.module/                # Module folder (NEW pattern)
    Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ 01-welcome.page/
    Ã¢â€â€š   Ã¢â€â€š   Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ index.md
    Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ 02-homework.assignment/
    Ã¢â€â€š   Ã¢â€â€š   Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ index.md
    Ã¢â€â€š   Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ 03-pretest.quiz/            # Quiz as first-class citizen
    Ã¢â€â€š       Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ index.md
    Ã¢â€â€š
    quiz-banks/                         # Source pools (not deployed directly)
    Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ chapter1.bank.md
    Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ chapter2.bank.md

Module folder patterns:
- NEW: '05-Week 1.module' -> infers module "Week 1" (suffix, strips numeric prefix)
- LEGACY: 'module-Week 1' -> infers module "Week 1" (prefix)

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
- Module inference from directory structure (*.module/ or module-*/)
- Bank references by name (resolves to Canvas bank ID)
- Inline questions for simple quizzes
- Supports fenced code blocks in questions

Incremental behavior:
- If ZAPHOD_CHANGED_FILES is set, only changed quiz folders are processed
- Otherwise, all *.quiz/ folders are processed
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

import requests
import yaml
from canvasapi import Canvas

from zaphod.config_utils import get_course_id
from zaphod.canvas_client import get_canvas_credentials, make_canvas_api_obj
from zaphod.security_utils import get_rate_limiter, mask_sensitive


# ============================================================================
# Constants and Paths
# ============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
COURSE_ROOT = Path.cwd()
PAGES_DIR = COURSE_ROOT / "pages"
CONTENT_DIR = COURSE_ROOT / "content"  # Alternative name
QUIZ_BANKS_DIR = COURSE_ROOT / "quiz-banks"
METADATA_DIR = COURSE_ROOT / "_course_metadata"
QUIZ_CACHE_FILE = METADATA_DIR / "quiz_cache.json"

# SECURITY: Request timeout constants (connect, read) in seconds
REQUEST_TIMEOUT = (10, 30)


# ============================================================================
# Cache Helpers
# ============================================================================

def load_quiz_cache() -> Dict[str, Any]:
    """Load the quiz cache from disk."""
    if QUIZ_CACHE_FILE.exists():
        try:
            return json.loads(QUIZ_CACHE_FILE.read_text())
        except Exception as e:
            print(f"[quiz:warn] Failed to load cache: {e}")
    return {}


def save_quiz_cache(cache: Dict[str, Any]):
    """Save the quiz cache to disk."""
    try:
        METADATA_DIR.mkdir(parents=True, exist_ok=True)
        QUIZ_CACHE_FILE.write_text(json.dumps(cache, indent=2))
    except Exception as e:
        print(f"[quiz:warn] Failed to save cache: {e}")


def compute_quiz_hash(folder_path: Path) -> str:
    """Compute a hash of the quiz folder content."""
    index_path = folder_path / "index.md"
    if not index_path.exists():
        return ""
    
    content = index_path.read_text(encoding="utf-8")
    return hashlib.md5(content.encode()).hexdigest()[:12]


def quiz_needs_sync(folder_path: Path, cache: Dict[str, Any], existing_quizzes: Dict[str, Any], force: bool = False) -> Tuple[bool, str]:
    """
    Check if a quiz needs to be synced based on content hash AND Canvas existence.
    
    Returns (needs_sync, reason) tuple.
    """
    if force:
        return True, "forced"
    
    current_hash = compute_quiz_hash(folder_path)
    cache_key = str(folder_path.relative_to(COURSE_ROOT))
    
    cached = cache.get(cache_key, {})
    cached_hash = cached.get("hash")
    cached_canvas_id = cached.get("canvas_id")
    
    # If we have a cached canvas_id, verify the quiz still exists
    if cached_canvas_id and cached_hash == current_hash:
        # Check if quiz exists in Canvas by looking at existing_quizzes
        # We need to parse the folder to get the quiz name
        index_path = folder_path / "index.md"
        if index_path.exists():
            try:
                raw = index_path.read_text(encoding="utf-8")
                meta, _ = split_frontmatter_and_body(raw)
                quiz_name = meta.get("name") or meta.get("title") or folder_path.stem.replace(".quiz", "")
                
                if quiz_name not in existing_quizzes:
                    return True, "missing from Canvas"
            except Exception:
                pass
        
        return False, "unchanged"
    
    if cached_hash == current_hash:
        # Hash matches but no canvas_id - probably failed before
        return True, "no canvas_id in cache"
    
    return True, "content changed"


def update_quiz_cache(folder_path: Path, quiz_id: int, cache: Dict[str, Any]):
    """Update the cache with quiz info."""
    cache_key = str(folder_path.relative_to(COURSE_ROOT))
    cache[cache_key] = {
        "hash": compute_quiz_hash(folder_path),
        "canvas_id": quiz_id,
    }


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
    """
    Infer module from directory structure.
    
    Module folder patterns (in order of precedence):
    1. NEW: Ends with '.module' suffix (case-insensitive)
       - Numeric prefix (##-) is stripped for sorting purposes
       - Examples:
         - '05-Donkey Training.module' -> 'Donkey Training'
         - 'Week 1.module' -> 'Week 1'
    
    2. LEGACY: Starts with 'module-' prefix (case-insensitive)
       - Examples:
         - 'module-Week 1' -> 'Week 1'
         - 'module-Credit 1' -> 'Credit 1'
    """
    try:
        rel_path = folder_path.relative_to(PAGES_DIR)
    except ValueError:
        try:
            rel_path = folder_path.relative_to(CONTENT_DIR)
        except ValueError:
            return None
    
    for part in rel_path.parts:
        part_lower = part.lower()
        
        # NEW pattern: .module suffix
        if part_lower.endswith(".module"):
            # Strip the .module suffix
            module_name = part[:-7]  # len(".module") == 7
            
            # Strip numeric prefix (##- pattern) used for sorting
            if len(module_name) >= 3 and module_name[:2].isdigit() and module_name[2] == '-':
                module_name = module_name[3:]
            
            return module_name.strip()
        
        # LEGACY pattern: module- prefix (for backward compatibility)
        if part_lower.startswith("module-"):
            # Extract module name: "module-01-intro" -> "01-intro"
            return part[7:]  # Remove "module-" prefix
    
    return None


def parse_quiz_folder(folder_path: Path) -> Optional[QuizFolder]:
    """Parse a .quiz/ folder and return QuizFolder."""
    index_path = folder_path / "index.md"
    meta_path = folder_path / "meta.json"
    
    if not index_path.is_file():
        print(f"[quiz:warn] No index.md in {folder_path}")
        return None
    
    raw = index_path.read_text(encoding="utf-8")
    
    # Prefer meta.json for metadata (consistent with sync_modules.py)
    # Fall back to parsing index.md frontmatter if no meta.json
    meta = {}
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    
    # Parse index.md for body content (questions, description)
    lines = raw.splitlines()
    if not lines or not lines[0].strip().startswith("---"):
        body = raw
        fm_meta = {}
    else:
        end_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip().startswith("---"):
                end_idx = i
                break
        
        if end_idx is None:
            body = raw
            fm_meta = {}
        else:
            fm_text = "\n".join(lines[1:end_idx])
            body = "\n".join(lines[end_idx + 1:])
            fm_meta = yaml.safe_load(fm_text) or {}
            if not isinstance(fm_meta, dict):
                fm_meta = {}
    
    # Merge: meta.json takes precedence for name/modules, frontmatter for quiz-specific settings
    # This ensures sync_quizzes and sync_modules use the same name
    if not meta:
        meta = fm_meta
    else:
        # Copy quiz-specific settings from frontmatter if not in meta.json
        for key in ["question_groups", "time_limit", "shuffle_answers", "allowed_attempts", 
                    "show_correct_answers", "quiz_type", "points_per_question"]:
            if key in fm_meta and key not in meta:
                meta[key] = fm_meta[key]
    
    # Extract quiz name - meta.json has canonical name from frontmatter_to_meta.py
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
    
    # Infer module from path OR get from meta.json
    # meta.json modules take precedence (set by frontmatter_to_meta.py)
    module = None
    if meta.get("modules"):
        module = meta["modules"][0] if isinstance(meta["modules"], list) else meta["modules"]
    elif meta.get("module"):
        module = meta["module"]
    else:
        # Fall back to path inference
        module = infer_module_from_path(folder_path)
    
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

# Bank cache file path (shared with sync_banks.py)
BANK_CACHE_FILE = METADATA_DIR / "bank_cache.json"


def load_bank_cache() -> Dict[str, Any]:
    """Load the bank cache created by sync_banks.py."""
    if BANK_CACHE_FILE.exists():
        try:
            return json.loads(BANK_CACHE_FILE.read_text())
        except Exception:
            pass
    return {}


def get_question_banks(course_id: int, api_url: str, api_key: str) -> Dict[str, int]:
    """
    Get question banks mapping {name: id}.
    
    Note: Canvas does NOT have a public API for listing question banks.
    This function tries the API (in case some instances have it enabled),
    then falls back to providing guidance for manual bank_id specification.
    """
    url = f"{api_url}/api/v1/courses/{course_id}/question_banks"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    banks = {}
    api_failed = False
    
    try:
        get_rate_limiter().wait_if_needed()  # SECURITY: Rate limiting
        resp = requests.get(url, headers=headers, params={"per_page": 100}, timeout=REQUEST_TIMEOUT)
        get_rate_limiter().check_response_headers(dict(resp.headers))
        
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                for bank in data:
                    title = bank.get("title", "")
                    bank_id = bank.get("id")
                    if title and bank_id:
                        banks[title] = bank_id
                return banks
        else:
            api_failed = True
                    
    except Exception:
        api_failed = True
    
    if api_failed:
        # Canvas doesn't have a public question_banks API
        # Load bank names from sync_banks.py cache for reference
        bank_cache = load_bank_cache()
        if bank_cache:
            print(f"[quiz:info] Canvas question_banks API not available")
            print(f"[quiz:info] Found {len(bank_cache)} bank(s) in local cache")
            print(f"[quiz:hint] To link quizzes to banks, find bank IDs in Canvas:")
            print(f"[quiz:hint]   Course > Quizzes > Manage Question Banks > click bank > ID in URL")
            print(f"[quiz:hint]   Then add 'bank_id: <id>' to quiz frontmatter question_groups")
        else:
            print(f"[quiz:info] Question bank lookup not available (Canvas API limitation)")
    
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
    """Delete all questions and question groups from a quiz."""
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # Delete question groups FIRST (before questions)
    groups_url = f"{api_url}/api/v1/courses/{course_id}/quizzes/{quiz.id}/groups"
    try:
        get_rate_limiter().wait_if_needed()  # SECURITY: Rate limiting
        resp = requests.get(groups_url, headers=headers, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            groups = resp.json()
            if groups:
                print(f"[quiz]   Deleting {len(groups)} question group(s)...")
            for g in groups:
                g_id = g.get("id")
                if g_id:
                    del_url = f"{groups_url}/{g_id}"
                    get_rate_limiter().wait_if_needed()  # SECURITY: Rate limiting
                    del_resp = requests.delete(del_url, headers=headers, timeout=REQUEST_TIMEOUT)
                    if del_resp.status_code not in (200, 204):
                        print(f"[quiz:warn] Failed to delete group {g_id}: HTTP {del_resp.status_code}")
    except Exception as e:
        print(f"[quiz:warn] Error deleting question groups: {e}")
    
    # Then delete questions
    questions_url = f"{api_url}/api/v1/courses/{course_id}/quizzes/{quiz.id}/questions"
    try:
        get_rate_limiter().wait_if_needed()  # SECURITY: Rate limiting
        resp = requests.get(questions_url, headers=headers, params={"per_page": 100}, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            questions = resp.json()
            if questions:
                print(f"[quiz]   Deleting {len(questions)} question(s)...")
            for q in questions:
                q_id = q.get("id")
                if q_id:
                    del_url = f"{questions_url}/{q_id}"
                    get_rate_limiter().wait_if_needed()  # SECURITY: Rate limiting
                    requests.delete(del_url, headers=headers, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        print(f"[quiz:warn] Error deleting questions: {e}")


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
            
            get_rate_limiter().wait_if_needed()  # SECURITY: Rate limiting
            resp = requests.post(groups_url, headers=headers, json=group_payload, timeout=REQUEST_TIMEOUT)
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force sync even if content hasn't changed"
    )
    args = parser.parse_args()
    
    course_id = get_course_id()
    if not course_id:
        raise SystemExit("COURSE_ID is not set")
    
    course_id_int = int(course_id)
    api_url, api_key = get_canvas_credentials()  # From canvas_client
    canvas = Canvas(api_url, api_key)
    course = canvas.get_course(course_id_int)
    
    # Load quiz cache
    quiz_cache = load_quiz_cache()
    
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
    skipped_count = 0
    for folder in quiz_folders:
        print(f"[quiz] === {folder.name} ===")
        
        # Check if quiz needs sync (based on content hash AND Canvas existence)
        needs_sync, reason = quiz_needs_sync(folder, quiz_cache, existing_quizzes, force=args.force)
        if not needs_sync:
            print(f"[quiz]   ({reason}, skipping)")
            skipped_count += 1
            continue
        
        if reason != "forced" and reason != "content changed":
            print(f"[quiz]   Reason: {reason}")
        
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
                # Update cache with new hash
                update_quiz_cache(folder, quiz.id, quiz_cache)
                success_count += 1
        
        print()
    
    # Save cache
    if not args.dry_run:
        save_quiz_cache(quiz_cache)
    
    print(f"[quiz] Completed: {success_count} synced, {skipped_count} unchanged")


if __name__ == "__main__":
    main()
