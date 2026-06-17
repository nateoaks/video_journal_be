---
name: dependency-upgrade
description: Scans dependencies for routine staleness and known CVEs, then opens PRs to update them — patch and minor bumps proceed autonomously (check gate must pass, no human approval needed before pushing), major bumps require human sign-off, except CVE patches which proceed regardless of bump size given the security urgency (with the breaking-change risk surfaced explicitly). Routine bumps batch into one Linear/Jira ticket; each CVE gets its own ticket. Use whenever the user says "check for dependency updates", "any CVEs in our deps", "update our packages", or on a recurring/scheduled basis if the orchestrator supports it. This is the one skill in this team designed to run with LESS oversight than the others by default — the autonomy line is the core design decision here, not a review checklist.
---

# Dependency Upgrade

Keeps dependencies current and patches known vulnerabilities — the one skill in this team built to run with less oversight than the others, because most dependency bumps genuinely are routine and gating every patch-version bump behind a human approval just trains people to rubber-stamp without reading. The autonomy line below is the actual point of this skill; read it carefully before changing it.

## The autonomy line

| Bump type | Routine staleness | CVE patch |
|---|---|---|
| Patch (`x.y.Z`) | Auto-PR, no human approval before push | Auto-PR, no human approval before push |
| Minor (`x.Y.z`) | Auto-PR, no human approval before push | Auto-PR, no human approval before push |
| Major (`X.y.z`) | **Human sign-off required before push** | Auto-PR, no human approval before push — but the PR description must surface that this is a major bump and name the specific breaking-change risk |

"Auto-PR, no human approval before push" still requires the check gate to pass first — autonomy applies to the human-approval checkpoint, not to the check gate. A failing check gate always stops the skill, regardless of category.

The CVE exception exists because the cost of staying on a known-vulnerable version is usually higher than the cost of a breaking change, but that judgment isn't this skill's to make silently — it surfaces the tradeoff in the PR and ticket rather than deciding it's fine and saying nothing.

## Trigger

Activate when the user says "check for dependency updates," "any CVEs in our deps," "update our packages," or on a recurring/scheduled basis if an orchestrator invokes this skill on a schedule.

## Step 1: Scan

Identify the package manager(s) in use (npm/yarn/pnpm, pip/poetry, cargo, go modules, etc. — check for lockfiles and manifests). Run the ecosystem's audit/outdated tooling:

- Staleness: `npm outdated` / `pip list --outdated` / `cargo outdated` / `go list -u -m all` or equivalent.
- CVEs: `npm audit` / `pip-audit` / `cargo audit` / `govulncheck` or equivalent. If the repo has a `.github/dependabot.yml` or similar already configured, check whether it's already covering this — don't duplicate work a tool is already doing, but still report what it found if relevant to this run.

Classify each available update by bump type (patch/minor/major, per semver or the ecosystem's equivalent) and whether it's CVE-driven (associated with an advisory) or routine staleness.

## Step 2: Decide what to act on

For CVEs: check severity from the advisory (critical/high/medium/low). Act on all of them per the autonomy line above regardless of bump size, but note severity in the ticket/PR so the human can prioritize review order even though no approval gate blocks the push.

For routine staleness: don't update everything just because a newer version exists. Skip:
- Versions explicitly pinned with a comment explaining why (don't silently override a documented pin).
- Pre-release/beta versions as the update target unless the current version is already pre-release.
- Updates to a package that's about to be replaced/removed per any open ticket or architecture doc referencing it (check briefly; don't deep-search for this).

If genuinely unsure whether a routine update is safe to batch (e.g. the changelog between versions is unreadable or missing), include it in the human-facing major-bump path instead of guessing it's fine.

## Step 3: Apply patch/minor bumps (routine and CVE)

For each patch/minor bump being applied:
1. Update the manifest and lockfile.
2. Run the project's full check gate (same command convention as `linear-implementation-build` — check README/CLAUDE.md/Makefile/package scripts for the documented command).
3. If the check gate fails for a specific bump, drop that one from the batch and report it separately rather than blocking the rest — a single problematic dependency shouldn't hold up everything else that's safe.

Batch all routine patch/minor bumps that passed the check gate into a single commit/PR. Each CVE patch (regardless of bump size, per the autonomy line) gets its own commit/PR, separate from the routine batch and from each other.

## Step 4: Apply major bumps

**Routine major bumps**: do not push. Present the proposed update, the changelog/migration notes between versions, and what (if anything) in the codebase the migration notes suggest needs changing. Ask the user directly: proceed, skip, or handle manually. Only push after explicit yes.

**CVE major bumps**: proceed per the autonomy line, but the PR description and ticket must state plainly: this is a major version bump being auto-applied due to a CVE, the breaking-change risk per the migration notes, and that a human should review promptly even though it wasn't gated on pre-push approval. Run the check gate same as any other bump — if it fails, do not push; report it as a major bump now requiring manual attention given both the break and the unresolved CVE.

## Step 5: Open PRs

For each PR (routine batch, or individual CVE patch):

```bash
gh pr create \
  --title "<chore: routine dependency updates | fix: patch CVE-XXXX-XXXXX in <package>>" \
  --body "## Summary
<what changed and why>

## Updates
<package> <old version> -> <new version> [routine | CVE-XXXX-XXXXX, severity: <level>]
...

## Check gate
Passed.

<For CVE major bumps only:> ## ⚠️ Breaking change risk
<the specific risk, from migration notes>" \
  --base main
```

## Step 6: Tracker

- **Routine batch**: one ticket (Linear or Jira, same disambiguation convention as other skills) titled something like "Dependency updates — <date>," listing every package bumped, linked to the PR. Status: whatever the team's "needs review" or equivalent is — these still merit a look even though they weren't gated on pre-push approval.
- **CVE patches**: one ticket per CVE, titled with the CVE ID and package, severity noted, linked to its PR. If the project already tracks security issues with a specific label/type, use it.

## What NOT to do

- Do not skip the check gate for any bump, including CVE patches — security urgency doesn't override "does it actually still work."
- Do not silently override an explicitly pinned/commented version without flagging it to the user.
- Do not bundle a routine major bump into the same PR as patch/minor bumps — it needs its own approval path and shouldn't be blocked behind, or block, the routine batch.
- Do not understate a CVE major bump's breaking-change risk to make the auto-push feel safer — the whole point of the exception is that the tradeoff is surfaced, not hidden.
- Do not assume a passing check gate means a major bump's behavioral changes are fully covered — check gates catch what they catch; say so rather than implying full confidence.
