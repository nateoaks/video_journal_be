---
name: eng-team-orchestrator
description: Runs a Linear or Jira ticket through the full autonomous engineering pipeline end to end — requirements-analyst, architect (if needed), planner, implementer (paired with test-runner, code-reviewer, security-reviewer, performance-reviewer, and documentation), stopping only at the approval checkpoints already built into those stages. Each stage runs as a dedicated agent with its own model — Opus for architect/requirements-analyst/planner/security-reviewer, Sonnet for implementer/code-reviewer/performance-reviewer, Haiku for test-runner/documentation — not all as the current session. Use whenever the user says "run TICKET-ID through the pipeline", "take TICKET-ID end to end", or asks to fully automate a ticket from requirements to PR. Does NOT invoke dependency-upgrade or release-prep — those are separate entry points.
---

# Engineering Team Orchestrator

Chains the team's stages into one continuous run for a single ticket — requirements through PR — stopping only where a stage already has a human checkpoint built in, not between every stage. This skill doesn't introduce new judgment; it sequences the judgment already encoded in each stage and carries the right context forward between them.

Each stage now runs as a dedicated subagent (defined in `.claude/agents/`), not as the current session reading a skill in place. Dispatch to each by name (e.g. "Use the architect agent to design [project]" or via the Agent/Task tool with `subagent_type`) rather than following the corresponding skill yourself in the main session — the whole point of the agent split is that each stage gets its own context window and the model suited to its reasoning load (Opus for architect/requirements-analyst/planner/security-reviewer, Sonnet for implementer/code-reviewer/performance-reviewer, Haiku for test-runner/documentation). Running a stage yourself instead of dispatching defeats that.

**Known platform uncertainty**: whether subagents reliably get MCP tool access (for Linear/Jira reads and writes) varies by Claude Code version and agent type, per current public reports. Each agent file is written to attempt its tracker calls and fall back to handing you the content if the call isn't available — if you see an agent report "tool unavailable, here's the content," perform that tracker write yourself from the main session rather than treating it as a failure to recover from.

## What this dispatches and doesn't

**In scope, in this order — each a separate agent dispatch:**
1. `requirements-analyst` agent (skip if the ticket already has a `## Requirements` section — see Step 1)
2. `architect` agent (skip if there's no project/epic-level decision to make — see Step 2's judgment call)
3. `planner` agent
4. `implementer` agent, followed by the review chain the orchestrator now coordinates directly: `test-runner`, `code-reviewer`, `security-reviewer` (conditionally), `performance-reviewer` (conditionally), then `documentation` — see Step 4. This is a change from the pre-agent design: when these were all one skill (`linear-implementation-build`), that skill called the others internally. As separate agents, the `implementer` agent can't spawn its own subagents, so the dispatching session (you, running this orchestrator) now owns calling each review agent and feeding results back to `implementer` for fixes.

**Not in scope:** `dependency-upgrade` and `release-prep` are independent entry points — scheduled or on-demand maintenance work and release cutting, respectively, not steps in a single ticket's pipeline. Don't dispatch them here even if a build surfaces a stale dependency or feels release-adjacent; flag it to the user and let them invoke those agents separately if relevant.

## Trigger

Activate when the user says "run [ticket ID] through the pipeline," "take [ticket ID] end to end," "do the full flow for [ticket ID]," or otherwise asks for a ticket to go from raw requirements to an opened PR without manual stage-by-stage invocation.

## The no-pause rule

Per design, this orchestrator does not stop between stages to ask "continue?" — each agent already has the right checkpoints baked into the skill it follows (clarifying questions before drafting, human approval before write-back), and re-asking on top of those would just be redundant friction. The orchestrator's job is to dispatch each agent, carry its output into the next, and only surface to the user when an agent's own checkpoint already would.

This means: if every agent's internal checkpoints are satisfied (the user answers clarifying questions, approves drafts — whatever each one already asks for), the orchestrator proceeds through the full chain in one continuous flow without an extra "ready for the next stage?" gate in between.

## Step 1: Requirements

Fetch the ticket. If it already has a `## Requirements` section, skip straight to Step 2 and tell the user you're skipping (don't re-run analysis on an already-analyzed ticket without being asked).

If not, dispatch the `requirements-analyst` agent. Its own clarifying-question step still applies — relay those to the user as they come up, same as if invoked directly. If the agent reports it couldn't perform the tracker write-back itself (the known MCP-passthrough uncertainty), perform that write-back yourself before continuing. Once requirements are written back and the ticket is moved to "Ready for Planning," continue.

## Step 2: Architecture (conditional)

Check whether this ticket sits in a project/epic that already has an architecture doc (`Linear:get_project` with `includeResources: true`, or `Linear:list_documents` scoped by `projectId`, looking for `Architecture: ...`).

If one exists, skip this stage and move to Step 3 — the `planner` agent will read it directly.

If none exists, don't automatically assume one is needed. Look at what the `requirements-analyst` agent actually produced: does it describe a new service, a new data model, a major technology choice, or another system-level decision per the `architect` skill's own "Step 2: Identify the actual decisions to make"? If yes, dispatch the `architect` agent now, before planning. If the ticket is straightforwardly an addition to existing, already-decided structure, skip architecture and say so — don't dispatch it just because it's in the pipeline diagram.

If genuinely unsure whether this ticket needs an architecture pass, surface that uncertainty to the user as a single question rather than silently picking a side — this is the one judgment call in the orchestrator worth a pause, since guessing wrong here is expensive to unwind later.

## Step 3: Plan

Dispatch the `planner` agent. It will pick up the `## Requirements` section and, if Step 2 ran, the architecture doc's constraints automatically — don't re-paste either into its prompt manually, it fetches them itself. Its own review passes and human-iteration step still apply. If it reports the write-back tool was unavailable, write the approved plan back yourself.

Once approved and written back (ticket moved to Todo), continue.

## Step 4: Build and review chain

Move the ticket to **In Progress** via `Linear:save_issue` (`state: "In Progress"`) before any implementation work begins. If that MCP call isn't available, report the ticket URL and tell the user to update it manually — then continue; this status update is not a blocker.

Before dispatching the implementer, create an isolated git worktree so that any WIP files in the main working tree don't bleed into the check gate:

```bash
# Derive branch name from the Linear ticket's gitBranchName field, or construct it:
#   feat/BLA-<id>-<slug>  /  fix/BLA-<id>-<slug>  /  chore/BLA-<id>-<slug>
git fetch origin main
git worktree add .claude/worktrees/<ticket-id> -b <branch-name> origin/main
```

All subsequent implementer work (edits, `poe check`, commit) happens inside `.claude/worktrees/<ticket-id>/`. Pass the worktree path to the implementer so it knows where to operate.

When passing the worktree path to agents or running shell commands yourself, use the **relative path** `.claude/worktrees/<ticket-id>` rather than the absolute path — the bash tool starts in the project root, so relative paths work and avoid the need for an absolute-path permission. Example: `cd .claude/worktrees/BLA-20 && uv run poe check`.

Dispatch the `implementer` agent. It fetches the plan, writes the code, and runs the check gate, then stops (per its own agent definition — it does not call the other review agents itself).

Once the check gate passes, dispatch in turn:
1. `test-runner` — always.
2. `code-reviewer` — always.
3. `security-reviewer` — if the diff touches new endpoints/handlers, auth, user/external input, secrets, or dependencies.
4. `performance-reviewer` — if the diff touches queries, loops, caching, or hot-path code.

Collect findings from all that ran. Resolve before proceeding, per each skill's own severity rules: all Blocking (code-reviewer), Critical/High (security-reviewer), Critical (performance-reviewer), and failures/acceptance-criteria gaps (test-runner) must be fixed. Hand these back to the `implementer` agent to apply fixes and re-run the check gate; repeat the relevant review dispatches if the fix was non-trivial.

Once findings are resolved, dispatch the `documentation` agent against the same diff.

Then return to `implementer` for its remaining steps: commit, push, and PR creation automatically — no human approval gate. Once review findings are resolved, the implementer proceeds directly to commit and PR without stopping.

## Step 5: Summary

Once the PR is open, give the user one consolidated summary covering the whole run: which agents actually ran (note any skipped, like architecture, and why), what the final PR contains, and a pointer to the ticket/PR URLs. Don't re-walk every sub-step in detail — each agent already reported its own findings as it ran; this is a final roll-up, not a re-narration.

## When to stop early

Stop the whole run (don't proceed to the next stage) if:
- Any agent reports it can't proceed without information only the user can provide (e.g. requirements-analyst can't resolve a genuine ambiguity, the check gate fails repeatedly in the build stage and the implementer is stuck).
- A stage's findings suggest a different ticket should run first (e.g. the planner's architecture pass flags that this ticket actually needs `architect` first, and Step 2 above didn't catch it because the need wasn't visible until planning was underway — go back to architect, don't push through).
- An agent reports a tracker tool was unavailable and you, the dispatching session, also can't perform the write — say so plainly rather than silently dropping the write-back.
- The user interrupts to redirect, correct, or stop — always honor that immediately over continuing the chain.

## What NOT to do

- Do not add a "ready to proceed?" checkpoint between stages beyond what each agent already asks for — that defeats the point of running this as one continuous flow.
- Do not dispatch `dependency-upgrade` or `release-prep` as part of this flow.
- Do not skip an agent's internal checkpoint (clarifying questions, draft approval) just because the orchestrator is running unattended — those checkpoints still require the user's actual input; the orchestrator doesn't have authority to approve on the user's behalf.
- Do not silently decide a ticket needs `architect` without surfacing the reasoning, and do not silently skip it without saying so either — both are visible, one-line notes to the user, not a silent fork.
- Do not run a stage yourself in the main session instead of dispatching to its agent, even if dispatch seems slower — the model tiering and context isolation are the point of this design.
