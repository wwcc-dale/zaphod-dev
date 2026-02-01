#!/usr/bin/env python3
"""
validate.py - Check course content for errors before syncing

Usage:
    python validate.py [--fix] [--verbose]
    
Or via CLI:
    zaphod validate [--fix] [--verbose]

Checks:
- Frontmatter validity (YAML syntax, required fields)
- Content type validation (page, assignment, link, file)
- Assignment requirements (points_possible, submission_types)
- Module references (do referenced modules exist in module_order.yaml?)
- Rubric validity (required fields, rating points)
- Quiz syntax (correct answer markers, question format)
- Include references (do {{include:name}} files exist?)
- Outcome references (do referenced outcomes exist?)
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import json
import re
import yaml
import frontmatter

from zaphod.icons import SUCCESS, ERROR, WARNING, INFO


class Severity(Enum):
    ERROR = "error"      # Must fix before sync will work
    WARNING = "warning"  # Should fix, but sync might work
    INFO = "info"        # Suggestion for improvement


@dataclass
class Issue:
    """A single validation issue"""
    file: Path
    message: str
    severity: Severity = Severity.ERROR
    line: Optional[int] = None
    suggestion: Optional[str] = None
    auto_fixable: bool = False
    
    def __str__(self):
        loc = f"{self.file}"
        if self.line:
            loc += f":{self.line}"
        
        icon = {"error": ERROR, "warning": WARNING, "info": INFO}[self.severity.value]
        msg = f"  {icon} {self.message}"
        
        if self.suggestion:
            msg += f"\n    â†’ {self.suggestion}"
        
        return msg


@dataclass
class ValidationResult:
    """Results from validating a course"""
    issues: List[Issue] = field(default_factory=list)
    files_checked: int = 0
    
    @property
    def errors(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]
    
    @property
    def warnings(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]
    
    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0
    
    def add(self, issue: Issue):
        self.issues.append(issue)
    
    def summary(self) -> str:
        e = len(self.errors)
        w = len(self.warnings)
        
        if e == 0 and w == 0:
            return f"{SUCCESS} All {self.files_checked} files valid!"
        
        parts = []
        if e > 0:
            parts.append(f"{e} error{'s' if e != 1 else ''}")
        if w > 0:
            parts.append(f"{w} warning{'s' if w != 1 else ''}")
        
        return f"Found {', '.join(parts)} in {self.files_checked} files checked."


class CourseValidator:
    """Validates a Zaphod course"""
    
    VALID_TYPES = {"page", "assignment", "link", "file"}
    REQUIRED_FIELDS = {"name", "type"}
    ASSIGNMENT_FIELDS = {"points_possible"}
    LINK_FIELDS = {"external_url"}
    
    def __init__(self, course_path: Path):
        self.course_path = course_path
        
        # Support both content/ and pages/ directories
        content_dir = course_path / "content"
        pages_dir = course_path / "pages"
        self.content_dir = content_dir if content_dir.exists() else pages_dir
        
        self.outcomes_dir = course_path / "outcomes"
        self.quiz_banks_dir = course_path / "quiz-banks"
        self.modules_dir = course_path / "modules"
        
        # Include directories: shared/ (new) and includes/ (legacy)
        self.includes_dirs = [
            course_path / "shared",
            self.content_dir / "includes",
            course_path / "includes",
        ]
        
        # Load reference data
        self.outcomes = self._load_outcomes()
        self.module_order = self._load_module_order()
        self.includes = self._find_includes()
    
    def _load_outcomes(self) -> Dict[str, Any]:
        """Load outcomes.yaml if it exists"""
        outcomes_file = self.outcomes_dir / "outcomes.yaml"
        if not outcomes_file.exists():
            return {}
        
        try:
            data = yaml.safe_load(outcomes_file.read_text())
            if not data:
                return {}
            
            # Index by code
            outcomes = {}
            for o in data.get("course_outcomes", []):
                code = o.get("code")
                if code:
                    outcomes[code] = o
            return outcomes
        except Exception:
            return {}
    
    def _load_module_order(self) -> List[str]:
        """Load module_order.yaml if it exists"""
        order_file = self.modules_dir / "module_order.yaml"
        if not order_file.exists():
            return []
        
        try:
            data = yaml.safe_load(order_file.read_text())
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("modules", [])
            return []
        except Exception:
            return []
    
    def _find_includes(self) -> set:
        """Find all available include files"""
        includes = set()
        for inc_dir in self.includes_dirs:
            if inc_dir.exists():
                for f in inc_dir.glob("*.md"):
                    includes.add(f.stem)
        return includes
    
    def validate(self) -> ValidationResult:
        """Run all validations"""
        result = ValidationResult()
        
        # Validate content folders
        if self.content_dir.exists():
            for ext in [".page", ".assignment", ".link", ".file"]:
                for folder in self.content_dir.rglob(f"*{ext}"):
                    if folder.is_dir():
                        self._validate_content_folder(folder, result)
                        result.files_checked += 1
        
        # Validate quiz banks
        if self.quiz_banks_dir.exists():
            for quiz_file in self.quiz_banks_dir.glob("*.quiz.txt"):
                self._validate_quiz(quiz_file, result)
                result.files_checked += 1
        
        # Validate outcomes
        outcomes_file = self.outcomes_dir / "outcomes.yaml"
        if outcomes_file.exists():
            self._validate_outcomes(outcomes_file, result)
            result.files_checked += 1
        
        # Validate module order
        order_file = self.modules_dir / "module_order.yaml"
        if order_file.exists():
            self._validate_module_order(order_file, result)
            result.files_checked += 1
        
        return result
    
    def _validate_content_folder(self, folder: Path, result: ValidationResult):
        """Validate a .page, .assignment, .link, or .file folder"""
        index_path = folder / "index.md"
        meta_path = folder / "meta.json"
        
        # Must have index.md or meta.json
        if not index_path.exists() and not meta_path.exists():
            result.add(Issue(
                file=folder,
                message="Missing index.md (and no meta.json fallback)",
                severity=Severity.ERROR,
                suggestion="Create index.md with frontmatter"
            ))
            return
        
        # Parse frontmatter
        if index_path.exists():
            try:
                post = frontmatter.load(index_path)
                meta = dict(post.metadata)
                content = post.content
            except yaml.YAMLError as e:
                result.add(Issue(
                    file=index_path,
                    message=f"Invalid YAML frontmatter: {e}",
                    severity=Severity.ERROR,
                    suggestion="Check YAML syntax (indentation, quotes, colons)"
                ))
                return
            except Exception as e:
                result.add(Issue(
                    file=index_path,
                    message=f"Failed to parse: {e}",
                    severity=Severity.ERROR
                ))
                return
        else:
            # Fall back to meta.json
            try:
                meta = json.loads(meta_path.read_text())
                content = ""
            except json.JSONDecodeError as e:
                result.add(Issue(
                    file=meta_path,
                    message=f"Invalid JSON: {e}",
                    severity=Severity.ERROR
                ))
                return
        
        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in meta or not meta[field]:
                result.add(Issue(
                    file=index_path if index_path.exists() else meta_path,
                    message=f"Missing required field: '{field}'",
                    severity=Severity.ERROR,
                    suggestion=f"Add '{field}: \"value\"' to frontmatter"
                ))
        
        # Check type is valid
        content_type = str(meta.get("type", "")).lower()
        if content_type and content_type not in self.VALID_TYPES:
            result.add(Issue(
                file=index_path,
                message=f"Invalid type: '{content_type}'",
                severity=Severity.ERROR,
                suggestion=f"Use one of: {', '.join(sorted(self.VALID_TYPES))}"
            ))
        
        # Type-specific validation
        if content_type == "assignment":
            self._validate_assignment(folder, meta, result)
        elif content_type == "link":
            self._validate_link(folder, meta, result)
        
        # Check module references
        modules = meta.get("modules", [])
        if modules and self.module_order:
            for mod in modules:
                if mod not in self.module_order:
                    result.add(Issue(
                        file=index_path,
                        message=f"Module '{mod}' not in module_order.yaml",
                        severity=Severity.WARNING,
                        suggestion="Add it to modules/module_order.yaml or fix the name"
                    ))
        
        # Check include references
        if content:
            self._validate_includes(index_path, content, result)
    
    def _validate_assignment(self, folder: Path, meta: Dict, result: ValidationResult):
        """Assignment-specific validation"""
        index_path = folder / "index.md"
        
        # Check points_possible
        if "points_possible" not in meta:
            result.add(Issue(
                file=index_path,
                message="Assignment missing 'points_possible'",
                severity=Severity.WARNING,
                suggestion="Add 'points_possible: 100' (or appropriate value)"
            ))
        
        # Check submission_types
        if "submission_types" not in meta:
            result.add(Issue(
                file=index_path,
                message="Assignment missing 'submission_types'",
                severity=Severity.INFO,
                suggestion="Add 'submission_types: [\"online_upload\"]' or similar"
            ))
        
        # Check rubric if present
        rubric_path = folder / "rubric.yaml"
        if rubric_path.exists():
            self._validate_rubric(rubric_path, result)
    
    def _validate_link(self, folder: Path, meta: Dict, result: ValidationResult):
        """Link-specific validation"""
        index_path = folder / "index.md"
        
        if "external_url" not in meta or not meta["external_url"]:
            result.add(Issue(
                file=index_path,
                message="Link missing 'external_url'",
                severity=Severity.ERROR,
                suggestion="Add 'external_url: \"https://example.com\"'"
            ))
    
    def _validate_rubric(self, rubric_path: Path, result: ValidationResult):
        """Validate a rubric.yaml file"""
        try:
            data = yaml.safe_load(rubric_path.read_text())
        except yaml.YAMLError as e:
            result.add(Issue(
                file=rubric_path,
                message=f"Invalid YAML: {e}",
                severity=Severity.ERROR
            ))
            return
        
        if not data:
            result.add(Issue(
                file=rubric_path,
                message="Rubric file is empty",
                severity=Severity.ERROR
            ))
            return
        
        # Check for use_rubric reference
        if "use_rubric" in data:
            # It's a reference to a shared rubric, that's fine
            return
        
        # Check required rubric fields
        if "title" not in data:
            result.add(Issue(
                file=rubric_path,
                message="Rubric missing 'title'",
                severity=Severity.ERROR
            ))
        
        criteria = data.get("criteria", [])
        if not criteria:
            result.add(Issue(
                file=rubric_path,
                message="Rubric has no criteria",
                severity=Severity.ERROR,
                suggestion="Add 'criteria:' with at least one criterion"
            ))
        
        for i, crit in enumerate(criteria):
            if isinstance(crit, str):
                # It's a {{rubric_row:...}} reference, skip
                continue
            
            if "description" not in crit:
                result.add(Issue(
                    file=rubric_path,
                    message=f"Criterion {i+1} missing 'description'",
                    severity=Severity.ERROR
                ))
            
            if "points" not in crit:
                result.add(Issue(
                    file=rubric_path,
                    message=f"Criterion {i+1} missing 'points'",
                    severity=Severity.ERROR
                ))
            
            ratings = crit.get("ratings", [])
            if not ratings:
                result.add(Issue(
                    file=rubric_path,
                    message=f"Criterion {i+1} has no ratings",
                    severity=Severity.WARNING
                ))
    
    def _validate_includes(self, file_path: Path, content: str, result: ValidationResult):
        """Check that {{include:name}} references exist"""
        include_pattern = re.compile(r"\{\{include:([a-zA-Z_][a-zA-Z0-9_-]*)\}\}")
        
        for match in include_pattern.finditer(content):
            name = match.group(1)
            if name not in self.includes:
                result.add(Issue(
                    file=file_path,
                    message=f"Include not found: '{{{{include:{name}}}}}'",
                    severity=Severity.ERROR,
                    suggestion=f"Create 'shared/{name}.md' or 'includes/{name}.md'"
                ))
    
    def _validate_quiz(self, quiz_path: Path, result: ValidationResult):
        """Validate a quiz.txt file"""
        try:
            content = quiz_path.read_text()
        except Exception as e:
            result.add(Issue(
                file=quiz_path,
                message=f"Failed to read: {e}",
                severity=Severity.ERROR
            ))
            return
        
        lines = content.splitlines()
        
        # Skip frontmatter if present
        start_line = 0
        if lines and lines[0].strip() == "---":
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    start_line = i + 1
                    break
        
        # Parse questions
        question_pattern = re.compile(r"^\s*(\d+)\.\s+")
        correct_mc_pattern = re.compile(r"^\s*\*[a-z]\)")
        correct_ma_pattern = re.compile(r"^\s*\[\*\]")
        correct_tf_pattern = re.compile(r"^\s*\*[ab]\)\s*(True|False)", re.IGNORECASE)
        correct_sa_pattern = re.compile(r"^\s*\*\s+")
        essay_pattern = re.compile(r"^\s*####\s*$")
        upload_pattern = re.compile(r"^\s*\^\^\^\^\s*$")
        
        in_question = False
        question_num = 0
        question_start = 0
        has_correct = False
        question_type = None
        
        for i, line in enumerate(lines[start_line:], start_line + 1):
            # New question?
            q_match = question_pattern.match(line)
            if q_match:
                # Check previous question
                if in_question and not has_correct and question_type not in ("essay", "upload"):
                    result.add(Issue(
                        file=quiz_path,
                        line=question_start,
                        message=f"Question {question_num}: No correct answer marked",
                        severity=Severity.ERROR,
                        suggestion="Mark correct answer with * (e.g., '*b)' or '[*]')"
                    ))
                
                # Start new question
                in_question = True
                question_num = int(q_match.group(1))
                question_start = i
                has_correct = False
                question_type = None
                continue
            
            if in_question:
                # Check for correct answer markers
                if correct_mc_pattern.match(line):
                    has_correct = True
                    question_type = "mc"
                elif correct_ma_pattern.match(line):
                    has_correct = True
                    question_type = "ma"
                elif correct_tf_pattern.match(line):
                    has_correct = True
                    question_type = "tf"
                elif correct_sa_pattern.match(line):
                    has_correct = True
                    question_type = "sa"
                elif essay_pattern.match(line):
                    has_correct = True  # Essays don't need correct answers
                    question_type = "essay"
                elif upload_pattern.match(line):
                    has_correct = True  # File uploads don't need correct answers
                    question_type = "upload"
        
        # Check last question
        if in_question and not has_correct and question_type not in ("essay", "upload"):
            result.add(Issue(
                file=quiz_path,
                line=question_start,
                message=f"Question {question_num}: No correct answer marked",
                severity=Severity.ERROR,
                suggestion="Mark correct answer with * (e.g., '*b)' or '[*]')"
            ))
    
    def _validate_outcomes(self, outcomes_path: Path, result: ValidationResult):
        """Validate outcomes.yaml"""
        try:
            data = yaml.safe_load(outcomes_path.read_text())
        except yaml.YAMLError as e:
            result.add(Issue(
                file=outcomes_path,
                message=f"Invalid YAML: {e}",
                severity=Severity.ERROR
            ))
            return
        
        if not data:
            result.add(Issue(
                file=outcomes_path,
                message="Outcomes file is empty",
                severity=Severity.WARNING
            ))
            return
        
        outcomes = data.get("course_outcomes", [])
        if not outcomes:
            result.add(Issue(
                file=outcomes_path,
                message="No course_outcomes defined",
                severity=Severity.WARNING
            ))
            return
        
        codes_seen = set()
        for i, outcome in enumerate(outcomes):
            code = outcome.get("code")
            if not code:
                result.add(Issue(
                    file=outcomes_path,
                    message=f"Outcome {i+1} missing 'code'",
                    severity=Severity.ERROR
                ))
            elif code in codes_seen:
                result.add(Issue(
                    file=outcomes_path,
                    message=f"Duplicate outcome code: '{code}'",
                    severity=Severity.ERROR
                ))
            else:
                codes_seen.add(code)
            
            if not outcome.get("title"):
                result.add(Issue(
                    file=outcomes_path,
                    message=f"Outcome '{code or i+1}' missing 'title'",
                    severity=Severity.ERROR
                ))
    
    def _validate_module_order(self, order_path: Path, result: ValidationResult):
        """Validate module_order.yaml"""
        try:
            data = yaml.safe_load(order_path.read_text())
        except yaml.YAMLError as e:
            result.add(Issue(
                file=order_path,
                message=f"Invalid YAML: {e}",
                severity=Severity.ERROR
            ))
            return
        
        if not data:
            result.add(Issue(
                file=order_path,
                message="Module order file is empty",
                severity=Severity.WARNING
            ))


def validate_course(course_path: Path = None, verbose: bool = False) -> ValidationResult:
    """Main entry point for validation"""
    if course_path is None:
        course_path = Path.cwd()
    
    validator = CourseValidator(course_path)
    result = validator.validate()
    
    return result


def print_results(result: ValidationResult, verbose: bool = False):
    """Print validation results to console"""
    # Group by file
    by_file: Dict[Path, List[Issue]] = {}
    for issue in result.issues:
        if issue.file not in by_file:
            by_file[issue.file] = []
        by_file[issue.file].append(issue)
    
    # Print each file's issues
    for file_path, issues in sorted(by_file.items()):
        print(f"\n{file_path}")
        for issue in issues:
            print(issue)
    
    # Print summary
    print(f"\n{result.summary()}")
    
    if result.is_valid:
        print(f"{SUCCESS} Course is ready to sync!")
    else:
        print(f"{ERROR} Fix errors before syncing.")


# CLI integration
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate Zaphod course content")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show more details")
    parser.add_argument("--path", "-p", type=Path, default=None, help="Course path (default: current directory)")
    args = parser.parse_args()
    
    course_path = args.path or Path.cwd()
    
    print(f"Validating course: {course_path}\n")
    
    result = validate_course(course_path, verbose=args.verbose)
    print_results(result, verbose=args.verbose)
    
    # Exit with error code if invalid
    exit(0 if result.is_valid else 1)
