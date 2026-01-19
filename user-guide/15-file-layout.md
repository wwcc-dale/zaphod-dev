### Simple overview of course directory structure for Zaphod

```text
curriculum-workshop/
├─ courses/
│  ├─ _all_courses/         # Items that pertain to all your courses
│  │ 
│  ├─ my-first-course/      # A single course (Canvas Shell) 
│  │  ├─ _course_metadata/  # Housekeeping Items for Zaphod
│  │  │  
│  │  ├─ assets/            # Images, Videos, and other media
│  │  ├─ exports/           # Exported IMSCC files
│  │  ├─ includes/          # Reusable content snippets
│  │  ├─ modules/           # Module order / empty modules you want to keep
│  │  ├─ outcomes/          # Course Learning Outcomes
│  │  ├─ pages/             # Course Pages and Assignments (with rubrics)
│  │  ├─ quiz-banks/        # Quiz bank text files (simple NYIT formatting)
│  │  ├─ rubrics/           # Shared Rubrics (reusable rubric rows and full rubrics)
│  │  ├─ templates/         # Headers/Footers for Pages and Assignments
│  │  └─ zaphod.yaml        # Course configuration file
│  │ 
│  ├─ basket-weaving-114/   # Another course (Canvas Shell)
│  │ 
│  ├─ scuba-diving-128/     # Another course (Canvas Shell)
│  │ 
│  └─ ...                   # More courses as needed
│   
├─ docs/ # Detailed Zaphod Documentation
│
│ ------------------ IGNORE ------------------------
├─ tests/ # IGNORE: Zaphod troubleshooting tests
├─ zaphod/ # IGNORE: Where the magic happens
├─ pytest.ini # IGNORE: Test configuration
└─ setup.py # IGNORE: Zaphod setup file
```


### Detailed overview of course directory structure for Zaphod

```text
curriculum-workshop/
├─ courses/
│  ├─ _all_courses/
│  │  └─ .placeholder
│  └─ my-first-course/
│     ├─ _course_metadata/
│     │  ├─ replacements.json
│     │  ├─ upload_cache.json
│     │  └─ watch_state.json
│     ├─ assets/
│     │  ├─ videos/
│     │  │  ├─ happiness.mp4
│     │  │  ├─ joy.mp4
│     │  │  └─ kindness.mp4
│     │  ├─ food.jpg
│     │  └─ drink.jpg
│     ├─ exports/
│     │  └─ my-first-course_export.imscc
│     ├─ includes/
│     │  ├─ assignment-checklist.md
│     │  └─ how-to-submit.md
│     ├─ modules/
│     │  └─ module_order.yaml
│     ├─ outcomes/
│     │  ├─ outcome_map.json
│     │  ├─ outcomes_import.csv
│     │  └─ outcomes.yaml
│     ├─ pages/
│     │  ├─ module-Credit 1/
│     │  ├─ module-Credit 2/
│     │  │  └─ page1.page/
│     │  │     ├─ index.md
│     │  │     └─ zaphod-picture.jpg
│     │  ├─ module-Credit 3/
│     │  │  └─ page2.page/
│     │  │     └─ index.md
│     │  ├─ module-Credit 4/
│     │  │  └─ page6.page/
│     │  │     └─ index.md
│     │  └─ module-Credit 5/
│     │     ├─ assignment1.assignment/
│     │     │  ├─ index.md
│     │     │  └─ rubric.yaml
│     │     └─ page9.page/
│     │        ├─ index.md
│     │        └─ rubric.yaml
│     ├─ quiz-banks/
│     │  └─ test.quiz.txt
│     ├─ rubrics/
│     │  ├─ rows/
│     │  │  ├─ thesis-rubric-row.yaml
│     │  │  └─ composition-rubric-row.yaml
│     │  ├─ some-often-used-rubric.yaml
│     │  └─ another-oft-used-rubric.yaml
│     ├─ templates/
│     │  └─ default/
│     │     ├─ footer.html
│     │     ├─ footer.md
│     │     ├─ header.html
│     │     └─ header.md
│     ├─ .gitignore
│     ├─ .zaphod_watch_state.json
│     └─ zaphod.yaml
├─ docs/
│  ├─ 00-overview.md
│  ├─ 01-pages.md
│  ├─ 02-assignments.md
│  ├─ 03-variables.md
│  ├─ 04-includes.md
│  ├─ 05-modules.md
│  ├─ 06-rubrics.md
│  ├─ 07-outcomes.md
│  ├─ 08-assets.md
│  ├─ 09-quizzes.md
│  ├─ 10-pipeline.md
│  └─ LICENSE
├─ tests/
│  ├─ conftest.py
│  ├─ requirements.txt
│  ├─ run_tests.py
│  ├─ test_cli.py
│  ├─ test_config_utils.py
│  ├─ test_export_cartridge.py
│  ├─ test_frontmatter.py
│  ├─ test_publish_all.py
│  ├─ test_quiz_parsing.py
│  ├─ test_quiz_parsing.pyZone.Identifier
│  ├─ test_rubrics.py
│  ├─ test_subfolder_features.py
│  ├─ test_subfolder_features.pyZone.Identifier
│  └─ test_sync_modules.py
├─ zaphod/
│  ├─ __init__.py
│  ├─ 00-README.md
│  ├─ 01-ARCHITECTURE.md
│  ├─ 02-DECISIONS.md
│  ├─ 03-GLOSSARY.md
│  ├─ 04-KNOWN-ISSUES.md
│  ├─ 05-QUICK-START.md
│  ├─ 07-TODO.md
│  ├─ canvas_client.py
│  ├─ canvas_publish.py
│  ├─ cli.py
│  ├─ config_utils.py
│  ├─ errors.py
│  ├─ export_cartridge.py
│  ├─ frontmatter_to_meta.py
│  ├─ prune_canvas_content.py
│  ├─ prune_quizzes.py
│  ├─ publish_all.py
│  ├─ scaffold_course.py
│  ├─ scrape_and_prep.py
│  ├─ sync_clo_via_csv.py
│  ├─ sync_modules.py
│  ├─ sync_quiz_banks.py
│  ├─ sync_rubrics.py
│  ├─ validate.py
│  └─ watch_and_publish.py
├─ .gitignore
├─ pytest.ini
└─ setup.py
```