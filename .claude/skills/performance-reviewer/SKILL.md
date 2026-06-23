---
name: performance-reviewer
description: Reviews an in-progress code change (uncommitted diff, or a specific commit/branch) for performance issues — inefficient queries, unbounded loops, unnecessary re-computation, memory growth — via static code reading, and runs existing benchmarks/profilers if the repo has them and they're cheap to run, reporting before/after deltas. Use whenever the user says "performance review this", "will this scale", "check for slowdowns", or whenever linear-implementation-build reaches its check-gate-passed step on a change touching queries, loops over collections, caching, or other hot-path code. This is performance only — it explicitly does NOT cover correctness (use code-reviewer), security (use security-reviewer), or architecture-level scaling decisions (use architect for those).
---

# Performance Reviewer

Acts as a performance engineer reviewing a diff for inefficiency before a human sees it — primarily by reading the code for known bad patterns, and secondarily by running the repo's existing benchmarks if doing so is fast and low-risk. Kept separate from `code-reviewer` for the same reason `security-reviewer` is separate: performance gets skipped when it's one concern among many a general reviewer is juggling.

## Scope boundary

This skill owns: algorithmic complexity, database/query efficiency, unnecessary or repeated computation, memory growth, and blocking operations on hot paths. It does not own:

- **Correctness or readability** — `code-reviewer`.
- **Security** — `security-reviewer`, even where the two overlap (e.g. an unbounded query is both a performance and a potential DoS issue — flag the performance angle here, note that security-reviewer should look at the DoS angle, don't write up both in full).
- **Whether the system's overall architecture can scale** (sharding, caching layer choices, read replicas) — that's a system-level call for `architect`, not a per-diff finding. If a diff's performance problem is really "the architecture doesn't support this load," say so and point upstream rather than trying to fix it with a local patch.

## Trigger

Activate when the user says "performance review this," "will this scale," "check for slowdowns," or when `linear-implementation-build` reaches its check-gate-passed step on a diff touching: database/ORM queries, loops over collections (especially nested, or over data of unbounded/user-controlled size), caching logic, anything in a documented hot path, or new dependencies known for heavy resource use. For diffs with none of these (e.g. a copy change, a config tweak with no runtime loop), skip and say so explicitly rather than running a full pass that won't find anything relevant.

## Step 1: Gather what's being reviewed

Get the diff (uncommitted, a commit, or branch-vs-base — same convention as the other reviewers). Get the implementation plan and architecture constraints if available, for context on expected scale (e.g. "this endpoint serves internal admin traffic" vs. "this is on the checkout hot path" changes how much a given inefficiency matters).

## Step 2: Static review pass

Read `references/performance-review-passes.md` and run each pass that applies to this diff's surface. Build a findings list tagged by severity:

- **Critical** — will cause a clear, immediate problem at expected scale (unbounded query that grows with table size on a high-traffic path, N+1 query in a loop over user-facing data, synchronous blocking call on a request path that needs to stay responsive).
- **Should fix** — a real inefficiency, but not severe enough to block at current scale; worth fixing because it compounds or because the fix is cheap relative to the gain.
- **Note** — a micro-optimization or theoretical concern not worth the complexity/readability tradeoff right now. Most "this could be O(1) instead of O(log n)" observations belong here, not in a blocking tier.

Be honest about scale before flagging Critical: a loop over a few dozen items isn't a finding just because a loop over a million would be. Ask "does this diff's actual, realistic data size make this a problem" before tagging severity — don't pattern-match "nested loop" to "Critical" without that check.

## Step 3: Run existing benchmarks, if cheap

Check whether the repo has existing benchmarks, load tests, or profiling scripts (common locations/markers: a `bench`/`benchmark` directory, `criterion`/`pytest-benchmark`/`k6`/similar tooling in the dependency manifest, a documented `make bench` or equivalent). If one exists and is scoped to the area this diff touches:

Run it once before applying analysis (or use a `git stash` / checkout of the base branch to get a baseline) and once with the diff applied, then report the delta. Treat "cheap" as a hard boundary, not a judgment call to stretch: a benchmark that's expected to finish in under roughly a minute and doesn't require spinning up infrastructure (databases, external services, containers) beyond what's already running. If it's not already set up and fast, don't set it up — note that a benchmark exists but wasn't run, and why, rather than spending the session standing up infrastructure for it.

If no benchmark exists for the touched area, say so plainly rather than fabricating a number or skipping the mention entirely — the absence of a benchmark is itself worth knowing for a team deciding whether to invest in one.

## Step 4: Report

Present findings grouped by severity with file/line references and the realistic scenario where it matters (not just "this is O(n²)" but "this runs per-request over a list that grows with user count, so it'll degrade as the user base grows"). Include the benchmark delta from Step 3 if one was run, or a one-line note on why none was run. Omit empty severity tiers.

If invoked standalone, stop here.

If invoked from inside `linear-implementation-build`: Critical findings must be addressed (re-edit, re-run check gate) before the human diff-approval checkpoint. Should-fix and Note are judgment calls for the implementer; if a Should-fix is deferred, say so explicitly when the diff is presented rather than dropping it silently.

## What NOT to do

- Do not run a benchmark, load test, or profiler that takes more than about a minute or requires standing up infrastructure — note it exists and move on.
- Do not flag theoretical complexity issues on code paths with small, bounded, or rarely-changing input as Critical — match severity to realistic scale, not big-O alone.
- Do not propose an architecture-level fix (add a cache layer, introduce a queue, shard a table) as a finding on this diff — flag that the diff is hitting a scaling limit the architecture doesn't address, and point to `architect`.
- Do not silently rewrite the code for performance — report the finding and let the implementer make the change.
- Do not treat the absence of measured numbers as license to skip the review — static analysis of the code is still valid and should still be reported even when no benchmark exists.
