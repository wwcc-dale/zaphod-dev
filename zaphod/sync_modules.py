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
  - .quiz        -> Canvas Quiz module items

Module ordering (priority):

  1. Explicit: modules/module_order.yaml if present:
        modules:
          - "Module 0: Start Here"
          - "Module 1: Getting Started"
          - ...

  2. Inferred: from directory structure if no YAML:
        pages/
        ├── 01-Week 1.module/     -> position 1, name "Week 1"
        ├── 02-Week 2.module/     -> position 2, name "Week 2"
        ├── 10-Final.module/      -> position 3, name "Final"
        └── Appendix.module/      -> position 4, name "Appendix" (no prefix)

     Module folder patterns:
     - NEW: '05-Donkey Training.module' -> "Donkey Training" (sorted by 05)
     - LEGACY: 'module-Week 1' -> "Week 1"

  After syncing items, reorders modules to match the determined order,
  then any remaining modules in name order.

Module item ordering:

  Items within a module are ordered by:
  1. Explicit 'position' field in frontmatter (lowest number first)
  2. Numeric prefix from folder name (e.g., 01-bake-a-cake -> position 1)
  3. Items without prefix sort last, alphabetically by folder name

  Examples:
    - position: -1 in frontmatter -> sorts as (0, -1, name) [floats to top]
    - position: 0 in frontmatter -> sorts as (0, 0, name)
    - position: 5 in frontmatter -> sorts as (0, 5, name)
    - 01-intro.page -> sorts as (1, 1, "01-intro.page")  
    - 02-setup.page -> sorts as (1, 2, "02-setup.page")
    - appendix.page -> sorts as (2, 0, "appendix.page") [last]

  Negative positions are supported for floating items above numbered content:
    position: -10  # appears before position: -1, which appears before 01-*

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
import re
from zaphod.config_utils import get_course_id
from canvasapi import Canvas
import yaml
from zaphod.errors import (
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


def get_folder_sort_key(folder: Path, meta: dict = None) -> tuple:
    """
    Generate a sort key for ordering content folders within modules.
    
    Priority:
    1. Explicit 'position' in frontmatter/meta.json (lowest sort priority number)
    2. Numeric prefix from folder name (e.g., 01-bake-a-cake -> 1)
    3. No prefix - sorts last, alphabetically by folder name
    
    Returns a tuple for sorting: (priority_tier, position_or_prefix, folder_name)
    """
    # Check for explicit position in metadata
    if meta is not None:
        position = meta.get("position")
        if position is not None:
            try:
                return (0, int(position), folder.name.lower())
            except (ValueError, TypeError):
                pass
    
    # Try to extract numeric prefix from folder name (e.g., "01-", "2-", "10-")
    match = re.match(r'^(\d+)-', folder.name)
    if match:
        return (1, int(match.group(1)), folder.name.lower())
    
    # No prefix - sort last, alphabetically
    return (2, 0, folder.name.lower())


def iter_all_content_dirs():
    """
    Yield every content folder under pages/ ending in one of the known extensions.
    Folders are sorted by position/prefix for predictable module ordering.
    """
    folders = []
    for ext in (".page", ".assignment", ".file", ".link", ".quiz"):
        for folder in PAGES_DIR.rglob(f"*{ext}"):
            folders.append(folder)
    
    # Sort by folder name prefix/position
    # Note: We don't have meta loaded here, so we only use filename-based sorting
    # Full sorting with meta.position happens in main() after loading meta
    folders.sort(key=lambda f: get_folder_sort_key(f))
    
    for folder in folders:
        yield folder


def iter_changed_content_dirs(changed_files: list[Path]):
    """
    From changed files, yield the content folders whose modules
    should be synced.

    Rules:
    - Trigger on index.md, source.md, or meta.json changes.
    - Must live under pages/**.
    - Parent folder must end with .page / .assignment / .file / .link.
    
    Results are sorted by position/prefix for predictable module ordering.
    """
    exts = {".page", ".assignment", ".file", ".link", ".quiz"}
    relevant_names = {"index.md", "source.md", "meta.json"}
    found: list[Path] = []

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

        if folder not in found:
            found.append(folder)
    
    # Sort by folder name prefix/position
    found.sort(key=lambda f: get_folder_sort_key(f))
    
    for folder in found:
        yield folder


# ---------- Canvas helpers ----------

def get_canvas() -> Canvas:
    """
    Load Canvas API client safely.
    
    SECURITY: Uses safe parsing instead of exec() to prevent code injection.
    """
    import re
    import stat
    
    # Try environment variables first
    env_key = os.environ.get("CANVAS_API_KEY")
    env_url = os.environ.get("CANVAS_API_URL")
    if env_key and env_url:
        return Canvas(env_url, env_key)
    
    cred_path = os.environ.get("CANVAS_CREDENTIAL_FILE")
    if not cred_path:
        raise SystemExit(
            "Canvas credentials not found. Set CANVAS_API_KEY and CANVAS_API_URL "
            "environment variables, or set CANVAS_CREDENTIAL_FILE."
        )

    cred_file = Path(cred_path)
    if not cred_file.is_file():
        raise SystemExit(f"CANVAS_CREDENTIAL_FILE does not exist: {cred_file}")

    # SECURITY: Parse credentials safely without exec()
    content = cred_file.read_text(encoding="utf-8")
    api_key = None
    api_url = None
    
    for pattern in [r'API_KEY\s*=\s*["\']([^"\']+)["\']', r'API_KEY\s*=\s*(\S+)']:
        match = re.search(pattern, content)
        if match:
            api_key = match.group(1).strip().strip('"\'')
            break
    
    for pattern in [r'API_URL\s*=\s*["\']([^"\']+)["\']', r'API_URL\s*=\s*(\S+)']:
        match = re.search(pattern, content)
        if match:
            api_url = match.group(1).strip().strip('"\'')
            break
    
    if not api_key or not api_url:
        raise SystemExit(
            f"Credentials file must define API_KEY and API_URL: {cred_file}"
        )
    
    # Check file permissions
    try:
        mode = os.stat(cred_file).st_mode
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            print(f"[modules:SECURITY] Credentials file has insecure permissions: {cred_file}")
            print(f"[modules:SECURITY] Fix with: chmod 600 {cred_file}")
    except OSError:
        pass
    
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
        elif item_type in {"Assignment", "File", "Quiz"}:
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


def find_quiz(course, title: str):
    """Find a quiz by title."""
    for q in course.get_quizzes():
        if q.title == title:
            return q
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


def sync_quiz(course, folder: Path, meta: dict):
    """Add a quiz to its specified modules."""
    name = meta.get("name")
    modules = meta.get("modules") or []
    indent = meta.get("indent", 0)

    if not name:
        print(f"[modules:warn] {folder.name}: missing 'name' in meta.json for quiz")
        return
    if not modules:
        return

    quiz = find_quiz(course, name)
    if not quiz:
        print(f"[modules:warn] {folder.name}: quiz '{name}' not found in Canvas")
        print(f"[modules:hint] Run sync_quizzes.py first to create the quiz")
        return

    content_id = quiz.id
    for mname in modules:
        module = ensure_module(course, mname)
        if module_has_item(module, "Quiz", content_id=content_id):
            print(f"[modules] {folder.name}: already in module '{mname}' (Quiz)")
            continue

        module.create_module_item(
            module_item={
                "type": "Quiz",
                "content_id": content_id,
                "title": name,
                "indent": indent,
            }
        )
        print(f"[modules] {folder.name}: added to module '{mname}' (Quiz)")


# ---------- Module order helpers ----------

def infer_module_order_from_directories() -> list[str]:
    """
    Infer module order from directory structure when module_order.yaml is absent.
    
    Scans for module folders and sorts by numeric prefix:
    - NEW pattern: '05-Week 1.module' -> extracts "Week 1", sorts by 05
    - LEGACY pattern: 'module-Week 1' -> extracts "Week 1", no numeric sort
    
    Returns list of module names in sorted order.
    """
    import re
    
    module_folders = []
    
    if not PAGES_DIR.exists():
        return []
    
    # Scan for module folders (both patterns)
    for item in PAGES_DIR.iterdir():
        if not item.is_dir():
            continue
        
        name = item.name
        name_lower = name.lower()
        
        # NEW pattern: .module suffix
        if name_lower.endswith(".module"):
            # Strip the .module suffix
            module_name = name[:-7]  # len(".module") == 7
            
            # Check for numeric prefix (##- pattern)
            match = re.match(r'^(\d+)-(.+)$', module_name)
            if match:
                sort_key = int(match.group(1))
                module_name = match.group(2).strip()
            else:
                sort_key = 999  # No prefix, sort at end
            
            module_folders.append((sort_key, module_name, item.name))
        
        # LEGACY pattern: module- prefix
        elif name_lower.startswith("module-"):
            module_name = name[7:]  # Strip "module-" prefix
            
            # Check for numeric prefix in the module name itself
            match = re.match(r'^(\d+)-(.+)$', module_name)
            if match:
                sort_key = int(match.group(1))
                # Keep full name for legacy (don't strip prefix from module name)
            else:
                sort_key = 999
            
            module_folders.append((sort_key, module_name, item.name))
    
    if not module_folders:
        return []
    
    # Sort by numeric prefix, then by name
    module_folders.sort(key=lambda x: (x[0], x[1].lower()))
    
    # Extract just the module names
    order = [name for _, name, _ in module_folders]
    
    print(f"[modules] Inferred module order from directories: {order}")
    return order


def load_module_order() -> list[str]:
    """
    Load desired module order, with fallback to directory inference.
    
    Priority:
    1. module_order.yaml (explicit configuration)
    2. Directory structure (inferred from *.module folder prefixes)
    
    module_order.yaml accepts either:
      - {"modules": [...]} (preferred), or
      - a bare list at top level.
    """
    # 1. Check for explicit module_order.yaml
    if MODULE_ORDER_PATH.is_file():
        data = yaml.safe_load(MODULE_ORDER_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            mods = data.get("modules") or []
        elif isinstance(data, list):
            mods = data
        else:
            mods = []
        order = [str(m).strip() for m in mods if str(m).strip()]
        if order:
            print(f"[modules] Desired module order from YAML: {order}")
            return order
    
    # 2. Fallback: infer from directory structure
    return infer_module_order_from_directories()

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


def reorder_module_items(course, content_dirs: list[Path]):
    """
    Reorder items within each module based on folder sort keys.
    
    This function:
    1. Builds a mapping of module -> items with their sort keys
    2. For each module, reorders items to match the desired order
    
    Sort priority:
    1. Explicit 'position' in meta.json
    2. Numeric prefix from folder name (01-, 02-, etc.)
    3. Alphabetically by folder name (items without prefix come last)
    """
    # Build a mapping: module_name -> [(sort_key, item_title, folder)]
    module_items_map: dict[str, list[tuple]] = {}
    
    for folder in content_dirs:
        try:
            meta = load_meta(folder)
        except FileNotFoundError:
            continue
        
        modules = meta.get("modules") or []
        title = meta.get("name")
        if not title or not modules:
            continue
        
        sort_key = get_folder_sort_key(folder, meta)
        
        for mname in modules:
            if mname not in module_items_map:
                module_items_map[mname] = []
            module_items_map[mname].append((sort_key, title, folder, meta))
    
    # For each module, get current items and reorder if needed
    for module in course.get_modules():
        mname = module.name
        if mname not in module_items_map:
            continue
        
        # Sort the desired items by sort key
        desired_items = sorted(module_items_map[mname], key=lambda x: x[0])
        desired_titles = [item[1] for item in desired_items]
        
        # Get current module items
        current_items = list(module.get_module_items())
        if not current_items:
            continue
        
        # Build mapping of title -> item for items we care about
        title_to_item = {}
        for item in current_items:
            item_title = getattr(item, "title", None)
            if item_title:
                title_to_item[item_title] = item
        
        # Check if reordering is needed by comparing current order to desired
        current_managed_titles = [
            getattr(item, "title", None) 
            for item in current_items 
            if getattr(item, "title", None) in desired_titles
        ]
        
        if current_managed_titles == desired_titles:
            # Already in correct order
            continue
        
        print(f"[modules] Reordering items in module '{mname}'")
        
        # Reorder items: move each item to position 1 in reverse desired order
        # This pushes them to the top in the correct sequence
        for title in reversed(desired_titles):
            if title in title_to_item:
                item = title_to_item[title]
                try:
                    item.edit(module_item={"position": 1})
                except Exception as e:
                    print(f"[modules:warn] Failed to reorder '{title}' in '{mname}': {e}")


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
            elif t == "quiz":
                sync_quiz(course, folder, meta)
            else:
                print(f"[modules:warn] {folder.name}: unsupported type '{t}' in meta.json")
        
        # Reorder items within modules based on folder sort keys
        # Use all content dirs for full reorder context, not just changed ones
        all_content_dirs = list(iter_all_content_dirs())
        reorder_module_items(course, all_content_dirs)

    # Apply desired module order if provided
    if desired_module_order:
        print("[modules] Applying module order from module_order.yaml")
        apply_module_order(course, desired_module_order)

    print("[modules] Done.")


if __name__ == "__main__":
    main()
