# Zaphod Security Hardening Report: `lax` → `hard`

## Executive Summary

This report documents the security improvements made to the Zaphod codebase, transforming it from the `lax` version (with known vulnerabilities) to the `hard` version (with security hardening applied).

**Files Modified:** 14
**Vulnerabilities Fixed:** 12 instances of critical `exec()` usage + multiple medium-priority issues
**New Files Added:** 1 (security_utils.py)

---

## 1. Critical Fixes: Credential Loading (exec() Removal)

### Issue
The original code used Python's `exec()` function to load credentials from files:
```python
# DANGEROUS - allows arbitrary code execution
ns = {}
exec(cred_file.read_text(), ns)
api_key = ns["API_KEY"]
```

If an attacker could modify the credentials file, they could execute arbitrary Python code.

### Fix Applied
Replaced all 12 instances with safe regex-based parsing:
```python
# SAFE - only parses specific patterns
content = cred_file.read_text(encoding="utf-8")
for pattern in [r'API_KEY\s*=\s*["\']([^"\']+)["\']', r'API_KEY\s*=\s*(\S+)']:
    match = re.search(pattern, content)
    if match:
        api_key = match.group(1).strip().strip('"\'')
        break
```

### Files Fixed
| File | Status |
|------|--------|
| `config_utils.py` | ✅ Fixed |
| `canvas_client.py` | ✅ Fixed |
| `sync_banks.py` | ✅ Fixed |
| `sync_quizzes.py` | ✅ Fixed |
| `sync_modules.py` | ✅ Fixed |
| `sync_rubrics.py` | ✅ Fixed (2 instances) |
| `sync_clo_via_csv.py` | ✅ Fixed |
| `sync_quiz_banks.py` | ✅ Fixed |
| `import_quiz_bank.py` | ✅ Fixed |
| `prune_quizzes.py` | ✅ Fixed |

---

## 2. Environment Variable Support Added

### Improvement
All credential loading functions now check environment variables first:
```python
# Priority 1: Environment variables (most secure for CI/containers)
env_key = os.environ.get("CANVAS_API_KEY")
env_url = os.environ.get("CANVAS_API_URL")
if env_key and env_url:
    return env_url.rstrip("/"), env_key

# Priority 2: Credential file (with safe parsing)
```

### Benefits
- Better security for CI/CD pipelines
- Container-friendly deployment
- Avoids storing credentials in files

---

## 3. File Permission Checks Added

### Improvement
All credential loading functions now warn about insecure file permissions:
```python
import stat
mode = os.stat(cred_file).st_mode
if mode & (stat.S_IRWXG | stat.S_IRWXO):
    print(f"[SECURITY] Credentials file has insecure permissions: {cred_file}")
    print(f"[SECURITY] Fix with: chmod 600 {cred_file}")
```

### Files Updated
All files with credential loading now include permission checks.

---

## 4. Request Timeouts Added

### Issue
HTTP requests without timeouts could hang indefinitely.

### Fix Applied (sync_banks.py)
```python
# Timeout constants
REQUEST_TIMEOUT = (10, 30)      # (connect, read) seconds
UPLOAD_TIMEOUT = (10, 120)      # longer for file uploads
MIGRATION_TIMEOUT = (10, 60)    # for status checks

# Applied to all requests
resp = requests.post(url, headers=headers, data=data, timeout=REQUEST_TIMEOUT)
```

---

## 5. Path Traversal Protection Added

### Issue
User-provided names could contain `../` or other path traversal attacks.

### Fix Applied (cli.py)
```python
def _sanitize_filename(name: str) -> str:
    """SECURITY: Prevents path traversal and shell injection."""
    safe = re.sub(r'[^\w\s-]', '', name)
    safe = re.sub(r'[-\s]+', '-', safe)
    safe = safe.strip('-').lower()
    
    if '..' in safe or safe.startswith('/'):
        raise click.ClickException(f"Invalid characters in name: {name}")
    
    return safe

# Also validates resolved path is within allowed directory
try:
    folder_path.resolve().relative_to(ctx.pages_dir.resolve())
except ValueError:
    click.echo(f"Error: Invalid name (path traversal detected)", err=True)
```

---

## 6. New Security Utilities Module

### Created: `security_utils.py`
A centralized module with reusable security functions:

```python
# Credential loading
load_canvas_credentials_safe(cred_path) -> Tuple[str, str]

# API key masking for logs
mask_sensitive(value, visible_chars=4) -> str

# Path validation
is_safe_path(base_dir, target_path) -> bool
sanitize_filename(name, max_length=255) -> str
validate_course_path(path, course_root) -> bool

# Input validation
validate_course_id(course_id) -> int
validate_url(url) -> str

# Safe JSON access
safe_get(data, key, expected_type, default) -> Any

# Content hashing
get_file_hash(file_path) -> str
get_content_hash(content) -> str

# Timeout constants
DEFAULT_TIMEOUT = (10, 30)
UPLOAD_TIMEOUT = (10, 120)
MIGRATION_TIMEOUT = (10, 60)
```

---

## 7. Summary of Changes by File

| File | Changes |
|------|---------|
| `security_utils.py` | **NEW** - Centralized security utilities |
| `config_utils.py` | Safe credential parsing, permission checks |
| `canvas_client.py` | Complete rewrite with safe parsing, env var support |
| `cli.py` | Path sanitization, _sanitize_filename helper |
| `sync_banks.py` | Safe credentials, request timeouts, env var support |
| `sync_quizzes.py` | Safe credentials, env var support |
| `sync_modules.py` | Safe credentials, env var support |
| `sync_rubrics.py` | Safe credentials (2 functions), env var support |
| `sync_clo_via_csv.py` | Safe credentials, env var support |
| `sync_quiz_banks.py` | Safe credentials, env var support |
| `import_quiz_bank.py` | Safe credentials, env var support |
| `prune_quizzes.py` | Safe credentials, env var support |
| `scaffold_course.py` | Updated templates (from lax changes) |
| `frontmatter_to_meta.py` | Unicode fixes (from lax changes) |

---

## 8. Remaining Recommendations

### Not Yet Implemented (Future Work)

1. **API Key Masking in Logs**
   - The `mask_sensitive()` function is available but not yet integrated into all logging

2. **Structured Logging**
   - Consider replacing print statements with proper logging module

3. **Rate Limiting**
   - Add rate limiting for Canvas API calls

4. **Input Validation for All User Inputs**
   - Quiz content, bank content, YAML files could benefit from schema validation

5. **Symlink Protection in File Processing**
   - Add `is_safe_path()` checks to file processing loops

---

## 9. Testing the Hardened Version

### Verify No exec() Remains
```bash
grep -r "exec(cred_file" *.py  # Should return nothing
```

### Verify Environment Variables Work
```bash
export CANVAS_API_KEY="test_key"
export CANVAS_API_URL="https://test.instructure.com"
python3 -c "from canvas_client import get_canvas_credentials; print(get_canvas_credentials())"
```

### Test Path Sanitization
```bash
# Should fail with error
python3 cli.py new --type page --name "../../../etc/passwd"
python3 cli.py new --type page --name "test; rm -rf /"
```

---

## 10. Migration Notes

### Credential File Format
The new safe parser supports the same format as before:
```python
API_KEY = "your_token_here"
API_URL = "https://canvas.institution.edu"
```

No changes required to existing credential files.

### Environment Variables (New Option)
For improved security, you can now use environment variables instead:
```bash
export CANVAS_API_KEY="your_token"
export CANVAS_API_URL="https://canvas.institution.edu"
```

---

*Report Generated: January 2026*
*Security Hardening Version: `hard`*
