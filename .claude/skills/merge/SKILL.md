---
name: merge
description: Merges a PR into main, updates the Linear ticket to Done, and removes the local worktree and branch. Run manually after a PR is ready to merge — not part of the automated pipeline. Handles conflict detection: stops and reports rather than resolving conflicts automatically.
---

# Merge

Merges a PR, moves the Linear ticket to Done, and cleans up the local worktree created by the pipeline.

> Placeholders: `<ticket-id>` is the Linear ticket key (e.g. `BLA-7`), `<branch-name>` is the feature branch.

## Trigger

Activate when the user says "merge [ticket ID]", "merge the PR for [ticket ID]", "clean up [ticket ID]", or similar.

## Step 1: Resolve the ticket and PR

Fetch the Linear ticket via `Linear:get_issue` to get the ticket title, branch name (`gitBranchName`), and current status. Derive or confirm the PR using the branch name:

```bash
gh pr list --head <branch-name> --json number,title,state,mergeable,mergeStateStatus
```

If no open PR is found for the branch, stop and tell the user — don't guess.

If the PR's `state` is not `OPEN`, stop and report the current state (already merged, closed, etc.).

## Step 2: Check merge readiness

```bash
gh pr view <pr-number> --json mergeable,mergeStateStatus,reviewDecision,statusCheckRollup
```

Evaluate the response:

- **`mergeStateStatus` is `BLOCKED`** — stop and report what's blocking (required checks still running, dismissals needed, etc.).
- **`mergeable` is `CONFLICTING`** — stop and report which files conflict (see Step 3). Do not attempt to resolve them automatically.
- **All clear** — proceed to Step 4.

Note: `reviewDecision` may be empty in repos without required-review branch protection rules. Do not block on it — only block if it is explicitly `CHANGES_REQUESTED`.

## Step 3: Conflict report (if applicable)

If conflicts are detected in Step 2, fetch the branch and show the conflicting files:

```bash
git -C .claude/worktrees/<ticket-id> fetch origin main
git -C .claude/worktrees/<ticket-id> merge --no-commit --no-ff origin/main 2>&1 || true
git -C .claude/worktrees/<ticket-id> diff --name-only --diff-filter=U
git -C .claude/worktrees/<ticket-id> merge --abort
```

Report the conflicting file paths and stop. Tell the user to resolve conflicts in the worktree at `.claude/worktrees/<ticket-id>/`, push the resolution, and then re-run `/merge <ticket-id>`.

## Step 4: Merge the PR

```bash
gh pr merge <pr-number> --squash
```

Use `--squash` to keep the main branch history linear. Do not pass `--delete-branch` here — it will fail if the worktree is still checked out on that branch. The remote branch is deleted in Step 6 after the worktree is removed.

Confirm the merge completed:

```bash
gh pr view <pr-number> --json state,mergedAt
```

If the merge fails for any reason, stop and report the error — do not proceed to cleanup.

## Step 5: Update Linear

Move the ticket to **Done** via `Linear:save_issue` (`state: "Done"`). If that MCP call isn't available, report the ticket URL and tell the user to update it manually.

## Step 6: Remove the local worktree

```bash
git worktree remove .claude/worktrees/<ticket-id> --force
git branch -d <branch-name>
git push origin --delete <branch-name> 2>/dev/null || true
```

`--force` handles the case where the worktree has a detached HEAD after the squash merge. The local branch is safe to delete because the commits are now on main. The remote branch delete is a best-effort cleanup (it may already be gone if GitHub auto-deleted it).

Confirm to the user: PR merged, ticket moved to Done, worktree removed.

## What NOT to do

- Do not merge a PR if `reviewDecision` is `CHANGES_REQUESTED` — the reviewer explicitly rejected it.
- Do not attempt to resolve merge conflicts automatically — stop and hand off to the user.
- Do not delete the worktree if the merge failed — the branch and worktree must stay intact so the user can recover.
- Do not push directly to main or skip the PR — the merge always goes through GitHub's PR merge, never `git push origin main`.
- Do not remove the worktree before confirming the PR merge completed successfully.
