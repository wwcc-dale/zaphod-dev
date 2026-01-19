## Quizzes in Zaphod

Quizzes in Zaphod are written as plain‑text files instead of being built one question at a time in Canvas. This makes them easier to version, reuse, and review. You describe each quiz’s settings and questions in a text file, and Zaphod turns that into a Classic quiz with fully‑formed questions in Canvas.

Quizzes in Zaphod are defined as plain‑text quiz bank files in `quiz-banks/` that use a YAML‑style frontmatter plus NYIT Canvas Exam Converter–style question bodies. 

## Where quiz files live

- Quizzes are stored in a `quiz-banks/` directory inside the course repository, for example:  
  `example-course/quiz-banks/week1.quiz.txt`. 
- Each `.quiz.txt` file defines one quiz; the Canvas quiz title comes from the file’s frontmatter, not the filename. 

## Quiz file frontmatter

The quiz file starts with optional YAML‑style frontmatter between `---` lines that controls quiz‑level settings. 

**Supported fields:**

- `title`: Quiz title shown in Canvas; if omitted, Zaphod falls back to the filename stem. 
- `points_per_question`: Default `points_possible` applied to parsed questions unless overridden later. 
- `shuffle_answers`: Boolean flag controlling Canvas’s answer‑shuffling setting. 
- `published`: Whether the quiz is published after creation/update. 
- `topics`: List of topic codes used for reporting/analytics (metadata only in the current version, not pushed into Canvas yet). 
- `outcomes`: List of outcome codes reserved for future outcome alignment features (metadata only for now). 
- `group`: Future hook for mapping questions into Canvas Quiz Question Groups via the API (not used in current behavior). 

Example:

```text
---
title: Week 1 Check-In
points_per_question: 2
shuffle_answers: true
published: true
topics:
  - intro
  - policies
outcomes:
  - OUTCOME-1
group: week1-pool-a
---
```

## Question body format

After the frontmatter and a blank line, the rest of the file is the question body.  Questions follow the NYIT Canvas Exam Converter rules and are separated by at least one blank line. 

**General structure:**

- Each question starts with a numbered stem on its own line, like: `1. Question text`. 
- The lines that follow define answers or special markers, depending on question type. 
- A blank line ends the question; Zaphod parses question type from the answer syntax and creates the corresponding Classic quiz question in Canvas. 

### Multiple choice

- Use `a)` / `b)` / `c)` style labels, with `*` before the correct option’s label. 
- Only one option should be marked correct for a single‑answer multiple‑choice question. 

Example:

```text
1. Which of the following best describes the syllabus?
a) A list of course policies and expectations
*b) A detailed biography of the instructor
c) A collection of student grades
d) A chat log from the discussion board
```

### Multiple answers (select all that apply)

- Use checkbox syntax where `[ ]` marks an incorrect option and `[*]` marks a correct option. 
- Two or more options may be marked with `[*]`, and Canvas will treat it as a multiple‑answers question. 

Example:

```text
2. Which of the following are good places to find due dates?
[*] The Canvas calendar
[ ] Random internet forums
[*] The syllabus
[ ] A classmate’s memory
```

### True/False

- Represent as a two‑option multiple choice with `True` and `False`, marking the correct one with `*`. 
- Either of the following patterns works:  
  - `*a) True` / `b) False`  
  - `a) True` / `*b) False` 

Example:

```text
3. You can find due dates only in Canvas and nowhere else.
a) True
*b) False
```

### Short answer

- Use one or more lines starting with `*` to list acceptable answers. 
- Each `* answer` line is treated as a correct short‑answer variant. 

Example:

```text
4. What is the name of the course platform?
* Canvas
* canvas
```

### Essay

- Use `####` on its own line to indicate an essay‑type question. 
- The question stem still starts with `n. Question text`; `####` tells Zaphod to create an essay response field. 

Example:

```text
5. Briefly describe how you plan to manage your study time for this course.
####
```

### File upload

- Use `^^^^` on its own line to indicate a file‑upload question. 
- Canvas will prompt the student to upload a file as the response. 

Example:

```text
6. Upload a PDF of your signed syllabus acknowledgement.
^^^^
```

## From text to Canvas

- When you run the quiz sync step in Zaphod, it scans all `.quiz.txt` files in `quiz-banks/`, reads the frontmatter to configure quiz‑level settings, and parses each question block according to the patterns above. 
- The result is a Classic Canvas quiz whose title, settings, and questions mirror the text file; if you edit the quiz file later and rerun the sync, Zaphod updates the existing quiz to match. 