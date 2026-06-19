# Backend (Python / FastAPI)

Always read the relevant doc in `docs/` before working in that area. Your training
data lags behind FastAPI, SQLAlchemy 2.0, and Pydantic v2 — the docs in this repo are
the source of truth for our conventions.

## Project Architecture

```
src/app/
├── core/         — Settings, logging, lifespan, middleware, exception handlers
├── db/           — SQLAlchemy Base, async engine + session, unit-of-work dependency
├── common/       — Shared building blocks (base repository, errors, pagination)
├── domains/      — Feature modules, one package per domain
│   └── <domain>/ — models, schemas, repository, service, dependencies, router
└── api/          — Aggregated versioned router (/api/v1) + shared dependencies
```

Each feature under `src/app/domains/` is a self-contained package with a fixed shape:

- `models.py` — SQLAlchemy 2.0 ORM models (the persistence layer)
- `schemas.py` — Pydantic v2 request/response models (never expose ORM models directly)
- `repository.py` — data access; extends `app.common.repository.BaseRepository`
- `service.py` — business logic; depends on the repository, raises domain errors
- `dependencies.py` — FastAPI providers that wire the service together
- `router.py` — `APIRouter` with thin endpoints that delegate to the service

`app/main.py` is a thin factory (`create_app()`) that configures logging, registers
middleware and exception handlers, and mounts routers. It contains no business logic.

## Tooling

Managed with **uv**. Lint and format with **ruff**, type-check with **mypy --strict**,
test with **pytest**. Run the full gate before reporting a task done:

```bash
uv run poe check    # ruff format + ruff check + mypy + pytest
```


## Reference Docs
@docs/architecture.md
@docs/configuration.md
@docs/data-models.md
@docs/database-migrations.md
@docs/logging.md
@docs/code-design.md
@docs/code-style.md
@docs/testing.md


# Engineering Team Pipeline

This repo uses a set of Claude Code skills and agents that together form an autonomous engineering pipeline, from a raw ticket to an opened PR. This file is the map — read it before assuming how something should be invoked.

## Skills vs. agents

**Skills** (`.claude/skills/`) are the "how" — each stage's procedure, checklists, severity tiers, scope boundaries. **Agents** (`.claude/agents/`) are the "who and on what model" — each agent is a thin wrapper naming a model and tool allowlist, then says "follow skill X exactly." This split means the skills themselves never needed to change when agents were introduced; only the dispatch mechanism did.

| Agent | Model | Tools | Skill it follows |
|---|---|---|---|
| `architect` | Opus | Read-only (+ WebSearch) | `architect` |
| `requirements-analyst` | Opus | Read-only | `requirements-analyst` |
| `planner` | Opus | Read-only | `linear-implementation-plan` |
| `implementer` | Sonnet | Read, Write, Edit, Bash | `linear-implementation-build` (Steps 1–2, then stops for the review chain, then Steps 3–5) |
| `code-reviewer` | Sonnet | Read-only | `code-reviewer` |
| `security-reviewer` | Opus | Read-only | `security-reviewer` |
| `performance-reviewer` | Sonnet | Read-only (+ Bash for benchmarks) | `performance-reviewer` |
| `test-runner` | Haiku | Read-only (+ Bash to run tests) | `test-runner-qa` |
| `documentation` | Haiku | Read, Write, Edit | `documentation` |
| `dependency-upgrade` | Sonnet | Read, Write, Edit, Bash | `dependency-upgrade` |
| `release-prep` | Sonnet | Read, Write, Edit, Bash | `release-prep` |
| `merge` | Sonnet | Bash, Read | `merge` |

Reviewer agents (architect, requirements-analyst, planner, code-reviewer, security-reviewer, performance-reviewer, test-runner) are hard-restricted to read-only tools — no Write/Edit. This is a structural guarantee, not just an instruction: they cannot silently apply a fix even if they see exactly what's wrong. They report findings; `implementer` (or the dispatching session) applies them.

## Pipeline order

```
requirements-analyst (agent) → architect (agent, conditional) → planner (agent) → implementer (agent)
                                                                                       │
                                                            ┌──────────────────────────┼──────────────────────────┐
                                                            ▼                          ▼                          ▼
                                                      test-runner              code-reviewer            security-reviewer (conditional)
                                                      (agent)                   (agent)                  performance-reviewer (agent, conditional)
                                                                                                                    │
                                                                                                                    ▼
                                                                                                          documentation (agent)
```

**Important difference from the pre-agent design:** when build was a single skill, it called the four review skills internally. As separate agents, `implementer` cannot spawn its own nested subagents, so the **dispatching session** (the orchestrator, or you directly) now owns calling each review agent and feeding findings back to `implementer` for fixes. See `eng-team-orchestrator`'s Step 4 for the exact sequencing.

Independent of the above (separate entry points, not part of a single ticket's flow):
- `dependency-upgrade` (agent) — scheduled/on-demand maintenance
- `release-prep` (agent) — cutting a release (versioning, CHANGELOG, tag — no deploy)
- `merge` (agent) — merge an approved PR, move the ticket to Done, remove the worktree

## How to run it

**Full pipeline, one ticket, hands-off except built-in checkpoints:**
```
/pipeline BLA-7
```
This runs the `eng-team-orchestrator` skill, which chains all four main stages automatically and only stops where a stage already has a human checkpoint (clarifying questions, draft/plan approval, diff approval). It does not add extra "continue?" gates between stages.

**One stage at a time, manual control:**
```
/requirements BLA-7
/architect <project or epic name>
/plan BLA-7
/build BLA-7
```

**Standalone review of an in-progress diff** (not tied to a ticket pipeline run):
```
/review
```
Runs code-reviewer + test-runner-qa always, security-reviewer and performance-reviewer conditionally based on what the diff touches.

**After PR approval — merge and clean up:**
```
/merge BLA-7
```
Squash-merges the approved PR, moves the ticket to Done, and removes the local worktree. Stops and reports if the PR isn't approved or has conflicts.

**Maintenance, run independently:**
```
/deps      — dependency-upgrade
/release   — release-prep
```

## Where checkpoints actually are

Every "approval" in this pipeline is a real stop, not a formality:

- `requirements-analyst` — asks clarifying questions before drafting; asks for approval before writing back to the ticket.
- `architect` — same pattern, plus its decisions are expensive to reverse, so its clarifying step pushes harder on real tradeoffs.
- `linear-implementation-plan` — same pattern; checks against an architecture doc's constraints if one exists.
- `linear-implementation-build` — runs a check gate (lint/typecheck/test), then test-runner-qa/code-reviewer/security-reviewer/performance-reviewer/documentation, then **shows the full diff for explicit approval before committing anything**. That single approval covers everything after it — commit, push, and PR creation happen automatically once given; there's no separate push/PR gate.
- `release-prep` — **no autonomous path at all**; always asks before tagging or writing the CHANGELOG.
- `dependency-upgrade` — the one skill designed for *less* oversight: patch/minor bumps auto-PR without a pre-push approval (still gated on the check gate passing); major bumps need sign-off; CVE patches proceed regardless of bump size, with the breaking-change risk surfaced explicitly rather than hidden.

If you're ever unsure whether something just happened autonomously or is waiting on you, the answer is in the relevant skill's `SKILL.md` under "The autonomy line" (dependency-upgrade) or its checkpoint steps (everything else).

## Known limitations

- **Subagent MCP tool access is unverified in your environment.** Public reports conflict on whether custom subagents reliably get MCP tool passthrough (for Linear/Jira reads and writes) — it may depend on Claude Code version and whether the agent is project-based vs. plugin-based. Every agent that needs tracker access is written to attempt the call and, if it fails or the tool isn't present, report that plainly and hand back the content for the dispatching session to write instead — rather than silently failing or guessing. Watch for this on your first real run; if it's consistently unavailable, the fix is to have the orchestrator (or you) perform all tracker writes directly rather than relying on agent-level MCP access.
- **Linear ticket fetching**: the primary path is `Linear:get_issue`. If that tool isn't loaded in a given session, skills fall back to `Linear:list_issues` with a query — but that fallback **truncates long descriptions** and points to a `get_issue` tool that, in the fallback case, isn't available. If a ticket's description looks cut off, the skill will say so and ask rather than proceeding on a partial spec. Don't assume a truncated-looking description in a transcript means the ticket itself is incomplete — check before concluding that.
- **No deploy step anywhere in this pipeline.** `release-prep` stops at a tagged, documented release. If your team needs an actual deploy trigger, that's not built yet — say so explicitly rather than assuming `/release` does it.
- **No orchestrator memory across sessions.** If a pipeline run is interrupted (you close the session mid-build, say), re-running `/pipeline <ticket>` re-checks ticket state from scratch (status, existing `## Requirements`/`## Implementation Plan` sections) rather than resuming from an internal checkpoint — which is generally safe since each stage already detects and asks about existing partial work, but worth knowing if a run seems to "redo" something.

## Adding a new skill

New skills go in `.claude/skills/<name>/SKILL.md` (project-scoped, ships with the repo) and should be added to the diagram above if they sit in the main pipeline, or to "independent entry points" if they don't. If it's meant to be reachable via slash command, add a one-line command file to `.claude/commands/`.

## Git worktree usage
When operating on a different worktree, use `git -C <worktree-path> <command>`
instead of `cd <worktree-path> && git <command>`.
