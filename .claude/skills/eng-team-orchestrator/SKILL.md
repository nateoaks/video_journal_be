---
name: eng-team-orchestrator
description: Runs a Linear or Jira ticket through the full autonomous engineering pipeline end to end — requirements-analyst, architect (if needed), linear-implementation-plan, linear-implementation-build (which itself runs test-runner-qa, code-reviewer, security-reviewer, performance-reviewer, and documentation), stopping only at the approval checkpoints already built into those skills, not between stages. Use whenever the user says "run TICKET-ID through the pipeline", "take TICKET-ID end to end", "do the full flow for TICKET-ID", or asks to fully automate a ticket from requirements to PR. Does NOT invoke dependency-upgrade or release-prep — those are separate, independently-triggered entry points, not part of a single ticket's pipeline.
---

# Engineering Team Orchestrator

Chains the team's skills into one continuous run for a single ticket — requirements through PR — stopping only where a skill already has a human checkpoint built in, not between every stage. This skill doesn't introduce new judgment; it sequences the judgment already encoded in each stage and carries the right context forward between them.

## What this does and doesn't run

**In scope, in this order:**
1. `requirements-analyst` (skip if the ticket already has a `## Requirements` section — see Step 1)
2. `architect` (skip if there's no project/epic-level decision to make — see Step 2's judgment call, exercised by the architect skill itself, not guessed here)
3. `linear-implementation-plan`
4. `linear-implementation-build` — which internally runs `test-runner-qa`, `code-reviewer`, `security-reviewer` (conditionally), `performance-reviewer` (conditionally), and `documentation`. This orchestrator does not call those five separately; the build skill already owns that sequencing.

**Not in scope:** `dependency-upgrade` and `release-prep` are independent entry points — scheduled or on-demand maintenance work and release cutting, respectively, not steps in a single ticket's pipeline. Don't invoke them here even if a build surfaces a stale dependency or feels release-adjacent; flag it to the user and let them invoke those skills separately if relevant.

## Trigger

Activate when the user says "run [ticket ID] through the pipeline," "take [ticket ID] end to end," "do the full flow for [ticket ID]," or otherwise asks for a ticket to go from raw requirements to an opened PR without manual stage-by-stage invocation.

## The no-pause rule

Per design, this orchestrator does not stop between stages to ask "continue?" — each stage's own skill already has the right checkpoints baked in (clarifying questions before drafting, human approval before write-back, diff approval before commit), and re-asking on top of those would just be redundant friction. The orchestrator's job is to feed output from one stage into the next automatically and only surface to the user when a stage it's running already would.

This means: if every stage's internal checkpoints are satisfied (the user answers clarifying questions, approves drafts, approves diffs — whatever each stage already asks for), the orchestrator proceeds through all four stages in one continuous flow without an extra "ready for the next stage?" gate in between.

## Step 1: Requirements

Fetch the ticket. If it already has a `## Requirements` section, skip straight to Step 2 and tell the user you're skipping (don't re-run analysis on an already-analyzed ticket without being asked).

If not, run `requirements-analyst`. Its own clarifying-question step still applies — answer those as they come up, same as if the user invoked it directly. Once it writes back and moves the ticket to "Ready for Planning," continue.

## Step 2: Architecture (conditional)

Check whether this ticket sits in a project/epic that already has an architecture doc (same lookup `linear-implementation-plan` does internally: `Linear:get_project` with `includeResources: true`, or `Linear:list_documents` scoped by `projectId`, looking for `Architecture: ...`).

If one exists, skip this stage and move to Step 3 — the planner will read it directly.

If none exists, don't automatically assume one is needed. Look at what `requirements-analyst` actually produced: does it describe a new service, a new data model, a major technology choice, or another system-level decision per `architect`'s own "Step 2: Identify the actual decisions to make"? If yes, run `architect` now, before planning. If the ticket is straightforwardly an addition to existing, already-decided structure, skip architecture and say so — don't run it just because it's in the pipeline diagram.

If genuinely unsure whether this ticket needs an architecture pass, surface that uncertainty to the user as a single question rather than silently picking a side — this is the one judgment call in the orchestrator worth a pause, since guessing wrong here is expensive to unwind later (per `architect`'s own framing).

## Step 3: Plan

Run `linear-implementation-plan`. It will pick up the `## Requirements` section and, if Step 2 ran, the architecture doc's constraints automatically — don't re-paste either into its context manually, it fetches them itself. Its own review passes and human-iteration step still apply.

Once approved and written back (ticket moved to Todo), continue.

## Step 4: Build

Run `linear-implementation-build`. It will fetch the plan, implement, run its own check gate, then internally run `test-runner-qa`, `code-reviewer`, conditionally `security-reviewer` and `performance-reviewer`, then `documentation`, then present the diff for approval, then (on approval) commit, push, open the PR, and move the ticket to In Review.

All of the build skill's existing checkpoints apply exactly as if invoked directly — the diff-approval checkpoint in particular is not skipped or weakened by being run through the orchestrator.

## Step 5: Summary

Once the PR is open, give the user one consolidated summary covering the whole run: which stages actually executed (note any skipped, like architecture, and why), what the final PR contains, and a pointer to the ticket/PR URLs. Don't re-walk every sub-step in detail — each stage already reported its own findings as it ran; this is a final roll-up, not a re-narration.

## When to stop early

Stop the whole run (don't proceed to the next stage) if:
- Any stage reports it can't proceed without information only the user can provide (e.g. requirements-analyst can't resolve a genuine ambiguity, the check gate fails repeatedly in the build stage and the implementer is stuck).
- A stage's findings suggest a different ticket should run first (e.g. `linear-implementation-plan`'s architecture pass flags that this ticket actually needs `architect` first, and Step 2 above didn't catch it because the need wasn't visible until planning was underway — go back to architect, don't push through).
- The user interrupts to redirect, correct, or stop — always honor that immediately over continuing the chain.

## What NOT to do

- Do not add a "ready to proceed?" checkpoint between stages beyond what each stage already asks for — that defeats the point of running this as one continuous flow.
- Do not invoke `dependency-upgrade` or `release-prep` as part of this flow.
- Do not skip a stage's internal checkpoint (clarifying questions, draft approval, diff approval) just because the orchestrator is running unattended — those checkpoints still require the user's actual input; the orchestrator doesn't have authority to approve on the user's behalf.
- Do not silently decide a ticket needs `architect` without surfacing the reasoning, and do not silently skip it without saying so either — both are visible, one-line notes to the user, not a silent fork.
