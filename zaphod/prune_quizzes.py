#!/usr/bin/env python3
"""
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

prune_quizzes.py (Zaphod)

Prune quiz content for the current course:

1) Delete Classic quizzes that are not backed by a local .quiz/ folder.
2) Delete question banks whose names do not correspond to any
   quiz-banks/*.bank.md or quiz-banks/*.quiz.txt file.

This script does NOT modify quiz import logic; it only inspects Canvas
state vs local content.

Env:
    CANVAS_CREDENTIAL_FILE
    COURSE_ID
    ZAPHOD_PRUNE_APPLY          (optional; falsey => dry-run, otherwise apply)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Any, Set

import yaml
from canvasapi import Canvas

from zaphod.config_utils import get_course_id

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_ROOT = SCRIPT_DIR.parent
COURSE_ROOT = Path.cwd()
QUIZ_BANKS_DIR = COURSE_ROOT / "quiz-banks"
CONTENT_DIR = COURSE_ROOT / "content"
PAGES_DIR = COURSE_ROOT / "pages"  # Legacy fallback


def get_content_dir() -> Path:
    """Get content directory, preferring content/ over pages/."""
    if CONTENT_DIR.exists():
        return CONTENT_DIR
    return PAGES_DIR


def _truthy_env(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.lower() in {"1", "true", "yes", "on"}


def load_canvas() -> Canvas:
    """
    Load Canvas API client safely.
    
    SECURITY: Uses safe parsing instead of exec() to prevent code injection.
    """
    import re
    import stat
    
    # Try environment variables first
    env_key = os.environ.get("CANVAS_API_KEY")
    env_url = os.environ.get("CANVAS_API_URL")
    if env_key and env_url:
        return Canvas(env_url, env_key)
    
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
    content = cred_file.read_text(encoding="utf-8")
    
    api_key = None
    api_url = None
    
    # Match API_KEY = "value" or API_KEY = 'value' or API_KEY = value
    for pattern in [r'API_KEY\s*=\s*["\']([^"\']+)["\']', r'API_KEY\s*=\s*(\S+)']:
        match = re.search(pattern, content)
        if match:
            api_key = match.group(1).strip().strip('"\'')
            break
    
    for pattern in [r'API_URL\s*=\s*["\']([^"\']+)["\']', r'API_URL\s*=\s*(\S+)']:
        match = re.search(pattern, content)
        if match:
            api_url = match.group(1).strip().strip('"\'')
            break
    
    if not api_key or not api_url:
        raise SystemExit(
            f"Credentials file must define API_KEY and API_URL: {cred_file}"
        )
    
    # Check file permissions
    try:
        mode = os.stat(cred_file).st_mode
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            print(f"[prune:SECURITY] Credentials file has insecure permissions: {cred_file}")
            print(f"[prune:SECURITY] Fix with: chmod 600 {cred_file}")
    except OSError:
        pass

    return Canvas(api_url, api_key)


def get_local_quiz_names() -> Set[str]:
    """
    Get quiz names from local .quiz/ folders by reading their meta.json or index.md.
    
    Searches for quiz content in:
    1. content/**/*.quiz/ directories (or pages/**/*.quiz/ for legacy)
    2. Reads name from meta.json or index.md frontmatter
    """
    names: Set[str] = set()
    content_dir = get_content_dir()
    if not content_dir.is_dir():
        return names

    for quiz_path in content_dir.rglob("*.quiz"):
        # Only process directories (quiz folders, not files)
        if not quiz_path.is_dir():
            continue
        
        quiz_folder = quiz_path
        
        # Try meta.json first
        meta_path = quiz_folder / "meta.json"
        if meta_path.exists():
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                name = data.get("name")
                if name:
                    names.add(name)
                    print(f"[prune:quiz]   Found quiz '{name}' from {quiz_folder.relative_to(content_dir)}/meta.json")
                    continue
            except Exception:
                pass
        
        # Fall back to index.md frontmatter
        index_path = quiz_folder / "index.md"
        if index_path.exists():
            try:
                content = index_path.read_text(encoding="utf-8")
                if content.startswith("---"):
                    end_idx = content.find("---", 3)
                    if end_idx > 0:
                        fm = yaml.safe_load(content[3:end_idx])
                        if isinstance(fm, dict):
                            name = fm.get("name")
                            if name:
                                names.add(name)
                                print(f"[prune:quiz]   Found quiz '{name}' from {quiz_folder.relative_to(content_dir)}/index.md")
                                continue
            except Exception:
                pass
        
        # If no name found in meta or frontmatter, derive from folder name
        # This ensures we don't prune quizzes that exist locally but lack metadata
        folder_stem = quiz_folder.stem  # e.g., "my-quiz" from "my-quiz.quiz"
        # Convert to title case (e.g., "my-quiz" -> "My Quiz")
        inferred_name = folder_stem.replace('-', ' ').replace('_', ' ').title()
        names.add(inferred_name)
        print(f"[prune:quiz]   Found quiz '{inferred_name}' (inferred from folder: {quiz_folder.relative_to(content_dir)})")
    
    return names


def get_local_bank_names() -> Set[str]:
    """
    Get expected bank names from quiz-banks/*.bank.md and *.quiz.txt files.
    
    Bank names are the file stems (e.g., "chapter1.bank" from "chapter1.bank.md").
    """
    names: Set[str] = set()
    if not QUIZ_BANKS_DIR.is_dir():
        return names

    # New format: *.bank.md
    for path in QUIZ_BANKS_DIR.glob("*.bank.md"):
        names.add(path.stem)  # "chapter1.bank"
    
    # Legacy format: *.quiz.txt
    for path in QUIZ_BANKS_DIR.glob("*.quiz.txt"):
        names.add(path.stem)  # "week1.quiz"
    
    return names


def prune_orphan_quizzes(course, local_names: Set[str], apply: bool):
    """
    Delete quizzes that don't have a corresponding local .quiz/ folder.
    """
    print("[prune:quiz] Checking for orphan quizzes...")
    print(f"[prune:quiz] Local quiz names: {sorted(local_names)}")
    
    scanned = 0
    deleted = 0

    for quiz in course.get_quizzes():
        scanned += 1
        
        if quiz.title in local_names:
            continue
        
        msg = f"[prune:quiz] Orphan quiz '{quiz.title}' (id={quiz.id})"
        if apply:
            quiz.delete()
            print(msg + " -> deleted")
            deleted += 1
        else:
            print(msg + " -> would delete")

    print(f"[prune:quiz] Scanned {scanned} quizzes, deleted {deleted} orphans.")


def prune_stale_banks(course, local_names: Set[str], apply: bool):
    """
    Delete question banks whose names do not match any local bank file.
    """
    print(f"[prune:banks] Local bank names: {sorted(local_names)}")

    if not local_names:
        print("[prune:banks] No local bank files; skipping bank prune.")
        return

    try:
        banks = list(course.get_question_banks())
    except AttributeError:
        print("[prune:banks] course.get_question_banks() not available; skipping.")
        return

    deleted = 0
    for bank in banks:
        name = getattr(bank, "title", "") or getattr(bank, "name", "") or ""
        if name in local_names:
            continue

        msg = f"[prune:banks] Stale bank '{name}' (id={bank.id})"
        if apply:
            try:
                bank.delete()
                print(msg + " -> deleted")
                deleted += 1
            except Exception as e:
                print(msg + f" -> failed: {e}")
        else:
            print(msg + " -> would delete")

    print(f"[prune:banks] Deleted {deleted} stale banks.")


def main():
    course_id = get_course_id()
    if not course_id:
        raise SystemExit("COURSE_ID is not set")

    # Default: apply deletions unless explicitly disabled.
    apply = _truthy_env("ZAPHOD_PRUNE_APPLY", default=True)

    canvas = load_canvas()
    course = canvas.get_course(int(course_id))

    print(f"[prune:quiz] Pruning quiz content in course {course_id} (apply={apply})")

    # Get local quiz and bank names
    local_quiz_names = get_local_quiz_names()
    local_bank_names = get_local_bank_names()

    # Prune orphan quizzes (not backed by local .quiz/ folder)
    prune_orphan_quizzes(course, local_quiz_names, apply=apply)
    
    # Prune stale banks (not backed by local bank file)
    prune_stale_banks(course, local_bank_names, apply=apply)

    print("[prune:quiz] Done.")


if __name__ == "__main__":
    main()
