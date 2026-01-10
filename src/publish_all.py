#!/usr/bin/env python3
"""
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

publish_all.py (Zaphod)

"""
from pathlib import Path
import os
import json
import re
import argparse

import markdown2canvas as mc
from markdown2canvas import canvas_objects
from markdown2canvas.setup_functions import make_canvas_api_obj

# Import get_course_id from your shared config_utils
from config_utils import get_course_id
from errors import (
    media_file_not_found_error,
    CanvasAPIError,
    SyncError,
)

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_ROOT = SCRIPT_DIR.parent
COURSES_ROOT = SHARED_ROOT.parent
COURSE_ROOT = Path.cwd()          # always "current course"
PAGES_DIR = COURSE_ROOT / "pages" # where applicable
ASSETS_DIR = COURSE_ROOT / "assets" # course assets folder
METADATA_DIR = COURSE_ROOT / "_course_metadata"
UPLOAD_CACHE_FILE = METADATA_DIR / "upload_cache.json"

# Optional: disable buggy module handling inside markdown2canvas
def _no_modules(self, course):
    return None

canvas_objects.Page.ensure_in_modules = _no_modules
canvas_objects.Assignment.ensure_in_modules = _no_modules
canvas_objects.Link.ensure_in_modules = _no_modules
canvas_objects.File.ensure_in_modules = _no_modules


def load_upload_cache() -> dict:
    """Load the cache of previously uploaded files."""
    if UPLOAD_CACHE_FILE.exists():
        try:
            return json.loads(UPLOAD_CACHE_FILE.read_text())
        except Exception as e:
            print(f"[cache:warn] Failed to load cache: {e}")
    return {}


def save_upload_cache(cache: dict):
    """Save the upload cache to disk."""
    try:
        # Ensure the metadata directory exists
        METADATA_DIR.mkdir(parents=True, exist_ok=True)
        UPLOAD_CACHE_FILE.write_text(json.dumps(cache, indent=2))
    except Exception as e:
        print(f"[cache:warn] Failed to save cache: {e}")


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
    for ext in [".page", ".assignment", ".link", ".file"]:
        for folder in PAGES_DIR.rglob(f"*{ext}"):
            yield folder


def iter_changed_content_dirs(changed_files: list[Path]):
    """
    From changed files, yield the content folders that should be
    published by this script.

    Rules:
    - Only care about index.md (or source.md if you want).
    - Must live under pages/**.
    - Parent folder must end with .page / .assignment / .link / .file.
    """
    exts = {".page", ".assignment", ".link", ".file"}
    seen: set[Path] = set()

    for path in changed_files:
        if path.name not in {"index.md", "source.md"}:
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


def find_all_asset_files() -> list[Path]:
    """
    Find all asset files in the assets directory.
    Returns list of Path objects for uploadable files.
    Excludes system files and metadata files.
    """
    if not ASSETS_DIR.exists():
        return []

    # Common asset extensions to upload
    asset_extensions = {
        # Videos
        '.mp4', '.mov', '.avi', '.webm', '.mkv', '.m4v', '.flv', '.wmv',
        # Images
        '.jpg', '.jpeg', '.png', '.gif', '.svg', '.bmp', '.webp', '.ico', '.tiff',
        # Documents
        '.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt',
        # Archives
        '.zip', '.tar', '.gz', '.rar', '.7z',
        # Spreadsheets
        '.xls', '.xlsx', '.csv', '.ods',
        # Presentations
        '.ppt', '.pptx', '.odp',
        # Audio
        '.mp3', '.wav', '.ogg', '.m4a', '.flac',
        # Other common formats
        '.json', '.xml', '.yaml', '.yml'
    }

    # Files to exclude
    exclude_patterns = {
        ':Zone.Identifier',  # Windows metadata
        '.DS_Store',         # macOS metadata
        'Thumbs.db',         # Windows thumbnails
        '.gitkeep',          # Git placeholder
    }

    asset_files = []

    for file_path in ASSETS_DIR.rglob('*'):
        if not file_path.is_file():
            continue

        # Check if file should be excluded
        if any(pattern in file_path.name for pattern in exclude_patterns):
            continue

        # Check if extension is in our list (case-insensitive)
        if file_path.suffix.lower() in asset_extensions:
            asset_files.append(file_path)

    return asset_files


def find_video_references_in_content() -> dict[str, list[Path]]:
    """
    Scan all .page and .assignment folders for video files referenced in source.md.
    Returns dict mapping filename to list of folders that reference it.
    """
    VIDEO_RE = re.compile(r"\{\{video:\s*\"?([^}\"]+?)\"?\s*\}\}")
    references = {}

    for ext in [".page", ".assignment"]:
        for folder in PAGES_DIR.rglob(f"*{ext}"):
            source_md = folder / "source.md"
            if source_md.is_file():
                text = source_md.read_text(encoding="utf-8")
                matches = VIDEO_RE.findall(text)
                for filename in matches:
                    filename = filename.strip()
                    if filename not in references:
                        references[filename] = []
                    references[filename].append(folder)

    return references


def make_mc_obj(path: Path):
    s = str(path)
    if s.endswith(".page"):
        return mc.Page(s)
    if s.endswith(".assignment"):
        return mc.Assignment(s)
    if s.endswith(".link"):
        return mc.Link(s)
    if s.endswith(".file"):
        return mc.File(s)
    raise ValueError(f"Unknown type for {s}")


# {{video:filename}} regex (with optional quotes)
VIDEO_RE = re.compile(r"\{\{video:\s*\"?([^}\"]+?)\"?\s*\}\}")


def upload_file_to_canvas(course, file_path: Path, cache: dict):
    """
    Upload a file to Canvas and return the File object.
    Uses cache to avoid re-uploading.
    """
    filename = file_path.name
    cache_key = f"{course.id}:{filename}"

    # 1) Check cache first
    if cache_key in cache:
        try:
            file_id = cache[cache_key]
            return course.get_file(file_id)
        except Exception as e:
            print(f"[cache:warn] Cached file {filename} (id={file_id}) not found, will re-upload: {e}")
            del cache[cache_key]

    # 2) Search existing files by name
    for f in course.get_files(search_term=filename):
        if f.display_name == filename or f.filename == filename:
            cache[cache_key] = f.id
            return f

    # 3) Upload from local disk
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    print(f"[upload] Uploading {filename}...")
    success, resp = course.upload(str(file_path))
    if not success:
        raise RuntimeError(f"Upload failed for {file_path}: {resp}")

    file_id = resp.get("id")
    if not file_id:
        raise RuntimeError(f"No file id in upload response for {file_path}: {resp}")

    # Cache the uploaded file
    cache[cache_key] = file_id

    return course.get_file(file_id)


def get_or_upload_video_file(course, folder: Path, filename: str, cache: dict):
    """
    Return a canvasapi File object for `filename` in this course.
    First tries to find in cache/Canvas, then looks in assets folder or content folder.
    """
    cache_key = f"{course.id}:{filename}"

    # 1) Check cache first
    if cache_key in cache:
        try:
            file_id = cache[cache_key]
            return course.get_file(file_id)
        except Exception as e:
            print(f"[cache:warn] Cached file {filename} (id={file_id}) not found, will re-upload: {e}")
            del cache[cache_key]

    # 2) Search existing files by name
    try:
        for f in course.get_files(search_term=filename):
            if f.display_name == filename or f.filename == filename:
                cache[cache_key] = f.id
                return f
    except Exception as e:
        # BETTER ERROR: API error with context
        raise CanvasAPIError(
            message="Failed to search for existing files in Canvas",
            suggestion="Check your Canvas API credentials and network connection",
            context={
                "course_id": course.id,
                "filename": filename,
                "operation": "search_files"
            },
            cause=e
        )

    # 3) Look for file in assets directory first, then in content folder
    local_path = None
    searched_paths = []
    
    if ASSETS_DIR.exists():
        asset_path = ASSETS_DIR / filename
        searched_paths.append(asset_path)
        if asset_path.is_file():
            local_path = asset_path

    if not local_path:
        content_path = folder / filename
        searched_paths.append(content_path)
        if content_path.is_file():
            local_path = content_path

    if not local_path:
        # BETTER ERROR: Show where we looked
        raise media_file_not_found_error(
            filename=filename,
            source_file=folder / "index.md",
            searched_paths=searched_paths
        )

    # Upload via Canvas API
    print(f"[upload] Uploading {filename} from {local_path.parent.name}/...")
    try:
        success, resp = course.upload(str(local_path))
        if not success:
            raise SyncError(
                message=f"Canvas upload failed for {filename}",
                suggestion=(
                    "Possible issues:\n"
                    "  - File too large (Canvas has size limits)\n"
                    "  - Insufficient permissions\n"
                    "  - Network timeout\n\n"
                    "Try:\n"
                    "  - Check file size\n"
                    "  - Verify Canvas permissions\n"
                    "  - Retry the sync"
                ),
                context={
                    "file": filename,
                    "size_mb": local_path.stat().st_size / (1024 * 1024),
                    "response": str(resp)
                }
            )
    except Exception as e:
        raise SyncError(
            message=f"Error uploading {filename}",
            context={
                "file": str(local_path),
                "course_id": course.id
            },
            cause=e
        )

    file_id = resp.get("id")
    if not file_id:
        raise SyncError(
            message=f"Upload succeeded but no file ID returned for {filename}",
            suggestion="This is unusual - check Canvas Files to see if upload succeeded",
            context={"response": resp}
        )

    # Cache the uploaded file
    cache[cache_key] = file_id
    return course.get_file(file_id)


def replace_video_placeholders(text: str, course, folder: Path, canvas_base_url: str, cache: dict) -> str:
    """
    Replace {{video:filename}} or {{video:"filename with spaces"}} with a Canvas media-attachment iframe.
    """
    def replace(match):
        raw = match.group(1).strip()
        try:
            f = get_or_upload_video_file(course, folder, raw, cache)
        except Exception as e:
            print(f"[publish:warn] {folder.name}: video '{raw}': {e}")
            return match.group(0)

        # Use Canvas media_attachments_iframe URL
        src = f"{canvas_base_url}/media_attachments_iframe/{f.id}"

        return (
            f'<iframe style="width: 480px; height: 300px; display: inline-block;" '
            f'title="Video player for {f.display_name}" '
            f'data-media-type="video" '
            f'src="{src}" '
            f'loading="lazy" '
            f'allowfullscreen="allowfullscreen" '
            f'allow="fullscreen"></iframe>'
        )

    result = VIDEO_RE.sub(replace, text)
    print(f"[debug] Final text length: {len(result)}")
    print(f"[debug] Final text contains media_attachments_iframe: {'media_attachments_iframe' in result}")
    return result


def bulk_upload_assets(course, canvas_base_url: str, cache: dict):
    """
    Bulk upload all asset files found in assets directory.
    Uploads videos, images, PDFs, zip files, and other common asset types.
    """
    print("[bulk-upload] Scanning for asset files...")

    # Get all assets from assets directory
    asset_files = find_all_asset_files()

    if not asset_files:
        print("[bulk-upload] No asset files found in assets/ directory.")
        return

    # Group files by type for better reporting
    file_types = {}
    for file_path in asset_files:
        ext = file_path.suffix.lower()
        if ext not in file_types:
            file_types[ext] = []
        file_types[ext].append(file_path)

    print(f"[bulk-upload] Found {len(asset_files)} asset file(s):")
    for ext, files in sorted(file_types.items()):
        print(f"  {ext}: {len(files)} file(s)")

    uploaded = 0
    skipped = 0
    failed = 0

    for file_path in sorted(asset_files):
        filename = file_path.name
        try:
            cache_key = f"{course.id}:{filename}"
            if cache_key in cache:
                print(f"[bulk-upload] ✓ {filename} (already uploaded)")
                skipped += 1
                continue

            upload_file_to_canvas(course, file_path, cache)
            uploaded += 1
            print(f"[bulk-upload] ✓ {filename}")
        except Exception as e:
            failed += 1
            print(f"[bulk-upload] ✗ {filename}: {type(e).__name__}: {e}")

    print(f"\n[bulk-upload] Summary: {uploaded} uploaded, {skipped} skipped, {failed} failed")
    save_upload_cache(cache)


def main():
    parser = argparse.ArgumentParser(description="Publish Canvas course content")
    parser.add_argument(
        "--assets-only",
        action="store_true",
        help="Only upload asset files (videos, images, PDFs, etc.) without publishing content"
    )
    args = parser.parse_args()

    if not PAGES_DIR.exists():
        raise SystemExit(f"No pages directory at {PAGES_DIR}")

    # Set up Canvas API
    canvas = make_canvas_api_obj()
    CANVAS_BASE_URL = os.environ.get("CANVAS_BASE_URL", "https://canvas.instructure.com")

    # Get the single course ID for this course
    course_id = get_course_id(course_dir=COURSE_ROOT)
    if course_id is None:
        raise SystemExit("[publish] Cannot determine Canvas course ID; aborting.")

    course = canvas.get_course(course_id)

    # Load upload cache
    cache = load_upload_cache()

    # Handle assets-only mode
    if args.assets_only:
        bulk_upload_assets(course, CANVAS_BASE_URL, cache)
        return

    # Normal publish mode
    changed_files = get_changed_files()

    if changed_files:
        # Incremental mode: only publish content dirs related to changed files
        content_dirs = list(iter_changed_content_dirs(changed_files))
        if not content_dirs:
            print("[publish] No relevant changed files; nothing to publish.")
            return
    else:
        # Full mode: no env var => publish everything (existing behavior)
        content_dirs = list(iter_all_content_dirs())

    for d in content_dirs:
        try:
            obj = make_mc_obj(d)
            print(f"[debug] Processing {d.name} as {type(obj).__name__}")

            # Only Pages and Assignments have source.md
            if isinstance(obj, (mc.Page, mc.Assignment)):
                source_md = d / "source.md"
                if source_md.is_file():
                    text = source_md.read_text(encoding="utf-8")
                    print(f"[debug] {d.name}: read source.md ({len(text)} chars)")
                    text = replace_video_placeholders(text, course, d, CANVAS_BASE_URL, cache)
                    print(f"[debug] {d.name}: after video replacement ({len(text)} chars)")
                    source_md.write_text(text, encoding="utf-8")
                    print(f"[debug] {d.name}: wrote modified source.md")
                else:
                    print(f"[debug] {d.name}: source.md not found")

            obj.publish(course, overwrite=True)
            print(f"[✓ publish] {d.name}")
        except Exception as e:
            print(f"[publish:err] {d.name}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        print()

    # Save cache after publishing
    save_upload_cache(cache)


if __name__ == "__main__":
    main()
