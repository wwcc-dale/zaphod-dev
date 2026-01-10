## Quizzes in Zaphod

Quizzes in Zaphod are written as plain‑text files instead of being built one question at a time in Canvas. This makes them easier to version, reuse, and review. You describe each quiz’s settings and questions in a text file, and Zaphod turns that into a Classic quiz with fully‑formed questions in Canvas.[1][2]

### Where quizzes live

Quizzes are usually kept in a `quiz-banks/` folder in your course:

```text
example-course/
  quiz-banks/
    week1.quiz.txt
    midterm.quiz.txt
```

- Each `.quiz.txt` file represents one quiz.
- The file name is mostly for your own organization; the title students see in Canvas comes from inside the file.[1]

You can think of `quiz-banks/` as the home for all your quiz definitions, separate from pages and assignments.

### Quiz file structure

Each quiz file has two main parts:

1. An optional YAML‑style header that describes quiz‑level settings.  
2. A body of questions written in a compact, line‑based format.

A simple example:

```text
---
title: Week 1 Check-In
points_per_question: 2
shuffle_answers: true
published: true
---

1. Which of the following best describes the syllabus?
A. A list of course policies and expectations
B. A detailed biography of the instructor
C. A collection of student grades
D. A chat log from the discussion board
ANSWER: A

2. True/False: You can find due dates only in Canvas and nowhere else.
A. True
B. False
ANSWER: B
```

- The header (`title`, `points_per_question`, etc.) controls the quiz settings in Canvas.  
- Each numbered block represents a question, followed by answer choices and a line marking the correct answer.[1]

Depending on your quiz format, you can represent multiple‑choice, multiple‑answer, true/false, short answer, essay, and file upload questions using simple text conventions.

### Editing and reusing quizzes

Because quizzes are plain text:

- You can quickly tweak questions, swap answer choices, or adjust correct answers by editing the file.  
- You can duplicate a quiz for a new term or section by copying the `.quiz.txt` file and adjusting the header or a few questions.  
- You can keep an entire quiz version history in Git, so you know exactly how it has changed over time.[2][1]

This is especially helpful for larger exams where clicking through the Canvas quiz editor would be slow and error‑prone.

### How quizzes get into Canvas

When you run the quiz sync step:

- Zaphod reads each `.quiz.txt` file in `quiz-banks/`.  
- It parses the header to configure the quiz (title, default points, shuffle settings, publish state, and so on).  
- It parses each question and creates matching question objects in Canvas with the correct type and answers.  

The result is a Classic quiz in Canvas that students can take like any other quiz. If you later update the `.quiz.txt` file, rerunning the sync will update the quiz so Canvas stays in sync with your text definition.