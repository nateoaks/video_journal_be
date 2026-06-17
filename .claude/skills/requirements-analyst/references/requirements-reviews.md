# Requirements Review Passes

Run each of these against the drafted requirements before presenting to the user. Only surface a finding if something is genuinely off — these are checks, not a quota of comments to generate.

## 1. Testability pass

For each line in "Acceptance criteria," ask: could two different engineers independently check this against a finished build and agree on the verdict? Flag any criterion that's subjective ("works smoothly," "is fast," "looks good") without a concrete standard attached, and propose a measurable substitute where you can.

## 2. Solution-creep pass

Scan the whole draft for implementation detail that snuck in: specific function names, library choices, database schemas, API designs. Requirements should describe outcomes, not mechanisms. Flag anything that's actually a design decision wearing a requirements hat — that belongs with the architect, not here.

## 3. Scope-boundary pass

Check "In scope" and "Out of scope" against each other for gaps. Is there an adjacent feature, edge case, or platform that a reasonable reader would assume is included, but isn't addressed either way? That ambiguity causes more rework than almost anything else — flag it explicitly rather than letting it stay implicit.

## 4. Stakeholder pass

Check the problem statement: is it clear who is affected and who benefits? Tickets written from a purely technical angle ("add caching to endpoint X") often bury the actual human or business reason. If the "why" is missing or only implicit, flag it — the planner and reviewers downstream make better tradeoffs when they know why something matters, not just what it is.

## 5. Conflict/dependency pass

Check "Dependencies" and "Constraints" against anything else known about the project (other open tickets, stated deadlines, prior architectural decisions if visible in linked docs). Flag any contradiction — e.g. a constraint that conflicts with a dependency's timeline, or scope that conflicts with a constraint.

## 6. Right-problem pass

This is the one pass that can override everything else: does solving this ticket as scoped actually address a real need, or does it look like a workaround for a deeper problem that isn't being named? This shouldn't block drafting, but if something looks off, it must be surfaced to the user as a flag, not silently absorbed into "Open questions."
