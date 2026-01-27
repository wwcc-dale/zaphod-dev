#!/usr/bin/env python3
"""
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

watch_and_publish.py (Zaphod)

- Watches pages/**/index.md in the current course for changes.
- On any change, runs the pipeline for only the files that have changed
  since the last run (as far as the downstream scripts support that).

Assumptions:
- You run this from a course root, e.g. ~/courses/test
- Shared layout: ~/courses/zaphod/.venv and ~/courses/zaphod
- Env:
    CANVAS_CREDENTIAL_FILE
    COURSE_ID
    ZAPHOD_PRUNE              (optional, truthy to enable prune step)
    ZAPHOD_PRUNE_APPLY        (optional, truthy to actually delete)
    ZAPHOD_PRUNE_ASSIGNMENTS  (optional, truthy to include assignments)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer
import threading

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_ROOT = SCRIPT_DIR.parent
COURSES_ROOT = SHARED_ROOT.parent
COURSE_ROOT = Path.cwd()
CONTENT_DIR = COURSE_ROOT / "content"
PAGES_DIR = COURSE_ROOT / "pages"  # Legacy fallback
MODULE_ORDER_PATH = COURSE_ROOT / "modules" / "module_order.yaml"

# Centralized metadata directory for all course state
METADATA_DIR = COURSE_ROOT / "_course_metadata"
STATE_FILE = METADATA_DIR / "watch_state.json"

DOT_LINE = "." * 70  # ~70-column visual separator

# Debounce window (seconds) for the whole pipeline
DEBOUNCE_SECONDS = 2.0

# Prevent overlapping runs
PIPELINE_RUNNING = False


def get_content_dir() -> Path:
    """Get content directory, preferring content/ over pages/."""
    if CONTENT_DIR.exists():
        return CONTENT_DIR
    return PAGES_DIR


def find_python_executable() -> str:
    """
    Find the best Python executable to use.
    
    Priority:
    1. .venv/bin/python in SCRIPT_DIR (if exists)
    2. .venv/bin/python in COURSE_ROOT (if exists)  
    3. The same Python running this script (sys.executable)
    """
    # Try venv in script directory
    venv_python = SCRIPT_DIR / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    
    # Try venv in course root
    course_venv = COURSE_ROOT / ".venv" / "bin" / "python"
    if course_venv.exists():
        return str(course_venv)
    
    # Fall back to current Python
    return sys.executable


def fence(label: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(DOT_LINE)
    print(f"[{ts}] {label}")
    print("\n")  # blank line after each phase


def _truthy_env(name: str) -> bool:
    v = os.environ.get(name, "")
    return v.lower() in {"1", "true", "yes", "on"}


# ---------- incremental state helpers ----------

def load_state() -> dict:
    """Load watch state from _course_metadata/watch_state.json"""
    if not STATE_FILE.is_file():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_state(state: dict) -> None:
    """Save watch state to _course_metadata/watch_state.json"""
    try:
        METADATA_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception as e:
        print(f"[watch:warn] Failed to save state: {e}")


def get_last_run_time() -> float:
    state = load_state()
    return float(state.get("last_run_ts", 0.0))


def set_last_run_time(ts: float) -> None:
    state = load_state()
    state["last_run_ts"] = ts

    # Track additional metadata
    if "run_count" not in state:
        state["run_count"] = 0
    state["run_count"] += 1
    state["last_run_datetime"] = datetime.now().isoformat()

    save_state(state)


def get_changed_files_since(last_ts: float) -> list[Path]:
    changed: list[Path] = []
    module_order_path = MODULE_ORDER_PATH


    for path in COURSE_ROOT.rglob("*"):
        if not path.is_file():
            continue

        name = path.name
        if (
            name == "index.md"
            or name == "outcomes.yaml"
            or name.endswith(".quiz.txt")
            or name.endswith(".bank.md")
            or path == module_order_path
            or name in ("rubric.yaml", "rubric.yml", "rubric.json")
        ):
            mtime = path.stat().st_mtime
            if mtime > last_ts:
                changed.append(path)

    return changed


# ---------- pipeline ----------

def run_pipeline(changed_files: list[Path]):
    """
    Run the Zaphod pipeline for the current course, restricted to changed_files.

    Downstream scripts learn about changed_files via the
    ZAPHOD_CHANGED_FILES environment variable (newline-separated paths).
    """
    global PIPELINE_RUNNING
    if PIPELINE_RUNNING:
        print("[watch] PIPELINE already running, skipping this run")
        return

    PIPELINE_RUNNING = True
    try:
        # Find Python executable (with fallback)
        python_exe = find_python_executable()
        print(f"[watch] Using Python: {python_exe}")

        env = os.environ.copy()
        env.setdefault(
            "CANVAS_CREDENTIAL_FILE",
            str(Path.home() / ".canvas" / "credentials.txt"),
        )

        # Export changed file list to children as an env var.
        env["ZAPHOD_CHANGED_FILES"] = "\n".join(str(p) for p in changed_files)

        steps: List[Path] = [
            SCRIPT_DIR / "frontmatter_to_meta.py",
            SCRIPT_DIR / "publish_all.py",
            SCRIPT_DIR / "sync_banks.py",        # Import question banks (before quizzes)
            SCRIPT_DIR / "sync_quizzes.py",      # Create/update quizzes (before modules)
            SCRIPT_DIR / "sync_modules.py",
            SCRIPT_DIR / "sync_clo_via_csv.py",
            SCRIPT_DIR / "sync_rubrics.py",
        ]

        fence("Zaphod pipeline start")
        print("[watch] processing changed files:")
        for p in changed_files:
            try:
                rel = p.relative_to(COURSE_ROOT)
            except ValueError:
                rel = p
            print(f"  - {rel}")
        print()

        for script in steps:
            if not script.is_file():
                print(f"[watch] SKIP missing script: {script}")
                continue
            fence(f"RUNNING: {script.name}")
            subprocess.run(
                [str(python_exe), str(script)],
                cwd=str(COURSE_ROOT),
                env=env,
                check=False,  # do not kill watcher on error
            )

        # Optional prune step at the end (zaphod script)
        prune_apply = _truthy_env("ZAPHOD_PRUNE_APPLY")
        prune_assignments = _truthy_env("ZAPHOD_PRUNE_ASSIGNMENTS")

        prune_script = SCRIPT_DIR / "prune_canvas_content.py"

        if prune_script.is_file():
            args = [str(python_exe), str(prune_script), "--prune"]
            if prune_assignments:
                args.append("--prune-assignments")
            if prune_apply:
                args.append("--apply")

            fence(f"RUNNING: {prune_script.name}")
            subprocess.run(
                args,
                cwd=str(COURSE_ROOT),
                env=env,
                check=False,
            )
        else:
            print(f"[watch] WARN: prune script not found at {prune_script}")

        quiz_prune_script = SCRIPT_DIR / "prune_quizzes.py"
        if quiz_prune_script.is_file():
            fence(f"RUNNING: {quiz_prune_script.name}")
            subprocess.run(
                [str(python_exe), str(quiz_prune_script)],
                cwd=str(COURSE_ROOT),
                env=env,
                check=False,
            )
        else:
            print(f"[watch] WARN: quiz prune script not found at {quiz_prune_script}")

        # Build media manifest (after all prune steps)
        manifest_script = SCRIPT_DIR / "build_media_manifest.py"
        if manifest_script.is_file():
            fence(f"RUNNING: {manifest_script.name}")
            subprocess.run(
                [str(python_exe), str(manifest_script)],
                cwd=str(COURSE_ROOT),
                env=env,
                check=False,
            )

        fence("Zaphod pipeline complete")
    finally:
        PIPELINE_RUNNING = False


# ---------- watchdog handler ----------

class MarkdownChangeHandler(PatternMatchingEventHandler):
    def __init__(self):
        super().__init__(
            patterns=[
                "*/index.md",                    # pages/*/index.md
                "outcomes.yaml",
                "modules/module_order.yaml",
                "*.quiz.txt",                    # Legacy quiz bank format
                "*.bank.md",                     # New question bank format
                "rubric.yaml",
                "rubric.yml",
                "rubric.json",
            ],
            ignore_directories=False,
            case_sensitive=False,
        )
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None
        self._pending_log: bool = True

    def _debounced_run(self):
        last_ts = get_last_run_time()
        changed = get_changed_files_since(last_ts)

        if not changed:
            print("[watch] DEBOUNCED RUN: no files changed since last pipeline, skipping\n")
            with self._lock:
                self._pending_log = True
            return

        print("[watch] DEBOUNCED RUN: starting pipeline")
        run_pipeline(changed)
        set_last_run_time(time.time())

        print("[watch] PIPELINE COMPLETE\n")
        with self._lock:
            # Next burst should log again
            self._pending_log = True

    def _schedule_pipeline(self, src_path: str):
        with self._lock:
            if self._pending_log:
                print(f"[watch] CHANGE DETECTED: {src_path}")
                self._pending_log = False
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(DEBOUNCE_SECONDS, self._debounced_run)
            self._timer.daemon = True
            self._timer.start()

    def on_any_event(self, event):
        if event.is_directory:
            return
        if event.event_type != "modified":
            return
        self._schedule_pipeline(str(event.src_path))


# ---------- main ----------

def main():
    content_dir = get_content_dir()
    if not content_dir.is_dir():
        raise SystemExit(f"content/ or pages/ directory not found under {COURSE_ROOT}")

    fence("WATCH")
    
    # Show which Python will be used
    python_exe = find_python_executable()
    print(f"[watch] Python executable: {python_exe}")

    observer = Observer()
    handler = MarkdownChangeHandler()
    observer.schedule(handler, str(COURSE_ROOT), recursive=True)
    observer.start()

    print(f"[watch] WATCHING: {content_dir} (index.md only)")
    print(f"[watch] COURSE_ROOT: {COURSE_ROOT}")
    print(f"[watch] STATE_FILE: {STATE_FILE}\n")

    # Run initial full sync on startup
    print("[watch] Running initial full sync...")
    all_index_files = list(content_dir.rglob("index.md"))
    if all_index_files:
        run_pipeline(all_index_files)
        set_last_run_time(time.time())
        print("[watch] INITIAL SYNC COMPLETE\n")
    else:
        print("[watch] No index.md files found, skipping initial sync\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n[watch] Stopping...")

        # Save final state with session info
        state = load_state()
        state["watch_stopped"] = datetime.now().isoformat()
        save_state(state)

    observer.join()


if __name__ == "__main__":
    main()