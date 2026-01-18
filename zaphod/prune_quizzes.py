#!/usr/bin/env python3
"""
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

prune_quizzes.py (Zaphod)

Prune quiz content for the current course:

1) Delete Classic quizzes that have zero questions.
2) Delete question banks whose names do not correspond to any
   quiz-banks/*.quiz.txt file.

This script does NOT modify quiz import logic; it only inspects Canvas
state vs local quiz-banks.

Env:
    CANVAS_CREDENTIAL_FILE
    COURSE_ID
    ZAPHOD_PRUNE_APPLY          (optional; falsey => dry-run, otherwise apply)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any, Set
from zaphod.config_utils import get_course_id

from canvasapi import Canvas  # [web:261][web:264]

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_ROOT = SCRIPT_DIR.parent
COURSE_ROOT = Path.cwd()
QUIZ_BANKS_DIR = COURSE_ROOT / "quiz-banks"


def _truthy_env(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.lower() in {"1", "true", "yes", "on"}


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

    return Canvas(api_url, api_key)  # [web:261]


def expected_quiz_stems_from_files() -> Set[str]:
    """
    Derive expected identifiers from quiz-banks/*.quiz.txt.

    For now this is just the filename stem:
        quiz-banks/week1.quiz.txt -> "week1"
    """
    stems: Set[str] = set()
    if not QUIZ_BANKS_DIR.is_dir():
        return stems

    for path in QUIZ_BANKS_DIR.glob("*.quiz.txt"):
        stems.add(path.stem)
    return stems


def prune_empty_quizzes(course, apply: bool):
    """
    Delete Classic quizzes with zero questions.
    """
    print("[prune:quiz] Checking for empty quizzes...")
    scanned = 0
    deleted = 0

    for quiz in course.get_quizzes():  # [web:264]
        scanned += 1
        questions = list(quiz.get_questions())  # [web:261]
        if questions:
            continue

        msg = f"[prune:quiz] EMPTY quiz '{quiz.title}' (id={quiz.id})"
        if apply:
            quiz.delete()
            print(msg + " -> deleted")
            deleted += 1
        else:
            print(msg + " -> would delete")

    print(f"[prune:quiz] Scanned {scanned} quizzes, deleted {deleted} (empty).")


def prune_stale_banks(course, apply: bool):
    """
    Delete question banks whose names do not match any quiz-banks/*.quiz.txt stem.

    This is a coarse heuristic and may be refined later.
    """
    expected_stems = expected_quiz_stems_from_files()
    print(f"[prune:banks] Expected stems from files: {sorted(expected_stems)}")

    if not expected_stems:
        print("[prune:banks] No quiz-banks/*.quiz.txt files; skipping bank prune.")
        return

    try:
        banks = list(course.get_question_banks())  # [web:208][web:221]
    except AttributeError:
        print("[prune:banks] course.get_question_banks() not available; skipping.")
        return

    deleted = 0
    for bank in banks:
        name = getattr(bank, "name", "") or ""
        if name in expected_stems:
            # Still backed by a local file
            continue

        msg = f"[prune:banks] Stale bank '{name}' (id={bank.id})"
        if apply:
            bank.delete()
            print(msg + " -> deleted")
            deleted += 1
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

    prune_empty_quizzes(course, apply=apply)
    prune_stale_banks(course, apply=apply)

    print("[prune:quiz] Done.")


if __name__ == "__main__":
    main()
