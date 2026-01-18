# Known Issues & Limitations

Current problems, limitations, and areas for improvement in Zaphod.

---

## 🔴 Critical Issues

### No Conflict Resolution
**Problem:** When Canvas content is newer than local, last-write-wins

**Scenario:**
1. Instructor A edits page in Canvas
2. Instructor B syncs local file (older version)
3. Canvas version is overwritten (Instructor A's changes lost)

**Status:** By design, but problematic for some workflows

**Workaround:**
- Always edit locally, never in Canvas
- Use sandbox for testing before live
- Coordinate with team on who's editing

**Future:** Add conflict detection (planned 2026)

---

### Upload Cache Staleness
**Problem:** Cache can get out of sync with actual Canvas files

**Scenario:**
- File is uploaded, cached
- File deleted in Canvas manually
- Next sync uses cached ID → broken link

**Status:** Known limitation

**Workaround:**
- Delete `_course_metadata/upload_cache.json` to rebuild
- Or use `--force-reupload` flag (if added)

**Future:** Add cache validation (planned)

---

### No Undo for Prune Operations
**Problem:** Deletions are immediate, can't be undone automatically

**Risk:** Accidentally delete Canvas content

**Status:** By design, but could be improved

**Mitigation:**
- Always use `--dry-run` first
- Keep git history (can republish deleted content)
- Use sandbox for testing

**Future:** Add backup/restore command

---

## ⚠️ Important Limitations

### Module Reordering Can Fail Silently
**Problem:** Sometimes modules don't reorder, no error shown

**Cause:** Canvas API returns success but doesn't update position

**Status:** Canvas API quirk, hard to fix

**Workaround:**
- Check Canvas after sync
- Manually adjust if needed
- Report to Canvas support if persistent

---

### Video Upload Cache is Filename-Based
**Problem:** Doesn't detect content changes if filename same

**Scenario:**
- Upload `intro.mp4`
- Replace with different `intro.mp4` (same name)
- Cache thinks it's already uploaded

**Status:** Known limitation

**Workaround:**
- Use unique filenames (intro-v2.mp4)
- Or delete cache entry manually

**Future:** Switch to content-hash caching (planned)

---

### Single Course at a Time
**Problem:** Can only sync one Canvas course per run

**Limitation:** `COURSE_ID` env var is global

**Status:** By design for simplicity

**Workaround:**
- Run separately for each course
- Change `COURSE_ID` between runs

**Future:** Multi-course workspace (planned)

---

### Classic Quizzes Only
**Problem:** No support for Canvas New Quizzes

**Limitation:** New Quizzes API is limited/different

**Status:** Technical limitation

**Workaround:** Use Classic Quizzes for now

**Future:** May add New Quizzes when API improves

---

## 💡 Minor Issues

### Error Messages Inconsistent
**Problem:** Some errors are cryptic, some are helpful

**Status:** Being actively improved (2026)

**Progress:**
- Added `errors.py` with better messages
- Gradually updating all scripts

---

### No Pre-Sync Validation
**Problem:** Errors discovered during sync, not before

**Example:** Missing required frontmatter fields found during publish

**Status:** Validation command in development

**Future:** `zaphod validate` command (planned)

---

### Watch Mode Doesn't Catch File Renames
**Problem:** Renaming a file doesn't trigger sync for the renamed file

**Cause:** Watchdog sees delete + create as separate events

**Status:** Edge case, low priority

**Workaround:** Manually sync after rename, or save the file to trigger

---

### Symlink Handling on Windows
**Problem:** Symlinks require admin privileges on Windows

**Impact:** Can't easily share assets between assignments

**Status:** Windows limitation

**Workaround:**
- Copy files instead of symlinking
- Or use WSL for development

---

## 📋 By Design (Not Bugs)

These are intentional limitations that come with Zaphod's design philosophy.

### Last-Write-Wins (No Merge)
- **Why:** Zaphod is local-first, Canvas is the reflection
- **Impact:** Can't merge changes from Canvas
- **Mitigation:** Edit locally always

### Local-Only (No Cloud Sync)
- **Why:** Simplicity, no server needed
- **Impact:** Each user has their own copy
- **Mitigation:** Use Git for team collaboration

### Single-User at a Time
- **Why:** Script-based, not server-based
- **Impact:** Can't have concurrent edits
- **Mitigation:** Coordinate with team, use Git branches

### Requires Command Line
- **Why:** Script-based tools
- **Impact:** Less accessible for non-technical users
- **Mitigation:** Web UI in development (2026)

### Canvas-Specific
- **Why:** Built for Canvas LMS
- **Impact:** Not portable to other LMS
- **Mitigation:** Plain text makes migration easier

---

## 🐛 Bugs to Fix

### Occasional Module Item Duplication
**Problem:** Sometimes same item appears twice in module

**Frequency:** Rare

**Cause:** Unknown, race condition suspected

**Workaround:** Delete duplicate manually in Canvas

**Priority:** Medium

---

### Empty Modules Not Always Deleted
**Problem:** Empty modules sometimes survive prune

**Frequency:** Intermittent

**Cause:** Timing issue or Canvas API inconsistency

**Workaround:** Delete manually or re-run prune

**Priority:** Low

---

## 🔮 Future Improvements

### Planned (2026)
- ✅ Unified CLI (done!)
- ✅ Better error messages (in progress)
- ✅ Testing infrastructure (in progress)
- ⏳ Validation command
- ⏳ Web UI for visual management
- ⏳ Configuration file support

### Under Consideration
- Conflict detection
- Content-hash caching
- Backup/restore commands
- Multi-course workspaces
- New Quizzes support
- Outcome alignment automation

### Not Planned
- Multi-user concurrent editing (architecture doesn't support)
- Real-time collaboration (use Git instead)
- Full Canvas replacement (Zaphod is a sync tool)

---

## 📞 Reporting Issues

If you find a bug:
1. Check this document first
2. Try `--dry-run` to see what would happen
3. Check `_course_metadata/watch_state.json` for state issues
4. Review recent git changes for cause
5. Report with:
   - What you did
   - What you expected
   - What actually happened
   - Error messages (full output)

---

## 💡 Tips for Avoiding Issues

1. **Always test in sandbox first**
2. **Use `--dry-run` before destructive operations**
3. **Keep git history clean** (can recover deleted content)
4. **Edit locally only** (don't edit in Canvas)
5. **Coordinate with team** (who's editing what)
6. **Clear cache when in doubt** (delete upload_cache.json)
7. **Check Canvas after sync** (verify changes applied)
8. **Use validation** (when available)