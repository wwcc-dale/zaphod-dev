# errors.py - NEW FILE
"""
Custom exception classes with improved error messages for Zaphod

All exceptions include:
- Clear error description
- Actionable suggestions
- Relevant context
"""
from pathlib import Path
from typing import Optional, Dict, Any


class ZaphodError(Exception):
    """Base exception for all Zaphod errors"""
    
    def __init__(
        self,
        message: str,
        suggestion: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.message = message
        self.suggestion = suggestion
        self.context = context or {}
        self.cause = cause
        super().__init__(self.format_message())
    
    def format_message(self) -> str:
        """Format error with all details"""
        lines = [
            "",
            "=" * 70,
            f"❌ {self.__class__.__name__}",
            "=" * 70,
            "",
            self.message,
        ]
        
        if self.context:
            lines.append("")
            lines.append("Context:")
            for key, value in self.context.items():
                lines.append(f"  {key}: {value}")
        
        if self.suggestion:
            lines.append("")
            lines.append("💡 Suggestion:")
            lines.append(f"  {self.suggestion}")
        
        if self.cause:
            lines.append("")
            lines.append(f"Caused by: {type(self.cause).__name__}: {self.cause}")
        
        lines.append("")
        lines.append("=" * 70)
        lines.append("")
        
        return "\n".join(lines)


class ConfigurationError(ZaphodError):
    """Configuration is missing or invalid"""
    pass


class ContentValidationError(ZaphodError):
    """Content failed validation"""
    pass


class FrontmatterError(ZaphodError):
    """Error parsing frontmatter"""
    pass


class CanvasAPIError(ZaphodError):
    """Error communicating with Canvas API"""
    pass


class FileNotFoundError(ZaphodError):
    """Required file not found"""
    pass


class SyncError(ZaphodError):
    """Error during sync operation"""
    pass


# Specific error factory functions

def missing_course_id_error() -> ConfigurationError:
    """Create error for missing course ID"""
    return ConfigurationError(
        message="Course ID not configured",
        suggestion=(
            "Set COURSE_ID environment variable:\n"
            "  export COURSE_ID=12345\n\n"
            "Or create _course_metadata/defaults.json:\n"
            '  {"course_id": "12345"}'
        ),
        context={
            "checked_locations": [
                "COURSE_ID environment variable",
                "_course_metadata/defaults.json"
            ]
        }
    )


def missing_credentials_error(expected_path: Path) -> ConfigurationError:
    """Create error for missing Canvas credentials"""
    return ConfigurationError(
        message="Canvas API credentials not found",
        suggestion=(
            f"Create credentials file at: {expected_path}\n\n"
            "Contents:\n"
            '  API_KEY = "your_token_here"\n'
            '  API_URL = "https://canvas.yourinstitution.edu"\n\n'
            "Get your API token from Canvas:\n"
            "  Account → Settings → New Access Token"
        ),
        context={
            "expected_path": str(expected_path),
            "env_var": "CANVAS_CREDENTIAL_FILE"
        }
    )


def invalid_frontmatter_error(
    file_path: Path,
    missing_fields: list[str],
    cause: Optional[Exception] = None
) -> FrontmatterError:
    """Create error for invalid frontmatter"""
    return FrontmatterError(
        message=f"Invalid frontmatter in {file_path.name}",
        suggestion=(
            f"Add required fields to frontmatter:\n"
            "  ---\n" +
            "\n".join(f'  {field}: "value"' for field in missing_fields) +
            "\n  ---"
        ),
        context={
            "file": str(file_path),
            "missing_fields": missing_fields,
            "required_fields": ["name", "type"]
        },
        cause=cause
    )


def canvas_not_found_error(
    resource_type: str,
    identifier: str,
    course_id: int
) -> CanvasAPIError:
    """Create error when Canvas resource not found"""
    return CanvasAPIError(
        message=f"{resource_type} not found in Canvas",
        suggestion=(
            f"Verify the {resource_type.lower()} exists in Canvas course {course_id}\n\n"
            "Possible causes:\n"
            "  - Name mismatch between local and Canvas\n"
            "  - Resource was deleted in Canvas\n"
            "  - Resource in different course\n\n"
            "Try running: zaphod sync --dry-run to see what would be created"),
        context={
            "resource_type": resource_type,
            "identifier": identifier,
            "course_id": course_id,
            "action": "Verify resource exists in Canvas or update local files"
        }
    )


def media_file_not_found_error(
    filename: str,
    source_file: Path,
    searched_paths: list[Path]
) -> FileNotFoundError:
    """Create error when media file cannot be found"""
    return FileNotFoundError(
        message=f"Media file not found: {filename}",
        suggestion=(
            f"Check that {filename} exists in one of these locations:\n" +
            "\n".join(f"  - {p}" for p in searched_paths) +
            "\n\nOr update the reference in the markdown file"
        ),
        context={
            "filename": filename,
            "referenced_in": str(source_file),
            "searched_locations": [str(p) for p in searched_paths]
        }
    )


def rubric_validation_error(
    rubric_file: Path,
    issues: list[str]
) -> ContentValidationError:
    """Create error for invalid rubric"""
    return ContentValidationError(
        message=f"Invalid rubric configuration in {rubric_file.name}",
        suggestion=(
            "Fix the following issues:\n" +
            "\n".join(f"  - {issue}" for issue in issues) +
            "\n\nSee docs/rubric-format.md for examples"
        ),
        context={
            "file": str(rubric_file),
            "issues": issues
        }
    )


def quiz_parsing_error(
    quiz_file: Path,
    line_number: int,
    line_content: str,
    cause: Optional[Exception] = None
) -> ContentValidationError:
    """Create error for quiz parsing failure"""
    return ContentValidationError(
        message=f"Failed to parse quiz question in {quiz_file.name}",
        suggestion=(
            f"Check line {line_number}:\n"
            f"  {line_content}\n\n"
            "Common issues:\n"
            "  - Missing question number (e.g., '1. ')\n"
            "  - No correct answer marked with *\n"
            "  - Invalid option format\n\n"
            "See docs/quiz-format.md for examples"
        ),
        context={
            "file": str(quiz_file),
            "line_number": line_number,
            "line_content": line_content
        },
        cause=cause
    )


def sync_conflict_error(
    local_file: Path,
    local_updated: str,
    canvas_updated: str
) -> SyncError:
    """Create error when Canvas version is newer"""
    return SyncError(
        message="Sync conflict: Canvas version is newer than local",
        suggestion=(
            "Choose one:\n"
            "  1. Keep local changes (overwrite Canvas):\n"
            "     zaphod sync --force\n\n"
            "  2. Pull Canvas changes (overwrite local):\n"
            "     zaphod pull\n\n"
            "  3. Manual merge:\n"
            "     - Review changes in Canvas\n"
            "     - Update local file\n"
            "     - Run sync again"
        ),
        context={
            "file": str(local_file),
            "local_updated": local_updated,
            "canvas_updated": canvas_updated
        }
    )


def api_rate_limit_error(
    endpoint: str,
    retry_after: Optional[int] = None
) -> CanvasAPIError:
    """Create error when hitting API rate limits"""
    suggestion = "Wait a moment and try again."
    if retry_after:
        suggestion = f"Wait {retry_after} seconds and try again."
    
    return CanvasAPIError(
        message="Canvas API rate limit exceeded",
        suggestion=(
            f"{suggestion}\n\n"
            "To avoid rate limits:\n"
            "  - Use incremental sync (--watch mode)\n"
            "  - Reduce parallel workers\n"
            "  - Sync during off-peak hours"
        ),
        context={
            "endpoint": endpoint,
            "retry_after_seconds": retry_after
        }
    )


def invalid_content_type_error(
    folder: Path,
    found_type: str,
    valid_types: list[str]
) -> ContentValidationError:
    """Create error for invalid content type"""
    return ContentValidationError(
        message=f"Invalid content type: {found_type}",
        suggestion=(
            f"Change 'type' in frontmatter to one of:\n" +
            "\n".join(f"  - {t}" for t in valid_types)
        ),
        context={
            "folder": str(folder),
            "found_type": found_type,
            "valid_types": valid_types
        }
    )