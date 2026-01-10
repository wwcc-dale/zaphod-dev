#!/usr/bin/env python3

# a script for publishing content that's ready to go!
# this script should be executed from root level in this repo.

dry_run = False

import markdown2canvas as mc
from pathlib import Path

# Ensure we are running from repo root even if script is called from elsewhere
script_dir = Path(__file__).resolve().parent
repo_root = script_dir.parent
print(f"Repo root: {repo_root}")
 
# we will skip blank lines and lines that start with # or %
with open(repo_root / "_tools" / "content_ready", "r") as f:
    ready_files = f.read().split("\n")

ready_files = [
    str((repo_root / f).resolve())
    for f in ready_files
    if f and not (f.startswith("#") or f.startswith("%"))
]

print("Ready files:", ready_files)

# 🎯 Only list your course IDs here
course_ids = [1259205]  # replace with your real course ID(s)

# Do NOT pass url=... here; let it use CANVAS_CREDENTIAL_FILE
canvas = mc.make_canvas_api_obj()

for course_id in course_ids:
    course = canvas.get_course(course_id)
    print(f"Publishing to {course.name} (ID {course_id})")

    # helper to choose correct markdown2canvas object from folder extension
    def make_mc_obj(path_str: str):
        if path_str.endswith(".page"):
            return mc.Page(path_str)
        if path_str.endswith(".assignment"):
            return mc.Assignment(path_str)
        if path_str.endswith(".link"):
            return mc.Link(path_str)
        if path_str.endswith(".file"):
            return mc.File(path_str)
        raise ValueError(f"Unrecognized content type for path: {path_str}")

    # loop over the files
    for f in ready_files:
        print("Processing:", f)
        obj = make_mc_obj(f)

        if not dry_run:
            obj.publish(course, overwrite=True)
        else:
            print(f"[dry run] would publish {obj}")
