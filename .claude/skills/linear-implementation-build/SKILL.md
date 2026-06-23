---
name: linear-implementation-build
description: Implements a Linear ticket's approved implementation plan end to end — creates a branch, writes the code and tests following the plan, runs the project's check/lint/test gate, runs the review chain, then commits, pushes, and opens a PR automatically once all review findings are resolved. No diff approval gate. Use this skill whenever the user says "implement TICKET-ID", "build TICKET-ID", "ship TICKET-ID", or otherwise asks to turn an already-planned Linear ticket into actual code and a PR — even if they don't use the exact word "implement." Always use this skill for this workflow rather than improvising branch names, commit formats, or PR structure ad hoc, since it encodes the required conventions.
---

# Linear Implementation Build

Takes a Linear ticket that already has an approved `## Implementation Plan` and turns it into a branch, code, tests, a passing check gate, and an automatically pushed PR.

> Placeholders used throughout: `<TEAM>` is the issue-tracker key for the project (e.g. the Linear team prefix); `<id>` is the ticket number; `<slug>` is a short kebab-case description of the ticket. This workflow is language- and framework-agnostic — concrete tool commands shown are examples; substitute the equivalent for the repo at hand.

## Trigger

Activate when the user says "implement [ticket ID]," "build [ticket ID]," "ship [ticket ID]," or similarly asks to turn a planned Linear ticket into code.

## Step 1: Fetch the ticket and plan

Fetch the ticket via `Linear:get_issue`. If that tool isn't available in the current connector, fall back to `Linear:list_issues` with `query: "<ticket ID>"`. Find the `## Implementation Plan` section in the description.

The `list_issues` fallback truncates long descriptions and may point to a `get_issue` tool that, if you're using this fallback, is unavailable by definition. If the description (and therefore the plan section) looks cut off and `get_issue` truly isn't reachable, tell the user and ask for the full text rather than building against a partial plan.

If no plan section exists, stop and tell the user the planning step hasn't run yet — don't improvise a plan here. (Point them to the planning skill if one is available.)

## Step 2: Implement the plan

Follow the plan step by step:

- Create a branch using the ticket type as the prefix:
  - Feature: `feat/<TEAM>-<id>-<slug>`
  - Bug fix: `fix/<TEAM>-<id>-<slug>`
  - Maintenance/chore: `chore/<TEAM>-<id>-<slug>`
  - Determine type from the ticket's labels and title/description. If it's genuinely ambiguous (no clear label, title doesn't indicate bug vs. feature vs. chore), ask the user which prefix to use rather than guessing.
- Create/edit files according to the plan's "Files and components affected" and "Implementation steps" sections.
- Write tests per the plan's "Tests to write" section.
- Update any relevant docs or types touched by the change.
- Run the project's full check command before considering the work done — fix any failures. Use whatever the repo defines as its complete pre-commit gate (lint + typecheck/compile + tests), e.g. `bun check`, `npm run check`, `make check`, `task check`, `cargo test && cargo clippy`, `go test ./... && go vet ./...`, `poe check`, `tox`. If the repo documents this command (README, CLAUDE.md, Makefile, package scripts), use that one specifically rather than guessing.

**If the check gate still fails after reasonable troubleshooting** (a handful of focused attempts at the actual root cause, not dozens of blind retries), stop and report to the user rather than continuing indefinitely or committing anyway. Show what's failing, what was tried, and your best read on the underlying cause. Do not proceed to the diff-review checkpoint with a known-failing check gate.

## Step 2.5: Automated review before the human sees it

**If you are running as the `implementer` agent** (see `.claude/agents/implementer.md`): stop after the check gate passes in Step 2. Do not perform this step yourself — the dispatching session (the orchestrator, or the user directly) calls `test-runner`, `code-reviewer`, `security-reviewer`, and `performance-reviewer` as separate agent dispatches and brings findings back to you to fix. This split exists because an agent invoked via Claude Code's Task/Agent tool cannot reliably spawn further nested subagents in the current design, so the calling-out has to happen one level up. Skip directly to this step's resolution rules below only once you've received findings back.

**If you are running this skill directly** (no agent layer — invoked via `/build` in a plain Claude Code session, or in claude.ai): perform this step yourself as originally designed. Once the check gate passes, run `test-runner-qa` against the diff for structured failure/coverage reporting (the check gate's pass/fail alone doesn't tell you whether acceptance criteria are actually covered), run `code-reviewer` against the diff, run `security-reviewer` if the diff touches any of: new endpoints/handlers, auth logic, user or external input, secrets/credentials, file or network I/O, or dependency changes, and run `performance-reviewer` if the diff touches any of: database/ORM queries, loops over collections, caching logic, or documented hot-path code (security-reviewer and performance-reviewer will each confirm whether they apply).

Resolve findings before proceeding:
- All **Blocking** (code-reviewer), **Critical**/**High** (security-reviewer), **Critical** (performance-reviewer), and failures/acceptance-criteria coverage gaps (test-runner-qa) must be fixed — re-edit and re-run the check gate after each fix.
- Use judgment on **Should fix** / **Medium** / non-criteria coverage gaps; if deferring one, say so explicitly when presenting the diff in Step 2's checkpoint rather than silently dropping it.
- **Note** findings can be mentioned in the PR description or skipped.

If a finding reveals the ticket actually needed a system-level decision (missing architecture doc, the diff conflicts with one that exists, or a performance finding traces back to an architectural scaling limit rather than something fixable in this diff), stop and tell the user rather than resolving it yourself — point to `architect`.

## Step 3: Commit

Once review findings are resolved:

- Stage all changes.
- Commit with: `<type>(<TEAM>-<id>): <ticket title>` — where `<type>` matches the branch prefix (`feat`, `fix`, or `chore`).

## Step 4: Push and create the PR

Once committed, push the branch and open the PR immediately — no separate go-ahead required.

1. Push the branch.
2. Create the PR with the `gh` CLI. Pull `<2-3 sentence summary from the plan>` from the plan's "Goal" (and "Approach" if needed for context), and `<bullet list of files changed and why>` from the plan's "Files and components affected" section — adjusted to reflect what was actually changed, since the implementation may have diverged slightly from the original plan:

```bash
gh pr create \
  --title "[<TEAM>-<id>] <ticket title>" \
  --body "Closes <TEAM>-<id>

## Summary
<2-3 sentence summary from the plan>

## Linear ticket
<linear ticket URL>

## Changes
<bullet list of files changed and why>" \
  --base main
```

## Step 4.5: Documentation

Run `documentation` against the diff now on the PR's branch. It will check the README and inline docs/docstrings for anything now stale, missing, or referencing removed code, and — if it finds something worth updating — apply the edits and push them as an additional commit to the same branch (it amends the existing PR, it does not open a new one).

If it finds nothing to update, it will say so; proceed without delay.

## Step 5: Update Linear

Set the Linear ticket's status to **In Review** via `Linear:save_issue` (`state: "In Review"`). Confirm to the user with both the PR URL and the ticket URL.

## What NOT to do

- Do not skip tests even if the plan doesn't mention them explicitly — the plan's test section is a minimum, not a ceiling.
- Do not proceed to the human diff checkpoint with unresolved Blocking (code-reviewer), Critical/High (security-reviewer), Critical (performance-reviewer), or failure/acceptance-criteria-coverage findings (test-runner-qa) — the check gate passing is not a substitute for these reviews.
- Do not push directly to main.
- Do not create the PR until the check gate passes.
- Do not add any human approval checkpoint between passing reviews and committing — once reviews are resolved the commit, push, and PR happen automatically.
- Do not silently improvise an implementation plan if one isn't on the ticket — stop and say so instead.
