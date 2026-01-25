#!/usr/bin/env python3

# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

from pathlib import Path
import json
import os
import re
import frontmatter
from zaphod.errors import (
    FrontmatterError,
    invalid_frontmatter_error,
    FileNotFoundError as ZaphodFileNotFoundError,
)


SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_ROOT = SCRIPT_DIR.parent
COURSES_ROOT = SHARED_ROOT.parent
COURSE_ROOT = Path.cwd()          # always "current course"
PAGES_DIR = COURSE_ROOT / "pages" # where applicable


def infer_module_from_path(folder: Path) -> str | None:
    """
    Given a content folder path, walk up the directory tree looking for
    a parent directory that starts with 'module-' (case-insensitive).
    
    Returns the module name (everything after 'module-'), or None if
    no module directory is found before reaching PAGES_DIR.
    
    If multiple module- directories exist in the path, returns the closest
    (innermost) one.
    
    Examples:
        pages/module-Week 1/intro.page/           -> "Week 1"
        pages/module-Credit 1/assignment1.assignment/ -> "Credit 1"
        pages/module-Outer/module-Inner/intro.page/  -> "Inner" (closest)
        pages/intro.page/                         -> None
    """
    current = folder.parent  # start with parent of content folder
    
    while current != PAGES_DIR and current != current.parent:
        name_lower = current.name.lower()
        if name_lower.startswith("module-"):
            # Extract module name (preserving original case after 'module-')
            return current.name[7:]  # len("module-") == 7
        current = current.parent
    
    return None


# {{var:key}} interpolation
VAR_RE = re.compile(r"\{\{var:([a-zA-Z_][a-zA-Z0-9_-]*)\}\}")


# {{include:name}} interpolation
INCLUDE_RE = re.compile(r"\{\{include:([a-zA-Z_][a-zA-Z0-9_-]*)\}\}")


def interpolate_body(body: str, metadata: dict) -> str:
    """
    Replace {{var:key}} in the body with corresponding values from metadata.
    If a key is missing, leave the placeholder as-is.
    """
    def replace(match):
        key = match.group(1)
        if key not in metadata:
            return match.group(0)
        return str(metadata[key])

    return VAR_RE.sub(replace, body)


def resolve_include_path(folder: Path, name: str) -> Path | None:
    """
    Resolve an include name to a concrete file path following precedence:
    1) <course>/pages/includes/name.md
    2) <course>/includes/name.md
    3) <root>/_all_courses/includes/name.md
    """
    candidates = [
        COURSE_ROOT / "pages" / "includes" / f"{name}.md",
        COURSE_ROOT / "includes" / f"{name}.md",
        COURSES_ROOT.parent / "_all_courses" / "includes" / f"{name}.md",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def interpolate_includes(body: str, folder: Path, metadata: dict) -> str:
    """
    Replace {{include:name}} in the body with the contents of the first
    matching includes/name.md, using the precedence rules above.
    Each included file is also processed with {{var:...}} interpolation.
    """
    def replace(match):
        name = match.group(1)
        inc_path = resolve_include_path(folder, name)
        if not inc_path:
            print(f"[frontmatter:warn] {folder.name}: include '{name}' not found")
            return match.group(0)
        try:
            inc_content = inc_path.read_text(encoding="utf-8")
            # Apply {{var:...}} to the include content
            inc_content = interpolate_body(inc_content, metadata)
            # Recursively expand any {{include:...}} inside the include
            inc_content = interpolate_includes(inc_content, folder, metadata)
            return inc_content
        except Exception as e:
            print(f"[frontmatter:warn] {folder.name}: failed to read include '{name}': {e}")
            return match.group(0)

    return INCLUDE_RE.sub(replace, body)


def get_changed_files() -> list[Path]:
    """
    Read ZAPHOD_CHANGED_FILES and return them as Path objects.
    If the env var is missing/empty, return an empty list.
    """
    raw = os.environ.get("ZAPHOD_CHANGED_FILES", "").strip()
    if not raw:
        return []
    return [Path(p) for p in raw.splitlines() if p.strip()]


def iter_all_content_dirs():
    """
    Existing full-scan behavior: yield every content folder under pages/
    ending in one of the known extensions.
    """
    for ext in [".page", ".assignment", ".link", ".file", ".quiz"]:
        for folder in PAGES_DIR.rglob(f"*{ext}"):
            yield folder


def iter_changed_content_dirs(changed_files: list[Path]):
    """
    From the changed files, yield the content folders that should be
    processed by this script.

    Rules:
    - Only care about index.md files.
    - Only if they live inside pages/** and inside a folder whose
      name ends with one of .page / .assignment / .link / .file.
    """
    exts = {".page", ".assignment", ".link", ".file", ".quiz"}

    seen: set[Path] = set()

    for path in changed_files:
        if path.name != "index.md":
            continue

        try:
            # Only consider files under this COURSE_ROOT
            rel = path.relative_to(COURSE_ROOT)
        except ValueError:
            continue

        # Must be under pages/
        if not rel.parts or rel.parts[0] != "pages":
            continue

        # Folder is the parent of index.md
        folder = path.parent

        if folder.suffix not in exts:
            continue

        if folder not in seen:
            seen.add(folder)
            yield folder


def process_folder(folder: Path):
    index_path = folder / "index.md"
    meta_path = folder / "meta.json"
    source_path = folder / "source.md"

    has_index = index_path.is_file()
    has_meta = meta_path.is_file()
    has_source = source_path.is_file()

    # 1) Preferred: index.md with frontmatter
    if has_index:
        try:
            post = frontmatter.load(index_path)
            metadata = dict(post.metadata)
            content = post.content.strip() + "\n"

            # First: expand includes, with {{var:...}} applied to each include
            content = interpolate_includes(content, folder, metadata)

            # Then: {{var:...}} in the main body
            content = interpolate_body(content, metadata)

        except Exception as e:
            print(f"[frontmatter:warn] {folder.name}: {e}")
        else:
            # Infer type from folder extension if not set
            if "type" not in metadata:
                ext_to_type = {
                    ".page": "page",
                    ".assignment": "assignment",
                    ".link": "link",
                    ".file": "file",
                    ".quiz": "quiz",
                }
                inferred_type = ext_to_type.get(folder.suffix)
                if inferred_type:
                    metadata["type"] = inferred_type
                    print(f"  [inferred type] '{inferred_type}' from folder extension")
            
            # Infer name from folder if not set
            if "name" not in metadata:
                folder_stem = folder.stem
                nice_name = re.sub(r'^\d+-', '', folder_stem)
                nice_name = nice_name.replace('-', ' ').replace('_', ' ').title()
                metadata["name"] = nice_name
                print(f"  [inferred name] '{nice_name}' from folder name")
            
            # Require minimum keys for a valid Canvas object
            for k in ["name", "type"]:
                if k not in metadata:
                    print(f"[frontmatter:warn] {folder.name}: missing '{k}', using meta.json if present")
                    break
            else:
                # Infer module from directory structure if not explicitly set
                if "modules" not in metadata or not metadata["modules"]:
                    inferred = infer_module_from_path(folder)
                    if inferred:
                        metadata["modules"] = [inferred]
                        print(f"  [inferred module] '{inferred}' from directory")
                
                with meta_path.open("w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                with source_path.open("w", encoding="utf-8") as f:
                    f.write(content)
                print(f"[✓ frontmatter] {folder.name}")
                return

    # 2) Fallback: existing meta.json + source.md
    if has_meta and has_source:
        print(f"[↻ meta.json] {folder.name}")
        return

    # 3) Nothing usable
    print(f"[frontmatter:err] {folder.name}: no usable metadata (index.md or meta.json/source.md)")


if __name__ == "__main__":
    if not PAGES_DIR.exists():
        raise SystemExit(f"No pages directory at {PAGES_DIR}")

    changed_files = get_changed_files()

    if changed_files:
        # Incremental mode: only process content folders for changed index.md files
        content_dirs = list(iter_changed_content_dirs(changed_files))
        if not content_dirs:
            print("[frontmatter] No relevant changed index.md files; nothing to do.")
    else:
        # Full mode: no env var => process everything (existing behavior)
        content_dirs = list(iter_all_content_dirs())

    for folder in content_dirs:
        process_folder(folder)
        print()  # separate each folder's output with a blank line
