# Code Review Passes

Run each of these against the diff. Only report a finding if something is genuinely off — these are checks, not a quota.

## 1. Plan-adherence pass

Does the diff actually do what the "Implementation steps" said? Flag any deviation — not to forbid deviation (sometimes the implementer correctly discovered the plan was wrong mid-build), but so it's visible and intentional rather than silent drift. Check "Files and components affected" against what was actually touched: anything touched that wasn't listed, or listed but untouched, gets a note.

## 2. Correctness pass

Read the actual logic, not just whether it looks plausible. Trace through at least one non-trivial path by hand. Common misses: off-by-one errors, incorrect boundary conditions, wrong operator (`&&` vs `||`), state mutated when it should be copied, async code that doesn't actually await what it needs to, error paths that swallow or misreport the original error.

## 3. Acceptance-criteria pass

If a `## Requirements` section exists, check each acceptance criterion against the diff: is there code (and a test) that actually satisfies it? A criterion with no corresponding code or test is a Blocking finding, not a Note.

## 4. Test-quality pass

Tests existing isn't the same as tests being good. Check for: tests that only exercise the happy path when the plan or requirements implied edge cases; tests that assert on implementation details rather than behavior (brittle to refactors); tests that would pass even if the logic being tested were wrong (e.g. asserting `true === true`, mocking away the thing under test).

## 5. Readability pass

Would another engineer (or agent) picking this up cold understand it without the PR description? Flag: unclear naming, functions doing too many unrelated things, magic numbers/strings without explanation, control flow that's needlessly clever. Don't flag style choices a linter already enforces.

## 6. Duplication pass

Does this introduce logic that already exists elsewhere in the codebase under a different name? Check for near-duplicate functions, copy-pasted blocks with minor variations, or reinventing a utility the codebase already has.

## 7. Blast-radius pass

For changes to shared code (utilities, types, exported interfaces, shared config) — were all call sites checked, not just the ones the plan mentioned? A change to a shared function's behavior that the implementer didn't trace through every caller is a common source of regressions that the check gate won't always catch, especially if test coverage on the other call sites is thin.

## 8. Security-adjacent flag (not a full review)

This skill does not do security review, but if something jumps out during the passes above — unvalidated input reaching a query or shell command, a secret that looks hardcoded, an auth check that looks missing on a new endpoint — flag it explicitly as "needs security-reviewer" rather than either ignoring it or attempting to resolve it here.
