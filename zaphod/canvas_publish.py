#!/usr/bin/env python3
"""
canvas_publish.py - Zaphod content classes for Canvas publishing

Replaces markdown2canvas's Page/Assignment/Link/File classes with native
Zaphod implementations that:
- Read meta.json and source.md from content folders
- Convert markdown to HTML
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
        """Convert markdown source to HTML."""
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
        """Convert markdown source to HTML."""
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
