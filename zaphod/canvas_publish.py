#!/usr/bin/env python3
"""
canvas_publish.py - Zaphod content classes for Canvas publishing

Replaces markdown2canvas's Page/Assignment/Link/File classes with native
Zaphod implementations that:
- Read meta.json and source.md from content folders
- Convert markdown to HTML
- Apply template wrappers (header/footer)
- Create/update Canvas objects via canvasapi
- Handle local asset uploads

These classes do NOT handle:
- Module membership (handled by sync_modules.py)
- Rubrics (handled by sync_rubrics.py)
- Video placeholder replacement (handled by publish_all.py before calling these)
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod

import markdown
from canvasapi.course import Course

from zaphod.security_utils import is_safe_path


# ============================================================================
# Template System
# ============================================================================

def get_course_root(content_folder: Path) -> Path:
    """
    Find course root by walking up from content folder.

    Course root contains zaphod.yaml or pages/ or content/ directory.
    """
    current = content_folder
    for _ in range(10):  # Prevent infinite loop
        if (current / "zaphod.yaml").exists():
            return current
        if (current / "pages").exists() or (current / "content").exists():
            return current
        current = current.parent

    # Fallback: assume cwd is course root
    return Path.cwd()


def load_template_files(course_root: Path, template_name: str = "default") -> Dict[str, str]:
    """
    Load template files for a given template set.

    Args:
        course_root: Course root directory
        template_name: Name of template set (e.g., "default", "fancy")

    Returns:
        Dict with keys: header_html, header_md, footer_md, footer_html
        Values are file contents or empty string if file doesn't exist

    Security:
        Validates template_name to prevent path traversal attacks.
        Only reads files within course_root/templates/ directory.
    """
    # SECURITY: Validate template name to prevent path traversal
    # Reject names with path separators or parent directory references
    if not template_name or not isinstance(template_name, str):
        template_name = "default"

    # Sanitize: only allow alphanumeric, hyphens, underscores
    if not all(c.isalnum() or c in ('-', '_') for c in template_name):
        # Invalid characters - fall back to default
        template_name = "default"

    templates_base = course_root / "templates"
    templates_dir = templates_base / template_name

    # SECURITY: Verify resolved path is within templates directory
    if not is_safe_path(templates_base, templates_dir):
        # Path traversal attempt detected - use default
        templates_dir = templates_base / "default"

    template_files = {
        "header_html": templates_dir / "header.html",
        "header_md": templates_dir / "header.md",
        "footer_md": templates_dir / "footer.md",
        "footer_html": templates_dir / "footer.html",
    }

    loaded = {}
    for key, path in template_files.items():
        # SECURITY: Double-check each file is within templates directory
        if not is_safe_path(templates_base, path):
            loaded[key] = ""
            continue

        if path.exists():
            try:
                loaded[key] = path.read_text(encoding="utf-8")
            except Exception:
                loaded[key] = ""
        else:
            loaded[key] = ""

    return loaded


def apply_templates(content_html: str, course_root: Path, meta: Dict[str, Any]) -> str:
    """
    Apply template wrappers to content HTML.

    Application order:
    1. header.html
    2. header.md (converted to HTML)
    3. [content]
    4. footer.md (converted to HTML)
    5. footer.html

    Args:
        content_html: Rendered HTML content
        course_root: Course root directory
        meta: Content metadata (frontmatter)

    Returns:
        Wrapped HTML with templates applied
    """
    # Check if templates should be skipped
    template_name = meta.get("template")

    # Explicit null/false means skip templates
    if template_name is False or template_name is None and "template" in meta:
        return content_html

    # Default to "default" template set
    if template_name is None:
        template_name = "default"

    # Load template files
    templates = load_template_files(course_root, template_name)

    # If no template files exist, return content as-is
    if not any(templates.values()):
        return content_html

    # Build wrapped content
    parts = []

    # 1. header.html
    if templates["header_html"]:
        parts.append(templates["header_html"])

    # 2. header.md (convert to HTML)
    if templates["header_md"]:
        header_html = markdown.markdown(
            templates["header_md"],
            extensions=['tables', 'fenced_code', 'codehilite', 'toc', 'nl2br']
        )
        parts.append(header_html)

    # 3. Content
    parts.append(content_html)

    # 4. footer.md (convert to HTML)
    if templates["footer_md"]:
        footer_html = markdown.markdown(
            templates["footer_md"],
            extensions=['tables', 'fenced_code', 'codehilite', 'toc', 'nl2br']
        )
        parts.append(footer_html)

    # 5. footer.html
    if templates["footer_html"]:
        parts.append(templates["footer_html"])

    return "\n".join(parts)


class ZaphodContentBase(ABC):
    """Base class for all Zaphod content types."""
    
    def __init__(self, folder: Path):
        """
        Initialize from a content folder.
        
        Args:
            folder: Path to content folder (e.g., pages/welcome.page/)
        """
        if isinstance(folder, str):
            folder = Path(folder)
        
        self.folder = folder
        self.meta_path = folder / "meta.json"
        self.source_path = folder / "source.md"
        
        # Load metadata
        if not self.meta_path.exists():
            raise FileNotFoundError(f"No meta.json in {folder}")
        
        with open(self.meta_path, encoding="utf-8") as f:
            self.meta: Dict[str, Any] = json.load(f)
        
        # Validate required fields
        if "name" not in self.meta:
            raise ValueError(f"meta.json missing 'name' in {folder}")
        if "type" not in self.meta:
            raise ValueError(f"meta.json missing 'type' in {folder}")
        
        self.name = self.meta["name"]
        self.content_type = self.meta["type"].lower()
    
    @abstractmethod
    def publish(self, course: Course, overwrite: bool = True) -> Any:
        """
        Publish this content to Canvas.
        
        Args:
            course: canvasapi Course object
            overwrite: If True, update existing content; if False, skip if exists
            
        Returns:
            The created/updated Canvas object
        """
        pass
    
    def _find_existing(self, course: Course) -> Optional[Any]:
        """Find existing Canvas object by name. Override in subclasses."""
        return None


class ZaphodPage(ZaphodContentBase):
    """Canvas Page content type."""
    
    def __init__(self, folder: Path):
        super().__init__(folder)
        
        # Load source content
        if not self.source_path.exists():
            raise FileNotFoundError(f"No source.md in {folder}")
        
        self.source_md = self.source_path.read_text(encoding="utf-8")
    
    def _render_html(self) -> str:
        """Convert markdown source to HTML and apply templates."""
        # Use Python-Markdown with common extensions
        html = markdown.markdown(
            self.source_md,
            extensions=[
                'tables',
                'fenced_code',
                'codehilite',
                'toc',
                'nl2br',  # Newlines to <br>
            ]
        )

        # Apply template wrappers
        course_root = get_course_root(self.folder)
        html = apply_templates(html, course_root, self.meta)

        return html
    
    def _find_existing(self, course: Course) -> Optional[Any]:
        """Find existing page by title."""
        for page in course.get_pages():
            if page.title == self.name:
                return page
        return None
    
    def publish(self, course: Course, overwrite: bool = True) -> Any:
        """
        Publish page to Canvas.
        
        Creates a new page or updates existing one.
        """
        html_body = self._render_html()
        published = self.meta.get("published", False)
        
        existing = self._find_existing(course)
        
        if existing:
            if not overwrite:
                print(f"[publish] Page '{self.name}' exists, skipping (overwrite=False)")
                return existing
            
            # Update existing page
            existing.edit(
                wiki_page={
                    "title": self.name,
                    "body": html_body,
                    "published": published,
                }
            )
            print(f"[publish] Updated page: {self.name}")
            return existing
        else:
            # Create new page
            page = course.create_page(
                wiki_page={
                    "title": self.name,
                    "body": html_body,
                    "published": published,
                }
            )
            print(f"[publish] Created page: {self.name}")
            return page


class ZaphodAssignment(ZaphodContentBase):
    """Canvas Assignment content type."""

    def __init__(self, folder: Path):
        super().__init__(folder)

        # Load source content (description)
        if not self.source_path.exists():
            raise FileNotFoundError(f"No source.md in {folder}")

        self.source_md = self.source_path.read_text(encoding="utf-8")

    def _render_html(self) -> str:
        """Convert markdown source to HTML and apply templates."""
        html = markdown.markdown(
            self.source_md,
            extensions=[
                'tables',
                'fenced_code',
                'codehilite',
                'toc',
                'nl2br',
            ]
        )

        # Apply template wrappers
        course_root = get_course_root(self.folder)
        html = apply_templates(html, course_root, self.meta)

        return html
    
    def _find_existing(self, course: Course) -> Optional[Any]:
        """Find existing assignment by name."""
        for assignment in course.get_assignments():
            if assignment.name == self.name:
                return assignment
        return None
    
    def publish(self, course: Course, overwrite: bool = True) -> Any:
        """
        Publish assignment to Canvas.
        
        Creates a new assignment or updates existing one.
        """
        html_body = self._render_html()
        published = self.meta.get("published", False)
        
        # Build assignment parameters from meta
        assignment_params = {
            "name": self.name,
            "description": html_body,
            "published": published,
        }
        
        # Optional fields from meta
        if "points_possible" in self.meta:
            assignment_params["points_possible"] = self.meta["points_possible"]
        
        if "submission_types" in self.meta:
            # Canvas expects submission_types as a list
            sub_types = self.meta["submission_types"]
            if isinstance(sub_types, str):
                sub_types = [sub_types]
            assignment_params["submission_types"] = sub_types
        
        if "allowed_extensions" in self.meta:
            assignment_params["allowed_extensions"] = self.meta["allowed_extensions"]
        
        if "due_at" in self.meta:
            assignment_params["due_at"] = self.meta["due_at"]
        
        if "unlock_at" in self.meta:
            assignment_params["unlock_at"] = self.meta["unlock_at"]
        
        if "lock_at" in self.meta:
            assignment_params["lock_at"] = self.meta["lock_at"]
        
        if "peer_reviews" in self.meta:
            assignment_params["peer_reviews"] = self.meta["peer_reviews"]
        
        if "group_category_id" in self.meta:
            assignment_params["group_category_id"] = self.meta["group_category_id"]
        
        existing = self._find_existing(course)
        
        if existing:
            if not overwrite:
                print(f"[publish] Assignment '{self.name}' exists, skipping (overwrite=False)")
                return existing
            
            # Update existing assignment
            existing.edit(assignment=assignment_params)
            print(f"[publish] Updated assignment: {self.name}")
            return existing
        else:
            # Create new assignment
            assignment = course.create_assignment(assignment=assignment_params)
            print(f"[publish] Created assignment: {self.name}")
            return assignment


class ZaphodLink(ZaphodContentBase):
    """Canvas External URL (Link) content type."""
    
    def __init__(self, folder: Path):
        super().__init__(folder)
        
        # Links require external_url in meta
        if "external_url" not in self.meta:
            raise ValueError(f"meta.json missing 'external_url' for link in {folder}")
        
        self.external_url = self.meta["external_url"]
        self.new_tab = self.meta.get("new_tab", True)
    
    def publish(self, course: Course, overwrite: bool = True) -> Any:
        """
        Publish link as an external tool/URL.
        
        Note: Canvas doesn't have standalone "links" - they exist as module items.
        This creates/updates the link as a module item in sync_modules.py.
        Here we just validate and return the meta for module sync to use.
        """
        # Links are handled primarily by sync_modules.py as ExternalUrl module items
        # We don't create a separate Canvas object for them
        print(f"[publish] Link '{self.name}' -> {self.external_url} (handled by module sync)")
        return {
            "type": "ExternalUrl",
            "external_url": self.external_url,
            "title": self.name,
            "new_tab": self.new_tab,
        }


class ZaphodFile(ZaphodContentBase):
    """Canvas File content type."""
    
    def __init__(self, folder: Path):
        super().__init__(folder)
        
        # Files require a filename in meta
        if "filename" not in self.meta:
            raise ValueError(f"meta.json missing 'filename' for file in {folder}")
        
        self.filename = self.meta["filename"]
        self.file_path = folder / self.filename
        
        if not self.file_path.exists():
            # Also check assets folder
            assets_path = folder.parent.parent / "assets" / self.filename
            if assets_path.exists():
                self.file_path = assets_path
            else:
                raise FileNotFoundError(
                    f"File not found: {self.filename} "
                    f"(checked {folder} and assets/)"
                )
    
    def _find_existing(self, course: Course) -> Optional[Any]:
        """Find existing file by filename."""
        for f in course.get_files(search_term=self.filename):
            if f.filename == self.filename or f.display_name == self.filename:
                return f
        return None
    
    def publish(self, course: Course, overwrite: bool = True) -> Any:
        """
        Upload file to Canvas.
        
        Creates a new file or updates existing one.
        """
        existing = self._find_existing(course)
        
        if existing and not overwrite:
            print(f"[publish] File '{self.filename}' exists, skipping (overwrite=False)")
            return existing
        
        # Upload file
        # Note: Canvas doesn't have a simple "update" for files - we upload again
        success, result = course.upload(str(self.file_path))
        
        if not success:
            raise RuntimeError(f"Failed to upload {self.filename}: {result}")
        
        file_id = result.get("id")
        if not file_id:
            raise RuntimeError(f"No file ID returned for {self.filename}")
        
        canvas_file = course.get_file(file_id)
        print(f"[publish] Uploaded file: {self.filename} (id={file_id})")
        return canvas_file


def make_zaphod_obj(folder: Path) -> ZaphodContentBase:
    """
    Create the appropriate Zaphod content object based on folder suffix.
    
    Drop-in replacement for the old make_mc_obj() function.
    
    Args:
        folder: Path to content folder
        
    Returns:
        ZaphodPage, ZaphodAssignment, ZaphodLink, or ZaphodFile instance
    """
    if isinstance(folder, str):
        folder = Path(folder)
    
    suffix = folder.suffix.lower()
    
    if suffix == ".page":
        return ZaphodPage(folder)
    elif suffix == ".assignment":
        return ZaphodAssignment(folder)
    elif suffix == ".link":
        return ZaphodLink(folder)
    elif suffix == ".file":
        return ZaphodFile(folder)
    else:
        raise ValueError(f"Unknown content type for folder: {folder}")
