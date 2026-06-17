---
name: documentation
description: Keeps README files and inline code comments/docstrings in sync with a code change — updating what's now stale, adding documentation for new public functions/classes/modules/endpoints, and removing documentation for anything deleted. Use whenever the user says "update the docs", "document this", "are the docs stale", or whenever linear-implementation-build has created a PR and the diff touches anything documented or any public-facing code without doc coverage. This is README and inline-doc scope only — it explicitly does NOT maintain a CHANGELOG (that's owned by release-prep) and does NOT write external user-facing help-center content.
---

# Documentation

Keeps the README and inline code documentation (docstrings, doc comments, type/interface documentation) honest about what the code actually does right now — added to the same PR as the code change, so docs and code never ship out of sync with each other.

## Scope boundary

This skill owns: README files (and any doc files that live alongside code in the repo, e.g. a `docs/` directory describing internals or usage), and inline documentation (docstrings, JSDoc/TSDoc, doc comments, README-equivalent module headers). It does not own:

- **CHANGELOG** — deliberately out of scope. A changelog describes what shipped in a release, which is `release-prep`'s job, not a "does the documentation match the code" concern. If a change seems changelog-worthy, note that for the user — `release-prep` will pick it up from merged PRs when a release is cut, it doesn't need this skill to maintain anything in the meantime.
- **External user-facing docs** (help center, marketing site, API reference portals) — out of scope. These usually have their own review/publish process and shouldn't be touched as a side effect of a code PR.
- **Whether the code itself is correct or well-structured** — that's `code-reviewer`. This skill assumes the code is right and makes the docs match it; it doesn't second-guess the implementation.

## Trigger

Activate when the user says "update the docs," "document this," "are the docs stale," or when `linear-implementation-build` has just created a PR (Step 4) for a diff that touches anything currently documented, or adds public-facing code (exported functions, classes, modules, API endpoints, CLI commands) with no doc coverage yet.

## Step 1: Gather the diff and existing docs

Get the diff (uncommitted, the just-created PR's branch vs. base, or a specific commit/branch if invoked standalone). Identify the repo's README(s) and any `docs/` directory or equivalent.

Get the implementation plan and requirements if available — the "Goal" and "Problem statement" are usually better source material for human-readable doc prose than the diff alone, since they explain *why*, which the code by itself doesn't.

## Step 2: Find what's now stale or missing

Check, in order:

- **Changed public behavior** — any function/class/module/endpoint whose existing docstring or README mention no longer matches what it does (changed parameters, return shape, side effects, error behavior).
- **New public surface with no docs** — new exported functions, classes, modules, CLI commands, or API endpoints that have no docstring/doc comment at all, or a README with no mention of a new capability a user would need to discover.
- **Removed surface still documented** — anything deleted or renamed in the diff that's still referenced in the README or another file's docs.
- **Config/setup changes** — new environment variables, config keys, dependencies, or setup steps a README's "Getting started"/"Setup" section should mention.

Don't flag internal/private implementation details with no docstring as a gap — match the doc-coverage bar to what the codebase already does for similar internal code, not an external ideal. If the codebase doesn't docstring private helpers, don't start requiring it unilaterally here.

## Step 3: Draft updates

For inline docs: match the existing docstring style and convention already used in that file/codebase (don't introduce a new doc format). Keep them accurate and concise — describe behavior, parameters, return values, and any non-obvious side effects or error conditions; skip restating what's obvious from a well-named signature.

For README/docs files: integrate into the existing structure rather than appending a disconnected new section at the bottom. If the new capability genuinely doesn't fit any existing section, it's fine to add one — but check first.

## Step 4: Present and apply

Show the user a summary of what's being added/changed/removed and why, then apply the edits directly to the same branch/diff (not a separate PR) so docs and code land together.

If invoked from inside `linear-implementation-build`'s flow (i.e., the PR already exists): apply the doc edits, then amend the existing PR (push an additional commit to the same branch) rather than opening a second PR. Mention in the PR description's "Changes" section, if not already covered, that docs were updated.

If invoked standalone with no PR yet: just apply the edits and let the user decide when to commit/push, consistent with how the other reviewer skills hand control back rather than committing on their own.

## What NOT to do

- Do not create or update a CHANGELOG entry — flag that the change may be changelog-worthy if relevant, and stop there.
- Do not touch external help-center or marketing content.
- Do not invent documentation for behavior that doesn't exist, or pad docstrings with restated-signature filler just to show coverage.
- Do not open a second PR for doc changes when invoked from the build flow — amend the existing one.
- Do not silently change documented behavior to match what you think the code *should* do instead of what it *actually* does — if the code and its existing docs disagree because the code is wrong, flag that as a code issue (point to `code-reviewer`), don't paper over it by rewriting the docs to match a bug.
