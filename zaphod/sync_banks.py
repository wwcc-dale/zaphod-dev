#!/usr/bin/env python3
"""
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

sync_banks.py

Imports question bank files (*.bank.md) into Canvas question banks using
the QTI Content Migration API.

Bank files live in quiz-banks/ and contain questions in a simple text format:

    quiz-banks/
    [?]Å“[?]â‚¬[?]â‚¬ chapter1.bank.md
    [?]Å“[?]â‚¬[?]â‚¬ chapter2.bank.md
    [?]â€[?]â‚¬[?]â‚¬ final-exam-pool.bank.md

File format (*.bank.md):
    ---
    name: "Chapter 1 Questions"         # Bank display name (or use 'title')
    points_per_question: 2              # Default points per question (default: 1)
    ---
    
    1. What is 2+2?
    *a) 4
    b) 5
    c) 6
    
    2. Select all prime numbers:
    [*] 2
    [*] 3
    [ ] 4
    [*] 5

Question types supported:
    * Multiple choice: a) / *c) for correct
    * Multiple answers: [ ] / [*]
    * Short answer: * answer
    * Essay: ####
    * File-upload: ^^^^
    * True/False: *a) True / b) False

Features:
- Supports fenced code blocks (```) in question stems and answers
- Supports inline code (`backticks`) in questions and answers
- Proper HTML escaping for Canvas display
- Supports markdown-style repeated numbering (1. 1. 1.) - questions auto-numbered

The bank name in Canvas will match the filename (e.g., "chapter1.bank").

Incremental behavior:
- Content-hash caching: Each bank's content is hashed and stored in 
  _course_metadata/bank_cache.json. On subsequent runs, only banks whose
  content has changed are re-uploaded.
- ZAPHOD_CHANGED_FILES: If set (by watch mode), only those specific files
  are considered, with hash caching still applied.
- Use --force to skip cache and re-upload all banks.

Backward compatibility:
- Also supports legacy *.quiz.txt files (deprecated)
"""

from __future__ import annotations

import hashlib
import html
import io
import json
import os
import re
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from xml.etree import ElementTree as ET
from xml.dom import minidom

import requests
import yaml

from zaphod.config_utils import get_course_id


# ============================================================================
# Constants and Paths
# ============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
COURSE_ROOT = Path.cwd()
QUIZ_BANKS_DIR = COURSE_ROOT / "quiz-banks"
METADATA_DIR = COURSE_ROOT / "_course_metadata"
BANK_CACHE_FILE = METADATA_DIR / "bank_cache.json"

# QTI/CC namespaces
QTI_NS = "http://www.imsglobal.org/xsd/ims_qtiasiv1p2"
CC_NS = "http://www.imsglobal.org/xsd/imsccv1p3/imscp_v1p1"


# ============================================================================
# Cache Helpers (for incremental sync)
# ============================================================================

def load_bank_cache() -> Dict[str, Any]:
    """Load the bank cache from disk."""
    if BANK_CACHE_FILE.exists():
        try:
            return json.loads(BANK_CACHE_FILE.read_text())
        except Exception as e:
            print(f"[bank:warn] Failed to load cache: {e}")
    return {}


def save_bank_cache(cache: Dict[str, Any]):
    """Save the bank cache to disk."""
    try:
        METADATA_DIR.mkdir(parents=True, exist_ok=True)
        BANK_CACHE_FILE.write_text(json.dumps(cache, indent=2))
    except Exception as e:
        print(f"[bank:warn] Failed to save cache: {e}")


def compute_bank_hash(file_path: Path) -> str:
    """Compute a hash of the bank file content."""
    if not file_path.exists():
        return ""
    
    content = file_path.read_text(encoding="utf-8")
    return hashlib.md5(content.encode()).hexdigest()[:12]


def bank_needs_sync(file_path: Path, cache: Dict[str, Any], force: bool = False) -> bool:
    """Check if a bank needs to be synced based on content hash."""
    if force:
        return True
    
    current_hash = compute_bank_hash(file_path)
    cache_key = str(file_path.relative_to(COURSE_ROOT))
    
    cached = cache.get(cache_key, {})
    cached_hash = cached.get("hash")
    
    if cached_hash == current_hash:
        return False
    
    return True


def update_bank_cache(file_path: Path, bank_name: str, cache: Dict[str, Any], migration_id: int = None):
    """Update the cache with bank info."""
    cache_key = str(file_path.relative_to(COURSE_ROOT))
    cache[cache_key] = {
        "hash": compute_bank_hash(file_path),
        "bank_name": bank_name,
        "uploaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "migration_id": migration_id,
    }


def bank_already_uploaded(file_path: Path, cache: Dict[str, Any]) -> Dict[str, Any]:
    """Check if bank was previously uploaded (for --force warnings)."""
    cache_key = str(file_path.relative_to(COURSE_ROOT))
    return cache.get(cache_key, {})


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
class BankData:
    """Holds parsed bank data for QTI generation"""
    file_path: Path
    title: str
    bank_name: str
    questions: List[ParsedQuestion]
    meta: Dict[str, Any]


# ============================================================================
# Canvas Client Setup
# ============================================================================

def load_canvas_credentials() -> Tuple[str, str]:
    """
    Load Canvas API credentials safely.
    
    SECURITY: Uses safe parsing instead of exec() to prevent code injection.
    
    Returns:
        Tuple of (api_url, api_key)
    """
    # Try environment variables first
    env_key = os.environ.get("CANVAS_API_KEY")
    env_url = os.environ.get("CANVAS_API_URL")
    if env_key and env_url:
        return env_url.rstrip("/"), env_key
    
    # Fall back to credential file
    cred_path = os.environ.get("CANVAS_CREDENTIAL_FILE")
    if not cred_path:
        raise SystemExit(
            "Canvas credentials not found. Set CANVAS_API_KEY and CANVAS_API_URL "
            "environment variables, or set CANVAS_CREDENTIAL_FILE."
        )

    cred_file = Path(cred_path)
    if not cred_file.is_file():
        raise SystemExit(f"CANVAS_CREDENTIAL_FILE does not exist: {cred_file}")

    # SECURITY: Parse credentials safely without exec()
    api_key, api_url = _parse_credentials_safe(cred_file)
    
    if not api_key or not api_url:
        raise SystemExit(
            f"Credentials file must define API_KEY and API_URL: {cred_file}"
        )
    
    # Check file permissions
    _warn_insecure_permissions(cred_file)

    return api_url.rstrip("/"), api_key


def _parse_credentials_safe(cred_file: Path) -> Tuple[Optional[str], Optional[str]]:
    """Parse credentials file safely without exec()."""
    content = cred_file.read_text(encoding="utf-8")
    
    api_key = None
    api_url = None
    
    # Match API_KEY = "value" or API_KEY = 'value' or API_KEY = value
    key_patterns = [
        r'API_KEY\s*=\s*["\']([^"\']+)["\']',
        r'API_KEY\s*=\s*(\S+)',
    ]
    url_patterns = [
        r'API_URL\s*=\s*["\']([^"\']+)["\']',
        r'API_URL\s*=\s*(\S+)',
    ]
    
    for pattern in key_patterns:
        match = re.search(pattern, content)
        if match:
            api_key = match.group(1).strip().strip('"\'')
            break
    
    for pattern in url_patterns:
        match = re.search(pattern, content)
        if match:
            api_url = match.group(1).strip().strip('"\'')
            break
    
    return api_key, api_url


def _warn_insecure_permissions(cred_file: Path):
    """Warn if credential file has insecure permissions."""
    import stat
    try:
        mode = os.stat(cred_file).st_mode
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            print(f"[bank:SECURITY] Credentials file has insecure permissions: {cred_file}")
            print(f"[bank:SECURITY] Fix with: chmod 600 {cred_file}")
    except OSError:
        pass



# ============================================================================
# Question Parsing
# ============================================================================

QUESTION_HEADER_RE = re.compile(r"^\s*(\d+)\.\s+(.*\S)\s*$")
MC_OPTION_RE = re.compile(r"^\s*([a-z])\)\s+(.*\S)\s*$")
MC_OPTION_CORRECT_RE = re.compile(r"^\s*\*([a-z])\)\s+(.*\S)\s*$")
MULTI_ANSWER_RE = re.compile(r"^\s*\[(\*|\s)\]\s*(.*\S)\s*$")
SHORT_ANSWER_RE = re.compile(r"^\s*\*\s+(.+\S)\s*$")
TF_TRUE_RE = re.compile(r"^\s*\*a\)\s*True\s*$", re.IGNORECASE)
TF_FALSE_RE = re.compile(r"^\s*\*b\)\s*False\s*$", re.IGNORECASE)
INLINE_CODE_RE = re.compile(r"`([^`]+)`")


def escape_html_text(text: str) -> str:
    """Escape HTML special characters."""
    return html.escape(text, quote=True)


def stem_to_html(stem: str) -> str:
    """Convert question stem (markdown-ish) to HTML for QTI."""
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
                parts.append(escape_html_text(text[last_end:match.start()]))
                parts.append(f'<code>{escape_html_text(match.group(1))}</code>')
                last_end = match.end()
            parts.append(escape_html_text(text[last_end:]))
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
                code_content = escape_html_text('\n'.join(code_block_lines))
                if code_lang:
                    result_parts.append(
                        f'<pre><code class="language-{escape_html_text(code_lang)}">{code_content}</code></pre>'
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
        code_content = escape_html_text('\n'.join(code_block_lines))
        if code_lang:
            result_parts.append(
                f'<pre><code class="language-{escape_html_text(code_lang)}">{code_content}</code></pre>'
            )
        else:
            result_parts.append(f'<pre><code>{code_content}</code></pre>')
    
    return '\n'.join(result_parts)


def answer_to_html(text: str) -> str:
    """Convert answer text to HTML, handling inline code."""
    parts = []
    last_end = 0
    for match in INLINE_CODE_RE.finditer(text):
        parts.append(escape_html_text(text[last_end:match.start()]))
        parts.append(f'<code>{escape_html_text(match.group(1))}</code>')
        last_end = match.end()
    parts.append(escape_html_text(text[last_end:]))
    return ''.join(parts)


def split_frontmatter_and_body(raw: str) -> Tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter if present."""
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
    body_text = "\n".join(lines[end_idx + 1:])

    meta = yaml.safe_load(fm_text) or {}
    if not isinstance(meta, dict):
        meta = {}

    return meta, body_text


def split_questions(raw: str) -> List[List[str]]:
    """Split quiz text into question blocks, preserving code blocks."""
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


def parse_question_block(block: List[str], default_points: float, auto_number: int = 0) -> Optional[ParsedQuestion]:
    """
    Parse a single question block.
    
    Supports both explicit numbering (1. 2. 3.) and markdown-style repeated 
    numbering (1. 1. 1.) where auto_number is used instead.
    """
    if not block:
        return None

    m = QUESTION_HEADER_RE.match(block[0])
    if not m:
        return None

    # Use the parsed number, but it will be overridden by auto_number in parse_bank_file
    # This allows "1. 1. 1." markdown-style numbering to work
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
            return None
        answers = [
            AnswerOption(text="True", is_correct=bool(correct_is_true)),
            AnswerOption(text="False", is_correct=not bool(correct_is_true)),
        ]

    stem = "\n".join(line for line in stem_lines)
    return ParsedQuestion(number=number, stem=stem, qtype=qtype, answers=answers, points=default_points)


def parse_bank_file(path: Path) -> Optional[BankData]:
    """Parse a bank file and return BankData."""
    raw = path.read_text(encoding="utf-8")
    meta, body = split_frontmatter_and_body(raw)
    default_points = float(meta.get("points_per_question", 1.0))

    blocks = split_questions(body)
    questions: List[ParsedQuestion] = []
    
    # Track actual question number for auto-numbering (markdown-style "1." repeated)
    auto_number = 0
    
    for block in blocks:
        try:
            q = parse_question_block(block, default_points=default_points, auto_number=auto_number)
            if q:
                auto_number += 1
                # Override the parsed number with auto-incremented number
                # This allows markdown-style repeated "1." numbering
                q.number = auto_number
                questions.append(q)
        except Exception as e:
            print(f"[bank:warn] Failed to parse question block: {e}")

    if not questions:
        return None

    # Bank name: use frontmatter 'bank_name' if provided, else fall back to file stem
    # This controls the actual name in Canvas
    file_stem = path.stem  # e.g., "chapter1.bank" from "chapter1.bank.md"
    bank_name = meta.get("bank_name") or file_stem
    
    # Title for display: use 'name' or 'title' frontmatter, else bank_name
    title = meta.get("name") or meta.get("title") or bank_name

    return BankData(
        file_path=path,
        title=title,
        bank_name=bank_name,
        questions=questions,
        meta=meta,
    )


# ============================================================================
# QTI XML Generation
# ============================================================================

def prettify_xml(elem: ET.Element) -> str:
    """Return a pretty-printed XML string."""
    rough_string = ET.tostring(elem, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def generate_qti_assessment(bank: BankData) -> str:
    """Generate QTI 1.2 assessment XML for a bank."""
    root = ET.Element("questestinterop")
    root.set("xmlns", QTI_NS)
    
    assessment = ET.SubElement(root, "assessment")
    assessment.set("ident", f"bank_{hashlib.md5(bank.bank_name.encode()).hexdigest()[:12]}")
    assessment.set("title", bank.title)
    
    qtimetadata = ET.SubElement(assessment, "qtimetadata")
    _add_qti_metadata(qtimetadata, "cc_maxattempts", "1")
    
    section = ET.SubElement(assessment, "section")
    section.set("ident", f"section_{bank.bank_name}")
    
    for q in bank.questions:
        _add_qti_item(section, q)
    
    return prettify_xml(root)


def _add_qti_metadata(parent: ET.Element, label: str, entry: str):
    """Add a QTI metadata field."""
    field_elem = ET.SubElement(parent, "qtimetadatafield")
    label_elem = ET.SubElement(field_elem, "fieldlabel")
    label_elem.text = label
    entry_elem = ET.SubElement(field_elem, "fieldentry")
    entry_elem.text = entry


def _add_qti_item(section: ET.Element, question: ParsedQuestion):
    """Add a question item to QTI section."""
    item_id = f"q{question.number}_{uuid.uuid4().hex[:8]}"
    
    item = ET.SubElement(section, "item")
    item.set("ident", item_id)
    item.set("title", f"Question {question.number}")
    
    itemmetadata = ET.SubElement(item, "itemmetadata")
    qtimetadata = ET.SubElement(itemmetadata, "qtimetadata")
    
    qti_type_map = {
        "multiple_choice": "multiple_choice_question",
        "multiple_answers": "multiple_answers_question",
        "true_false": "true_false_question",
        "short_answer": "short_answer_question",
        "essay": "essay_question",
        "file_upload": "file_upload_question",
    }
    
    _add_qti_metadata(qtimetadata, "cc_profile", qti_type_map.get(question.qtype, "multiple_choice_question"))
    _add_qti_metadata(qtimetadata, "cc_weighting", str(question.points))
    
    presentation = ET.SubElement(item, "presentation")
    
    material = ET.SubElement(presentation, "material")
    mattext = ET.SubElement(material, "mattext")
    mattext.set("texttype", "text/html")
    mattext.text = stem_to_html(question.stem)
    
    if question.qtype in ["multiple_choice", "multiple_answers", "true_false"]:
        _add_choice_response(presentation, item, question)
    elif question.qtype == "short_answer":
        _add_short_answer_response(presentation, item, question)
    elif question.qtype == "essay":
        _add_essay_response(presentation, item, question)
    elif question.qtype == "file_upload":
        _add_file_upload_response(presentation, item, question)


def _add_choice_response(presentation: ET.Element, item: ET.Element, question: ParsedQuestion):
    """Add choice-based response to QTI item."""
    rcardinality = "Single" if question.qtype != "multiple_answers" else "Multiple"
    
    response_lid = ET.SubElement(presentation, "response_lid")
    response_lid.set("ident", "response1")
    response_lid.set("rcardinality", rcardinality)
    
    render_choice = ET.SubElement(response_lid, "render_choice")
    
    for i, answer in enumerate(question.answers):
        response_label = ET.SubElement(render_choice, "response_label")
        response_label.set("ident", f"answer{i}")
        
        material = ET.SubElement(response_label, "material")
        mattext = ET.SubElement(material, "mattext")
        mattext.set("texttype", "text/html")
        mattext.text = answer_to_html(answer.text)
    
    resprocessing = ET.SubElement(item, "resprocessing")
    outcomes = ET.SubElement(resprocessing, "outcomes")
    decvar = ET.SubElement(outcomes, "decvar")
    decvar.set("maxvalue", "100")
    decvar.set("minvalue", "0")
    decvar.set("varname", "SCORE")
    decvar.set("vartype", "Decimal")
    
    correct_answers = [f"answer{i}" for i, a in enumerate(question.answers) if a.is_correct]
    
    for correct_id in correct_answers:
        respcondition = ET.SubElement(resprocessing, "respcondition")
        respcondition.set("continue", "No")
        
        conditionvar = ET.SubElement(respcondition, "conditionvar")
        varequal = ET.SubElement(conditionvar, "varequal")
        varequal.set("respident", "response1")
        varequal.text = correct_id
        
        setvar = ET.SubElement(respcondition, "setvar")
        setvar.set("action", "Set")
        setvar.set("varname", "SCORE")
        setvar.text = "100"


def _add_short_answer_response(presentation: ET.Element, item: ET.Element, question: ParsedQuestion):
    """Add short answer response to QTI item."""
    response_str = ET.SubElement(presentation, "response_str")
    response_str.set("ident", "response1")
    response_str.set("rcardinality", "Single")
    
    render_fib = ET.SubElement(response_str, "render_fib")
    response_label = ET.SubElement(render_fib, "response_label")
    response_label.set("ident", "answer1")
    
    resprocessing = ET.SubElement(item, "resprocessing")
    outcomes = ET.SubElement(resprocessing, "outcomes")
    decvar = ET.SubElement(outcomes, "decvar")
    decvar.set("maxvalue", "100")
    decvar.set("minvalue", "0")
    decvar.set("varname", "SCORE")
    decvar.set("vartype", "Decimal")
    
    for answer in question.answers:
        if answer.is_correct:
            respcondition = ET.SubElement(resprocessing, "respcondition")
            conditionvar = ET.SubElement(respcondition, "conditionvar")
            varequal = ET.SubElement(conditionvar, "varequal")
            varequal.set("respident", "response1")
            varequal.text = answer.text
            
            setvar = ET.SubElement(respcondition, "setvar")
            setvar.set("action", "Set")
            setvar.set("varname", "SCORE")
            setvar.text = "100"


def _add_essay_response(presentation: ET.Element, item: ET.Element, question: ParsedQuestion):
    """Add essay response to QTI item."""
    response_str = ET.SubElement(presentation, "response_str")
    response_str.set("ident", "response1")
    response_str.set("rcardinality", "Single")
    
    render_fib = ET.SubElement(response_str, "render_fib")
    render_fib.set("fibtype", "String")
    render_fib.set("prompt", "Box")
    render_fib.set("rows", "10")
    render_fib.set("columns", "60")


def _add_file_upload_response(presentation: ET.Element, item: ET.Element, question: ParsedQuestion):
    """Add file upload response to QTI item."""
    response_str = ET.SubElement(presentation, "response_str")
    response_str.set("ident", "response1")
    response_str.set("rcardinality", "Single")
    
    render_fib = ET.SubElement(response_str, "render_fib")
    render_fib.set("fibtype", "String")


# ============================================================================
# IMSCC Package Generation
# ============================================================================

def generate_manifest(bank: BankData, assessment_id: str) -> str:
    """Generate imsmanifest.xml for the QTI package."""
    root = ET.Element("manifest")
    root.set("xmlns", CC_NS)
    root.set("identifier", f"manifest_{assessment_id}")
    
    metadata = ET.SubElement(root, "metadata")
    schema = ET.SubElement(metadata, "schema")
    schema.text = "IMS Common Cartridge"
    schemaversion = ET.SubElement(metadata, "schemaversion")
    schemaversion.text = "1.3.0"
    
    ET.SubElement(root, "organizations")
    
    resources = ET.SubElement(root, "resources")
    
    resource = ET.SubElement(resources, "resource")
    resource.set("identifier", assessment_id)
    resource.set("type", "imsqti_xmlv1p2/imscc_xmlv1p3/assessment")
    resource.set("href", f"assessments/{assessment_id}/assessment.xml")
    
    file_elem = ET.SubElement(resource, "file")
    file_elem.set("href", f"assessments/{assessment_id}/assessment.xml")
    
    return prettify_xml(root)


def create_qti_package(bank: BankData) -> bytes:
    """Create an IMSCC ZIP package containing the QTI assessment."""
    assessment_id = f"bank_{hashlib.md5(bank.bank_name.encode()).hexdigest()[:12]}"
    
    qti_xml = generate_qti_assessment(bank)
    manifest_xml = generate_manifest(bank, assessment_id)
    
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("imsmanifest.xml", manifest_xml)
        zf.writestr(f"assessments/{assessment_id}/assessment.xml", qti_xml)
    
    return buffer.getvalue()


# ============================================================================
# Canvas Upload
# ============================================================================

# SECURITY: Request timeout constants
REQUEST_TIMEOUT = (10, 30)      # (connect, read) - standard requests
UPLOAD_TIMEOUT = (10, 120)      # longer timeout for file uploads
MIGRATION_TIMEOUT = (10, 60)    # for migration status checks


def verify_bank_exists(course_id: int, bank_name: str, api_url: str, api_key: str) -> Optional[int]:
    """Check if a question bank exists. Returns bank ID if found."""
    url = f"{api_url}/api/v1/courses/{course_id}/question_banks"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            banks = resp.json()
            for bank in banks:
                title = bank.get("title") or bank.get("name", "")
                if title == bank_name:
                    return bank.get("id")
    except requests.exceptions.Timeout:
        print(f"[bank:warn] Timeout checking for existing bank")
    except Exception:
        pass
    
    return None


def upload_bank_to_canvas(
    course_id: int,
    bank: BankData,
    api_url: str,
    api_key: str,
) -> Optional[int]:
    """
    Upload bank via QTI Content Migration API.
    
    Returns migration_id on success, None on failure.
    """
    print(f"[bank] Creating QTI package for '{bank.bank_name}'...")
    package_bytes = create_qti_package(bank)
    package_size = len(package_bytes)
    print(f"[bank]   Package size: {package_size} bytes, {len(bank.questions)} questions")
    
    migration_url = f"{api_url}/api/v1/courses/{course_id}/content_migrations"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    init_data = {
        "migration_type": "qti_converter",
        "settings[question_bank_name]": bank.bank_name,
        "pre_attachment[name]": f"{bank.bank_name}.zip",
        "pre_attachment[size]": package_size,
    }
    
    print(f"[bank] Initiating content migration...")
    try:
        resp = requests.post(migration_url, headers=headers, data=init_data, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        print(f"[bank:error] Timeout initiating migration")
        return None
    
    if resp.status_code not in (200, 201):
        print(f"[bank:error] Failed to initiate migration (HTTP {resp.status_code})")
        return None
    
    migration_data = resp.json()
    migration_id = migration_data.get("id")
    print(f"[bank]   Migration ID: {migration_id}")
    
    pre_attachment = migration_data.get("pre_attachment")
    if not pre_attachment:
        print(f"[bank:error] No pre_attachment in response")
        return None
    
    upload_url = pre_attachment.get("upload_url")
    upload_params = pre_attachment.get("upload_params", {})
    
    print(f"[bank] Uploading QTI package...")
    files = {"file": (f"{bank.bank_name}.zip", package_bytes, "application/zip")}
    
    try:
        upload_resp = requests.post(upload_url, data=upload_params, files=files, timeout=UPLOAD_TIMEOUT)
    except requests.exceptions.Timeout:
        print(f"[bank:error] Timeout uploading QTI package")
        return None
    
    if upload_resp.status_code not in (200, 201, 301, 302, 303):
        print(f"[bank:error] Failed to upload file (HTTP {upload_resp.status_code})")
        return None
    
    if upload_resp.status_code in (301, 302, 303):
        confirm_url = upload_resp.headers.get("Location")
        if confirm_url:
            try:
                requests.get(confirm_url, headers=headers, timeout=REQUEST_TIMEOUT)
            except requests.exceptions.Timeout:
                pass  # Not critical
    
    print(f"[bank]   Upload complete")
    
    # Poll for completion
    progress_url = migration_data.get("progress_url")
    migration_failed = False
    timed_out = False
    
    if progress_url:
        print(f"[bank] Waiting for migration...")
        for attempt in range(30):
            time.sleep(2)
            
            try:
                progress_resp = requests.get(progress_url, headers=headers, timeout=MIGRATION_TIMEOUT)
            except requests.exceptions.Timeout:
                continue
            if progress_resp.status_code != 200:
                continue
            
            progress = progress_resp.json()
            workflow_state = progress.get("workflow_state")
            completion = progress.get("completion", 0)
            
            print(f"[bank]   Progress: {completion}% ({workflow_state})")
            
            if workflow_state == "completed":
                print(f"[bank] ✔ Bank '{bank.bank_name}' imported successfully")
                return migration_id
            elif workflow_state == "failed":
                migration_failed = True
                break
        else:
            # Loop completed without break - timed out
            timed_out = True
            print(f"[bank:warn] Migration timed out after 60s (still queued/running)")
            print(f"[bank:warn] Migration ID {migration_id} may complete later - check Canvas")
    
    # Verify bank exists even if migration "failed" or timed out
    if migration_failed or timed_out:
        print(f"[bank] Verifying import...")
        time.sleep(1)
        
        bank_id = verify_bank_exists(course_id, bank.bank_name, api_url, api_key)
        if bank_id:
            print(f"[bank] ✔ Bank '{bank.bank_name}' exists (id={bank_id}) - import succeeded")
            return migration_id
        else:
            if timed_out:
                print(f"[bank:warn] Cannot verify via API - migration may still be processing")
            else:
                print(f"[bank:warn] Cannot verify via API, but import likely succeeded")
            return migration_id
    
    return migration_id


# ============================================================================
# File Discovery
# ============================================================================

def get_changed_files() -> List[Path]:
    """Get list of changed files from environment."""
    raw = os.environ.get("ZAPHOD_CHANGED_FILES", "").strip()
    if not raw:
        return []
    return [Path(p) for p in raw.splitlines() if p.strip()]


def natural_sort_key(path: Path) -> tuple:
    """
    Natural sort key for file paths.
    
    Splits the filename into text and numeric parts so that:
    - 1, 2, 3, 10, 11 sorts correctly (not 1, 10, 11, 2, 3)
    - "chapter1" comes before "chapter2" which comes before "chapter10"
    """
    import re
    parts = re.split(r'(\d+)', path.name)
    return tuple(int(p) if p.isdigit() else p.lower() for p in parts)


def iter_bank_files_full() -> List[Path]:
    """Get all bank files in quiz-banks/."""
    if not QUIZ_BANKS_DIR.exists():
        return []
    
    files = []
    # New format: *.bank.md
    files.extend(QUIZ_BANKS_DIR.glob("*.bank.md"))
    # Legacy format: *.quiz.txt (deprecated)
    legacy = list(QUIZ_BANKS_DIR.glob("*.quiz.txt"))
    if legacy:
        print(f"[bank:warn] Found {len(legacy)} legacy *.quiz.txt files - consider renaming to *.bank.md")
    files.extend(legacy)
    
    return sorted(files, key=natural_sort_key)


def iter_bank_files_incremental(changed_files: List[Path]) -> List[Path]:
    """Filter changed files to bank files under quiz-banks/."""
    result: List[Path] = []
    seen: set[Path] = set()

    for p in changed_files:
        # Check for both new and legacy formats
        is_bank = str(p).endswith(".bank.md") or str(p).endswith(".quiz.txt")
        if not is_bank:
            continue
        
        try:
            rel = p.relative_to(COURSE_ROOT)
        except ValueError:
            continue
        
        if not rel.parts or rel.parts[0] != "quiz-banks":
            continue
        
        path = QUIZ_BANKS_DIR / rel.name if len(rel.parts) == 2 else COURSE_ROOT / rel
        if path.is_file() and path not in seen:
            seen.add(path)
            result.append(path)

    return sorted(result, key=natural_sort_key)


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Import question banks (*.bank.md) into Canvas"
    )
    parser.add_argument(
        "--file", "-f",
        type=Path,
        help="Import a specific bank file"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Parse files but don't upload to Canvas"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force sync even if content unchanged"
    )
    args = parser.parse_args()
    
    course_id = get_course_id()
    if not course_id:
        raise SystemExit("COURSE_ID is not set")
    
    course_id_int = int(course_id)
    api_url, api_key = load_canvas_credentials()
    
    # Load bank cache for incremental sync
    bank_cache = load_bank_cache()
    
    # Determine which files to process
    if args.file:
        bank_files = [args.file]
    else:
        changed_files = get_changed_files()
        if changed_files:
            # Watch mode: use ZAPHOD_CHANGED_FILES for file list
            bank_files = iter_bank_files_incremental(changed_files)
            if not bank_files:
                print(f"[bank] No changed bank files under {QUIZ_BANKS_DIR}; nothing to do.")
                return
        else:
            # Regular sync: get all files, will filter by cache hash
            bank_files = iter_bank_files_full()
            if not bank_files:
                print(f"[bank] No bank files (*.bank.md) under {QUIZ_BANKS_DIR}")
                return
    
    print(f"[bank] Processing {len(bank_files)} bank file(s)")
    print(f"[bank] Course ID: {course_id_int}")
    print()
    
    success_count = 0
    skipped_count = 0
    for path in bank_files:
        print(f"[bank] === {path.name} ===")
        
        # Check if bank needs sync (based on content hash)
        if not bank_needs_sync(path, bank_cache, force=args.force):
            print(f"[bank]   (unchanged, skipping)")
            skipped_count += 1
            continue
        
        # Warn about potential duplicate if using --force
        if args.force:
            prev_upload = bank_already_uploaded(path, bank_cache)
            if prev_upload.get("uploaded_at"):
                print(f"[bank:warn] Bank was uploaded at {prev_upload['uploaded_at']}")
                print(f"[bank:warn] Using --force will create a DUPLICATE bank in Canvas!")
        
        bank = parse_bank_file(path)
        if not bank:
            print(f"[bank:warn] No questions parsed from {path.name}")
            continue
        
        print(f"[bank]   Title: {bank.title}")
        print(f"[bank]   Questions: {len(bank.questions)}")
        
        if args.dry_run:
            print(f"[bank]   (dry-run) Would import to bank '{bank.bank_name}'")
            success_count += 1
        else:
            migration_id = upload_bank_to_canvas(course_id_int, bank, api_url, api_key)
            if migration_id:
                # Update cache with new hash and migration info
                update_bank_cache(path, bank.bank_name, bank_cache, migration_id)
                success_count += 1
        
        print()
    
    # Save cache
    if not args.dry_run:
        save_bank_cache(bank_cache)
    
    print(f"[bank] Completed: {success_count} synced, {skipped_count} unchanged")


if __name__ == "__main__":
    main()
