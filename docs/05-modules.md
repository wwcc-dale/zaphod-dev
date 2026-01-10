## Modules in Zaphod

Modules control the path students follow through your course in Canvas. In Zaphod, you describe module structure in text—both which modules exist and which items belong in them—and Zaphod makes Canvas match that description.

### How items choose their modules

Every page, assignment, file item, or link item can list the modules it belongs to in its own `index.md` frontmatter:

```yaml
---
name: "Week 1 Overview"
type: "Page"
modules:
  - "Module 1: Getting Started"
  - "Module 1: Getting Started / Optional Resources"
published: true
indent: 1
---
```

In this example:

- The page will appear in “Module 1: Getting Started”.
- It will also appear under a sub‑section or follow‑up module named “Module 1: Getting Started / Optional Resources”, depending on how you choose to name things.
- `indent` controls how far the item is indented within the module, which Canvas uses to visually group related items.

You can add or remove module names here at any time; on the next sync, Zaphod will update Canvas to reflect the new structure.

### Optional module ordering file

In addition to each item listing its own modules, you can maintain a simple module ordering file (for example `modules/module_order.yaml`) to describe the overall sequence of modules and which ones should never be deleted:

```yaml
protected_modules:
  - "Course Resources"
  - "Instructor Notes"

module_order:
  - "Module 0: Start Here"
  - "Module 1: Getting Started"
  - "Module 2: Drafting"
  - "Module 3: Revising"
```

Typical uses:

- **`module_order`** tells Zaphod the preferred top‑to‑bottom order of modules in Canvas.  
- **`protected_modules`** are modules Zaphod should leave alone, even if they end up empty (for example an ongoing “Course Resources” module).

If you don’t provide this file, Zaphod will still create whatever modules your content asks for; they just won’t have a centrally controlled order.

### What the module sync does

When you run the module‑related steps in the pipeline, Zaphod:

- Reads each item’s `modules` list from its frontmatter.  
- Ensures those modules exist in Canvas, creating them if necessary.  
- Adds each item to the modules it lists, avoiding duplicate entries.  
- Optionally reorders modules in Canvas to match `module_order`, and prunes extra module items or empty modules according to your settings.

The result is that your file structure and frontmatter become the source of truth for how the course is organized, while Canvas’s Modules page becomes a live reflection of what you’ve described in text.