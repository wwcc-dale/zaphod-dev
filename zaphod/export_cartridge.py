#!/usr/bin/env python3
"""
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

export_cartridge.py

Export a Zaphod course to IMS Common Cartridge 1.3 format.

This creates a complete course package that can be imported into:
- Canvas LMS
- Moodle
- Blackboard
- Brightspace (D2L)
- Sakai
- And other CC-compliant LMS platforms

The export includes:
- Pages (as web content)
- Assignments (with rubrics)
- Quizzes (QTI 1.2 format)
- Learning Outcomes
- Module structure
- Media files and assets

Usage:
    python export_cartridge.py [--output PATH] [--title "Course Title"]

Environment:
    ZAPHOD_CHANGED_FILES    (optional) For incremental exports
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET
from xml.dom import minidom

import yaml
import frontmatter
import markdown

from zaphod.config_utils import get_course_id


# ============================================================================
# Constants and Paths
# ============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
COURSE_ROOT = Path.cwd()
PAGES_DIR = COURSE_ROOT / "pages"
ASSETS_DIR = COURSE_ROOT / "assets"
QUIZ_BANKS_DIR = COURSE_ROOT / "quiz-banks"
OUTCOMES_DIR = COURSE_ROOT / "outcomes"
MODULES_DIR = COURSE_ROOT / "modules"
RUBRICS_DIR = COURSE_ROOT / "rubrics"
EXPORTS_DIR = COURSE_ROOT / "exports"

# Common Cartridge namespaces
NS = {
    "imscc": "http://www.imsglobal.org/xsd/imsccv1p3/imscp_v1p1",
    "lom": "http://ltsc.ieee.org/xsd/imsccv1p3/LOM/resource",
    "lomimscc": "http://ltsc.ieee.org/xsd/imsccv1p3/LOM/manifest",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

# QTI namespaces
QTI_NS = {
    "": "http://www.imsglobal.org/xsd/ims_qtiasiv1p2",
}


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ContentItem:
    """Represents a content item (page, assignment, etc.)"""
    identifier: str
    title: str
    item_type: str  # page, assignment, link, file
    folder_path: Path
    meta: Dict[str, Any]
    source_html: str = ""
    modules: List[str] = field(default_factory=list)
    rubric: Optional[Dict[str, Any]] = None
    

@dataclass
class QuizItem:
    """Represents a quiz for export"""
    identifier: str
    title: str
    file_path: Path
    meta: Dict[str, Any]
    questions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class OutcomeItem:
    """Represents a learning outcome"""
    identifier: str
    code: str
    title: str
    description: str
    mastery_points: float
    ratings: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ModuleItem:
    """Represents a module/unit in the course"""
    identifier: str
    title: str
    position: int
    items: List[str] = field(default_factory=list)  # List of content identifiers


@dataclass
class CartridgeExport:
    """Container for all export data"""
    title: str
    identifier: str
    content_items: List[ContentItem] = field(default_factory=list)
    quizzes: List[QuizItem] = field(default_factory=list)
    outcomes: List[OutcomeItem] = field(default_factory=list)
    modules: List[ModuleItem] = field(default_factory=list)
    assets: List[Path] = field(default_factory=list)


# ============================================================================
# ID Generation
# ============================================================================

def generate_id(prefix: str = "i") -> str:
    """Generate a unique identifier for CC resources."""
    return f"{prefix}{uuid.uuid4().hex[:16]}"


def generate_content_id(folder: Path) -> str:
    """Generate a deterministic ID based on folder path."""
    hash_input = str(folder.relative_to(COURSE_ROOT))
    return f"i{hashlib.md5(hash_input.encode()).hexdigest()[:16]}"


# ============================================================================
# XML Helpers
# ============================================================================

def prettify_xml(elem: ET.Element) -> str:
    """Return a pretty-printed XML string."""
    rough_string = ET.tostring(elem, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def add_text_element(parent: ET.Element, tag: str, text: str, **attribs) -> ET.Element:
    """Add a text element to parent."""
    elem = ET.SubElement(parent, tag, **attribs)
    elem.text = text
    return elem


# ============================================================================
# Content Loaders
# ============================================================================

def load_content_items() -> List[ContentItem]:
    """Load all content items from pages/ directory."""
    items = []
    
    if not PAGES_DIR.exists():
        print("[cartridge:warn] No pages directory found")
        return items
    
    for ext in [".page", ".assignment", ".link", ".file"]:
        for folder in PAGES_DIR.rglob(f"*{ext}"):
            if not folder.is_dir():
                continue
            
            item = load_content_item(folder, ext[1:])  # Remove leading dot
            if item:
                items.append(item)
    
    return items


def load_content_item(folder: Path, item_type: str) -> Optional[ContentItem]:
    """Load a single content item from a folder."""
    index_path = folder / "index.md"
    meta_path = folder / "meta.json"
    source_path = folder / "source.md"
    
    # Try to load metadata
    meta = {}
    source_content = ""
    
    if index_path.is_file():
        try:
            post = frontmatter.load(index_path)
            meta = dict(post.metadata)
            source_content = post.content
        except Exception as e:
            print(f"[cartridge:warn] Failed to parse {index_path}: {e}")
    
    if not meta and meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[cartridge:warn] Failed to load {meta_path}: {e}")
    
    if source_path.is_file() and not source_content:
        source_content = source_path.read_text(encoding="utf-8")
    
    if not meta.get("name"):
        print(f"[cartridge:warn] Skipping {folder.name}: no name in metadata")
        return None
    
    # Convert markdown to HTML
    source_html = markdown.markdown(
        source_content,
        extensions=['tables', 'fenced_code', 'codehilite']
    )
    
    # Load rubric if present (for assignments)
    rubric = None
    if item_type == "assignment":
        rubric = load_rubric(folder)
    
    return ContentItem(
        identifier=generate_content_id(folder),
        title=meta.get("name", folder.name),
        item_type=item_type,
        folder_path=folder,
        meta=meta,
        source_html=source_html,
        modules=meta.get("modules", []),
        rubric=rubric,
    )


def load_rubric(folder: Path) -> Optional[Dict[str, Any]]:
    """Load rubric from an assignment folder."""
    for filename in ["rubric.yaml", "rubric.yml", "rubric.json"]:
        rubric_path = folder / filename
        if rubric_path.is_file():
            try:
                if filename.endswith(".json"):
                    return json.loads(rubric_path.read_text(encoding="utf-8"))
                else:
                    data = yaml.safe_load(rubric_path.read_text(encoding="utf-8"))
                    # Handle use_rubric references
                    if isinstance(data, dict) and data.get("use_rubric"):
                        return load_shared_rubric(data["use_rubric"])
                    return data
            except Exception as e:
                print(f"[cartridge:warn] Failed to load rubric {rubric_path}: {e}")
    return None


def load_shared_rubric(name: str) -> Optional[Dict[str, Any]]:
    """Load a shared rubric from rubrics/ directory."""
    for ext in [".yaml", ".yml", ".json"]:
        path = RUBRICS_DIR / f"{name}{ext}"
        if path.is_file():
            try:
                if ext == ".json":
                    return json.loads(path.read_text(encoding="utf-8"))
                else:
                    return yaml.safe_load(path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[cartridge:warn] Failed to load shared rubric {path}: {e}")
    return None


# ============================================================================
# Quiz Loaders
# ============================================================================

def load_quizzes() -> List[QuizItem]:
    """Load all quizzes from quiz-banks/ directory."""
    quizzes = []
    
    if not QUIZ_BANKS_DIR.exists():
        return quizzes
    
    for quiz_file in QUIZ_BANKS_DIR.glob("*.quiz.txt"):
        quiz = load_quiz(quiz_file)
        if quiz:
            quizzes.append(quiz)
    
    return quizzes


def load_quiz(quiz_file: Path) -> Optional[QuizItem]:
    """Load a single quiz file."""
    try:
        raw = quiz_file.read_text(encoding="utf-8")
        meta, body = split_quiz_frontmatter(raw)
        questions = parse_quiz_questions(body, meta.get("points_per_question", 1.0))
        
        return QuizItem(
            identifier=generate_id("quiz"),
            title=meta.get("title", quiz_file.stem),
            file_path=quiz_file,
            meta=meta,
            questions=questions,
        )
    except Exception as e:
        print(f"[cartridge:warn] Failed to parse quiz {quiz_file}: {e}")
        return None


def split_quiz_frontmatter(raw: str) -> Tuple[Dict[str, Any], str]:
    """Split YAML frontmatter from quiz body."""
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
    return meta if isinstance(meta, dict) else {}, body_text


def parse_quiz_questions(body: str, default_points: float) -> List[Dict[str, Any]]:
    """Parse quiz questions from body text."""
    # Reuse patterns from sync_quiz_banks.py
    QUESTION_HEADER_RE = re.compile(r"^\s*(\d+)\.\s+(.*\S)\s*$")
    MC_OPTION_RE = re.compile(r"^\s*([a-z])\)\s+(.*\S)\s*$")
    MC_OPTION_CORRECT_RE = re.compile(r"^\s*\*([a-z])\)\s+(.*\S)\s*$")
    MULTI_ANSWER_RE = re.compile(r"^\s*\[(\*|\s)\]\s*(.*\S)\s*$")
    SHORT_ANSWER_RE = re.compile(r"^\s*\*\s+(.+\S)\s*$")
    
    questions = []
    blocks = split_question_blocks(body)
    
    for block in blocks:
        if not block:
            continue
        
        m = QUESTION_HEADER_RE.match(block[0])
        if not m:
            continue
        
        number = int(m.group(1))
        stem = m.group(2).strip()
        rest = block[1:]
        
        # Detect question type
        qtype = detect_question_type(block)
        answers = []
        
        # Parse answers based on type
        if qtype == "multiple_choice":
            for line in rest:
                m_corr = MC_OPTION_CORRECT_RE.match(line)
                m_opt = MC_OPTION_RE.match(line)
                if m_corr:
                    answers.append({"text": m_corr.group(2), "correct": True})
                elif m_opt:
                    answers.append({"text": m_opt.group(2), "correct": False})
                elif not answers:  # Part of stem
                    stem += " " + line.strip()
        
        elif qtype == "multiple_answers":
            for line in rest:
                m_ma = MULTI_ANSWER_RE.match(line)
                if m_ma:
                    answers.append({
                        "text": m_ma.group(2),
                        "correct": m_ma.group(1) == "*"
                    })
        
        elif qtype == "true_false":
            answers = [
                {"text": "True", "correct": any("*a)" in line.lower() for line in block)},
                {"text": "False", "correct": any("*b)" in line.lower() for line in block)},
            ]
        
        elif qtype == "short_answer":
            for line in rest:
                m_sa = SHORT_ANSWER_RE.match(line)
                if m_sa:
                    answers.append({"text": m_sa.group(1), "correct": True})
        
        questions.append({
            "number": number,
            "stem": stem,
            "type": qtype,
            "answers": answers,
            "points": default_points,
        })
    
    return questions


def split_question_blocks(body: str) -> List[List[str]]:
    """Split quiz body into question blocks."""
    lines = body.splitlines()
    blocks = []
    current = []
    
    for line in lines:
        if not line.strip():
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(line)
    
    if current:
        blocks.append(current)
    
    return blocks


def detect_question_type(block: List[str]) -> str:
    """Detect question type from block content."""
    body = "\n".join(block)
    
    if "####" in body:
        return "essay"
    if "^^^^" in body:
        return "file_upload"
    
    for line in block:
        if re.match(r"^\s*\[[\*\s]\]", line):
            return "multiple_answers"
    
    has_true = any(re.search(r"a\)\s*True", line, re.IGNORECASE) for line in block)
    has_false = any(re.search(r"b\)\s*False", line, re.IGNORECASE) for line in block)
    if has_true and has_false:
        return "true_false"
    
    if any(re.match(r"^\s*\*\s+", line) for line in block):
        return "short_answer"
    
    return "multiple_choice"


# ============================================================================
# Outcomes Loader
# ============================================================================

def load_outcomes() -> List[OutcomeItem]:
    """Load learning outcomes from outcomes/outcomes.yaml."""
    outcomes = []
    outcomes_file = OUTCOMES_DIR / "outcomes.yaml"
    
    if not outcomes_file.is_file():
        return outcomes
    
    try:
        data = yaml.safe_load(outcomes_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return outcomes
        
        for clo in data.get("course_outcomes", []):
            outcomes.append(OutcomeItem(
                identifier=generate_id("outcome"),
                code=clo.get("code", ""),
                title=clo.get("title", ""),
                description=clo.get("description", ""),
                mastery_points=float(clo.get("mastery_points", 3)),
                ratings=clo.get("ratings", []),
            ))
    except Exception as e:
        print(f"[cartridge:warn] Failed to load outcomes: {e}")
    
    return outcomes


# ============================================================================
# Module Structure Loader
# ============================================================================

def load_module_structure(content_items: List[ContentItem]) -> List[ModuleItem]:
    """Build module structure from content item metadata."""
    module_map: Dict[str, ModuleItem] = {}
    
    # Load module order if available
    module_order = []
    order_file = MODULES_DIR / "module_order.yaml"
    if order_file.is_file():
        try:
            data = yaml.safe_load(order_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                module_order = data.get("modules", [])
            elif isinstance(data, list):
                module_order = data
        except Exception:
            pass
    
    # Create modules from order first
    for i, name in enumerate(module_order):
        if name not in module_map:
            module_map[name] = ModuleItem(
                identifier=generate_id("module"),
                title=name,
                position=i,
                items=[],
            )
    
    # Add content to modules
    position = len(module_order)
    for item in content_items:
        for module_name in item.modules:
            if module_name not in module_map:
                module_map[module_name] = ModuleItem(
                    identifier=generate_id("module"),
                    title=module_name,
                    position=position,
                    items=[],
                )
                position += 1
            module_map[module_name].items.append(item.identifier)
    
    # Sort by position
    modules = sorted(module_map.values(), key=lambda m: m.position)
    return modules


# ============================================================================
# Asset Collection
# ============================================================================

def collect_assets() -> List[Path]:
    """Collect all asset files for inclusion in the cartridge."""
    assets = []
    
    # Files to exclude (Windows metadata, macOS, etc.)
    exclude_patterns = {
        ':Zone.Identifier',  # Windows security metadata
        '.DS_Store',         # macOS
        'Thumbs.db',         # Windows thumbnails
        '.gitkeep',          # Git placeholder
        'desktop.ini',       # Windows folder settings
    }
    
    if ASSETS_DIR.exists():
        for file_path in ASSETS_DIR.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.name.startswith("."):
                continue
            # Check for excluded patterns in filename
            if any(pattern in file_path.name for pattern in exclude_patterns):
                continue
            assets.append(file_path)
    
    return assets


# ============================================================================
# QTI Export
# ============================================================================

def generate_qti_assessment(quiz: QuizItem) -> str:
    """Generate QTI 1.2 XML for a quiz."""
    # Root element with QTI namespace
    root = ET.Element("questestinterop")
    root.set("xmlns", "http://www.imsglobal.org/xsd/ims_qtiasiv1p2")
    
    # Assessment element
    assessment = ET.SubElement(root, "assessment")
    assessment.set("ident", quiz.identifier)
    assessment.set("title", quiz.title)
    
    # Assessment metadata
    qtimetadata = ET.SubElement(assessment, "qtimetadata")
    add_qti_metadata(qtimetadata, "cc_profile", "cc.exam.v0p1")
    add_qti_metadata(qtimetadata, "qmd_assessmenttype", "Examination")
    
    if quiz.meta.get("time_limit"):
        add_qti_metadata(qtimetadata, "qmd_timelimit", str(quiz.meta["time_limit"]))
    
    # Section containing all items
    section = ET.SubElement(assessment, "section")
    section.set("ident", f"{quiz.identifier}_section")
    
    # Add each question as an item
    for q in quiz.questions:
        add_qti_item(section, q, quiz.identifier)
    
    return prettify_xml(root)


def add_qti_metadata(parent: ET.Element, label: str, entry: str):
    """Add a QTI metadata field."""
    field = ET.SubElement(parent, "qtimetadatafield")
    add_text_element(field, "fieldlabel", label)
    add_text_element(field, "fieldentry", entry)


def add_qti_item(section: ET.Element, question: Dict[str, Any], quiz_id: str):
    """Add a question item to QTI section."""
    item_id = f"{quiz_id}_q{question['number']}"
    
    item = ET.SubElement(section, "item")
    item.set("ident", item_id)
    item.set("title", f"Question {question['number']}")
    
    # Item metadata
    itemmetadata = ET.SubElement(item, "itemmetadata")
    qtimetadata = ET.SubElement(itemmetadata, "qtimetadata")
    
    # Map question types to QTI types
    qti_type_map = {
        "multiple_choice": "multiple_choice_question",
        "multiple_answers": "multiple_answers_question",
        "true_false": "true_false_question",
        "short_answer": "short_answer_question",
        "essay": "essay_question",
        "file_upload": "file_upload_question",
    }
    
    add_qti_metadata(qtimetadata, "cc_profile", qti_type_map.get(question["type"], "multiple_choice_question"))
    add_qti_metadata(qtimetadata, "cc_weighting", str(question["points"]))
    
    # Presentation
    presentation = ET.SubElement(item, "presentation")
    
    # Question text (material)
    material = ET.SubElement(presentation, "material")
    mattext = ET.SubElement(material, "mattext")
    mattext.set("texttype", "text/html")
    mattext.text = f"<p>{html.escape(question['stem'])}</p>"
    
    # Response based on question type
    if question["type"] in ["multiple_choice", "multiple_answers", "true_false"]:
        add_choice_response(presentation, item, question)
    elif question["type"] == "short_answer":
        add_short_answer_response(presentation, item, question)
    elif question["type"] == "essay":
        add_essay_response(presentation, item, question)


def add_choice_response(presentation: ET.Element, item: ET.Element, question: Dict[str, Any]):
    """Add choice-based response to QTI item."""
    rcardinality = "Single" if question["type"] != "multiple_answers" else "Multiple"
    
    response_lid = ET.SubElement(presentation, "response_lid")
    response_lid.set("ident", "response1")
    response_lid.set("rcardinality", rcardinality)
    
    render_choice = ET.SubElement(response_lid, "render_choice")
    
    # Add answer choices
    for i, answer in enumerate(question.get("answers", [])):
        response_label = ET.SubElement(render_choice, "response_label")
        response_label.set("ident", f"answer{i}")
        
        material = ET.SubElement(response_label, "material")
        mattext = ET.SubElement(material, "mattext")
        mattext.set("texttype", "text/plain")
        mattext.text = answer["text"]
    
    # Add response processing
    resprocessing = ET.SubElement(item, "resprocessing")
    outcomes = ET.SubElement(resprocessing, "outcomes")
    decvar = ET.SubElement(outcomes, "decvar")
    decvar.set("maxvalue", "100")
    decvar.set("minvalue", "0")
    decvar.set("varname", "SCORE")
    decvar.set("vartype", "Decimal")
    
    # Add correct answer conditions
    correct_answers = [f"answer{i}" for i, a in enumerate(question.get("answers", [])) if a.get("correct")]
    
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


def add_short_answer_response(presentation: ET.Element, item: ET.Element, question: Dict[str, Any]):
    """Add short answer response to QTI item."""
    response_str = ET.SubElement(presentation, "response_str")
    response_str.set("ident", "response1")
    response_str.set("rcardinality", "Single")
    
    render_fib = ET.SubElement(response_str, "render_fib")
    response_label = ET.SubElement(render_fib, "response_label")
    response_label.set("ident", "answer1")
    
    # Add response processing with correct answers
    resprocessing = ET.SubElement(item, "resprocessing")
    outcomes = ET.SubElement(resprocessing, "outcomes")
    decvar = ET.SubElement(outcomes, "decvar")
    decvar.set("maxvalue", "100")
    decvar.set("minvalue", "0")
    decvar.set("varname", "SCORE")
    decvar.set("vartype", "Decimal")
    
    for answer in question.get("answers", []):
        if answer.get("correct"):
            respcondition = ET.SubElement(resprocessing, "respcondition")
            conditionvar = ET.SubElement(respcondition, "conditionvar")
            varequal = ET.SubElement(conditionvar, "varequal")
            varequal.set("respident", "response1")
            varequal.text = answer["text"]
            
            setvar = ET.SubElement(respcondition, "setvar")
            setvar.set("action", "Set")
            setvar.set("varname", "SCORE")
            setvar.text = "100"


def add_essay_response(presentation: ET.Element, item: ET.Element, question: Dict[str, Any]):
    """Add essay response to QTI item."""
    response_str = ET.SubElement(presentation, "response_str")
    response_str.set("ident", "response1")
    response_str.set("rcardinality", "Single")
    
    render_fib = ET.SubElement(response_str, "render_fib")
    render_fib.set("fibtype", "String")
    render_fib.set("rows", "15")
    render_fib.set("columns", "60")


# ============================================================================
# Rubric Export (CC Extension)
# ============================================================================

def generate_rubric_xml(rubric: Dict[str, Any], assignment_id: str) -> str:
    """Generate rubric XML for Common Cartridge."""
    root = ET.Element("rubric")
    root.set("xmlns", "http://canvas.instructure.com/xsd/rubric")
    root.set("identifier", f"{assignment_id}_rubric")
    
    add_text_element(root, "title", rubric.get("title", "Rubric"))
    add_text_element(root, "description", rubric.get("description", ""))
    add_text_element(root, "free_form_criterion_comments", 
                     str(rubric.get("free_form_criterion_comments", False)).lower())
    
    criteria_elem = ET.SubElement(root, "criteria")
    
    for i, criterion in enumerate(rubric.get("criteria", [])):
        if isinstance(criterion, str):
            continue  # Skip template references
        
        crit_elem = ET.SubElement(criteria_elem, "criterion")
        crit_elem.set("id", f"criterion_{i}")
        
        add_text_element(crit_elem, "description", criterion.get("description", ""))
        add_text_element(crit_elem, "long_description", criterion.get("long_description", ""))
        add_text_element(crit_elem, "points", str(criterion.get("points", 0)))
        
        ratings_elem = ET.SubElement(crit_elem, "ratings")
        for j, rating in enumerate(criterion.get("ratings", [])):
            rating_elem = ET.SubElement(ratings_elem, "rating")
            rating_elem.set("id", f"rating_{i}_{j}")
            
            add_text_element(rating_elem, "description", rating.get("description", ""))
            add_text_element(rating_elem, "long_description", rating.get("long_description", ""))
            add_text_element(rating_elem, "points", str(rating.get("points", 0)))
    
    return prettify_xml(root)


# ============================================================================
# Common Cartridge Manifest
# ============================================================================

def generate_manifest(export: CartridgeExport) -> str:
    """Generate the imsmanifest.xml file."""
    # For Common Cartridge, we need precise control over namespace declarations.
    # ElementTree's namespace handling can be tricky, so we'll build the XML
    # with explicit namespace prefixes where needed.
    
    # Register the default namespace
    ET.register_namespace('', NS["imscc"])
    ET.register_namespace('lom', NS["lom"])
    ET.register_namespace('lomimscc', NS["lomimscc"])
    ET.register_namespace('xsi', NS["xsi"])
    
    # Create root with default namespace using Clark notation
    nsmap_imscc = NS["imscc"]
    manifest = ET.Element(f"{{{nsmap_imscc}}}manifest")
    manifest.set("identifier", export.identifier)
    manifest.set(f"{{{NS['xsi']}}}schemaLocation",
                 "http://www.imsglobal.org/xsd/imsccv1p3/imscp_v1p1 " +
                 "http://www.imsglobal.org/profile/cc/ccv1p3/ccv1p3_imscp_v1p2_v1p0.xsd")
    
    # Metadata (in default namespace)
    metadata = ET.SubElement(manifest, f"{{{nsmap_imscc}}}metadata")
    schema = ET.SubElement(metadata, f"{{{nsmap_imscc}}}schema")
    schema.text = "IMS Common Cartridge"
    schemaversion = ET.SubElement(metadata, f"{{{nsmap_imscc}}}schemaversion")
    schemaversion.text = "1.3.0"
    
    # LOM metadata (in lomimscc namespace)
    lom = ET.SubElement(metadata, f"{{{NS['lomimscc']}}}lom")
    general = ET.SubElement(lom, f"{{{NS['lomimscc']}}}general")
    title_elem = ET.SubElement(general, f"{{{NS['lomimscc']}}}title")
    string_elem = ET.SubElement(title_elem, f"{{{NS['lomimscc']}}}string")
    string_elem.set("language", "en-US")
    string_elem.text = export.title
    
    # Organizations (in default namespace)
    organizations = ET.SubElement(manifest, f"{{{nsmap_imscc}}}organizations")
    organization = ET.SubElement(organizations, f"{{{nsmap_imscc}}}organization")
    organization.set("identifier", "org1")
    organization.set("structure", "rooted-hierarchy")
    
    # Add modules as items
    for module in export.modules:
        add_module_to_org(organization, module, export, nsmap_imscc)
    
    # Resources
    resources = ET.SubElement(manifest, f"{{{nsmap_imscc}}}resources")
    
    # Add content resources
    for item in export.content_items:
        add_content_resource(resources, item, nsmap_imscc)
    
    # Add quiz resources
    for quiz in export.quizzes:
        add_quiz_resource(resources, quiz, nsmap_imscc)
    
    # Add asset resources
    for asset in export.assets:
        add_asset_resource(resources, asset, nsmap_imscc)
    
    return prettify_xml(manifest)


def add_module_to_org(organization: ET.Element, module: ModuleItem, export: CartridgeExport, ns: str):
    """Add a module structure to the organization."""
    item = ET.SubElement(organization, f"{{{ns}}}item")
    item.set("identifier", module.identifier)
    
    title = ET.SubElement(item, f"{{{ns}}}title")
    title.text = module.title
    
    # Add content items in this module
    for content_id in module.items:
        content_item = next((c for c in export.content_items if c.identifier == content_id), None)
        if content_item:
            sub_item = ET.SubElement(item, f"{{{ns}}}item")
            sub_item.set("identifier", f"item_{content_id}")
            sub_item.set("identifierref", content_id)
            
            sub_title = ET.SubElement(sub_item, f"{{{ns}}}title")
            sub_title.text = content_item.title


def add_content_resource(resources: ET.Element, item: ContentItem, ns: str):
    """Add a content item as a resource."""
    resource = ET.SubElement(resources, f"{{{ns}}}resource")
    resource.set("identifier", item.identifier)
    resource.set("type", get_resource_type(item.item_type))
    
    if item.item_type == "link":
        resource.set("href", item.meta.get("external_url", ""))
    elif item.item_type == "assignment":
        # Assignments point to assignment.xml as primary resource
        resource.set("href", f"web_resources/{item.identifier}/assignment.xml")
    else:
        resource.set("href", f"web_resources/{item.identifier}/content.html")
    
    # Add file references
    if item.item_type == "link":
        pass  # Links don't have files
    elif item.item_type == "assignment":
        # Assignment XML is the primary file
        file_elem = ET.SubElement(resource, f"{{{ns}}}file")
        file_elem.set("href", f"web_resources/{item.identifier}/assignment.xml")
        # Also include the HTML content
        file_elem = ET.SubElement(resource, f"{{{ns}}}file")
        file_elem.set("href", f"web_resources/{item.identifier}/content.html")
        # Add rubric file if present
        if item.rubric:
            file_elem = ET.SubElement(resource, f"{{{ns}}}file")
            file_elem.set("href", f"web_resources/{item.identifier}/rubric.xml")
    else:
        file_elem = ET.SubElement(resource, f"{{{ns}}}file")
        file_elem.set("href", f"web_resources/{item.identifier}/content.html")


def add_quiz_resource(resources: ET.Element, quiz: QuizItem, ns: str):
    """Add a quiz as a resource."""
    resource = ET.SubElement(resources, f"{{{ns}}}resource")
    resource.set("identifier", quiz.identifier)
    resource.set("type", "imsqti_xmlv1p2/imscc_xmlv1p3/assessment")
    resource.set("href", f"assessments/{quiz.identifier}/assessment.xml")
    
    file_elem = ET.SubElement(resource, f"{{{ns}}}file")
    file_elem.set("href", f"assessments/{quiz.identifier}/assessment.xml")


def add_asset_resource(resources: ET.Element, asset: Path, ns: str):
    """Add an asset file as a resource."""
    asset_id = f"asset_{hashlib.md5(str(asset).encode()).hexdigest()[:12]}"
    rel_path = asset.relative_to(ASSETS_DIR)
    
    resource = ET.SubElement(resources, f"{{{ns}}}resource")
    resource.set("identifier", asset_id)
    resource.set("type", "webcontent")
    resource.set("href", f"web_resources/assets/{rel_path}")
    
    file_elem = ET.SubElement(resource, f"{{{ns}}}file")
    file_elem.set("href", f"web_resources/assets/{rel_path}")


def get_resource_type(item_type: str) -> str:
    """Map Zaphod item types to CC resource types."""
    type_map = {
        "page": "webcontent",
        # Canvas expects this specific type for assignments
        "assignment": "associatedcontent/imscc_xmlv1p3/learning-application-resource",
        "link": "imswl_xmlv1p3",
        "file": "webcontent",
    }
    return type_map.get(item_type, "webcontent")


# ============================================================================
# Assignment XML Generation
# ============================================================================

def generate_assignment_xml(item: ContentItem) -> str:
    """Generate assignment XML for Common Cartridge (Canvas-compatible)."""
    # Canvas uses a specific assignment settings format
    root = ET.Element("assignment")
    root.set("xmlns", "http://canvas.instructure.com/xsd/cccv1p0")
    root.set("xmlns:xsi", NS["xsi"])
    root.set("identifier", item.identifier)
    
    add_text_element(root, "title", item.title)
    
    # Description with HTML content
    add_text_element(root, "description", item.source_html, texttype="text/html")
    
    # Assignment settings from metadata
    meta = item.meta
    
    if meta.get("points_possible"):
        add_text_element(root, "points_possible", str(meta["points_possible"]))
    
    # Grading type
    add_text_element(root, "grading_type", meta.get("grading_type", "points"))
    
    # Submission types - Canvas format
    if meta.get("submission_types"):
        sub_types = meta["submission_types"]
        if isinstance(sub_types, list):
            add_text_element(root, "submission_types", ",".join(sub_types))
        else:
            add_text_element(root, "submission_types", str(sub_types))
    else:
        add_text_element(root, "submission_types", "online_upload")
    
    # Allowed extensions
    if meta.get("allowed_extensions"):
        exts = meta["allowed_extensions"]
        if isinstance(exts, list):
            add_text_element(root, "allowed_extensions", ",".join(exts))
        else:
            add_text_element(root, "allowed_extensions", str(exts))
    
    # Position/workflow
    add_text_element(root, "position", str(meta.get("position", 1)))
    add_text_element(root, "workflow_state", "published" if meta.get("published") else "unpublished")
    
    # Add rubric reference if present
    if item.rubric:
        rubric_ref = ET.SubElement(root, "rubric_identifierref")
        rubric_ref.text = f"{item.identifier}_rubric"
    
    return prettify_xml(root)


# ============================================================================
# Web Link XML Generation
# ============================================================================

def generate_weblink_xml(item: ContentItem) -> str:
    """Generate web link XML for Common Cartridge."""
    root = ET.Element("webLink")
    root.set("xmlns", "http://www.imsglobal.org/xsd/imsccv1p3/imswl_v1p3")
    root.set("xmlns:xsi", NS["xsi"])
    
    add_text_element(root, "title", item.title)
    
    url_elem = ET.SubElement(root, "url")
    url_elem.set("href", item.meta.get("external_url", ""))
    
    if item.meta.get("new_tab"):
        url_elem.set("target", "_blank")
    
    return prettify_xml(root)


# ============================================================================
# Content HTML Generation
# ============================================================================

def generate_content_html(item: ContentItem) -> str:
    """Generate HTML file for a content item."""
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{html.escape(item.title)}</title>
</head>
<body>
{item.source_html}
</body>
</html>
"""


# ============================================================================
# Cartridge Builder
# ============================================================================

def build_cartridge(export: CartridgeExport, output_path: Path):
    """Build the complete Common Cartridge ZIP file."""
    # Create temporary directory for building
    temp_dir = output_path.parent / f".{output_path.stem}_temp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)
    
    try:
        # Create directory structure
        (temp_dir / "web_resources").mkdir()
        (temp_dir / "assessments").mkdir()
        
        # Generate manifest
        manifest_content = generate_manifest(export)
        (temp_dir / "imsmanifest.xml").write_text(manifest_content, encoding="utf-8")
        print(f"[cartridge] Generated imsmanifest.xml")
        
        # Generate content items
        for item in export.content_items:
            item_dir = temp_dir / "web_resources" / item.identifier
            item_dir.mkdir(parents=True, exist_ok=True)
            
            if item.item_type == "link":
                # Web links get their own XML
                weblink_xml = generate_weblink_xml(item)
                (item_dir / "weblink.xml").write_text(weblink_xml, encoding="utf-8")
            elif item.item_type == "assignment":
                # Assignments get assignment XML + HTML content
                assignment_xml = generate_assignment_xml(item)
                (item_dir / "assignment.xml").write_text(assignment_xml, encoding="utf-8")
                
                content_html = generate_content_html(item)
                (item_dir / "content.html").write_text(content_html, encoding="utf-8")
                
                if item.rubric:
                    rubric_xml = generate_rubric_xml(item.rubric, item.identifier)
                    (item_dir / "rubric.xml").write_text(rubric_xml, encoding="utf-8")
            else:
                # Pages and files get HTML content
                content_html = generate_content_html(item)
                (item_dir / "content.html").write_text(content_html, encoding="utf-8")
            
            print(f"[cartridge] Generated {item.item_type}: {item.title}")
        
        # Generate quizzes
        for quiz in export.quizzes:
            quiz_dir = temp_dir / "assessments" / quiz.identifier
            quiz_dir.mkdir(parents=True, exist_ok=True)
            
            qti_xml = generate_qti_assessment(quiz)
            (quiz_dir / "assessment.xml").write_text(qti_xml, encoding="utf-8")
            print(f"[cartridge] Generated quiz: {quiz.title} ({len(quiz.questions)} questions)")
        
        # Copy assets
        if export.assets:
            assets_dir = temp_dir / "web_resources" / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            
            for asset in export.assets:
                rel_path = asset.relative_to(ASSETS_DIR)
                dest_path = assets_dir / rel_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(asset, dest_path)
            
            print(f"[cartridge] Copied {len(export.assets)} asset files")
        
        # Create ZIP file
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in temp_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(temp_dir)
                    zf.write(file_path, arcname)
        
        print(f"\n[cartridge] âœ“ Created {output_path}")
        print(f"[cartridge]   Size: {output_path.stat().st_size / 1024:.1f} KB")
        
    finally:
        # Cleanup
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Export Zaphod course to IMS Common Cartridge format"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output file path (default: course_export.imscc)"
    )
    parser.add_argument(
        "--title", "-t",
        help="Course title (default: from zaphod.yaml or folder name)"
    )
    args = parser.parse_args()
    
    # Determine course title
    title = args.title
    if not title:
        # Try to load from zaphod.yaml
        config_file = COURSE_ROOT / "zaphod.yaml"
        if config_file.is_file():
            try:
                config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
                title = config.get("title") or config.get("course_name")
            except Exception:
                pass
        if not title:
            title = COURSE_ROOT.name
    
    # Determine output path
    output_path = args.output
    if not output_path:
        output_path = EXPORTS_DIR / f"{COURSE_ROOT.name}_export.imscc"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"[cartridge] Exporting course: {title}")
    print(f"[cartridge] Output: {output_path}")
    print()
    
    # Load all content
    print("[cartridge] Loading content...")
    content_items = load_content_items()
    print(f"[cartridge]   {len(content_items)} content items")
    
    quizzes = load_quizzes()
    print(f"[cartridge]   {len(quizzes)} quizzes")
    
    outcomes = load_outcomes()
    print(f"[cartridge]   {len(outcomes)} learning outcomes")
    
    modules = load_module_structure(content_items)
    print(f"[cartridge]   {len(modules)} modules")
    
    assets = collect_assets()
    print(f"[cartridge]   {len(assets)} asset files")
    print()
    
    # Create export package
    export = CartridgeExport(
        title=title,
        identifier=f"cc_{hashlib.md5(title.encode()).hexdigest()[:12]}",
        content_items=content_items,
        quizzes=quizzes,
        outcomes=outcomes,
        modules=modules,
        assets=assets,
    )
    
    # Build the cartridge
    print("[cartridge] Building cartridge...")
    build_cartridge(export, output_path)


if __name__ == "__main__":
    main()
