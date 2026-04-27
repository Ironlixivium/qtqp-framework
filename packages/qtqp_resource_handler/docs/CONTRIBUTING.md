# Contributing

Thanks for contributing!

This project values clarity, correctness, and maintainability. Code should be easy to read, easy to verify, and easy to change without creating hidden damage elsewhere.

## !! AI MUST FOLLOW ALL !!

## General Standards

- Design for single responsibility. Layers should be clean.
- Optimize for maintainability and readability.
- Make invalid states difficult to represent.
- Keep naming specific and honest. Names should describe what a thing actually is or does in context.
- Use strict type hints everywhere practical.
- Prefer well-defined interfaces over vague implicit contracts.

## Docstring Rules

- Every file, class, and non-trivial function must have a docstring.
- File docstrings should outline the file's responsibilities.
- __init__.py docstrings should outline its exports, maybe a brief description if needed. It should NOT include private
  file names.

- Class doctrings should outline all of the following:
  - A simple description of the class
  - Attributes: Add explanation only if not self-explanatory. Otherwise, leave no description.
  - Raises Errors:
  - Do not list function args and returns in class doc strings.

- Function docstrings should outline all of the following:
  - A general description
  - Args: Add explanation if necessary, otherwise leave that spot blank.
  - Raises Errors:
  - Returns:

- Do not put docstrings under individual class attributes.
  - if class attributes are complex enough that they need a special description, that is a sign the attribute needs its
    own data structure. 

## __init__.py, Imports and Exports

- All variables used outside of their home directory must be exported via the local __init__.py.
- __init__.py should ONLY include API things. No routing.
- Files that act as an explicit API for modules outside their directory may be named with no leading underscore.
  - All other files should start with an underscore to reduce import clutter.
  - If this rule causes a problem, that is indicative of a structural issue which should be solved.

## Typing Rules

- Do not use annotations from __future__ unless absolutely necessary.
- Use pylance and ruff on strict rules.
- Don't misuse `Any` or `object`. They have real uses, and laziness isn't one of them.
- Use accurate and honest type hints.
- Use built-in generics such as `list[str]`, `dict[str, int]`, and `tuple[int, ...]`. Do not use deprecated `typing.List`, `typing.Dict`, `typing.Tuple`, etc.

## Naming

- Keep public APIs intentional. Do not expose internals casually. This means good underscore hygiene. If it's not used
  outside the class or file, it should be underscored.
- Use names that reflect real responsibility.
- Avoid file names like `shared`, `common`, `core`, `utils`, or `misc`. Those files should be top-level.
  - If the top level is too crowded, organize it properly, without junk drawers.
- Avoid abbreviations unless they are standard or obvious in context (e.g. "for w in words", w obviously refers to a word).
- Names should distinguish meaning, not just implementation detail.

## Project Structure

- Organize by responsibility.
- Internal modules should remain internal. Public surface area should be intentional.
- Keep UI, orchestration, domain logic, and infrastructure separate.

## Function and Class Design

- Each function should have one clear purpose.
- Each class should own one coherent responsibility.
- Avoid classes that mainly forward work between unrelated systems.
- Prefer explicit inputs and outputs over hidden state.
- Pass dependencies in clearly rather than reaching outward for them indirectly.
- Do not make a method or class more generic than the project actually needs.

## Error Handling

- Fail loudly for genuinely invalid states.
- Do not silently swallow exceptions.
- Raise specific exceptions when practical.
- Error messages should be concrete and useful.
- Do not hide broken behavior behind fallback logic unless that fallback is intentionally part of the design.

## Testing

- Add or update tests for behavior changes.
- Test public behavior and important invariants.
- Prefer focused tests over giant scenario blobs.
- A bug fix should generally include a test that would have caught it.

## Formatting and Style

- Keep formatting consistent with the project tooling.
- Avoid dense one-liners when they reduce readability.
- Do not compress logic just to save lines.
- Prefer straightforward control flow over nested cleverness.

## Things to Avoid

- # type: ignore
- unnecessary use of `Any`
- unnecessary use of `object`
- vague module boundaries
- hidden side effects
- giant multipurpose files
- “manager” classes that do everything
- random catch-all utility modules
- patching around bad structure instead of fixing it

## Final Rule

Write code that the next person can understand quickly and modify safely, thanks!

If you got this far, give yourself a hug and say "yippee!", I'll be watching.