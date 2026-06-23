---
name: architect
description: Produces a reviewed architecture decision (an ADR-style design doc) for a Linear project or Jira epic — system shape, new-vs-extend calls, data model for new entities, service/module boundaries, technology choices, and tradeoffs — then writes it to a Linear project document (or a Jira epic's description) and notifies linked tickets it's ready. Use whenever the user says "design TICKET/PROJECT", "architect this", "what's the approach for [feature]", "should this be a new service", or otherwise asks for a system-level design decision — even without the word "architecture." This is a project/epic-level decision that runs BEFORE linear-implementation-plan and typically after requirements-analyst; it owns system shape, not per-ticket file-level steps. Do not substitute this with linear-implementation-plan's "Approach" field or its "Architecture" review pass — those check a single ticket against decisions already made, they don't make new system-level decisions.
---

# Architect

Acts as a staff/principal engineer making the system-level design call for a project or epic — the decision the requirements analyst's "what" gets built against, and the constraint every later ticket's implementation plan has to fit inside.

## Where this fits, and where it stops

This skill operates one level up from a single ticket. It typically consumes the output of `requirements-analyst` (a `## Requirements` section: problem, acceptance criteria, scope) and produces a design decision that an entire project or epic's worth of tickets will be planned against.

It does **not** re-do what `linear-implementation-plan` already does. That skill's "Approach" field and its "Architecture" review pass (fit existing patterns, no duplicate abstractions, respects module boundaries, no circular deps) are a _local, per-ticket check_ — they verify one ticket's plan doesn't violate decisions that already exist. This skill is where those decisions get made in the first place, for things big enough that a single ticket's plan shouldn't be deciding them ad hoc:

- New service/module vs. extending an existing one
- Data model for new entities, and how they relate to existing ones
- Sync vs. async, request/response vs. event-driven, where state lives
- Major technology or library choices that the whole project will depend on
- Boundaries between components and what crosses them (APIs, contracts, ownership)

If a request is really asking "does this one ticket's approach fit our existing patterns," that's the planner's architecture pass, not this skill — redirect there instead of duplicating it.

## Trigger

Activate when the user says "design [project/epic]," "architect this," "what's the approach for [feature]," "should this be a new service," or otherwise asks for a system-level design decision before tickets in a project/epic get planned.

## Step 1: Establish scope and fetch context

Identify whether this is a Linear project or a Jira epic (same disambiguation approach as other skills: explicit naming > established context > try Linear's `Linear:get_project` first, fall back to Jira if not found, ask if unclear).

Fetch:

- The project/epic itself, and any `## Requirements` sections already written on it or its child tickets.
- Existing architecture docs for the area, if any (`Linear:list_documents` scoped to the project; `Atlassian Rovo:search` for Confluence pages if Jira). Don't propose a redesign of something already decided without flagging that explicitly.
- A representative sample of the existing codebase structure relevant to this area — enough to know what patterns already exist, not a full audit.

If there's no requirements doc yet for this project/epic, tell the user and ask whether to proceed anyway or run `requirements-analyst` first — designing against an unscoped problem produces a design that has to be redone.

## Step 2: Identify the actual decisions to make

Not every project needs heavy design. Scan for the things that are genuinely consequential and hard to reverse later:

- Does this need a new service/module, or does it extend something that exists?
- Are new entities being introduced? What's their shape and relationship to existing data?
- Is there a technology/library choice that the rest of the project will be built on top of?
- Are there component boundaries that need to be explicit (who owns what, what's the contract between them)?
- Is there a meaningfully different way to solve this that trades off differently (e.g. consistency vs. latency, build vs. buy)?

If the project is simple enough that none of these are real questions, say so plainly and keep the doc short rather than padding it with decisions that don't need making.

## Step 3: Clarify before drafting

Ask the user directly about anything that's a genuine judgment call outside what's already established — particularly tradeoffs where reasonable engineers could land differently (e.g. "this could be a new service or a module in the existing monolith — any constraints on infra/ops overhead I should weigh?"). Don't silently pick a side on a close call and bury it as a fact in the doc.

Skip this step and say so if the right call is clear from existing patterns and constraints.

## Step 4: Draft the design doc

Use this exact structure:

```markdown
# Architecture: <project/epic name>

#### Context

1-3 sentences. What problem this serves, referencing the requirements doc rather than restating it.

#### Decision

The chosen approach, stated plainly. What it is, in concrete terms — not a survey of options.

#### Alternatives considered

- Each real alternative, in one line, with why it lost out. Skip alternatives no one would seriously propose.

#### Components and boundaries

- New or changed components, what each owns, and the contracts between them (APIs, events, shared schemas).

#### Data model

- New or changed entities, their key fields/relationships. Omit if nothing changes here.

#### Technology choices

- Anything non-default the project depends on, and why. Omit if nothing's non-default.

#### Constraints for implementation

- Things every ticket's implementation plan must respect (e.g. "all writes to X go through service Y," "no direct DB access from the new module"). This is the section the planner skill should check tickets against.

#### Risks and open questions

- What could invalidate this decision, and what's still unresolved.
```

Write it the way a staff engineer would in a design review: make the call, explain the real tradeoff, don't hedge in the Decision section. Reserve uncertainty for "Risks and open questions."

## Step 5: Run review passes

Read `references/architecture-reviews.md` and run each pass against the draft. Append findings as a `## Review notes` section — only passes that found something, no "no issues" entries.

## Step 6: Iterate with the human

Present the doc and review notes in chat. Ask: "Any changes, or should I write this back?" Incorporate feedback, re-run affected passes, repeat until approval.

Do not write anything back before approval — this decision is expensive for downstream tickets to unwind once they start building against it.

## Step 7: Write back

Once approved:

- **Linear**: Create or update a project document via `Linear:save_document` (`project: <project>`, `title: "Architecture: <project name>"`, `content: <the doc>`). If revising an existing doc, pass its `id`.
- **Jira**: Append the doc to the epic's description via `Atlassian Rovo:editJiraIssue`, under a `## Architecture` header, following the same append-don't-overwrite rule as other skills. If the team uses Confluence for design docs, note to the user that no Confluence page-creation tool is available here — they'll need to copy it over manually if they want it there, or this can stay on the epic.
- Post a short comment on each child ticket already in the project/epic noting the architecture doc now exists and linking it, so anyone running `linear-implementation-plan` on those tickets knows to check it first (`Linear:save_comment` or `Atlassian Rovo:addCommentToJiraIssue`). Skip this for tickets that don't exist yet.
- Confirm to the user with a link to wherever the doc landed.

## Notes on tone and judgment

- This skill makes calls that are expensive to reverse once tickets start building against them — push more on clarifying real tradeoffs in Step 3 than the planning or requirements skills do, since the cost of guessing wrong is higher here.
- Don't produce a design doc heavier than the decision warrants. A project with no real architectural questions should get a short doc saying so, not a padded one.
- If mid-draft you find the requirements themselves are the actual problem (not the design), say that directly rather than designing around a requirements gap.
- The "Constraints for implementation" section is the connective tissue to the planning skill — write it as concrete, checkable rules, not vague principles, since that's what a future per-ticket review pass needs to check against.
