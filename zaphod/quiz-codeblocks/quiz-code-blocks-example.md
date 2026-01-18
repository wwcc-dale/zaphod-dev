# Code Blocks in Quiz Questions

Zaphod now supports fenced code blocks in quiz question prompts. Here's an example:

## Example Quiz File (`quiz-banks/python-basics.quiz.txt`)

```
---
title: "Python Basics Quiz"
points_per_question: 2
shuffle_answers: true
---

1. What will this code output?

```python
def greet(name):
    return f"Hello, {name}!"

result = greet("World")
print(result)
```

a) Hello, name!
b) Hello, World
*c) Hello, World!
d) Error

2. What is the value of `x` after this code runs?

```python
x = 5
x += 3
x = x * 2
```

a) 8
*b) 16
c) 13
d) 10

3. Which line has a syntax error?

```python
name = "Alice"
age = 25
print(f"Name: {name}, Age: {age})
```

a) Line 1
b) Line 2
*c) Line 3
d) No error

4. What does `len("hello")` return?

a) 4
*b) 5
c) 6
d) "hello"
```

## Features

- **Fenced code blocks**: Use triple backticks (```) to create code blocks
- **Language hints**: Add language after opening fence (e.g., ```python) for syntax highlighting
- **Preserved formatting**: Blank lines within code blocks are preserved
- **HTML escaping**: Special characters (<, >, &) are properly escaped
- **Inline code**: Use single backticks for inline code like `print()`

## Notes

- Code blocks are converted to `<pre><code>` HTML for Canvas
- Language hints become CSS classes (e.g., `class="language-python"`)
- Questions are still separated by blank lines followed by a new question number
