#!/usr/bin/env python3
"""
sync_clo.py (Zaphod, CLO-only, CanvasAPI-compatible)

- Reads _course_metadata/outcomes.yaml
- Ignores institution_outcomes and program_outcomes
- Uses Course.get_outcome_group() to get the root outcome group for the course [web:220][web:315]
- Creates CLOs inside that group by POSTing to its outcomes_url [web:288][web:285]
- Writes _course_metadata/outcome_map.json mapping CLO codes to outcome IDs
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Any, List

import yaml
from canvasapi import Canvas  # [web:282]


SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_ROOT = SCRIPT_DIR.parent
COURSES_ROOT = SHARED_ROOT.parent
COURSE_ROOT = Path.cwd()
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


def get_root_outcome_group(canvas: Canvas, course_id: int) -> Dict[str, Any]:
    """
    Use Course.get_outcome_group() to get the root outcome group. [web:220][web:315]
    """
    course = canvas.get_course(course_id)
    group = course.get_outcome_group()
    attrs = getattr(group, "_attributes", None)
    if not isinstance(attrs, dict):
        raise SystemExit("Could not access attributes of root outcome group")
    return attrs


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


# ---------- CLO creation via outcome group ----------

def create_clos_in_group(
    canvas: Canvas,
    outcome_group: Dict[str, Any],
    course_clos: List[Dict[str, Any]],
    outcome_map: Dict[str, int],
):
    """
    Create CLOs inside the given outcome group using its outcomes_url. [web:288][web:285]
    """
    outcomes_url = outcome_group.get("outcomes_url")
    if not outcomes_url:
        raise SystemExit("Root outcome group has no outcomes_url; cannot create CLOs")

    for clo in course_clos:
        code = clo.get("code")
        title = clo.get("title")
        description = clo.get("description", "")
        vendor_guid = clo.get("vendor_guid") or code
        mastery_points = clo.get("mastery_points")

        if not title:
            print(f"[outcomes:warn] Skipping CLO with code '{code}' (missing title)")
            continue

        # OutcomeGroups link/create endpoint expects these as top-level params. [web:288][web:285]
        payload: Dict[str, Any] = {
            "title": title,
            "description": description,
            "vendor_guid": vendor_guid,
        }
        if mastery_points is not None:
            payload["mastery_points"] = float(mastery_points)

        try:
            created = canvas._Canvas__requester.request(
                "POST",
                outcomes_url,   # e.g. /api/v1/courses/:course_id/outcome_groups/:id/outcomes
                _kwargs=payload,
            )
            # Response is an OutcomeLink; the actual outcome is in 'outcome'. [web:288]
            outcome = created.get("outcome") if isinstance(created, dict) and "outcome" in created else created
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

    root_group = get_root_outcome_group(canvas, course_id_int)
    outcome_map: Dict[str, int] = {}
    create_clos_in_group(canvas, root_group, course_clos, outcome_map)
    save_course_outcome_map(outcome_map)


if __name__ == "__main__":
    main()
