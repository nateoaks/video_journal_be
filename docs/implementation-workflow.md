# Implementation workflow

> Placeholders: `<TEAM>` is the issue-tracker key for the project (e.g. the
> Linear/Jira team prefix); `<id>` is the ticket number; `<slug>` is a short
> kebab-case description. This workflow is language- and framework-agnostic —
> wherever a concrete tool command appears it's an example; substitute the
> equivalent for the repo at hand.

## Trigger
When told to "implement [ticket ID]" or "build [ticket ID]":

## Steps

### 1. Fetch the ticket
- Read the ticket from Linear using the Linear MCP
- Find the "## Implementation Plan" section in the description
- If no plan section exists, stop and tell the user — the planning step hasn't run yet

### 2. Implement
Follow the plan step by step:
- Create branch using the ticket type as the prefix:
  - Feature: `feat/<TEAM>-<id>-<slug>`
  - Bug fix: `fix/<TEAM>-<id>-<slug>`
  - Maintenance/chore: `chore/<TEAM>-<id>-<slug>`
- Create/edit files according to the plan
- Write tests for new logic
- Update any relevant docs or types
- Run the project's check command before committing — fix any failures.
  Use whatever the repo defines as its full pre-commit gate (lint +
  typecheck/compile + tests), e.g. `bun check`, `npm run check`, `make check`,
  `task check`, `cargo test && cargo clippy`, `go test ./... && go vet ./...`,
  `poe check`, `tox`, etc. If the repo documents this command (README,
  CLAUDE.md, Makefile, package scripts), use that.

### 3. Commit and push
- Stage all changes
- Commit: `<type>(<TEAM>-<id>): <ticket title>` — where `<type>` matches the branch prefix (`feat`, `fix`, or `chore`)
- Push branch

### 4. Create the PR
Use the `gh` CLI:
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

### 6. Update Linear
Set Linear ticket to In Review

<!-- ### 5. Ping Slack
Post to #eng-reviews:
```bash
curl -X POST $SLACK_WEBHOOK_URL \
  -H 'Content-type: application/json' \
  --data '{"text":"PR ready for review: <PR URL> | <Linear ticket URL>"}'
```
The `SLACK_WEBHOOK_URL` env var must be set in your shell or .env.local (gitignored). -->


## What NOT to do
- Do not skip tests even if the plan doesn't mention them
- Do not push directly to main
- Do not create the PR until tests pass