---
name: test-runner-qa
description: Runs a project's test suite and produces a structured report — pass/fail counts, failure detail with root-cause read, and a coverage check of new/changed code against the ticket's stated acceptance criteria — flagging any acceptance criterion or non-trivial code path with no corresponding test. Use whenever the user says "run the tests", "what's failing", "are we covered", "QA this", or whenever linear-implementation-build needs test reporting beyond a bare pass/fail from its check gate. This is execution and reporting only — it explicitly does NOT decide if the code itself is correct (use code-reviewer for that) and does NOT investigate flaky/nondeterministic tests (a dedicated flaky-test skill, if one exists).
---

# Test Runner / QA

Runs the test suite and turns the result into a structured, actionable report — the layer between "the check gate passed or failed" and actually knowing what's covered, what's not, and why something failed. The build skill's check gate is a binary pass/fail trigger; this skill is what explains the result and checks whether passing tests actually means the work is covered.

## Scope boundary

This skill owns: executing tests, reporting failures with enough detail to act on, and checking that new/changed code and stated acceptance criteria have corresponding test coverage. It does not own:
- **Whether the test logic itself is good** (asserting the right things, not testing implementation details) — that's `code-reviewer`'s test-quality pass. This skill checks *that* coverage exists, not whether existing tests are well-written.
- **Flaky/nondeterministic test investigation** — out of scope per current design; note it if observed, don't chase it down.
- **Fixing failures** — report them; the implementer or build skill fixes and re-runs.

## Trigger

Activate when the user says "run the tests," "what's failing," "are we covered," "QA this," or when `linear-implementation-build` needs test reporting at its check-gate or Step 2.5 stage.

## Step 1: Find the right test command and scope

Don't guess a generic `npm test` if the repo defines something more specific. Check, in order: README, CLAUDE.md, Makefile, package.json scripts, or other project config for the documented test command. Use that one specifically.

Determine scope:
- If invoked on a specific diff/branch (standalone, or from the build skill), identify which files changed (`git diff --name-only` against the relevant base) — this scopes the coverage check in Step 3.
- If invoked generally ("run the tests"), run the full suite.

## Step 2: Run and capture structured results

Run the test command. Capture, not just pass/fail: which specific tests failed, the assertion or error for each, and which test files/suites didn't run at all (skipped, or excluded by config) versus ran and passed.

If a failure looks environmental rather than code-related (missing dependency, service not running, stale cache) rather than a real test failure, say so distinctly — don't report it as a failing test if it's actually a setup problem, but don't silently fix the environment either; surface it.

## Step 3: Check coverage against what should be tested

This is the part a bare pass/fail misses. Two checks, not one:

**Against acceptance criteria** — if a `## Requirements` section exists for the ticket, walk each acceptance criterion and check whether a test actually exercises it. A criterion with no corresponding test is a finding, regardless of whether the existing suite passes.

**Against changed code** — for files identified in Step 1's scoping, look at non-trivial new logic (branches, error handling, edge cases) and check whether tests touch each path. Use the project's coverage tool if one is configured and easy to run (e.g. `--coverage` flags, `nyc`, `coverage.py`) for a quantitative read; fall back to manual inspection of test files against source if no coverage tooling exists. Flag specific untested paths, not just a percentage — "the error branch in `parseInput` at line 42 has no test" is actionable, "62% coverage" is not.

Don't flag trivial code (getters, simple pass-throughs, generated code) as needing tests just to hit a number.

## Step 4: Report

Structure the report as:

```markdown
## Test results
[count] passed, [count] failed, [count] skipped

### Failures
- `path/to/test.spec.ts` — [test name]: [error/assertion, and your read on the root cause if apparent]

### Coverage gaps
- Acceptance criteria with no test: [list, or omit section if none]
- Untested non-trivial paths in changed code: [file:line — what's untested, why it matters]
```

Omit any subsection with nothing to report — don't write "none found."

If invoked standalone, stop here.

If invoked from inside `linear-implementation-build`: failures and acceptance-criteria coverage gaps should be treated like Blocking findings — must be addressed (write the missing test, fix the failure, re-run) before the human diff-approval checkpoint. Untested-but-non-criteria code paths are a judgment call for the implementer, same tier as code-reviewer's "Should fix."

## What NOT to do

- Do not report a passing suite as sufficient if acceptance criteria lack corresponding tests — passing is necessary, not sufficient.
- Do not attempt to diagnose or fix flaky tests by re-running until green; report a test that seems nondeterministic as a flag, not a pass.
- Do not write or fix tests yourself when invoked from the build flow — report the gap and let the implementer add coverage, so there's a clear record of what changed and why.
- Do not treat coverage percentage alone as a meaningful finding — always point to the specific untested path or criterion.
