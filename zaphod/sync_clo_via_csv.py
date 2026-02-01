#!/usr/bin/env python3
"""
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

sync_clo_via_csv.py (Zaphod, CLOs with Canvas-style ratings)

For the current course (cwd):

- Reads outcomes/outcomes.yaml (course_outcomes)
- Generates outcomes/outcomes_import.csv using Canvas Outcomes CSV format,
  including rating levels as separate CSV cells after the `ratings` header
  (points,description,points,description,...).
- Imports that CSV into the course via Course.import_outcome().

Incremental behavior:

- If ZAPHOD_CHANGED_FILES is set, this script only runs when
  outcomes/outcomes.yaml is among the changed paths.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Dict, Any, List

import yaml
from zaphod.config_utils import get_course_id
from zaphod.canvas_client import make_canvas_api_obj
from canvasapi import Canvas  # [web:49][web:92]


SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_ROOT = SCRIPT_DIR.parent
COURSES_ROOT = SHARED_ROOT.parent
COURSE_ROOT = Path.cwd()

# Use a course-level outcomes folder instead of _course_metadata.
COURSE_OUTCOMES_DIR = COURSE_ROOT / "outcomes"
COURSE_OUTCOMES_YAML = COURSE_OUTCOMES_DIR / "outcomes.yaml"
COURSE_OUTCOMES_CSV = COURSE_OUTCOMES_DIR / "outcomes_import.csv"


# ---------- helpers ----------


def load_course_outcomes_yaml() -> Dict[str, Any]:
    if not COURSE_OUTCOMES_YAML.is_file():
        raise SystemExit(f"No outcomes.yaml at {COURSE_OUTCOMES_YAML}")
    with COURSE_OUTCOMES_YAML.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise SystemExit("outcomes.yaml must be a mapping at top level")
    return data


def build_rows(course_clos: List[Dict[str, Any]]) -> List[List[str]]:
    """
    Build rows using the Outcomes CSV format with ratings encoded as separate cells
    after the ratings header.
    """
    rows: List[List[str]] = []

    for clo in course_clos:
        code = clo.get("code")
        title = clo.get("title")
        description = clo.get("description", "")
        vendor_guid = clo.get("vendor_guid") or code
        mastery_points = clo.get("mastery_points")
        ratings = clo.get("ratings") or []

        if not code or not title or not vendor_guid:
            print(f"[outcomes:warn] Skipping CLO with missing code/title/vendor_guid: {clo}")
            continue

        try:
            ratings_sorted = sorted(
                ratings,
                key=lambda r: float(r.get("points", 0)),
                reverse=True,
            )
        except Exception:
            ratings_sorted = ratings

        ratings_cells: List[str] = []
        for r in ratings_sorted:
            pts = r.get("points", "")
            desc = r.get("description", "")
            ratings_cells.append(str(pts))
            ratings_cells.append(desc)

        base = [
            str(vendor_guid),
            "outcome",
            title,
            description,
            code,           # display_name
            "",             # calculation_method
            "",             # calculation_int
            "active",       # workflow_state
            "",             # parent_guids
            str(mastery_points) if mastery_points is not None else "",
        ]

        row = base + ratings_cells
        rows.append(row)

    return rows


def write_csv(rows: List[List[str]]):
    COURSE_OUTCOMES_DIR.mkdir(parents=True, exist_ok=True)

    max_len = max((len(r) for r in rows), default=10)
    base_headers = [
        "vendor_guid",
        "object_type",
        "title",
        "description",
        "display_name",
        "calculation_method",
        "calculation_int",
        "workflow_state",
        "parent_guids",
        "mastery_points",
    ]
    extra_count = max(1, max_len - len(base_headers))
    extra_headers = ["ratings"] + [""] * (extra_count - 1)
    headers = base_headers + extra_headers

    with COURSE_OUTCOMES_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            padded = row[:]
            while len(padded) < len(headers):
                padded.append("")
            writer.writerow(padded)

    print(f"[outcomes] Wrote CSV with {len(rows)} outcomes to {COURSE_OUTCOMES_CSV}")


def import_csv_to_course(canvas: Canvas, course_id: int):
    """
    POST /api/v1/courses/:course_id/outcome_imports via Course.import_outcome().
    """
    course = canvas.get_course(course_id)
    print(f"[outcomes] Importing CSV into course {course_id}...")
    outcome_import = course.import_outcome(str(COURSE_OUTCOMES_CSV))
    attrs = getattr(outcome_import, "_attributes", {})
    print(
        f"[outcomes] Outcome import created: id={attrs.get('id')} "
        f"workflow_state={attrs.get('workflow_state')}"
    )


def outcomes_yaml_changed() -> bool:
    """
    Return True if ZAPHOD_CHANGED_FILES is unset (full run) or
    if outcomes/outcomes.yaml is listed among the changed paths.
    """
    raw = os.environ.get("ZAPHOD_CHANGED_FILES", "").strip()
    if not raw:
        # No incremental context: behave as full run.
        return True

    changed_paths = [Path(p) for p in raw.splitlines() if p.strip()]
    for p in changed_paths:
        try:
            rel = p.relative_to(COURSE_ROOT)
        except ValueError:
            continue
        if rel == COURSE_OUTCOMES_YAML.relative_to(COURSE_ROOT):
            return True
    return False


# ---------- main ----------


def main():
    if not outcomes_yaml_changed():
        print("[outcomes] outcomes.yaml not changed; skipping CLO sync.")
        return

    course_id = get_course_id()
    if not course_id:
        raise SystemExit("COURSE_ID is not set")
    course_id_int = int(course_id)

    yaml_data = load_course_outcomes_yaml()
    course_clos: List[Dict[str, Any]] = yaml_data.get("course_outcomes") or []

    if not course_clos:
        print("[outcomes] No course_outcomes defined; nothing to do")
        return

    rows = build_rows(course_clos)
    if not rows:
        print("[outcomes] No valid CLO rows built; nothing written")
        return

    write_csv(rows)

    canvas = make_canvas_api_obj()  # From canvas_client
    import_csv_to_course(canvas, course_id_int)


if __name__ == "__main__":
    main()
