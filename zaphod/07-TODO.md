# To Do List

## Completed
- [x] Common Cartridge export (`export_cartridge.py`) - Exports full course to .imscc format
- [x] **Asset subfolder resolution** - Users can organize assets in subdirectories
  - Auto-discovers assets from any subfolder in `assets/`
  - Supports explicit paths like `../assets/images/logo.png`
  - Warns and fails on duplicate filenames (requires explicit path)
  - Fixed path resolution with `../` relative paths using `.resolve()`
- [x] **Module inference from directory** - `module-` prefix convention
  - Directories like `pages/module-Week 1/` auto-assign contents to "Week 1" module
  - Explicit `modules:` in frontmatter always overrides
  - Reduces repetitive frontmatter for module-organized courses
- [x] **Content-hash caching** - All upload functions now use content hash
  - Cache key format: `{course_id}:{filename}:{content_hash}`
  - Updated files with same name get re-uploaded (different hash)
  - Same filename in different locations handled correctly
  - Applied to: video uploads, local assets, bulk uploads
- [x] **Initial sync on watch startup** - Full sync runs when watch mode starts
- [x] **Prune cleanup** - `meta.json` added to auto-cleaned work files
- [x] **Simplified prune in watch** - Uses script defaults, no extra env vars needed
- [x] **Unicode cleanup** - Fixed corrupted unicode in all Python files

## In Progress
1. Outcome ratings file with replacement pattern {{ratings:default}} or would it be better to simply rely on an extension of includes?

## Future Enhancements
1. Rename `pages/` to `content/` for clarity (contains pages, assignments, links, files)
2. Add Canvas-specific extensions to CC export (discussion topics, announcements)
3. Add QTI 2.1 support as alternative to QTI 1.2
4. Add CC import capability (reverse of export)
5. Add selective export (--modules flag to export only specific modules)
6. Add export validation against CC 1.3 schema
7. Testing infrastructure - pytest tests for core functions
8. Web UI for non-technical users
9. **Large media manifest system** - Keep Git repos clean by excluding large media files
   - **Problem**: Large video/audio files bloat Git repos and make cloning slow
   - **Solution**: Manifest-based system with hydrate script for shared media store
   - **Design principles**:
     - File-type based `.gitignore` (e.g., `*.mp4`, `*.mov`, `*.wav`) - not directory-based
     - Local asset handling unchanged - Zaphod works exactly as now for authors
     - Manifest built after prune step - snapshot of large media for later hydration
     - Hydrate checks local first - only pulls what's missing from shared store
     - Manifest is just a bill of materials - source location supplied at hydrate time
   - **Components**:
     - `.gitignore` patterns for large media extensions
     - `_course_metadata/media_manifest.json` - lists large files (tracked in Git)
     - `build_media_manifest.py` - Runs after prune, scans for large media types
     - `hydrate_media.py --source PATH` - For instructors: checks local, pulls missing
   - **Manifest format**:
     ```json
     {
       "version": "1.0",
       "generated_at": "2026-01-18T18:05:00Z",
       "items": [
         {
           "relative_path": "assets/videos/lecture01.mp4",
           "checksum": "sha256:abcd1234...",
           "size_bytes": 123456789
         }
       ]
     }
     ```
   - **Author workflow**: No change - work normally, manifest auto-generated after prune
   - **Instructor workflow**: Clone repo → run `hydrate_media.py --source "\\server\share"` → done
   - **Backend options**: SMB file server, local path, or HTTP(S) URL
