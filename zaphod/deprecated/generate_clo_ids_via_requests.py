#!/usr/bin/env python3
"""
sync_clo_ids_via_requests.py

For the current course (cwd):

- Reads _course_metadata/outcomes.yaml (course_outcomes) to get the expected
  vendor_guid values (falling back to code).
- Calls GET /api/v1/courses/:course_id/outcomes (with pagination) using
  raw HTTP via requests, authorized with API_KEY from CANVAS_CREDENTIAL_FILE.
- Builds _course_metadata/outcome_map.json mapping vendor_guid -> Canvas outcome id
  for any outcomes in the course whose vendor_guid matches the YAML.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, urljoin

import requests
import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_ROOT = SCRIPT_DIR.parent
COURSES_ROOT = SHARED_ROOT.parent
COURSE_ROOT = Path.cwd()
COURSE_META_DIR = COURSE_ROOT / "_course_metadata"
COURSE_OUTCOMES_YAML = COURSE_META_DIR / "outcomes.yaml"
COURSE_OUTCOMES_MAP_JSON = COURSE_META_DIR / "outcome_map.json"


def load_credentials() -> Dict[str, str]:
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

    return {"API_KEY": api_key, "API_URL": api_url.rstrip("/")}


def load_expected_vendor_guids() -> List[str]:
    if not COURSE_OUTCOMES_YAML.is_file():
        raise SystemExit(f"No outcomes.yaml at {COURSE_OUTCOMES_YAML}")
    with COURSE_OUTCOMES_YAML.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise SystemExit("outcomes.yaml must be a mapping at top level")

    course_clos: List[Dict[str, Any]] = data.get("course_outcomes") or []
    expected: List[str] = []
    for clo in course_clos:
        code = clo.get("code")
        vendor_guid = clo.get("vendor_guid") or code
        if vendor_guid:
            expected.append(str(vendor_guid))
    return expected


def parse_next_link(link_header: Optional[str]) -> Optional[str]:
    """
    Parse Canvas-style Link header and return the URL for rel="next", if any.
    """
    if not link_header:
        return None
    parts = [p.strip() for p in link_header.split(",")]
    for p in parts:
        if 'rel="next"' in p:
            start = p.find("<") + 1
            end = p.find(">", start)
            if start > 0 and end > start:
                return p[start:end]
    return None


def fetch_course_outcomes(api_url: str, api_key: str, course_id: int) -> List[Dict[str, Any]]:
    """
    Fetch all outcomes for a course via GET /api/v1/courses/:course_id/outcomes,
    following pagination, and return a flat list of Outcome objects.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    outcomes: List[Dict[str, Any]] = []

    url = f"{api_url}/api/v1/courses/{course_id}/outcomes"
    params: Dict[str, Any] = {"outcome_style": "full", "per_page": 100}

    while url:
        print(f"[outcomes:requests] GET {url}")
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            raise SystemExit(f"Failed to fetch outcomes: {resp.status_code} {resp.text}")

        page_data = resp.json()
        if not isinstance(page_data, list):
            print(f"[outcomes:warn] Unexpected outcomes payload type: {type(page_data)}")
            break

        outcomes.extend(page_data)

        link_header = resp.headers.get("Link") or resp.headers.get("link")
        next_url = parse_next_link(link_header)
        if next_url:
            # Make next_url absolute relative to api_url if needed.
            if next_url.startswith("/"):
                # Preserve protocol/host from api_url.
                parsed = urlparse(api_url)
                base = f"{parsed.scheme}://{parsed.netloc}"
                url = urljoin(base, next_url)
            else:
                url = next_url
            params = {}  # subsequent pages already include params in the URL
        else:
            url = None

    return outcomes


def rebuild_outcome_map(api_url: str, api_key: str, course_id: int, expected_vendor_guids: List[str]):
    print(f"[outcomes] expected_vendor_guids={expected_vendor_guids}")
    print(f"[outcomes] Discovering outcomes via /courses/{course_id}/outcomes ...")

    outcomes_data = fetch_course_outcomes(api_url, api_key, course_id)

    mapping: Dict[str, int] = {}

    for o in outcomes_data:
        vendor_guid = o.get("vendor_guid")
        outcome_id = o.get("id")
        title = o.get("title")

        print(
            "[outcomes:debug] outcome"
            f" id={outcome_id} vendor_guid={vendor_guid!r} title={title!r}"
        )

        if not vendor_guid or outcome_id is None:
            continue

        vg_str = str(vendor_guid)
        if vg_str in expected_vendor_guids:
            mapping[vg_str] = int(outcome_id)

    if not mapping:
        print(
            "[outcomes:warn] No matching vendor_guid values found via course outcomes; "
            "outcome_map.json not written"
        )
        return

    COURSE_META_DIR.mkdir(parents=True, exist_ok=True)
    with COURSE_OUTCOMES_MAP_JSON.open("w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)

    print(f"[outcomes] Wrote outcome_map.json with {len(mapping)} entries to {COURSE_OUTCOMES_MAP_JSON}")


def main():
    course_id = os.environ.get("COURSE_ID")
    if not course_id:
        raise SystemExit("COURSE_ID is not set")
    course_id_int = int(course_id)

    creds = load_credentials()
    api_key = creds["API_KEY"]
    api_url = creds["API_URL"]

    expected_vendor_guids = load_expected_vendor_guids()
    rebuild_outcome_map(api_url, api_key, course_id_int, expected_vendor_guids)


if __name__ == "__main__":
    main()
