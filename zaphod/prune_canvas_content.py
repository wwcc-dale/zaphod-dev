#!/usr/bin/env python3
"""
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

prune_canvas_content.py

Reconcile Canvas content and module membership against the current
Zaphod/markdown2canvas flat-file repo for the current course.

Behaviors:

1) Content pruning
   - Pages: delete Canvas pages whose titles are not present in any index.md frontmatter.
   - Assignments: delete Canvas assignments whose names are not present
     in any .assignment frontmatter (by default).

2) Module-item pruning
   - For pages, assignments, files, and links that STILL exist:
       * Read their `modules` list from meta.json.
       * For each module in Canvas containing that item:
           - If the module name is NOT in the desired list, delete that module item
             (but keep the underlying page/assignment/file/link).

3) Empty module pruning
   - After adjusting module items, delete any modules that have no items,
     except modules whose names appear in module_order.yaml.

4) Work-file cleanup
   - Remove auto-generated work files under pages/ to keep the repo clean.

Defaults:
- Deletions are applied by default (ZAPHOD_PRUNE_APPLY default true).
- Assignment pruning is on by default (ZAPHOD_PRUNE_ASSIGNMENTS default true).
- CLI flags can override these defaults.
"""

from pathlib import Path
import argparse
import json
import os
import yaml
import frontmatter
from markdown2canvas.setup_functions import make_canvas_api_obj  # [web:131]
from zaphod.config_utils import get_course_id

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_ROOT = SCRIPT_DIR.parent
COURSES_ROOT = SHARED_ROOT.parent
COURSE_ROOT = Path.cwd()
PAGES_DIR = COURSE_ROOT / "pages"
MODULE_ORDER_PATH = COURSE_ROOT / "modules" / "module_order.yaml"

AUTO_WORK_FILES = {
    "styled_source.md",
    "extra_styled_source.md",
    "extra_styled_source.html",
    "result.html",
    "source.md",
}


def _truthy_env(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.lower() in {"1", "true", "yes", "on"}


def load_local_meta_maps():
    """
    Build mappings from local meta.json for use in module pruning.

    Returns:
        page_modules_by_title:         {page_title: [module_names]}
        assignment_modules_by_name:    {assignment_name: [module_names]}
        file_modules_by_filename:      {filename: [module_names]}
        link_modules_by_url:           {external_url: [module_names]}
    """
    page_modules_by_title = {}
    assignment_modules_by_name = {}
    file_modules_by_filename = {}
    link_modules_by_url = {}

    if not PAGES_DIR.exists():
        print(f"[prune] No pages directory at {PAGES_DIR}")
        return (
            page_modules_by_title,
            assignment_modules_by_name,
            file_modules_by_filename,
            link_modules_by_url,
        )

    for meta_path in PAGES_DIR.rglob("meta.json"):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[prune:warn] Skipping {meta_path}: failed to parse JSON ({e})")
            continue

        t = str(data.get("type", "")).lower()
        mods = data.get("modules") or []
        if not mods:
            continue

        if t == "page":
            title = data.get("name")
            if title:
                page_modules_by_title[title] = mods
        elif t == "assignment":
            name = data.get("name")
            if name:
                assignment_modules_by_name[name] = mods
        elif t == "file":
            filename = data.get("filename")
            if filename:
                file_modules_by_filename[filename] = mods
        elif t == "link":
            url = data.get("external_url")
            if url:
                link_modules_by_url[url] = mods

    return (
        page_modules_by_title,
        assignment_modules_by_name,
        file_modules_by_filename,
        link_modules_by_url,
    )


def load_local_names():
    """
    Return (page_names, assignment_names) from index.md frontmatter,
    treating index.md as the single source of truth.

    Looks for type/name in each pages/**/*.page/index.md and
    pages/**/*.assignment/index.md.
    """
    page_names = set()
    assignment_names = set()

    if not PAGES_DIR.exists():
        print(f"[prune] No pages directory at {PAGES_DIR}")
        return page_names, assignment_names

    for index_path in PAGES_DIR.rglob("index.md"):
        try:
            post = frontmatter.load(index_path)
            meta = dict(post.metadata)
        except Exception as e:
            print(f"[prune:warn] Skipping {index_path}: failed to parse frontmatter ({e})")
            continue

        t = str(meta.get("type", "")).lower()
        name = meta.get("name")
        if not name:
            continue

        if t == "page":
            page_names.add(name)
        elif t == "assignment":
            assignment_names.add(name)

    return page_names, assignment_names


def load_canvas_sets(course):
    """Return (canvas_page_names, canvas_assignment_names) for the course."""
    canvas_page_names = {p.title for p in course.get_pages()}
    canvas_assignment_names = {a.name for a in course.get_assignments()}
    return canvas_page_names, canvas_assignment_names


def delete_extra_pages(course, extra_pages, apply=False):
    """Delete or report Canvas pages that are not in the repo."""
    if not extra_pages:
        print("[prune] No extra pages to delete.")
        return

    print("\n[prune] Extra Canvas pages (not present in repo):")
    for title in sorted(extra_pages):
        print(f"  - {title}")

    if not apply:
        print("[prune] Dry-run (no page deletions).")
        return

    print("[prune] Deleting extra pages...")
    for page in course.get_pages():
        if page.title in extra_pages:
            try:
                print(f"  deleting page: {page.title}")
                page.delete()
            except Exception as e:
                print(f"  [prune:err] failed to delete page '{page.title}': {e}")


def delete_extra_assignments(course, extra_assignments, apply=False):
    """Delete or report Canvas assignments that are not in the repo."""
    if not extra_assignments:
        print("[prune] No extra assignments to delete.")
        return

    print("\n[prune] Extra Canvas assignments (not present in repo):")
    for name in sorted(extra_assignments):
        print(f"  - {name}")

    if not apply:
        print("[prune] Dry-run (no assignment deletions).")
        return

    print("[prune] Deleting extra assignments...")
    for a in course.get_assignments():
        if a.name in extra_assignments:
            try:
                print(f"  deleting assignment: {a.name}")
                a.delete()
            except Exception as e:
                print(f"  [prune:err] failed to delete assignment '{a.name}': {e}")


# ---------- Module-item pruning ----------

def prune_module_items(
    course,
    page_modules_by_title,
    assignment_modules_by_name,
    file_modules_by_filename,
    link_modules_by_url,
    apply=False,
):
    """
    Remove module items whose module name is no longer listed in meta.json.

    Only affects module membership; underlying content remains.
    """

    if not apply:
        print("\n[prune] Module-item pruning: dry-run (no deletions).")
    else:
        print("\n[prune] Module-item pruning: deleting extra module items.")

    files_by_id = {f.id: f for f in course.get_files()}
    pages_by_title = {p.title: p for p in course.get_pages()}
    assignments_by_id = {a.id: a for a in course.get_assignments()}

    slug_to_title = {
        getattr(p, "url", None): title for title, p in pages_by_title.items()
    }

    for module in course.get_modules():
        for item in module.get_module_items():
            mname = module.name
            itype = item.type

            desired_modules = None

            if itype == "Page":
                page_url = getattr(item, "page_url", None)
                page_title = slug_to_title.get(page_url)
                if page_title:
                    desired_modules = page_modules_by_title.get(page_title)

            elif itype == "Assignment":
                content_id = getattr(item, "content_id", None)
                a = assignments_by_id.get(content_id)
                if a:
                    desired_modules = assignment_modules_by_name.get(a.name)

            elif itype == "File":
                content_id = getattr(item, "content_id", None)
                f = files_by_id.get(content_id)
                if f:
                    desired_modules = file_modules_by_filename.get(f.filename)

            elif itype == "ExternalUrl":
                external_url = getattr(item, "external_url", None)
                if external_url:
                    desired_modules = link_modules_by_url.get(external_url)

            if desired_modules is None:
                continue

            if mname not in desired_modules:
                msg = f"[prune] removing module item '{item.title}' from module '{mname}' ({itype})"
                if not apply:
                    print(msg)
                else:
                    try:
                        print(msg)
                        item.delete()
                    except Exception as e:
                        print(f"[prune:err] failed to delete module item '{item.title}' in '{mname}': {e}")


# ---------- Module order / empty modules ----------

def load_allowed_empty_modules() -> set[str]:
    """
    Return the set of module names that are allowed to remain empty,
    taken from module_order.yaml (if present).
    """
    if not MODULE_ORDER_PATH.is_file():
        return set()
    data = yaml.safe_load(MODULE_ORDER_PATH.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        mods = data.get("modules") or []
    elif isinstance(data, list):
        mods = data
    else:
        mods = []
    return {str(m).strip() for m in mods if str(m).strip()}


def delete_empty_modules(course, apply=False):
    """
    Delete modules that have no items, except those whose names
    appear in module_order.yaml.
    """
    allowed_empty = load_allowed_empty_modules()
    print("\n[prune] Checking for empty modules...")
    for module in course.get_modules():
        items = list(module.get_module_items())
        if items:
            continue

        if module.name in allowed_empty:
            print(f"[prune] keeping empty module '{module.name}' (listed in module_order.yaml)")
            continue

        msg = f"[prune] deleting empty module '{module.name}'"
        if not apply:
            print(msg + " (dry-run)")
        else:
            try:
                print(msg)
                module.delete()
            except Exception as e:
                print(f"[prune:err] failed to delete module '{module.name}': {e}")


def write_module_order_yaml(course):
    """
    Rewrite module_order.yaml from the current Canvas module order.
    Only called when --rewrite-order is passed.
    """
    modules = sorted(course.get_modules(), key=lambda m: m.position)
    order = [m.name for m in modules]

    MODULE_ORDER_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {"modules": order}
    with MODULE_ORDER_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)
    print(f"[prune] Wrote module order to {MODULE_ORDER_PATH}")


# ---------- Work-file cleanup ----------

def cleanup_work_files():
    """
    Remove auto-generated work files under pages/ to keep the repo clean.
    """
    if not PAGES_DIR.exists():
        return

    print("\n[prune] Cleaning up auto-generated work files...")
    removed = 0
    for f in PAGES_DIR.rglob("*"):
        if f.is_file() and f.name in AUTO_WORK_FILES:
            try:
                f.unlink()
                removed += 1
            except Exception as e:
                print(f"[prune:warn] failed to remove {f}: {e}")
    print(f"[prune] Removed {removed} work files.")


# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser(
        description="Prune Canvas content and module items not present in the local Zaphod repo."
    )
    parser.add_argument(
        "--course-id",
        type=int,
        help="Canvas course ID (optional if COURSE_ID env is set).",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Ignored marker flag when called from watch_and_publish.py.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete extra items on Canvas and module items. "
             "If omitted, falls back to env or default.",
    )
    parser.add_argument(
        "--prune-assignments",
        action="store_true",
        help="Include assignments in content pruning.",
    )
    parser.add_argument(
        "--rewrite-order",
        action="store_true",
        help="Rewrite _course_metadata/module_order.yaml from current Canvas modules.",
    )
    args = parser.parse_args()

    env_apply_default = _truthy_env("ZAPHOD_PRUNE_APPLY", default=True)
    env_prune_assignments_default = _truthy_env("ZAPHOD_PRUNE_ASSIGNMENTS", default=True)

    apply = args.apply or env_apply_default
    prune_assignments = args.prune_assignments or env_prune_assignments_default

    canvas = make_canvas_api_obj()

    if args.course_id:
        course_id = args.course_id
    else:
        course_id = get_course_id()
        if not course_id:
            raise SystemExit("COURSE_ID not set and --course-id not provided.")

    course = canvas.get_course(course_id)
    print(
        f"[prune] Pruning against course: {course.name} (ID {course_id}), "
        f"apply={apply}, prune_assignments={prune_assignments}"
    )

    # 1) Content-level pruning (pages and assignments)
    local_page_names, local_assignment_names = load_local_names()
    canvas_page_names, canvas_assignment_names = load_canvas_sets(course)

    extra_pages = canvas_page_names - local_page_names
    extra_assignments = canvas_assignment_names - local_assignment_names

    delete_extra_pages(course, extra_pages, apply=apply)

    if prune_assignments:
        delete_extra_assignments(course, extra_assignments, apply=apply)
    else:
        if extra_assignments:
            print(
                "\n[prune] Assignments with no local counterpart exist, "
                "but assignment pruning is disabled; they were not deleted."
            )

    # 2) Module-item pruning based on current meta.json mappings
    (
        page_modules_by_title,
        assignment_modules_by_name,
        file_modules_by_filename,
        link_modules_by_url,
    ) = load_local_meta_maps()

    prune_module_items(
        course,
        page_modules_by_title,
        assignment_modules_by_name,
        file_modules_by_filename,
        link_modules_by_url,
        apply=apply,
    )

    # 3) Remove empty modules (respecting module_order.yaml)
    delete_empty_modules(course, apply=apply)

    # 3b) Optionally rewrite module_order.yaml from Canvas
    if args.rewrite_order:
        write_module_order_yaml(course)

    # 4) Remove auto-generated work files
    cleanup_work_files()


if __name__ == "__main__":
    main()
