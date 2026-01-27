#!/usr/bin/env python3
"""
icons.py - Centralized icon/emoji definitions for Zaphod CLI output

Usage:
    from icons import icons
    print(f"{icons.SUCCESS} Task completed!")
    print(f"{icons.ERROR} Something went wrong")

Or import individual icons:
    from icons import SUCCESS, WARNING, ERROR
    print(f"{SUCCESS} Done!")

All unicode characters are defined here once. Never edit unicode
characters in other files - import from this module instead.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Icons:
    """
    Centralized icon definitions.
    
    Categories:
    - Status: SUCCESS, ERROR, WARNING, INFO, SKIP
    - Actions: SYNC, UPLOAD, DOWNLOAD, DELETE, CREATE, EDIT
    - Content: PAGE, ASSIGNMENT, QUIZ, MODULE, BANK, RUBRIC, OUTCOME
    - Progress: WORKING, WAITING, DONE
    - Misc: FOLDER, FILE, LINK, CLOCK, TARGET, LIST
    """
    
    # =========================================================================
    # Status Icons
    # =========================================================================
    SUCCESS: str = "✅"      # Green checkmark - operation succeeded
    ERROR: str = "❌"        # Red X - operation failed  
    WARNING: str = "⚠️"      # Warning triangle
    INFO: str = "ℹ️"         # Information
    SKIP: str = "⏭️"         # Skip forward - skipped
    
    # =========================================================================
    # Action Icons
    # =========================================================================
    SYNC: str = "🔄"        # Sync/refresh arrows
    UPLOAD: str = "⬆️"       # Upload arrow
    DOWNLOAD: str = "⬇️"     # Download arrow
    DELETE: str = "🗑️"       # Trash can
    CREATE: str = "➕"       # Plus sign
    EDIT: str = "✏️"         # Pencil
    
    # =========================================================================
    # Content Type Icons
    # =========================================================================
    PAGE: str = "📄"        # Document/page
    ASSIGNMENT: str = "📝"  # Assignment/task
    QUIZ: str = "❓"        # Quiz/question
    MODULE: str = "📚"      # Module/books
    BANK: str = "🏦"        # Question bank
    RUBRIC: str = "📊"      # Rubric/chart
    OUTCOME: str = "🎯"     # Learning outcome/target
    ASSET: str = "🖼"       # Media asset/image
    
    # =========================================================================
    # Progress Icons
    # =========================================================================
    WORKING: str = "⏳"      # Hourglass - working/in progress
    WAITING: str = "🕐"      # Clock - waiting
    DONE: str = "✅"         # Checkmark - complete
    
    # =========================================================================
    # Misc Icons
    # =========================================================================
    FOLDER: str = "📁"      # Folder
    FILE: str = "📄"        # File
    LINK: str = "🔗"        # External link
    CLOCK: str = "🕐"       # Time/clock
    TARGET: str = "🎯"      # Target/goal
    LIST: str = "📋"        # List/clipboard
    SWEEP: str = "🧹"       # Cleanup/sweep
    PACKAGE: str = "📦"     # Package/export
    WAVE: str = "👋"        # Wave/goodbye
    BOOK: str = "📖"        # Single book
    BOOKS: str = "📚"       # Multiple books
    
    # =========================================================================
    # Compound/Semantic Aliases
    # =========================================================================
    @property
    def PUBLISHED(self) -> str:
        return self.SUCCESS
    
    @property
    def UNPUBLISHED(self) -> str:
        return self.SKIP
    
    @property
    def CHANGED(self) -> str:
        return self.EDIT
    
    @property
    def UNCHANGED(self) -> str:
        return self.SKIP
    
    @property
    def DRY_RUN(self) -> str:
        return self.INFO


# Global singleton instance
icons = Icons()

# Also export individual icons for convenience
SUCCESS = icons.SUCCESS
ERROR = icons.ERROR
WARNING = icons.WARNING
INFO = icons.INFO
SKIP = icons.SKIP
SYNC = icons.SYNC
UPLOAD = icons.UPLOAD
DOWNLOAD = icons.DOWNLOAD
DELETE = icons.DELETE
CREATE = icons.CREATE
EDIT = icons.EDIT
PAGE = icons.PAGE
ASSIGNMENT = icons.ASSIGNMENT
QUIZ = icons.QUIZ
MODULE = icons.MODULE
BANK = icons.BANK
RUBRIC = icons.RUBRIC
OUTCOME = icons.OUTCOME
ASSET = icons.ASSET
WORKING = icons.WORKING
WAITING = icons.WAITING
DONE = icons.DONE
FOLDER = icons.FOLDER
FILE = icons.FILE
LINK = icons.LINK
CLOCK = icons.CLOCK
TARGET = icons.TARGET
LIST = icons.LIST
SWEEP = icons.SWEEP
PACKAGE = icons.PACKAGE
WAVE = icons.WAVE
BOOK = icons.BOOK
BOOKS = icons.BOOKS


# =========================================================================
# Helper Functions
# =========================================================================

def status_icon(success: bool) -> str:
    """Return SUCCESS or ERROR icon based on boolean."""
    return SUCCESS if success else ERROR


def published_icon(published: bool) -> str:
    """Return icon for published status."""
    return SUCCESS if published else SKIP


def content_type_icon(content_type: str) -> str:
    """Return icon for a content type string."""
    type_map = {
        "page": PAGE,
        "assignment": ASSIGNMENT,
        "quiz": QUIZ,
        "module": MODULE,
        "bank": BANK,
        "rubric": RUBRIC,
        "outcome": OUTCOME,
        "link": LINK,
        "file": FILE,
        "asset": ASSET,
    }
    return type_map.get(content_type.lower(), FILE)


# =========================================================================
# Fallback Mode (for terminals that don't support unicode)
# =========================================================================

class AsciiIcons:
    """ASCII-only fallback icons for limited terminals."""
    
    SUCCESS = "[OK]"
    ERROR = "[X]"
    WARNING = "[!]"
    INFO = "[i]"
    SKIP = "[ ]"
    SYNC = "[~]"
    UPLOAD = "[^]"
    DOWNLOAD = "[v]"
    DELETE = "[-]"
    CREATE = "[+]"
    EDIT = "[*]"
    PAGE = "[P]"
    ASSIGNMENT = "[A]"
    QUIZ = "[Q]"
    MODULE = "[M]"
    BANK = "[B]"
    RUBRIC = "[R]"
    OUTCOME = "[O]"
    ASSET = "[I]"
    WORKING = "[.]"
    WAITING = "[:]"
    DONE = "[#]"
    FOLDER = "[D]"
    FILE = "[F]"
    LINK = "[L]"
    CLOCK = "[T]"
    TARGET = "[>]"
    LIST = "[=]"
    SWEEP = "[-]"
    PACKAGE = "[Z]"
    WAVE = "[~]"
    BOOK = "[B]"
    BOOKS = "[B]"


def use_ascii_icons():
    """
    Switch to ASCII-only icons globally.
    
    Call this if unicode icons cause problems:
        from icons import use_ascii_icons
        use_ascii_icons()
    """
    global icons, SUCCESS, ERROR, WARNING, INFO, SKIP
    global SYNC, UPLOAD, DOWNLOAD, DELETE, CREATE, EDIT
    global PAGE, ASSIGNMENT, QUIZ, MODULE, BANK, RUBRIC, OUTCOME, ASSET
    global WORKING, WAITING, DONE
    global FOLDER, FILE, LINK, CLOCK, TARGET, LIST, SWEEP, PACKAGE, WAVE, BOOK, BOOKS
    
    ascii_icons = AsciiIcons()
    icons = ascii_icons
    
    SUCCESS = ascii_icons.SUCCESS
    ERROR = ascii_icons.ERROR
    WARNING = ascii_icons.WARNING
    INFO = ascii_icons.INFO
    SKIP = ascii_icons.SKIP
    SYNC = ascii_icons.SYNC
    UPLOAD = ascii_icons.UPLOAD
    DOWNLOAD = ascii_icons.DOWNLOAD
    DELETE = ascii_icons.DELETE
    CREATE = ascii_icons.CREATE
    EDIT = ascii_icons.EDIT
    PAGE = ascii_icons.PAGE
    ASSIGNMENT = ascii_icons.ASSIGNMENT
    QUIZ = ascii_icons.QUIZ
    MODULE = ascii_icons.MODULE
    BANK = ascii_icons.BANK
    RUBRIC = ascii_icons.RUBRIC
    OUTCOME = ascii_icons.OUTCOME
    ASSET = ascii_icons.ASSET
    WORKING = ascii_icons.WORKING
    WAITING = ascii_icons.WAITING
    DONE = ascii_icons.DONE
    FOLDER = ascii_icons.FOLDER
    FILE = ascii_icons.FILE
    LINK = ascii_icons.LINK
    CLOCK = ascii_icons.CLOCK
    TARGET = ascii_icons.TARGET
    LIST = ascii_icons.LIST
    SWEEP = ascii_icons.SWEEP
    PACKAGE = ascii_icons.PACKAGE
    WAVE = ascii_icons.WAVE
    BOOK = ascii_icons.BOOK
    BOOKS = ascii_icons.BOOKS


# =========================================================================
# Output Helper Functions
# =========================================================================

def log(icon: str, message: str, prefix: str = "") -> str:
    """
    Format a log message with icon.
    
    Args:
        icon: Icon to display (use constants from this module)
        message: Message text
        prefix: Optional prefix tag like "publish" or "sync"
    
    Returns:
        Formatted string like "✓ Done!" or "[publish] ✓ Done!"
    
    Example:
        print(log(SUCCESS, "Upload complete"))
        print(log(SUCCESS, "Page created", prefix="publish"))
    """
    if prefix:
        return f"[{prefix}] {icon} {message}"
    return f"{icon} {message}"


def log_success(message: str, prefix: str = "") -> str:
    """Format a success message."""
    return log(SUCCESS, message, prefix)


def log_error(message: str, prefix: str = "") -> str:
    """Format an error message."""
    return log(ERROR, message, prefix)


def log_warning(message: str, prefix: str = "") -> str:
    """Format a warning message."""
    return log(WARNING, message, prefix)


def log_info(message: str, prefix: str = "") -> str:
    """Format an info message."""
    return log(INFO, message, prefix)


# Legacy bracket-style helpers (for gradual migration)
# These match the existing [v], [x], [!], [*] patterns

# Aliases for backward compatibility (B_ prefix no longer means "bracketed")
B_SUCCESS = SUCCESS
B_ERROR = ERROR
B_WARNING = WARNING
B_INFO = INFO
B_SKIP = SKIP


if __name__ == "__main__":
    # Demo all icons
    print("Zaphod Icons Demo")
    print("=" * 40)
    print()
    print("Status Icons:")
    print(f"  {SUCCESS} SUCCESS - Operation succeeded")
    print(f"  {ERROR} ERROR - Operation failed")
    print(f"  {WARNING} WARNING - Warning message")
    print(f"  {INFO} INFO - Information")
    print(f"  {SKIP} SKIP - Skipped")
    print()
    print("Action Icons:")
    print(f"  {SYNC} SYNC - Synchronizing")
    print(f"  {UPLOAD} UPLOAD - Uploading")
    print(f"  {DOWNLOAD} DOWNLOAD - Downloading")
    print(f"  {DELETE} DELETE - Deleting")
    print(f"  {CREATE} CREATE - Creating")
    print(f"  {EDIT} EDIT - Editing")
    print()
    print("Content Type Icons:")
    print(f"  {PAGE} PAGE")
    print(f"  {ASSIGNMENT} ASSIGNMENT")
    print(f"  {QUIZ} QUIZ")
    print(f"  {MODULE} MODULE")
    print(f"  {BANK} BANK")
    print(f"  {RUBRIC} RUBRIC")
    print(f"  {OUTCOME} OUTCOME")
    print(f"  {ASSET} ASSET")
    print()
    print("Misc Icons:")
    print(f"  {FOLDER} FOLDER")
    print(f"  {FILE} FILE")
    print(f"  {LINK} LINK")
    print(f"  {SWEEP} SWEEP")
    print(f"  {PACKAGE} PACKAGE")
    print()
    print("ASCII Fallback Mode:")
    use_ascii_icons()
    print(f"  {SUCCESS} SUCCESS (ASCII)")
    print(f"  {ERROR} ERROR (ASCII)")
    print(f"  {WARNING} WARNING (ASCII)")
