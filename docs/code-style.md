# Code Style

Formatting and linting are enforced by **ruff**; types by **mypy --strict**. Do not fix by
hand what the tools fix automatically — run them.

```bash
uv run ruff format src tests      # format (line length 88)
uv run ruff check --fix src tests # lint + autofix (import order, etc.)
uv run mypy src                   # strict type check
```

`uv run poe check` runs the whole gate (format → lint → typecheck → test).

## Type annotations

- **Every** function and method is fully annotated — parameters and return type. mypy strict
  rejects untyped definitions.
- Use built-in generics and the union operator: `list[str]`, `dict[str, int]`, `str | None`.
  Never import `List`, `Dict`, or `Optional` from `typing`.
- Avoid `Any`. Reach for `object` + narrowing, a `Protocol`, or a `TypeVar` instead. If `Any`
  is truly unavoidable, isolate it behind a typed boundary.
- Annotate collections at the abstract level where it fits the contract: accept
  `Sequence[T]` / `Iterable[T]`, return concrete `list[T]`.

## Imports

- Let ruff's isort (`I`) order imports: stdlib, third-party, first-party (`app`), each group
  separated by a blank line. Don't hand-order.
- Absolute imports only (`from app.domains.items.service import ItemService`). No relative
  imports across packages.
- Never `from module import *`.

## General conventions

- `snake_case` for functions, variables, and modules; `PascalCase` for classes; `UPPER_CASE`
  for module-level constants.
- Prefer `pathlib.Path` over `os.path` for filesystem work.
- For subprocesses use `subprocess.run([...], check=True)` with an argument list — never
  `shell=True` with interpolated input and never `os.system`.
- f-strings for interpolation; no `%` or `.format()`.
- Don't read `os.environ` outside `app/core/config.py` (see `docs/configuration.md`).
- Don't `print()` — use the logger (see `docs/logging.md`).

## Security linting

Ruff runs the bandit (`S`) ruleset as part of `ruff check`, so common security smells (shell
injection, hardcoded temp paths, unsafe deserialization) fail the lint. `assert` is allowed in
`tests/` but not in application code — use real validation and raised exceptions instead.

## Docstrings and comments

- Public modules, classes, and non-trivial functions get a short docstring describing intent,
  not a restatement of the signature.
- Comments explain **why**, not **what**. Delete commented-out code rather than committing it.
