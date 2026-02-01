#!/usr/bin/env python3
"""
publish_all.py (Zaphod)

Publish course content to Canvas.

This script:
1. Iterates over content folders (pages/*.page, *.assignment, *.link, *.file)
2. Replaces {{video:...}} placeholders with Canvas media iframes
3. Publishes content to Canvas via native Zaphod classes

No longer depends on markdown2canvas - uses canvasapi directly.
"""

from pathlib import Path
import os
import json
import re
import argparse
import hashlib

# Zaphod modules
from zaphod.canvas_client import make_canvas_api_obj, get_canvas_base_url
from zaphod.canvas_publish import make_zaphod_obj, ZaphodPage, ZaphodAssignment
from zaphod.config_utils import get_course_id
from zaphod.errors import (
    media_file_not_found_error,
    CanvasAPIError,
    SyncError,
)
from zaphod.security_utils import is_safe_path
from zaphod.icons import SUCCESS, ERROR


# Paths relative to course root (cwd)
COURSE_ROOT = Path.cwd()
CONTENT_DIR = COURSE_ROOT / "content"
PAGES_DIR = COURSE_ROOT / "pages"  # Legacy fallback
ASSETS_DIR = COURSE_ROOT / "assets"
METADATA_DIR = COURSE_ROOT / "_course_metadata"
UPLOAD_CACHE_FILE = METADATA_DIR / "upload_cache.json"


# =============================================================================
# Content Directory Resolution
# =============================================================================

def get_content_dir() -> Path:
    """Get content directory, preferring content/ over pages/."""
    if CONTENT_DIR.exists():
        return CONTENT_DIR
    return PAGES_DIR


# =============================================================================
# Upload cache helpers
# =============================================================================

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
        METADATA_DIR.mkdir(parents=True, exist_ok=True)
        UPLOAD_CACHE_FILE.write_text(json.dumps(cache, indent=2))
    except Exception as e:
        print(f"[cache:warn] Failed to save cache: {e}")


# =============================================================================
# Changed files helpers (for incremental mode)
# =============================================================================

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
    Yield every content folder under content/ (or pages/) ending in a known extension.
    """
    content_dir = get_content_dir()
    for ext in [".page", ".assignment", ".link", ".file"]:
        for folder in content_dir.rglob(f"*{ext}"):
            yield folder


def iter_changed_content_dirs(changed_files: list[Path]):
    """
    From changed files, yield the content folders that should be published.
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

        # Must be under content/ or pages/
        if not rel.parts or rel.parts[0] not in ("content", "pages"):
            continue

        folder = path.parent

        if folder.suffix not in exts:
            continue

        if folder not in seen:
            seen.add(folder)
            yield folder


# =============================================================================
# Video placeholder handling
# =============================================================================

# {{video:filename}} regex (with optional quotes)
VIDEO_RE = re.compile(r"\{\{video:\s*\"?([^}\"]+?)\"?\s*\}\}")


def get_or_upload_video_file(course, folder: Path, filename: str, cache: dict):
    """
    Return a canvasapi File object for `filename` in this course.
    First tries cache/Canvas, then looks locally using find_local_asset.
    
    Uses content-hash caching to handle file updates properly.
    
    Supports:
    - Simple filename: {{video:intro.mp4}}
    - Explicit path: {{video:videos/intro.mp4}} or {{video:../assets/videos/intro.mp4}}
    """
    clean_name = Path(filename).name
    
    # Find the local file first to get content hash
    local_path = find_local_asset(folder, filename)
    
    if local_path:
        # Use content hash for cache key (handles updates)
        content_hash = hashlib.md5(local_path.read_bytes()).hexdigest()[:12]
        cache_key = f"{course.id}:{clean_name}:{content_hash}"
    else:
        # Fallback to name-only key if file not found locally
        cache_key = f"{course.id}:{clean_name}"
        content_hash = None

    # 1) Check cache first
    if cache_key in cache:
        try:
            file_id = cache[cache_key]
            return course.get_file(file_id)
        except Exception as e:
            print(f"[cache:warn] Cached file {clean_name} (id={file_id}) not found, will re-upload: {e}")
            del cache[cache_key]

    # 2) If no local file, search Canvas by name (legacy behavior)
    if not local_path:
        try:
            for f in course.get_files(search_term=clean_name):
                if f.display_name == clean_name or f.filename == clean_name:
                    cache[cache_key] = f.id
                    return f
        except Exception as e:
            raise CanvasAPIError(
                message="Failed to search for existing files in Canvas",
                suggestion="Check your Canvas API credentials and network connection",
                context={
                    "course_id": course.id,
                    "filename": clean_name,
                    "operation": "search_files"
                },
                cause=e
            )
        
        # Build list of searched paths for error message
        searched_paths = [folder / clean_name]
        if ASSETS_DIR.exists():
            searched_paths.append(ASSETS_DIR / clean_name)
        raise media_file_not_found_error(
            filename=filename,
            source_file=folder / "index.md",
            searched_paths=searched_paths
        )

    # 3) Upload to Canvas
    print(f"[upload] Uploading {clean_name} from {local_path.parent.name}/...")
    try:
        success, resp = course.upload(str(local_path))
        if not success:
            raise SyncError(
                message=f"Canvas upload failed for {clean_name}",
                suggestion="Check file size, permissions, and network connection",
                context={
                    "file": clean_name,
                    "size_mb": local_path.stat().st_size / (1024 * 1024),
                    "response": str(resp)
                }
            )
    except SyncError:
        raise
    except Exception as e:
        raise SyncError(
            message=f"Error uploading {clean_name}",
            context={"file": str(local_path), "course_id": course.id},
            cause=e
        )

    file_id = resp.get("id")
    if not file_id:
        raise SyncError(
            message=f"Upload succeeded but no file ID returned for {clean_name}",
            suggestion="Check Canvas Files to see if upload succeeded",
            context={"response": resp}
        )

    cache[cache_key] = file_id
    print(f"[upload] Uploaded {clean_name} (id={file_id}, hash={content_hash})")
    return course.get_file(file_id)


def replace_video_placeholders(text: str, course, folder: Path, canvas_base_url: str, cache: dict) -> str:
    """
    Replace {{video:filename}} with Canvas media-attachment iframe.
    
    Includes data-zaphod-video attribute for round-trip preservation.
    """
    def replace(match):
        original_token = match.group(0)  # e.g., {{video:"intro.mp4"}}
        raw = match.group(1).strip()     # e.g., intro.mp4
        
        try:
            f = get_or_upload_video_file(course, folder, raw, cache)
        except Exception as e:
            print(f"[publish:warn] {folder.name}: video '{raw}': {e}")
            return original_token  # Leave placeholder if upload fails

        # Canvas media iframe URL
        src = f"{canvas_base_url}/media_attachments_iframe/{f.id}"
        
        # Escape the original token for HTML attribute
        escaped_token = original_token.replace('"', '&quot;')

        return (
            f'<iframe style="width: 640px; height: 360px; display: inline-block;" '
            f'title="Video player for {f.display_name}" '
            f'data-media-type="video" '
            f'data-zaphod-video="{escaped_token}" '
            f'src="{src}" '
            f'loading="lazy" '
            f'allowfullscreen="allowfullscreen" '
            f'allow="fullscreen" '
            f'frameborder="0"></iframe>'
        )

    return VIDEO_RE.sub(replace, text)


# =============================================================================
# Local asset reference handling (images, PDFs, etc. in markdown)
# =============================================================================

# Patterns to match local file references in markdown
# Markdown image: ![alt](path) or ![alt](path "title")
MD_IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)')

# Markdown link: [text](path) or [text](path "title")  
MD_LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)')

# HTML img tag: <img src="path" ...>
HTML_IMG_RE = re.compile(r'<img\s+[^>]*src=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)

# HTML anchor with href to local file: <a href="path" ...>
HTML_LINK_RE = re.compile(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)

# File extensions we consider local assets (not URLs)
LOCAL_ASSET_EXTENSIONS = {
    # Images
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.bmp', '.webp', '.ico', '.tiff',
    # Documents
    '.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt',
    # Spreadsheets
    '.xls', '.xlsx', '.csv', '.ods',
    # Presentations
    '.ppt', '.pptx', '.odp',
    # Archives
    '.zip', '.tar', '.gz', '.rar', '.7z',
    # Audio (non-video)
    '.mp3', '.wav', '.ogg', '.m4a', '.flac',
    # Other
    '.json', '.xml', '.yaml', '.yml', '.html', '.htm',
}


def is_local_asset_reference(path_str: str) -> bool:
    """
    Determine if a path string is a local asset reference (not a URL or anchor).
    """
    # Skip URLs
    if path_str.startswith(('http://', 'https://', '//', 'data:')):
        return False
    
    # Skip anchors
    if path_str.startswith('#'):
        return False
    
    # Skip Canvas file URLs (already processed)
    if '/files/' in path_str or '/courses/' in path_str:
        return False
    
    # Check if it has a recognized asset extension
    path_lower = path_str.lower()
    return any(path_lower.endswith(ext) for ext in LOCAL_ASSET_EXTENSIONS)


def find_local_asset(folder: Path, filename: str) -> Path | None:
    """
    Find a local asset file, checking in order:
    1. The content folder itself (exact filename)
    2. Explicit relative path from the content folder (e.g., ../assets/images/logo.png)
    3. Path relative to assets/ directory (e.g., images/logo.png)
    4. Auto-discover by filename anywhere in assets/ subfolders
    
    For auto-discovery (#4), if multiple files match the same filename,
    prints a warning and returns None (user must use explicit path).
    
    SECURITY: All paths are validated to be within COURSE_ROOT or ASSETS_DIR
    to prevent path traversal attacks.
    
    Returns the Path if found (unambiguously), None otherwise.
    """
    clean_name = Path(filename).name
    
    # 1. Check content folder for exact filename
    local_path = folder / clean_name
    if local_path.is_file():
        # SECURITY: Validate path is within course directory
        if is_safe_path(COURSE_ROOT, local_path):
            return local_path
        else:
            print(f"[assets:SECURITY] Blocked path traversal: {filename}")
            return None
    
    # 2. Try explicit relative path from content folder, resolved
    #    This handles ../assets/images/logo.png correctly
    relative_path = (folder / filename).resolve()
    if relative_path.is_file():
        # SECURITY: Validate resolved path is within course directory
        if is_safe_path(COURSE_ROOT, relative_path):
            return relative_path
        else:
            print(f"[assets:SECURITY] Blocked path traversal: {filename}")
            print(f"[assets:SECURITY] Resolved path {relative_path} is outside course directory")
            return None
    
    # 3. Try path relative to assets/ directory (e.g., images/logo.png)
    if ASSETS_DIR.exists():
        asset_relative = ASSETS_DIR / filename
        if asset_relative.is_file():
            # SECURITY: Validate path is within assets directory
            if is_safe_path(ASSETS_DIR, asset_relative):
                return asset_relative
            else:
                print(f"[assets:SECURITY] Blocked path traversal: {filename}")
                return None
        
        # 4. Auto-discover: search all subfolders for filename match
        #    But only if we haven't already found it via explicit path
        matches = list(ASSETS_DIR.rglob(clean_name))
        matches = [m for m in matches if m.is_file()]
        
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            # Ambiguous - multiple files with same name
            locations = [str(m.relative_to(ASSETS_DIR)) for m in matches]
            print(f"[assets:warn] Multiple files named '{clean_name}' found:")
            for loc in locations:
                print(f"              - assets/{loc}")
            print(f"              Use explicit path, e.g., ../assets/{locations[0]}")
            return None
    
    return None


def get_or_upload_local_asset(course, folder: Path, filename: str, cache: dict) -> str | None:
    """
    Upload a local asset to Canvas and return its download URL.
    
    Uses content hash in cache key to handle:
    - Same filename in different locations (assets/ vs page folder)
    - Updated files with the same name
    
    Returns:
        Canvas file download URL, or None if file not found/upload failed
    """
    # Find the local file
    local_path = find_local_asset(folder, filename)
    if not local_path:
        print(f"[assets:warn] Local asset not found: {filename}")
        return None
    
    actual_filename = local_path.name
    
    # Use content hash to uniquely identify files
    # This handles same filename in different locations + file updates
    content_hash = hashlib.md5(local_path.read_bytes()).hexdigest()[:12]
    cache_key = f"{course.id}:{actual_filename}:{content_hash}"
    
    # Check cache first
    if cache_key in cache:
        try:
            file_id = cache[cache_key]
            canvas_file = course.get_file(file_id)
            # Return the download URL
            return canvas_file.url
        except Exception as e:
            print(f"[assets:warn] Cached file {actual_filename} not found, re-uploading: {e}")
            del cache[cache_key]
    
    # Note: We skip searching Canvas by filename since content hash means
    # we want this specific version of the file. If hash changed, re-upload.
    
    # Upload the file
    print(f"[assets] Uploading {actual_filename} from {local_path.parent.name}/...")
    try:
        success, resp = course.upload(str(local_path))
        if not success:
            print(f"[assets:err] Upload failed for {actual_filename}: {resp}")
            return None
        
        file_id = resp.get("id")
        if not file_id:
            print(f"[assets:err] No file ID returned for {actual_filename}")
            return None
        
        cache[cache_key] = file_id
        canvas_file = course.get_file(file_id)
        print(f"[assets] Uploaded {actual_filename} (id={file_id}, hash={content_hash})")
        return canvas_file.url
        
    except Exception as e:
        print(f"[assets:err] Error uploading {actual_filename}: {e}")
        return None


def replace_local_asset_references(text: str, course, folder: Path, cache: dict) -> str:
    """
    Find local asset references in markdown/HTML and replace with Canvas URLs.
    
    Handles:
    - Markdown images: ![alt](local.png)
    - Markdown links: [text](document.pdf)
    - HTML img tags: <img src="local.png">
    - HTML anchor tags: <a href="document.pdf">
    
    Only processes references that:
    - Are not URLs (http://, https://, //)
    - Have recognized asset extensions
    - Can be found locally (in folder or assets/)
    """
    # Track which files we've processed to avoid duplicate uploads
    processed_files: dict[str, str] = {}  # original_ref -> canvas_url
    
    def get_canvas_url(original_ref: str) -> str | None:
        """Get Canvas URL for a reference, using cache to avoid re-processing."""
        if original_ref in processed_files:
            return processed_files[original_ref]
        
        if not is_local_asset_reference(original_ref):
            return None
        
        canvas_url = get_or_upload_local_asset(course, folder, original_ref, cache)
        if canvas_url:
            processed_files[original_ref] = canvas_url
        return canvas_url
    
    # Process markdown images: ![alt](path)
    def replace_md_image(match):
        alt_text = match.group(1)
        file_ref = match.group(2)
        
        canvas_url = get_canvas_url(file_ref)
        if canvas_url:
            return f'![{alt_text}]({canvas_url})'
        return match.group(0)  # Keep original if not found
    
    text = MD_IMAGE_RE.sub(replace_md_image, text)
    
    # Process markdown links: [text](path) - only for asset files
    def replace_md_link(match):
        link_text = match.group(1)
        file_ref = match.group(2)
        
        canvas_url = get_canvas_url(file_ref)
        if canvas_url:
            return f'[{link_text}]({canvas_url})'
        return match.group(0)
    
    text = MD_LINK_RE.sub(replace_md_link, text)
    
    # Process HTML img tags: <img src="path">
    def replace_html_img(match):
        full_tag = match.group(0)
        file_ref = match.group(1)
        
        canvas_url = get_canvas_url(file_ref)
        if canvas_url:
            return full_tag.replace(file_ref, canvas_url)
        return full_tag
    
    text = HTML_IMG_RE.sub(replace_html_img, text)
    
    # Process HTML anchor tags: <a href="path"> - only for asset files
    def replace_html_link(match):
        full_tag = match.group(0)
        file_ref = match.group(1)
        
        canvas_url = get_canvas_url(file_ref)
        if canvas_url:
            return full_tag.replace(file_ref, canvas_url)
        return full_tag
    
    text = HTML_LINK_RE.sub(replace_html_link, text)
    
    return text


# =============================================================================
# Asset bulk upload
# =============================================================================

def find_all_asset_files() -> list[Path]:
    """Find all uploadable asset files in the assets directory."""
    if not ASSETS_DIR.exists():
        return []

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
        # Other
        '.json', '.xml', '.yaml', '.yml'
    }

    exclude_patterns = {
        ':Zone.Identifier', '.DS_Store', 'Thumbs.db', '.gitkeep',
    }

    asset_files = []
    for file_path in ASSETS_DIR.rglob('*'):
        if not file_path.is_file():
            continue
        if any(pattern in file_path.name for pattern in exclude_patterns):
            continue
        if file_path.suffix.lower() in asset_extensions:
            asset_files.append(file_path)

    return asset_files


def upload_file_to_canvas(course, file_path: Path, cache: dict):
    """Upload a file to Canvas, using content-hash cache to avoid re-uploads."""
    filename = file_path.name
    
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Use content hash for cache key
    content_hash = hashlib.md5(file_path.read_bytes()).hexdigest()[:12]
    cache_key = f"{course.id}:{filename}:{content_hash}"

    if cache_key in cache:
        try:
            file_id = cache[cache_key]
            return course.get_file(file_id)
        except Exception:
            del cache[cache_key]

    print(f"[upload] Uploading {filename}...")
    success, resp = course.upload(str(file_path))
    if not success:
        raise RuntimeError(f"Upload failed for {file_path}: {resp}")

    file_id = resp.get("id")
    if not file_id:
        raise RuntimeError(f"No file id in upload response for {file_path}")

    cache[cache_key] = file_id
    print(f"[upload] Uploaded {filename} (id={file_id}, hash={content_hash})")
    return course.get_file(file_id)


def bulk_upload_assets(course, cache: dict):
    """Bulk upload all asset files."""
    print("[bulk-upload] Scanning for asset files...")

    asset_files = find_all_asset_files()
    if not asset_files:
        print("[bulk-upload] No asset files found in assets/ directory.")
        return

    # Group by extension for reporting
    file_types = {}
    for file_path in asset_files:
        ext = file_path.suffix.lower()
        file_types.setdefault(ext, []).append(file_path)

    print(f"[bulk-upload] Found {len(asset_files)} asset file(s):")
    for ext, files in sorted(file_types.items()):
        print(f"  {ext}: {len(files)} file(s)")

    uploaded = skipped = failed = 0

    for file_path in sorted(asset_files):
        filename = file_path.name
        try:
            # Use content hash for cache check
            content_hash = hashlib.md5(file_path.read_bytes()).hexdigest()[:12]
            cache_key = f"{course.id}:{filename}:{content_hash}"
            if cache_key in cache:
                print(f"[bulk-upload] {SUCCESS} {filename} (already uploaded)")
                skipped += 1
                continue

            upload_file_to_canvas(course, file_path, cache)
            uploaded += 1
        except Exception as e:
            failed += 1
            print(f"[bulk-upload]  {ERROR}  {filename}: {type(e).__name__}: {e}")

    print(f"\n[bulk-upload] Summary: {uploaded} uploaded, {skipped} skipped, {failed} failed")
    save_upload_cache(cache)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Publish Canvas course content")
    parser.add_argument(
        "--assets-only",
        action="store_true",
        help="Only upload asset files, skip content publishing"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Preview what would be published without making changes"
    )
    args = parser.parse_args()

    content_dir = get_content_dir()
    if not content_dir.exists():
        raise SystemExit(f"No content directory found. Create content/ or pages/ in {COURSE_ROOT}")

    print(f"[publish] Using content directory: {content_dir.name}/")

    # Set up Canvas API using native Zaphod client
    canvas = make_canvas_api_obj()
    canvas_base_url = get_canvas_base_url()

    # Get course ID
    course_id = get_course_id(course_dir=COURSE_ROOT)
    if course_id is None:
        raise SystemExit("[publish] Cannot determine Canvas course ID; aborting.")

    course = canvas.get_course(course_id)
    if args.dry_run:
        print(f"[publish] DRY RUN - would publish to course: {course.name} (ID {course_id})")
    else:
        print(f"[publish] Publishing to course: {course.name} (ID {course_id})")

    # Load upload cache
    cache = load_upload_cache()

    # Handle assets-only mode
    if args.assets_only:
        if args.dry_run:
            print("[publish] (dry-run) Would upload assets")
        else:
            bulk_upload_assets(course, cache)
        return

    # Determine which content to publish
    changed_files = get_changed_files()

    if changed_files:
        content_dirs = list(iter_changed_content_dirs(changed_files))
        if not content_dirs:
            print("[publish] No relevant changed files; nothing to publish.")
            return
    else:
        content_dirs = list(iter_all_content_dirs())

    # Publish each content folder
    for d in content_dirs:
        try:
            # Create Zaphod content object
            obj = make_zaphod_obj(d)
            
            if args.dry_run:
                print(f"[publish] (dry-run) Would publish {d.name} as {type(obj).__name__}")
                continue
            
            print(f"[publish] Processing {d.name} as {type(obj).__name__}")

            # For Pages and Assignments: process placeholders and local assets
            if isinstance(obj, (ZaphodPage, ZaphodAssignment)):
                source_md = d / "source.md"
                if source_md.is_file():
                    text = source_md.read_text(encoding="utf-8")
                    
                    # 1. Replace {{video:...}} placeholders
                    text = replace_video_placeholders(text, course, d, canvas_base_url, cache)
                    
                    # 2. Upload and rewrite local asset references (images, PDFs, etc.)
                    text = replace_local_asset_references(text, course, d, cache)
                    
                    source_md.write_text(text, encoding="utf-8")
                    
                    # Reload the object so it picks up the modified source
                    obj = make_zaphod_obj(d)

            # Publish to Canvas
            obj.publish(course, overwrite=True)
            print(f"[ÃƒÂ¢Ã…â€œÃ¢â‚¬Å“ publish] {d.name}")
            
        except Exception as e:
            print(f"[publish:err] {d.name}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        
        print()

    # Save cache (skip in dry-run mode)
    if not args.dry_run:
        save_upload_cache(cache)
        print("[publish] Done.")
    else:
        print("[publish] Dry run complete - no changes made.")


if __name__ == "__main__":
    main()
