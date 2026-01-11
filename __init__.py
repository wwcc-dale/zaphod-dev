"""
Zaphod - Canvas course management from plain text files

A local-first course authoring workspace that makes Canvas LMS course
management faster, safer, and more reusable than editing directly in
the browser.

Core Concept: Plain-text files on disk are the single source of truth,
Zaphod scripts sync them to Canvas.
"""

__version__ = "1.0.0"
__author__ = "Dale Chapman"
__license__ = "MIT"

# Make key utilities easily importable
from .config_utils import get_course_id
from .errors import ZaphodError, ConfigurationError

__all__ = [
    "__version__",
    "get_course_id",
    "ZaphodError",
    "ConfigurationError",
]
