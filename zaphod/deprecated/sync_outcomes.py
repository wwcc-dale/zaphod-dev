#!/usr/bin/env python3
"""
sync_outcomes.py (Zaphod, CLO-only)

For the current course (cwd):

- Reads _course_metadata/outcomes.yaml
- Ignores institution_outcomes and program_outcomes (no admin access needed)
- Creates course-level outcomes (CLOs) directly for the course via Outcomes API
- Writes _course_metadata/outcome_map.json mapping CLO codes to outcome IDs

Assumptions:
- Env:
    CANVAS_CREDENTIAL_FILE=/home/chapman/.canvas/credentials.txt
    COURSE_ID=<canvas course id>
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Any, List

import yaml  # pip install pyyaml
from canvasapi import Canvas  # [web:282][web:431]


# Shared layout paths
SCRIPT_DIR = Path(__file__).resolve().parent          # .../courses/zaphod/scripts
SHARED_ROOT = SCRIPT_DIR.parent                       # .../courses/zaphod
COURSES_ROOT = SHARED_ROOT.parent                     # .../courses
COURSE_ROOT = Path.cwd()                              # current course
COURSE_META_DIR = COURSE_ROOT / "_course_metadata"
COURSE_OUTCOMES_YAML = COURSE_META_DIR / "outcomes.yaml"
COURSE_OUTCOME_MAP_JSON = COURSE_META_DIR / "outcome_map.json"


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

    return Canvas(api_url, api_key)  # [web:282]


# ---------- YAML + map helpers ----------

def load_course_outcomes_yaml() -> Dict[str, Any]:
    if not COURSE_OUTCOMES_YAML.is_file():
        raise SystemExit(f"No outcomes.yaml at {COURSE_OUTCOMES_YAML}")
    with COURSE_OUTCOMES_YAML.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise SystemExit("outcomes.yaml must be a mapping at top level")
    return data


def save_course_outcome_map(map_data: Dict[str, int]):
    COURSE_META_DIR.mkdir(parents=True, exist_ok=True)
    with COURSE_OUTCOME_MAP_JSON.open("w", encoding="utf-8") as f:
        json.dump(map_data, f, indent=2, ensure_ascii=False)
    print(f"[outcomes] Wrote outcome_map.json with {len(map_data)} entries")


# ---------- CLO creation ----------

def create_course_outcomes(
    canvas: Canvas,
    course_id: int,
    course_clos: List[Dict[str, Any]],
    outcome_map: Dict[str, int],
):
    """
    Create CLOs directly for the course using Outcomes API:
    POST /api/v1/courses/:course_id/outcomes [web:282][web:285][web:508]
    """
    path = f"/api/v1/courses/{course_id}/outcomes"

    for clo in course_clos:
        code = clo.get("code")
        title = clo.get("title")
        description = clo.get("description", "")
        vendor_guid = clo.get("vendor_guid") or code
        mastery_points = clo.get("mastery_points")

        ratings_spec = clo.get("ratings") or []

        outcome_def: Dict[str, Any] = {
            "short_description": title,
            "description": description,
            "vendor_guid": vendor_guid,
        }
        if mastery_points is not None:
            outcome_def["mastery_points"] = float(mastery_points)

        if ratings_spec:
            rating_defs = []
            for r in ratings_spec:
                rating_defs.append(
                    {
                        "description": r.get("description", ""),
                        "points": float(r.get("points", 0)),
                    }
                )
            outcome_def["ratings"] = rating_defs

        try:
            created = canvas._Canvas__requester.request(
                "POST",
                path,
                _kwargs={"outcome": outcome_def},
            )
            outcome = created.get("outcome") or created
            oid = int(outcome.get("id"))
            print(f"[outcomes] Created CLO '{code}' (id={oid})")
            if code:
                outcome_map[code] = oid
        except Exception as e:
            print(f"[outcomes:err] Failed to create CLO '{code}': {e}")


# ---------- main ----------

def main():
    course_id = os.environ.get("COURSE_ID")
    if not course_id:
        raise SystemExit("COURSE_ID is not set")

    course_id_int = int(course_id)
    canvas = load_canvas()

    yaml_data = load_course_outcomes_yaml()
    course_clos: List[Dict[str, Any]] = yaml_data.get("course_outcomes") or []

    if not course_clos:
        print("[outcomes] No course_outcomes defined; nothing to do")
        return

    outcome_map: Dict[str, int] = {}

    # Create CLOs for this course
    create_course_outcomes(canvas, course_id_int, course_clos, outcome_map)

    # Save mapping for rubrics/quizzes
    save_course_outcome_map(outcome_map)


if __name__ == "__main__":
    main()
