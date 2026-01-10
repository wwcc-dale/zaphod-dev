#!/usr/bin/env python3
"""
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

sync_modules.py (Zaphod)

Ensure Canvas modules contain all items declared in meta.json for:

  - .page        -> Canvas Page module items
  - .assignment  -> Canvas Assignment module items
  - .file        -> Canvas File module items
  - .link        -> Canvas ExternalUrl module items

Module ordering:

  - Reads _course_metadata/module_order.yaml if present:
        modules:
          - "Module 0: Start Here"
          - "Module 1: Getting Started"
          - ...
  - After syncing items, reorders modules to match that list first,
    then any remaining modules in name order.

Assumptions:
  - Run from the course root (where pages/ lives).
  - Env:
      CANVAS_CREDENTIAL_FILE   path to credentials.txt
      COURSE_ID                Canvas course id
      ZAPHOD_CHANGED_FILES     optional, newline-separated list of changed paths
  - Credentials file defines:
      API_KEY = "..."
      API_URL = "https://yourcanvas.institution.edu"
"""

from pathlib import Path
import json
import os
from config_utils import get_course_id
from canvasapi import Canvas
import yaml
from errors import (
    canvas_not_found_error,
    ConfigurationError,
    CanvasAPIError,
)


SCRIPT_DIR = Path(__file__).resolve().parent
COURSE_ROOT = Path.cwd()
PAGES_DIR = COURSE_ROOT / "pages"
COURSE_META_DIR = COURSE_ROOT / "_course_metadata"
MODULE_ORDER_PATH = COURSE_ROOT / "modules" / "module_order.yaml"


# ---------- changed-files helpers ----------

def get_changed_files() -> list[Path]:
    """
    Read ZAPHOD_CHANGED_FILES and return them as Path objects.
    Empty list if the env var is missing/empty.
    """
    raw = os.environ.get("ZAPHOD_CHANGED_FILES", "").strip()
    if not raw:
        return []
    return [Path(p) for p in raw.splitlines() if p.strip()]


def iter_all_content_dirs():
    """
    Existing behavior: yield every content folder under pages/
    ending in one of the known extensions.
    """
    for ext in (".page", ".assignment", ".file", ".link"):
        for folder in PAGES_DIR.rglob(f"*{ext}"):
            yield folder


def iter_changed_content_dirs(changed_files: list[Path]):
    """
    From changed files, yield the content folders whose modules
    should be synced.

    Rules:
    - Trigger on index.md, source.md, or meta.json changes.
    - Must live under pages/**.
    - Parent folder must end with .page / .assignment / .file / .link.
    """
    exts = {".page", ".assignment", ".file", ".link"}
    relevant_names = {"index.md", "source.md", "meta.json"}
    seen: set[Path] = set()

    for path in changed_files:
        if path.name not in relevant_names:
            continue

        try:
            rel = path.relative_to(COURSE_ROOT)
        except ValueError:
            continue

        if not rel.parts or rel.parts[0] != "pages":
            continue

        folder = path.parent
        if folder.suffix not in exts:
            continue

        if folder not in seen:
            seen.add(folder)
            yield folder


# ---------- Canvas helpers ----------

def get_canvas() -> Canvas:
    cred_path = os.environ.get("CANVAS_CREDENTIAL_FILE")
    if not cred_path:
        raise SystemExit("CANVAS_CREDENTIAL_FILE is not set")

    cred_file = Path(cred_path)
    if not cred_file.is_file():
        raise SystemExit(f"CANVAS_CREDENTIAL_FILE does not exist: {cred_file}")

    ns = {}
    exec(cred_file.read_text(encoding="utf-8"), ns)
    try:
        api_key = ns["API_KEY"]
        api_url = ns["API_URL"]
    except KeyError as e:
        raise SystemExit(
            f"Credentials file must define API_KEY and API_URL. Missing {e!r}"
        )
    return Canvas(api_url, api_key)


def load_meta(folder: Path) -> dict:
    meta_path = folder / "meta.json"
    if not meta_path.is_file():
        raise FileNotFoundError(f"No meta.json in folder {folder}")
    with meta_path.open(encoding="utf-8") as f:
        return json.load(f)


def ensure_module(course, name: str):
    """
    Find or create a module with the given name.
    """
    for m in course.get_modules():
        if m.name == name:
            return m
    return course.create_module({"name": name})


def module_has_item(
    module,
    item_type: str,
    *,
    page_url=None,
    content_id=None,
    external_url=None,
) -> bool:
    """
    Check if the module already has an item of the given type pointing at the same content.
    """
    for item in module.get_module_items():
        if item.type != item_type:
            continue

        if item_type == "Page":
            if getattr(item, "page_url", None) == page_url:
                return True
        elif item_type in {"Assignment", "File"}:
            if getattr(item, "content_id", None) == content_id:
                return True
        elif item_type == "ExternalUrl":
            if getattr(item, "external_url", None) == external_url:
                return True

    return False


# ---------- Find Canvas objects by name ----------

def find_page(course, title: str):
    for page in course.get_pages():
        if page.title == title:
            return page
    return None


def find_assignment(course, name: str):
    for a in course.get_assignments():
        if a.name == name:
            return a
    return None


def find_file(course, filename: str):
    """
    Naive search by filename; adjust if you need stricter path matching.
    """
    for f in course.get_files():
        if f.filename == filename:
            return f
    return None


# ---------- Sync functions per content type ----------

def sync_page(course, folder: Path, meta: dict):
    title = meta.get("name")
    modules = meta.get("modules") or []
    indent = meta.get("indent", 0)

    if not title:
        print(f"[modules:warn] {folder.name}: missing 'name' in meta.json for page")
        return
    if not modules:
        return

    page = find_page(course, title)
    if not page:
        # BETTER ERROR: Specific to missing page
        raise canvas_not_found_error(
            resource_type="Page",
            identifier=title,
            course_id=course.id
        )

    page_url = page.url
    for mname in modules:
        try:
            module = ensure_module(course, mname)
            if module_has_item(module, "Page", page_url=page_url):
                print(f"[modules] {folder.name}: already in module '{mname}' (Page)")
                continue

            module.create_module_item(
                module_item={
                    "type": "Page",
                    "page_url": page_url,
                    "title": title,
                    "indent": indent,
                }
            )
            print(f"[modules] {folder.name}: added to module '{mname}' (Page)")
        except Exception as e:
            raise CanvasAPIError(
                message=f"Failed to add page to module '{mname}'",
                suggestion=(
                    "Check:\n"
                    "  - Module exists in Canvas\n"
                    "  - You have permission to edit modules\n"
                    "  - Page is published if module requires it"
                ),
                context={
                    "page_title": title,
                    "module_name": mname,
                    "course_id": course.id
                },
                cause=e
            )


def sync_assignment(course, folder: Path, meta: dict):
    name = meta.get("name")
    modules = meta.get("modules") or []
    indent = meta.get("indent", 0)

    if not name:
        print(f"[modules:warn] {folder.name}: missing 'name' in meta.json for assignment")
        return
    if not modules:
        return

    assignment = find_assignment(course, name)
    if not assignment:
        print(f"[modules:warn] {folder.name}: assignment name '{name}' not found in Canvas")
        return

    content_id = assignment.id
    for mname in modules:
        module = ensure_module(course, mname)
        if module_has_item(module, "Assignment", content_id=content_id):
            print(f"[modules] {folder.name}: already in module '{mname}' (Assignment)")
            continue

        module.create_module_item(
            module_item={
                "type": "Assignment",
                "content_id": content_id,
                "title": name,
                "indent": indent,
            }
        )
        print(f"[modules] {folder.name}: added to module '{mname}' (Assignment)")


def sync_file_item(course, folder: Path, meta: dict):
    filename = meta.get("filename")
    modules = meta.get("modules") or []
    indent = meta.get("indent", 0)
    title = meta.get("title", filename)

    if not filename:
        print(f"[modules:warn] {folder.name}: missing 'filename' in meta.json for file")
        return
    if not modules:
        return

    file_obj = find_file(course, filename)
    if not file_obj:
        print(f"[modules:warn] {folder.name}: file '{filename}' not found in Canvas")
        return

    content_id = file_obj.id
    for mname in modules:
        module = ensure_module(course, mname)
        if module_has_item(module, "File", content_id=content_id):
            print(f"[modules] {folder.name}: already in module '{mname}' (File)")
            continue

        module.create_module_item(
            module_item={
                "type": "File",
                "content_id": content_id,
                "title": title,
                "indent": indent,
            }
        )
        print(f"[modules] {folder.name}: added to module '{mname}' (File)")


def sync_link(course, folder: Path, meta: dict):
    external_url = meta.get("external_url")
    name = meta.get("name")
    modules = meta.get("modules") or []
    indent = meta.get("indent", 0)
    new_tab = bool(meta.get("new_tab", False))

    if not external_url or not name:
        print(f"[modules:warn] {folder.name}: missing 'external_url' or 'name' in meta.json for link")
        return
    if not modules:
        return

    for mname in modules:
        module = ensure_module(course, mname)
        if module_has_item(module, "ExternalUrl", external_url=external_url):
            print(f"[modules] {folder.name}: already in module '{mname}' (ExternalUrl)")
            continue

        module.create_module_item(
            module_item={
                "type": "ExternalUrl",
                "external_url": external_url,
                "title": name,
                "new_tab": new_tab,
                "indent": indent,
            }
        )
        print(f"[modules] {folder.name}: added to module '{mname}' (ExternalUrl)")


# ---------- Module order helpers ----------

def load_module_order() -> list[str]:
    """
    Load desired module order from module_order.yaml, if present.
    Accepts either:
      - {"modules": [...]} (preferred), or
      - a bare list at top level.
    """
    if not MODULE_ORDER_PATH.is_file():
        return []
    data = yaml.safe_load(MODULE_ORDER_PATH.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        mods = data.get("modules") or []
    elif isinstance(data, list):
        mods = data
    else:
        mods = []
    order = [str(m).strip() for m in mods if str(m).strip()]
    print(f"[modules] Desired module order from YAML: {order}")
    return order

def apply_module_order(course, desired_order: list[str]):
    """
    Ensure all modules in desired_order exist, then reorder modules:

      1) Modules whose names appear in desired_order, in that sequence.
      2) Any remaining modules, sorted by name.
    """
    # Current modules
    modules = list(course.get_modules())
    modules_by_name = {m.name: m for m in modules}

    # 1) Create missing modules from desired_order
    for name in desired_order:
        if name in modules_by_name:
            continue
        print(f"[modules] Creating missing module '{name}' from module_order.yaml")
        new_mod = course.create_module({"name": name})
        modules_by_name[name] = new_mod
        modules.append(new_mod)

    # 2) Build target ordering (first desired_order, then extras)
    ordered = []
    for name in desired_order:
        m = modules_by_name.get(name)
        if m is not None and m not in ordered:
            ordered.append(m)

    for m in modules:
        if m not in ordered:
            ordered.append(m)

    # 3) Apply positions only when they actually change
    for idx, mod in enumerate(ordered, start=1):
        if getattr(mod, "position", None) == idx:
            continue
        print(f"[modules] Setting module '{mod.name}' to position {idx}")
        mod.edit(module={"position": idx})


# ---------- Main ----------

def main():
    course_id = get_course_id()
    if not course_id:
        raise SystemExit("COURSE_ID is not set")

    canvas = get_canvas()
    course = canvas.get_course(int(course_id))

    if not PAGES_DIR.exists():
        raise SystemExit(f"No pages directory at {PAGES_DIR}")

    desired_module_order = load_module_order()

    print(f"[modules] Syncing modules in course {course.name} (ID {course_id})")

    changed_files = get_changed_files()

    if changed_files:
        # Incremental mode
        content_dirs = list(iter_changed_content_dirs(changed_files))
        if not content_dirs:
            print("[modules] No relevant changed files; nothing to sync.")
    else:
        # Full mode
        content_dirs = list(iter_all_content_dirs())

    if content_dirs:
        for folder in content_dirs:
            try:
                meta = load_meta(folder)
            except FileNotFoundError as e:
                print(f"[modules:warn] {folder.name}: {e}")
                continue

            t = str(meta.get("type", "")).lower()
            if t == "page":
                sync_page(course, folder, meta)
            elif t == "assignment":
                sync_assignment(course, folder, meta)
            elif t == "file":
                sync_file_item(course, folder, meta)
            elif t == "link":
                sync_link(course, folder, meta)
            else:
                print(f"[modules:warn] {folder.name}: unsupported type '{t}' in meta.json")

    # Apply desired module order if provided
    if desired_module_order:
        print("[modules] Applying module order from module_order.yaml")
        apply_module_order(course, desired_module_order)

    print("[modules] Done.")


if __name__ == "__main__":
    main()
