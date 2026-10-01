# Backend Code Style

Sources: [PEP 8: Style Guide for Python Code](https://peps.python.org/pep-0008/) and [PEP 257: Docstring Conventions](https://peps.python.org/pep-0257/). I used these Python community guides for this project's conventions.

## Names and formatting

- Use UTF-8 and four spaces for indentation, without tabs.
- Use `snake_case` for modules, functions, and variables; `PascalCase` for classes; and `UPPER_SNAKE_CASE` for constants.
- Put imports near the top and group standard library, third-party, and local imports. Import the PostgreSQL driver only in PostgreSQL mode.
- Keep functions focused and split long expressions into readable lines.
- Add short docstrings to public modules, classes, and functions whose behavior is not obvious. Comments should explain why code exists rather than repeat what it says.

## Backend rules

- Keep HTTP handling, expression parsing, and database access in separate modules. Do not put calculator logic or SQL in routes.
- Validate JSON input, expression length and characters, and history IDs. Use clear HTTP status codes and a consistent JSON error shape.
- Do not use `eval`, `exec`, or another way to run a user's expression as program code.
- Bind SQL parameters. Save each successful calculation before returning its result, and close database connections promptly.
- Use timezone-aware ISO 8601 timestamps. Do not hard-code a developer's local filesystem path.
- Do not expose stack traces or local paths in API errors. Log internal failures so they can be diagnosed.

## Before submission

- Test precedence, parentheses, unary signs, decimals, invalid input, division by zero, and saved history.
- Run the test command in `README.md` and check the frontend and backend together.
