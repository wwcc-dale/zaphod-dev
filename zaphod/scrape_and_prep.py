#!/usr/bin/env python3
r"""
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

scrape_and_prep.py

Convert a course codebase into a Zaphod-compatible structure.

- Walk only course subdirectories matching: ^\d{2}-.+
- Inside each, look for templates/ and process .md files.
- Only process markdown filenames matching: ^(\d)-(\d{2})-(.+)\.md$
- For each file, create a .assignment folder with index.md, media handling,
  <video-card> → HTML5 <video> transform, slt-buttons → markdown button,
  and rubric-draft.yaml when a rubric block exists.
"""

import argparse
import logging
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Optional, Tuple, List
import urllib.parse  # URL decoding for %20 etc.
from datetime import datetime  # for fence timestamps

import frontmatter  # python-frontmatter must be installed [web:87]
import yaml         # PyYAML for rubric-draft.yaml and topics formatting [web:39]


# -----------------------------------------------------------------------------
# Logging setup with icons
# -----------------------------------------------------------------------------

# Message-only; no per-line timestamps
LOG_FORMAT = "%(message)s"

LEVEL_ICONS = {
    logging.DEBUG: "ðŸ”",
    logging.INFO: "âœ”ï¸",
    logging.WARNING: "âš ï¸",
    logging.ERROR: "âŒ",
    logging.CRITICAL: "ðŸ’¥",
}


class IconLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        icon = LEVEL_ICONS.get(record.levelno, "âœ”ï¸")
        base = super().format(record)
        return f"{icon} {base}"


def setup_logging(verbosity: int) -> None:
    level = logging.INFO
    if verbosity >= 2:
        level = logging.DEBUG

    handler = logging.StreamHandler()
    formatter = IconLogFormatter(LOG_FORMAT)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)


# -----------------------------------------------------------------------------
# Fence helper for visual phase markers
# -----------------------------------------------------------------------------

DOT_LINE = "." * 80


def fence(label: str) -> None:
    """
    Print a visual fence with a timestamped label.
    Used only at assignment start to bracket logs.
    """
    ts = datetime.now().strftime("%H:%M:%S")
    print(DOT_LINE)
    print(f"[{ts}] {label}")
    print("\n")  # extra blank line


# -----------------------------------------------------------------------------
# Patterns and constants
# -----------------------------------------------------------------------------

COURSE_DIR_PATTERN = re.compile(r"^\d{2}-.+")
ASSIGNMENT_FILE_PATTERN = re.compile(r"^(\d)-(\d{2})-(.+)\.md$", re.IGNORECASE)

# Matches:
#   ![alt](path)
#   [alt](path)
#   <img src="path">
#   <video src="path">
MARKDOWN_LINK_PATTERN = re.compile(
    r"""
    (?:!\[.*?\]\((?P<img_md>[^)]+)\))      # Markdown image ![alt](path)
    |(?:\[[^\]]*\]\((?P<link_md>[^)]+)\))  # Markdown link [text](path)
    |(?:<img[^>]+src=["'](?P<img_html>[^"']+)["'])      # <img src="path">
    |(?:<video[^>]+src=["'](?P<video_html>[^"']+)["'])  # <video src="path">
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Generic attribute capture: src="...", file="...", poster="..."
GENERIC_ATTR_PATTERN = re.compile(
    r"""\b(?P<attr>src|file|poster)\s*=\s*["'](?P<attr_value>[^"']+)["']""",
    re.IGNORECASE | re.DOTALL,
)

# For replacing <video-card> blocks
VIDEO_CARD_PATTERN = re.compile(
    r"""
    <video-card
    (?P<attrs>[^>]*)>
    \s*
    </video-card>
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

# For extracting rubric blocks
RUBRIC_BLOCK_PATTERN = re.compile(
    r"###\s+Rubric\s*?\n\s*?<accordion-list>(?P<body>.*?)</accordion-list>",
    re.IGNORECASE | re.DOTALL,
)

RUBRIC_LEVEL_PATTERN = re.compile(
    r"^######\s+(?P<label>.+?)\s*$\s*(?P<text>.*?)(?=^######\s+|\Z)",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)

# For replacing <slt-buttons> ... file-download</slt-buttons>
SLT_BUTTON_PATTERN = re.compile(
    r"""<slt-buttons>\s*
        \[Get Lesson Files\]\(      # fixed link text
        (?P<target><[^)]+>)         # capture the <...> href part (ignored for now)
        \s*"[^"]*"\)\s*\|\s*file-download
        \s*</slt-buttons>""",
    re.VERBOSE,
)

# Media mapping constants
LEGACY_VIDEO_PREFIX = "../../../VIDEOS/dd/"
NEW_VIDEO_PREFIX = "photoshop/Photoshop 30/"
TOPICS_PREFIX = "../topics/"
VIDEO_DIR_NAME = "videos"
ASSETS_PREFIX = "assets/"


# -----------------------------------------------------------------------------
# Small helpers
# -----------------------------------------------------------------------------

def is_course_dir(path: Path) -> bool:
    return COURSE_DIR_PATTERN.match(path.name) is not None


def parse_assignment_filename(filename: str) -> Optional[Tuple[str, str, str]]:
    """
    Parse filenames like: 1-11-filename.md

    Returns (module_num, order_num, base_name) or None if no match.
    """
    m = ASSIGNMENT_FILE_PATTERN.match(filename)
    if not m:
        return None
    module_num, order_num, base = m.group(1), m.group(2), m.group(3)
    return module_num, order_num, base


def build_assignment_folder_name(module_num: str, order_num: str, base: str) -> str:
    """
    Build folder name: 1-11-filename.assignment
    """
    return f"{module_num}-{order_num}-{base}.assignment"


def is_url(path_str: str) -> bool:
    lower = path_str.lower()
    return lower.startswith("http://") or lower.startswith("https://")


def clean_quotes(path_str: str) -> str:
    return path_str.strip().strip('"').strip("'")


def _safe_is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        logging.warning("Skipping non-regular path when checking media: %s", path)
        return False


# -----------------------------------------------------------------------------
# Markdown and content transformations (pure functions)
# -----------------------------------------------------------------------------

def _strip_markdown_title(reference: str) -> str:
    """
    Remove any markdown link title or trailing quoted text from a URL/path.

    Examples:
      'path/to/file.pdf "Some Title"' -> 'path/to/file.pdf'
      "path/to/file.pdf 'Some Title'" -> 'path/to/file.pdf'
    """
    # Normalize whitespace so titles that break lines don't confuse us
    ref = " ".join(reference.split())

    for quote in ('"', "'"):
        idx = ref.find(quote)
        if idx != -1:
            ref = ref[:idx].strip()
            break

    return ref


def _parse_video_card_attrs(attrs: str) -> dict:
    """
    Parse attributes from a <video-card ...> tag into a dict.
    """
    attr_pattern = re.compile(
        r"""\b(?P<key>\w+)\s*=\s*["'](?P<value>[^"']*)["']""",
        re.IGNORECASE | re.DOTALL,
    )
    out: dict[str, str] = {}
    for m in attr_pattern.finditer(attrs):
        key = m.group("key").lower()
        value = m.group("value")
        out[key] = value
    return out


def transform_video_cards(markdown_text: str) -> str:
    """
    Replace custom <video-card ...>...</video-card> blocks with standard HTML5 video markup.
    """

    def _repl(match: re.Match) -> str:
        attrs_str = match.group("attrs") or ""
        attrs = _parse_video_card_attrs(attrs_str)

        file_path = (attrs.get("file") or "").strip()
        topic = (attrs.get("topic") or "").strip()
        time_str = (attrs.get("time") or "").strip()
        poster = (attrs.get("poster") or "").strip()

        caption_parts = []
        if topic:
            caption_parts.append(topic)
        if time_str:
            caption_parts.append(f"({time_str})")
        caption = " ".join(caption_parts)

        video_html_lines = [
            '<figure class="video-card">',
            f'  <video controls{f" poster=\"{poster}\"" if poster else ""}>',
            f'    <source src="{file_path}" type="video/mp4">',
            "    Your browser does not support the video tag.",
            "  </video>",
        ]
        if caption:
            video_html_lines.append(f"  <figcaption>{caption}</figcaption>")
        video_html_lines.append("</figure>")

        return "\n".join(video_html_lines)

    return VIDEO_CARD_PATTERN.sub(_repl, markdown_text)


def transform_slt_buttons(markdown_text: str) -> str:
    """
    Replace <slt-buttons>[Get Lesson Files](...) | file-download</slt-buttons>
    with a standard markdown button-style link.
    """

    def _repl(_: re.Match) -> str:
        return '[Download PDF](/path/to/file.pdf){: .button .file-download}'

    return SLT_BUTTON_PATTERN.sub(_repl, markdown_text)


def extract_rubric(markdown_text: str) -> tuple[Optional[dict], str]:
    """
    Extract rubric definition from a markdown string and return:

      (rubric_dict_or_None, markdown_without_rubric_block)
    """
    m = RUBRIC_BLOCK_PATTERN.search(markdown_text)
    if not m:
        return None, markdown_text

    body = m.group("body")
    criteria: List[dict] = []

    for level_match in RUBRIC_LEVEL_PATTERN.finditer(body):
        label = level_match.group("label").strip()  # e.g. "8-9: Achieving"
        text = level_match.group("text").strip()
        description = " ".join(text.split())  # collapse whitespace

        if ":" in label:
            range_part, short_desc = [p.strip() for p in label.split(":", 1)]
        else:
            range_part, short_desc = "", label

        # Points mapping: use the upper end of the numeric range
        max_points = 0
        if "-" in range_part:
            try:
                max_points = int(range_part.split("-")[-1])
            except ValueError:
                max_points = 0
        else:
            try:
                max_points = int(range_part)
            except ValueError:
                max_points = 0

        criteria.append(
            {
                "description": short_desc,
                "long_description": description,
                "points": max_points,
                "ratings": [
                    {
                        "description": short_desc,
                        "long_description": description,
                        "points": max_points,
                    }
                ],
            }
        )

    rubric = {
        "title": "Assignment Rubric",
        "free_form_criterion_comments": False,
        "criteria": criteria,
    }

    new_markdown = (markdown_text[: m.start()] + markdown_text[m.end() :]).strip()

    return rubric, new_markdown


def find_media_paths(markdown_text: str) -> List[str]:
    """
    Extract potential local media paths from markdown or HTML/custom tags.
    """
    paths: List[str] = []

    # Normalize whitespace early to reduce odd captures
    text = markdown_text.replace("\r\n", "\n")

    for match in MARKDOWN_LINK_PATTERN.finditer(text):
        group_dict = match.groupdict()
        for key in ["img_md", "link_md", "img_html", "video_html"]:
            val = group_dict.get(key)
            if not val:
                continue
            val = clean_quotes(val)
            val = _strip_markdown_title(val)
            if not val or is_url(val) or val.startswith("#"):
                continue
            paths.append(val)

    for match in GENERIC_ATTR_PATTERN.finditer(text):
        val = match.group("attr_value")
        val = clean_quotes(val)
        val = _strip_markdown_title(val)
        if not val or is_url(val) or val.startswith("#"):
            continue
        paths.append(val)

    return paths


# -----------------------------------------------------------------------------
# Frontmatter and index.md creation (pure + small I/O)
# -----------------------------------------------------------------------------

def _format_topics_block(topics_value) -> List[str]:
    """
    Render topics as a block-style YAML list, returning lines like:

    topics:
      - Color
      - adjustment layers
    """
    dumped = yaml.safe_dump(
        {"topics": topics_value},
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
    return dumped.splitlines()


def build_zaphod_frontmatter(
    module_num: str,
    order_num: str,
    base_name: str,
    original_meta: Optional[dict] = None,
) -> str:
    """
    Build the Zaphod-compatible YAML frontmatter as a string.
    """
    display_name = base_name.replace("-", " ").title()
    module_label = f"Credit {module_num}"

    frontmatter_lines = [
        "---",
        f'name: "{display_name}"',
        'type: "Assignment"',
        "modules:",
        f'  - "{module_label}"',
        "published: true",
        "",
        "# assignment settings",
        "points_possible: 31",
        "submission_types:",
        '  - "online_upload"',
        "allowed_extensions:",
        '  - "pdf"',
        '  - "docx"',
        "",
        "# optional Canvas flags",
        "peer_reviews: false",
        "group_category: null",
    ]

    surfaced_keys = ("duration", "credit", "order")

    if original_meta:
        imported_lines: List[str] = []
        for key in surfaced_keys:
            if key in original_meta:
                imported_lines.append(f"{key}: {original_meta[key]}")
        if imported_lines:
            frontmatter_lines.append("")
            frontmatter_lines.append("# imported")
            frontmatter_lines.extend(imported_lines)

        # topics as an active, block-style YAML key if present
        if "topics" in original_meta:
            frontmatter_lines.append("")
            frontmatter_lines.extend(_format_topics_block(original_meta["topics"]))

    frontmatter_lines.append("---")
    frontmatter_lines.append("")

    fm_text = "\n".join(frontmatter_lines)

    # Comment out remaining original frontmatter, excluding imported keys and topics
    if original_meta:
        fm_text += "# Original frontmatter (commented out):\n"
        for key, value in original_meta.items():
            if key in surfaced_keys:
                continue
            if key == "topics":
                continue
            fm_text += f"# {key}: {value}\n"
        fm_text += "\n"

    return fm_text


def create_index_md(
    dest_assignment_dir: Path,
    module_num: str,
    order_num: str,
    base_name: str,
    original_metadata: Optional[dict],
    original_content: str,
) -> None:
    """
    Create the index.md file with Zaphod frontmatter, commented original frontmatter, and original content.
    """
    dest_assignment_dir.mkdir(parents=True, exist_ok=True)
    index_path = dest_assignment_dir / "index.md"

    fm_text = build_zaphod_frontmatter(
        module_num=module_num,
        order_num=order_num,
        base_name=base_name,
        original_meta=original_metadata,
    )

    to_write = fm_text + original_content

    with index_path.open("w", encoding="utf-8") as f:
        f.write(to_write)

    logging.info("  - Created index.md")


# -----------------------------------------------------------------------------
# MediaResolver class (encapsulates media resolution and de-duplication)
# -----------------------------------------------------------------------------

class MediaResolver:
    """
    Handle media resolution, copying and de-duplication for a single course.
    """

    def __init__(
        self,
        course_root: Path,
        topics_root: Optional[Path],
        course_id: str,
        dest_course_dir: Path,
    ) -> None:
        self.course_root = course_root
        self.topics_root = topics_root
        self.course_id = course_id
        self.dest_course_dir = dest_course_dir

        # basename -> first assignment dir that got it
        self._seen_once: dict[str, Path] = {}
        # basename -> path in course assets/
        self._in_assets: dict[str, Path] = {}
        # list of (source_file, last_candidate_path)
        self.missing_media: list[tuple[Path, Path]] = []

        self._assets_dir = self.dest_course_dir / "assets"
        self._assets_dir.mkdir(parents=True, exist_ok=True)

    def resolve_media_path(
        self,
        reference: str,
        source_file: Path,
    ) -> Optional[Path]:
        """
        Resolve a media reference to an actual file.

        Records the final resolved path attempted into missing_media when resolution fails.
        """
        # Normalize markdown-style title or trailing quoted text first
        reference = _strip_markdown_title(reference)

        # Decode %20 etc.
        reference = urllib.parse.unquote(reference)

        # Strip <...> wrapper if present, e.g. <../topics/...>
        if reference.startswith("<") and reference.endswith(">"):
            reference = reference[1:-1].strip()

        # Strip again defensively in case angle-brackets exposed a title
        reference = _strip_markdown_title(reference)

        last_candidate: Optional[Path] = None

        # Legacy video paths: ../../../VIDEOS/dd/...  -> topics_root/videos/...
        if self.topics_root is not None and reference.startswith(LEGACY_VIDEO_PREFIX):
            remainder = reference[len(LEGACY_VIDEO_PREFIX) :]
            candidate = (self.topics_root / VIDEO_DIR_NAME / remainder).resolve()
            last_candidate = candidate
            if _safe_is_file(candidate):
                logging.debug(
                    "Mapped legacy video reference '%s' → %s",
                    reference,
                    candidate,
                )
                return candidate
            reference = remainder

        # New video paths: photoshop/Photoshop 30/... -> topics_root/videos/photoshop/Photoshop 30/...
        if self.topics_root is not None and reference.startswith(NEW_VIDEO_PREFIX):
            candidate = (self.topics_root / VIDEO_DIR_NAME / reference).resolve()
            last_candidate = candidate
            if _safe_is_file(candidate):
                logging.debug(
                    "Mapped new video reference '%s' → %s",
                    reference,
                    candidate,
                )
                return candidate

        # Shared topics paths: ../topics/... → topics_root/...
        if self.topics_root is not None and reference.startswith(TOPICS_PREFIX):
            rel_under_topics = reference[len(TOPICS_PREFIX) :]
            candidate = (self.topics_root / rel_under_topics).resolve()
            last_candidate = candidate
            if _safe_is_file(candidate):
                logging.debug(
                    "Resolved topics media '%s' → %s",
                    reference,
                    candidate,
                )
                return candidate

        candidates: List[Path] = []

        try:
            course_dir = source_file.parents[1]
        except IndexError:
            course_dir = self.course_root

        # Strict: assets/ only inside the local course
        if reference.startswith(ASSETS_PREFIX):
            candidates.append((course_dir / reference).resolve())
        else:
            # Other relatives: source file dir, then overall course_root
            candidates.append((source_file.parent / reference).resolve())
            candidates.append((self.course_root / reference).resolve())

        for candidate in candidates:
            last_candidate = candidate
            if _safe_is_file(candidate):
                logging.debug("Resolved media '%s' → %s", reference, candidate)
                return candidate

        unresolved = last_candidate or (self.course_root / reference)
        self.missing_media.append((source_file, unresolved))
        return None

    def copy_media_to_assignment(
        self,
        media_paths: List[str],
        source_file: Path,
        dest_assignment_dir: Path,
    ) -> None:
        """
        Resolve media paths for a course and enforce de-duplication.

        Per-course de-dup (by basename):
          - First time: copy into that assignment folder only.
          - Second time: move first copy into assets/, remove from assignment,
            and leave symlinks in each assignment.
          - Third+: create only a symlink in the assignment to the assets/ copy.

        Per-assignment de-dup:
          - Copy/symlink at most once per basename into that assignment folder.
        """
        for ref in media_paths:
            src = self.resolve_media_path(ref, source_file)
            if not src:
                continue

            basename = src.name
            asset_target = self._assets_dir / basename

            # If it's already in assets, just ensure this assignment has a symlink.
            if basename in self._in_assets:
                logging.debug(
                    "Shared media '%s' already in assets at %s",
                    basename,
                    self._in_assets[basename],
                )
                link_path = dest_assignment_dir / basename
                if not link_path.exists():
                    try:
                        link_path.symlink_to(self._in_assets[basename])
                        logging.debug(
                            "Created symlink for '%s' in %s -> %s",
                            basename,
                            link_path,
                            self._in_assets[basename],
                        )
                    except OSError as e:
                        logging.error(
                            "Failed to create symlink '%s' -> '%s': %s",
                            link_path,
                            self._in_assets[basename],
                            e,
                        )
                continue

            # First time we see this basename in the course.
            if basename not in self._seen_once:
                dest_path = dest_assignment_dir / basename
                try:
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    if not dest_path.exists():
                        shutil.copy2(src, dest_path)
                        logging.debug(
                            "Copied unique media '%s' into assignment %s",
                            basename,
                            dest_assignment_dir,
                        )
                    self._seen_once[basename] = dest_assignment_dir
                except Exception as e:
                    logging.error(
                        "Failed to copy media '%s' to '%s': %s",
                        src,
                        dest_path,
                        e,
                    )
                continue

            # Second (or later) time we see this basename:
            #  - move/copy into assets/
            #  - replace first assignment copy with a symlink
            #  - create a symlink in the current assignment
            first_assignment_dir = self._seen_once[basename]
            first_assignment_file = first_assignment_dir / basename

            if first_assignment_file.exists():
                try:
                    shutil.move(str(first_assignment_file), str(asset_target))
                    logging.debug(
                        "Moved media '%s' from %s to course assets: %s",
                        basename,
                        first_assignment_file,
                        asset_target,
                    )
                except Exception as e:
                    logging.error(
                        "Failed to move '%s' to assets '%s': %s",
                        first_assignment_file,
                        asset_target,
                        e,
                    )
            else:
                try:
                    shutil.copy2(src, asset_target)
                    logging.debug(
                        "Copied media '%s' directly to course assets: %s",
                        basename,
                        asset_target,
                    )
                except Exception as e:
                    logging.error(
                        "Failed to copy media '%s' to '%s': %s",
                        src,
                        asset_target,
                        e,
                    )

            # Symlink back into the first assignment folder
            first_link = first_assignment_dir / basename
            if not first_link.exists():
                try:
                    first_link.symlink_to(asset_target)
                    logging.debug(
                        "Created symlink for '%s' in %s -> %s",
                        basename,
                        first_link,
                        asset_target,
                    )
                except OSError as e:
                    logging.error(
                        "Failed to create symlink '%s' -> '%s': %s",
                        first_link,
                        asset_target,
                        e,
                    )

            # Symlink into the current assignment folder
            current_link = dest_assignment_dir / basename
            if not current_link.exists():
                try:
                    current_link.symlink_to(asset_target)
                    logging.debug(
                        "Created symlink for '%s' in %s -> %s",
                        basename,
                        current_link,
                        asset_target,
                    )
                except OSError as e:
                    logging.error(
                        "Failed to create symlink '%s' -> '%s': %s",
                        current_link,
                        asset_target,
                        e,
                    )

            self._in_assets[basename] = asset_target
            del self._seen_once[basename]


# -----------------------------------------------------------------------------
# High-level processing
# -----------------------------------------------------------------------------

def load_markdown_with_frontmatter(md_path: Path) -> tuple[Optional[dict], str]:
    """
    Load a markdown file, returning (frontmatter_dict_or_None, content).
    """
    try:
        post = frontmatter.load(md_path)
        original_metadata = dict(post.metadata) if post.metadata else None
        content = post.content
        logging.info("  - Parsed frontmatter and content")
        return original_metadata, content
    except Exception as e:
        logging.error("Failed to parse frontmatter for %s: %s", md_path, e)
        try:
            content = md_path.read_text(encoding="utf-8")
            logging.info("  - Loaded content without frontmatter")
            return None, content
        except Exception as e2:
            logging.error("Failed to read markdown file %s: %s", md_path, e2)
            return None, ""


def transform_assignment_content(content: str) -> tuple[Optional[dict], str]:
    """
    Apply rubric extraction and content transforms to assignment body.
    Returns (rubric_dict_or_None, transformed_content).
    """
    rubric, body = extract_rubric(content)
    if rubric:
        logging.info("  - Extracted rubric")

    body = transform_video_cards(body)
    logging.info("  - Transformed video cards")

    body = transform_slt_buttons(body)
    logging.info("  - Transformed lesson file button")

    return rubric, body


def process_assignment_file(
    md_path: Path,
    course_root: Path,
    dest_root: Path,
    topics_root: Optional[Path],
    course_id: str,
    resolver: MediaResolver,
) -> None:
    """
    Process a single assignment markdown file.
    """
    start_label = f"START: {course_id}/{md_path.name}"
    fence(start_label)

    logging.debug("Processing assignment: %s/%s", course_id, md_path.name)

    parsed = parse_assignment_filename(md_path.name)
    if not parsed:
        logging.debug("Skipping file (does not match pattern): %s", md_path)
        return

    module_num, order_num, base_name = parsed
    assignment_folder_name = build_assignment_folder_name(
        module_num, order_num, base_name
    )

    dest_course_dir = dest_root / course_id
    dest_pages_dir = dest_course_dir / "pages"
    dest_pages_dir.mkdir(parents=True, exist_ok=True)
    dest_course_dir.mkdir(parents=True, exist_ok=True)

    dest_assignment_dir = dest_pages_dir / assignment_folder_name

    original_metadata, content = load_markdown_with_frontmatter(md_path)
    if not content:
        logging.error("No content loaded for %s; skipping", md_path)
        return

    rubric, content = transform_assignment_content(content)

    # Create index.md (ensures dest_assignment_dir exists)
    create_index_md(
        dest_assignment_dir=dest_assignment_dir,
        module_num=module_num,
        order_num=order_num,
        base_name=base_name,
        original_metadata=original_metadata,
        original_content=content,
    )

    # If a rubric was found, write rubric-draft.yaml in this assignment folder
    if rubric:
        rubric_path = dest_assignment_dir / "rubric-draft.yaml"
        rubric_path.parent.mkdir(parents=True, exist_ok=True)
        with rubric_path.open("w", encoding="utf-8") as rf:
            yaml.safe_dump(rubric, rf, sort_keys=False, allow_unicode=True)
        logging.info("  - Wrote rubric-draft.yaml")

    media_paths = find_media_paths(content)
    if media_paths:
        logging.debug(
            "Found %d potential media references in %s", len(media_paths), md_path
        )
    resolver.copy_media_to_assignment(
        media_paths=media_paths,
        source_file=md_path,
        dest_assignment_dir=dest_assignment_dir,
    )
    logging.info("  - Copied and deduplicated media")

    logging.info(" Assignment complete\n")


def process_templates_dir(
    templates_dir: Path,
    course_root: Path,
    dest_root: Path,
    topics_root: Optional[Path],
    course_id: str,
) -> list[tuple[Path, Path]]:
    """
    Process all matching .md files in a templates/ directory.
    Returns the list of missing media pairs (source_file, unresolved_path) for this course.
    """
    logging.info("Processing course: %s", course_id)

    dest_course_dir = dest_root / course_id
    resolver = MediaResolver(
        course_root=course_root,
        topics_root=topics_root,
        course_id=course_id,
        dest_course_dir=dest_course_dir,
    )

    for entry in sorted(templates_dir.iterdir()):
        if not entry.is_file():
            continue
        if entry.suffix.lower() != ".md":
            logging.debug("Skipping non-markdown file: %s", entry)
            continue

        if not ASSIGNMENT_FILE_PATTERN.match(entry.name):
            logging.debug("Skipping markdown (pattern mismatch): %s", entry)
            continue

        process_assignment_file(
            md_path=entry,
            course_root=course_root,
            dest_root=dest_root,
            topics_root=topics_root,
            course_id=course_id,
            resolver=resolver,
        )

    logging.info(" Course complete: %s", course_id)
    return resolver.missing_media


def walk_course_root(
    course_root: Path, dest_root: Path, topics_root: Optional[Path]
) -> dict[str, list[tuple[Path, Path]]]:
    r"""
    Walk the course root directory, but only enter course directories that match
    the pattern ^\d{2}-.+ and process their templates/ subdirectory if present.

    Returns a mapping: course_id -> list of (source_file, unresolved_path).
    """
    logging.info("Scanning course root: %s", course_root)

    if not course_root.is_dir():
        logging.error("Source path is not a directory: %s", course_root)
        return {}

    missing_media_by_course: dict[str, list[tuple[Path, Path]]] = defaultdict(list)

    for entry in sorted(course_root.iterdir()):
        if not entry.is_dir():
            continue

        if not is_course_dir(entry):
            logging.debug(" Skipping non-course directory: %s", entry)
            continue

        logging.debug(" Found course directory: %s", entry)

        templates_dir = entry / "templates"
        if not templates_dir.is_dir():
            logging.warning(" No templates/ directory in %s; skipping", entry)
            continue

        course_id = entry.name
        course_missing = process_templates_dir(
            templates_dir=templates_dir,
            course_root=course_root,
            dest_root=dest_root,
            topics_root=topics_root,
            course_id=course_id,
        )
        if course_missing:
            missing_media_by_course[course_id].extend(course_missing)

    return missing_media_by_course


# -----------------------------------------------------------------------------
# CLI and entrypoint
# -----------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a course codebase into Zaphod-compatible assignments."
    )
    parser.add_argument(
        "--source",
        "-s",
        required=True,
        help="Path to the course root directory",
    )
    parser.add_argument(
        "--dest",
        "-d",
        required=True,
        help="Path to the Zaphod output directory",
    )
    parser.add_argument(
        "--topics",
        "-t",
        required=False,
        help="Optional path to shared topics/media directory",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v for more info, -vv for debug logging)",
    )
    return parser.parse_args()


def _quote_path_for_shell(p: Path) -> str:
    """
    Return a shell-friendly, single-argument representation of a path.
    Uses simple double-quoting; good enough for typical POSIX shells.
    """
    s = str(p)
    s = s.replace('"', r'\"')
    return f'"{s}"'


def run(course_root: Path, dest_root: Path, topics_root: Optional[Path]) -> None:
    dest_root.mkdir(parents=True, exist_ok=True)

    missing_media_by_course = walk_course_root(
        course_root=course_root,
        dest_root=dest_root,
        topics_root=topics_root,
    )

    # After all processing, write a missing-media report if needed
    if missing_media_by_course:
        report_path = dest_root / "missing-media.txt"
        with report_path.open("w", encoding="utf-8") as f:
            for course_id, items in sorted(missing_media_by_course.items()):
                f.write(f"# Course: {course_id}\n")
                for source_file, resolved_path in items:
                    missing = _quote_path_for_shell(resolved_path)
                    src = _quote_path_for_shell(source_file)
                    f.write(f"{missing}  # from {src}\n")
                f.write("\n")
        logging.info("Wrote missing media report to %s", report_path)
    else:
        logging.info(" No missing media references detected.")

    logging.info(" Processing complete.")


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)

    course_root = Path(args.source).resolve()
    dest_root = Path(args.dest).resolve()
    topics_root = Path(args.topics).resolve() if args.topics else None

    logging.info("Source (course root): %s", course_root)
    logging.info("Destination (Zaphod root): %s", dest_root)
    if topics_root:
        logging.info("Topics/media directory: %s", topics_root)

    run(course_root=course_root, dest_root=dest_root, topics_root=topics_root)


if __name__ == "__main__":
    main()
