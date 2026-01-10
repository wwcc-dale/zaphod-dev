#!/usr/bin/env python3
"""
generate_outcomes_csv.py (Zaphod)

For the current course (cwd):

- Reads _course_metadata/outcomes.yaml
- Uses only course_outcomes (CLOs)
- Writes _course_metadata/outcomes_import.csv in Canvas Outcomes CSV format. [web:324][web:321]

You then import this CSV in the Canvas course Outcomes page (Import → choose file). [web:539]
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Any, List

import yaml  # pip install pyyaml


SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_ROOT = SCRIPT_DIR.parent
COURSES_ROOT = SHARED_ROOT.parent
COURSE_ROOT = Path.cwd()
COURSE_META_DIR = COURSE_ROOT / "_course_metadata"
COURSE_OUTCOMES_YAML = COURSE_META_DIR / "outcomes.yaml"
COURSE_OUTCOMES_CSV = COURSE_META_DIR / "outcomes_import.csv"


def load_course_outcomes_yaml() -> Dict[str, Any]:
    if not COURSE_OUTCOMES_YAML.is_file():
        raise SystemExit(f"No outcomes.yaml at {COURSE_OUTCOMES_YAML}")
    with COURSE_OUTCOMES_YAML.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise SystemExit("outcomes.yaml must be a mapping at top level")
    return data


def build_rows(course_clos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build rows matching the Outcomes CSV format. [web:324][web:504]

    We keep it minimal:
    - vendor_guid: from YAML (or code)
    - object_type: outcome
    - title: YAML title
    - description: YAML description
    - display_name: code (short label)
    - calculation_method / calculation_int: left blank (Canvas defaults) [web:324]
    - workflow_state: active
    - parent_guids: blank (course root group)
    - mastery_points: from YAML, optional
    - ratings: omitted (Canvas will use default mastery scale if configured) [web:324]
    """
    rows: List[Dict[str, Any]] = []

    for clo in course_clos:
        code = clo.get("code")
        title = clo.get("title")
        description = clo.get("description", "")
        vendor_guid = clo.get("vendor_guid") or code
        mastery_points = clo.get("mastery_points")

        if not code or not title or not vendor_guid:
            print(f"[outcomes:warn] Skipping CLO with missing code/title/vendor_guid: {clo}")
            continue

        row: Dict[str, Any] = {
            "vendor_guid": str(vendor_guid),
            "object_type": "outcome",
            "title": title,
            "description": description,
            "display_name": code,
            "calculation_method": "",
            "calculation_int": "",
            "workflow_state": "active",
            "parent_guids": "",
            "mastery_points": mastery_points if mastery_points is not None else "",
            # ratings columns omitted for simplicity [web:324]
        }
        rows.append(row)

    return rows


def write_csv(rows: List[Dict[str, Any]]):
    COURSE_META_DIR.mkdir(parents=True, exist_ok=True)

    # Header per Outcomes CSV docs, minimal subset. [web:324][web:321]
    fieldnames = [
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
        # ratings columns would go here if used
    ]

    with COURSE_OUTCOMES_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"[outcomes] Wrote CSV with {len(rows)} outcomes to {COURSE_OUTCOMES_CSV}")


def main():
    data = load_course_outcomes_yaml()
    course_clos: List[Dict[str, Any]] = data.get("course_outcomes") or []

    if not course_clos:
        print("[outcomes] No course_outcomes defined; nothing to do")
        return

    rows = build_rows(course_clos)
    if not rows:
        print("[outcomes] No valid CLO rows built; nothing written")
        return

    write_csv(rows)


if __name__ == "__main__":
    main()
