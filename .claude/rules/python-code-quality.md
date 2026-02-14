---
paths:
  - "deps/**/*.py"
  - "cogs/**/*.py"
---

# Code Conventions

- Always set the file imports at the top of the files, never inside functions.
- Break function in small cohesive small unit of work.
- Put all the test inside the `tests` folder
- Always unit tests using the `_unit_test.py` suffix.
- Unit test must always mock dependencies, never hit the database.
- After unit tests, create `_integration_test.py` which use the database.
