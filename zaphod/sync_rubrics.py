#!/usr/bin/env python3

"""
Zaphod

sync_rubrics.py

For the current course (cwd):

- Finds all .assignment folders under pages/
- If rubric.yaml / rubric.yml / rubric.json exists in a folder, loads it (YAML/JSON)
- Uses meta.json to identify the assignment in Canvas
- Creates a rubric via the Rubrics API from the YAML/JSON spec
- Associates that rubric with the assignment using RubricAssociations semantics

Extended behavior:

- Supports course-level shared rubrics in rubrics/<n>.yaml|yml|json
  referenced from assignment rubric.yaml via:

    use_rubric: "<n>"

- Supports reusable rubric rows in rubrics/rows/<identifier>.yaml|yml|json,
  referenced from criteria via:

    - "{{rubric_row:identifier}}"

Assumptions

- Run from course root (where pages/ lives).
- Env:

  CANVAS_CREDENTIAL_FILE=$HOME/.canvas/credentials.txt
  COURSE_ID=canvas course id

- Credentials file defines:

  API_KEY = "..."
  API_URL = "https://yourcanvas.institution.edu"
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import requests
import yaml
from zaphod.config_utils import get_course_id
from zaphod.canvas_client import make_canvas_api_obj, get_canvas_credentials
from canvasapi import Canvas
from canvasapi.course import Course
from zaphod.errors import (
    rubric_validation_error,
    CanvasAPIError,
)


SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_ROOT = SCRIPT_DIR.parent
COURSE_ROOT = Path.cwd()
CONTENT_DIR = COURSE_ROOT / "content"
PAGES_DIR = COURSE_ROOT / "pages"  # Legacy fallback

# New: shared rubric locations
RUBRICS_DIR = COURSE_ROOT / "rubrics"
RUBRIC_ROWS_DIR = RUBRICS_DIR / "rows"

# Outcome mapping locations
OUTCOME_MAP_PATHS = [
    COURSE_ROOT / "_course_metadata" / "outcome_map.json",
    COURSE_ROOT / "outcomes" / "outcome_map.json",
]

# New: placeholder pattern for row includes
RUBRIC_ROW_REF_RE = re.compile(r"^\s*\{\{\s*rubric_row:([a-zA-Z0-9_\-]+)\s*\}\}\s*$")

# Cache for outcome map (loaded once per run)
_outcome_map_cache: Dict[str, int] | None = None


def load_outcome_map() -> Dict[str, int]:
    """
    Load outcome map that translates outcome codes (e.g., CLO1) to Canvas outcome IDs.
    
    Searches in:
    1. _course_metadata/outcome_map.json
    2. outcomes/outcome_map.json
    
    Returns:
        Dict mapping outcome codes to Canvas outcome IDs
    """
    global _outcome_map_cache
    if _outcome_map_cache is not None:
        return _outcome_map_cache
    
    for path in OUTCOME_MAP_PATHS:
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    # Convert all values to int
                    _outcome_map_cache = {str(k): int(v) for k, v in data.items()}
                    print(f"[rubrics] Loaded outcome map from {path} ({len(_outcome_map_cache)} outcomes)")
                    return _outcome_map_cache
            except Exception as e:
                print(f"[rubrics:warn] Failed to load outcome map from {path}: {e}")
    
    _outcome_map_cache = {}
    return _outcome_map_cache


def get_content_dir() -> Path:
    """Get content directory, preferring content/ over pages/."""
    if CONTENT_DIR.exists():
        return CONTENT_DIR
    return PAGES_DIR


# ---------- Canvas helpers ----------
# Note: Credential loading now uses centralized canvas_client.py


# ---------- Local file helpers ----------


def iter_assignment_folders_with_rubrics() -> List[Path]:
    """
    Find all .assignment folders that contain a rubric file.
    """
    content_dir = get_content_dir()
    if not content_dir.exists():
        return []

    folders: List[Path] = []
    for folder in content_dir.rglob("*.assignment"):
        if not folder.is_dir():
            continue
        if find_rubric_file(folder) is not None:
            folders.append(folder)

    return folders


def find_rubric_file(folder: Path) -> Optional[Path]:
    """
    Look for rubric.yaml / rubric.yml / rubric.json in the folder.
    """
    candidates = [
        folder / "rubric.yaml",
        folder / "rubric.yml",
        folder / "rubric.json",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def load_meta(folder: Path) -> Dict[str, Any]:
    meta_path = folder / "meta.json"
    if not meta_path.is_file():
        raise FileNotFoundError(f"No meta.json in folder {folder}")
    with meta_path.open(encoding="utf-8") as f:
        return json.load(f)


def find_assignment_by_name(course: Course, name: str):
    """
    Find a Canvas assignment with a title matching name.
    """
    for a in course.get_assignments():
        if a.name == name:
            return a
    return None


# ---------- Shared rubric helpers ----------


def load_shared_rubric(name: str) -> Dict[str, Any]:
    """
    Load a shared rubric spec from rubrics/<n>.(yaml|yml|json).
    """
    if not RUBRICS_DIR.exists():
        raise FileNotFoundError(f"No rubrics directory at {RUBRICS_DIR}")

    for ext in (".yaml", ".yml", ".json"):
        path = RUBRICS_DIR / f"{name}{ext}"
        if path.is_file():
            return _load_rubric_mapping(path)

    raise FileNotFoundError(f"Shared rubric {name!r} not found under {RUBRICS_DIR}")


def load_rubric_row_snippet(identifier: str) -> List[Dict[str, Any]]:
    """
    Load one or more criteria rows from rubrics/rows/<identifier>.(yaml|yml|json).
    Always returns a list of criterion dicts.
    """
    if not RUBRIC_ROWS_DIR.exists():
        raise FileNotFoundError(f"No rubric rows directory at {RUBRIC_ROWS_DIR}")

    for ext in (".yaml", ".yml", ".json"):
        path = RUBRIC_ROWS_DIR / f"{identifier}{ext}"
        if path.is_file():
            if ext in (".yaml", ".yml"):
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
            else:
                data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return [data]
            if isinstance(data, list):
                return data
            raise RuntimeError(f"Rubric row snippet {path} must be a dict or list.")

    raise FileNotFoundError(
        f"Rubric row snippet not found for {identifier!r} under {RUBRIC_ROWS_DIR}"
    )


def expand_rubric_criteria(criteria: List[Any]) -> List[Dict[str, Any]]:
    """
    Expand {{rubric_row:identifier}} entries into full criterion dicts.
    Leaves existing criterion dicts (aligned or not) unchanged.
    """
    expanded: List[Dict[str, Any]] = []
    for crit in criteria:
        if isinstance(crit, str):
            m = RUBRIC_ROW_REF_RE.match(crit)
            if m:
                ident = m.group(1)
                rows = load_rubric_row_snippet(ident)
                expanded.extend(rows)
                continue
            raise RuntimeError(f"Unexpected string in criteria: {crit!r}")
        # assume dict / already-valid criterion
        expanded.append(crit)
    return expanded


# ---------- Rubric YAML/JSON loading ----------


def _load_rubric_mapping(path: Path) -> Dict[str, Any]:
    """
    Load a rubric file and ensure it is a mapping (YAML/JSON object).
    """
    try:
        if path.suffix.lower() in (".yaml", ".yml"):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        elif path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            raise ValueError(f"Unsupported rubric file extension {path.suffix}")
    except Exception as e:
        raise RuntimeError(f"Failed to parse rubric file {path}: {e}")

    if not isinstance(data, dict):
        raise RuntimeError(f"Rubric spec {path} must be a mapping (YAML/JSON object).")

    return data


def load_rubric_spec(path: Path) -> Dict[str, Any]:
    """
    Load rubric spec from YAML or JSON file.

    If the loaded spec has a 'use_rubric' key, treat it as an alias to
    rubrics/<use_rubric>.(yaml|yml|json).
    """
    data = _load_rubric_mapping(path)

    shared_name = data.get("use_rubric")
    if shared_name:
        if not isinstance(shared_name, str):
            raise RuntimeError(
                f"'use_rubric' must be a string in {path}, got {type(shared_name)}"
            )
        return load_shared_rubric(shared_name)

    return data


def build_rubric_payload(
    rubric: Dict[str, Any],
    assignment,
    rubric_file: Path = None,
) -> Dict[str, Any]:
    """
    Turn a rubric spec (YAML/JSON) into Canvas API payload.
    
    Args:
        rubric: The rubric specification dict
        assignment: Canvas assignment object
        rubric_file: Path to rubric file (for error messages)
    """
    rubric_file = rubric_file or Path("rubric.yaml")
    
    title = rubric.get("title")
    if not title:
        raise rubric_validation_error(
            rubric_file=rubric_file,
            issues=["Missing 'title' field"]
        )

    criteria = rubric.get("criteria") or []
    if not criteria:
        raise rubric_validation_error(
            rubric_file=rubric_file,
            issues=["Missing or empty 'criteria' list"]
        )

    # Validate each criterion
    issues = []
    for i, crit in enumerate(criteria):
        c_desc = crit.get("description")
        c_points = crit.get("points")
        ratings = crit.get("ratings") or []

        if not c_desc:
            issues.append(f"Criterion {i}: Missing 'description'")
        if c_points is None:
            issues.append(f"Criterion {i}: Missing 'points'")
        if not ratings:
            issues.append(f"Criterion {i}: Missing or empty 'ratings'")
        
        for j, rating in enumerate(ratings):
            if not rating.get("description"):
                issues.append(f"Criterion {i}, Rating {j}: Missing 'description'")
            if rating.get("points") is None:
                issues.append(f"Criterion {i}, Rating {j}: Missing 'points'")
    
    if issues:
        raise rubric_validation_error(
            rubric_file=rubric_file,
            issues=issues
        )

    # Expand any {{rubric_row:...}} references
    criteria = expand_rubric_criteria(criteria)

    free_form = bool(rubric.get("free_form_criterion_comments", False))
    assoc_cfg = rubric.get("association") or {}

    # Association is always to an Assignment in this script
    assoc_type = "Assignment"
    assoc_id = str(assoc_cfg.get("id") or assignment.id)
    assoc_purpose = assoc_cfg.get("purpose", "grading")
    assoc_use_for_grading = bool(assoc_cfg.get("use_for_grading", True))

    data: Dict[str, Any] = {
        "title": title,
        "rubric_id": "new",
        "rubric[title]": title,
        "rubric[free_form_criterion_comments]": "1" if free_form else "0",
        "rubric_association[association_type]": assoc_type,
        "rubric_association[association_id]": assoc_id,
        "rubric_association[use_for_grading]": "1" if assoc_use_for_grading else "0",
        "rubric_association[purpose]": assoc_purpose,
        "rubric_association[title]": assignment.name,
    }

    for i, crit in enumerate(criteria):
        c_desc = crit.get("description")
        c_long = crit.get("long_description", "")
        c_points = crit.get("points")
        c_use_range = bool(crit.get("use_range", False))
        c_outcome_code = crit.get("outcome_code")  # NEW: outcome alignment
        ratings = crit.get("ratings") or []

        if c_desc is None or c_points is None or not ratings:
            raise SystemExit(
                f"Criterion {i} must define 'description', 'points', and non-empty 'ratings'."
            )

        base = f"rubric[criteria][{i}]"
        data[f"{base}[description]"] = str(c_desc)
        data[f"{base}[long_description]"] = str(c_long)
        data[f"{base}[points]"] = str(c_points)
        data[f"{base}[criterion_use_range]"] = "1" if c_use_range else "0"
        
        # NEW: Add learning outcome association if outcome_code is specified
        if c_outcome_code:
            outcome_map = load_outcome_map()
            outcome_id = outcome_map.get(str(c_outcome_code))
            if outcome_id:
                data[f"{base}[learning_outcome_id]"] = str(outcome_id)
                print(f"    [outcome] Criterion '{c_desc}' aligned to {c_outcome_code} (ID {outcome_id})")
            else:
                print(f"    [outcome:warn] Criterion '{c_desc}' references unknown outcome '{c_outcome_code}'")
                print(f"                   Add it to outcome_map.json: {{\"{c_outcome_code}\": <canvas_outcome_id>}}")

        for j, rating in enumerate(ratings):
            r_desc = rating.get("description")
            r_long = rating.get("long_description", "")
            r_points = rating.get("points")

            if r_desc is None or r_points is None:
                raise SystemExit(
                    f"Criterion {i} rating {j} must define 'description' and 'points'."
                )

            rbase = f"{base}[ratings][{j}]"
            data[f"{rbase}[description]"] = str(r_desc)
            data[f"{rbase}[long_description]"] = str(r_long)
            data[f"{rbase}[points]"] = str(r_points)

    return data


# ---------- Rubric creation ----------


def create_rubric_via_api(
    course_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    POST /api/v1/courses/:course_id/rubrics using the provided payload.
    
    Includes rate limiting to avoid hitting Canvas API limits.
    """
    from zaphod.security_utils import get_rate_limiter, mask_sensitive, DEFAULT_TIMEOUT
    
    # Rate limit check
    get_rate_limiter().wait_if_needed()
    
    api_url, api_key = get_canvas_credentials()  # From canvas_client
    url = f"{api_url}/api/v1/courses/{course_id}/rubrics"
    headers = {"Authorization": f"Bearer {api_key}"}

    resp = requests.post(url, headers=headers, data=payload, timeout=DEFAULT_TIMEOUT)
    
    # Check rate limit headers
    get_rate_limiter().check_response_headers(dict(resp.headers))

    if resp.status_code in (200, 201):
        return resp.json()

    if resp.status_code == 403 and 'rate limit' in resp.text.lower():
        get_rate_limiter().handle_rate_limit_response()
        raise RuntimeError("Rate limit exceeded. Please wait and try again.")

    if resp.status_code in (401, 403):
        raise RuntimeError("Not authorized to create rubrics (token/role lacks permission).")

    if resp.status_code == 404:
        raise RuntimeError("Rubrics endpoint not reachable (bad course id, base URL, or API disabled).")

    if resp.status_code == 422:
        raise RuntimeError(f"Rubric validation error (422): {resp.text}")

    raise RuntimeError(f"Unexpected status {resp.status_code}: {resp.text}")


# ---------- Per-folder processing ----------


def process_assignment_folder(course: Course, folder: Path):
    rubric_file = find_rubric_file(folder)
    if not rubric_file:
        print(f"[rubrics:skip] {folder.name}: no rubric.yaml/yml/json")
        return

    try:
        meta = load_meta(folder)
    except FileNotFoundError as e:
        print(f"[rubrics:err] {folder.name}: {e}")
        return

    ctype = str(meta.get("type", "")).lower()
    name = meta.get("name")

    if ctype != "assignment":
        print(f"[rubrics:skip] {folder.name}: meta.type is {ctype!r}, expected 'assignment'")
        return

    if not name:
        print(f"[rubrics:err] {folder.name}: meta.json missing 'name'")
        return

    assignment = find_assignment_by_name(course, name)
    if not assignment:
        print(f"[rubrics:err] {folder.name}: assignment name {name!r} not found in Canvas")
        return

    print(
        f"[rubrics] Processing {folder.name}: "
        f"associating rubric to assignment {assignment.id} ({assignment.name})"
    )

    try:
        rubric_spec = load_rubric_spec(rubric_file)
    except Exception as e:
        print(f"[rubrics:err] {folder.name}: failed to load rubric spec: {e}")
        return

    try:
        payload = build_rubric_payload(rubric_spec, assignment, rubric_file)
    except Exception as e:
        print(f"[rubrics:err] {folder.name}: invalid rubric spec: {e}")
        return

    try:
        result = create_rubric_via_api(str(course.id), payload)
        rubric = result.get("rubric") or {}
        rubric_id = rubric.get("id")
        print(f"[rubrics] Created rubric id={rubric_id} for assignment {assignment.id}")
    except Exception as e:
        print(f"[rubrics:err] {folder.name}: failed to create rubric: {e}")


# ---------- Main ----------


def main():
    course_id = get_course_id()
    if not course_id:
        raise SystemExit("COURSE_ID is not set")

    content_dir = get_content_dir()
    if not content_dir.exists():
        raise SystemExit(f"No content directory found. Create content/ or pages/ in {COURSE_ROOT}")

    print(f"[rubrics] Using content directory: {content_dir.name}/")

    canvas = make_canvas_api_obj()  # From canvas_client
    course = canvas.get_course(int(course_id))

    folders = iter_assignment_folders_with_rubrics()
    if not folders:
        print("[rubrics] No .assignment folders with rubric.yaml found under", content_dir)
        return

    print(f"[rubrics] Syncing rubrics for course {course.name} (ID {course_id})")
    for folder in folders:
        process_assignment_folder(course, folder)
        print()

    print("[rubrics] Done.")


if __name__ == "__main__":
    main()
