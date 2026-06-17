---
name: linear-implementation-plan
description: Drafts a senior-engineer-quality implementation plan for a Linear ticket, runs structured review passes (architecture, security, testing, complexity, performance), iterates with the user, and writes the approved plan back to the Linear ticket description before moving it to Todo. Use this skill whenever the user says "plan TICKET-ID", "create a plan for TICKET-ID", "plan out TICKET-ID", or otherwise asks for an implementation plan for a Linear ticket — even if they don't use the exact word "plan." Always use this skill for Linear ticket planning rather than drafting an ad hoc plan directly, since it encodes the required review passes and write-back behavior.
---

# Linear Implementation Plan

Acts as a senior engineer turning a Linear ticket into a reviewed, ready-to-execute implementation plan, then writes it back to the ticket.

## Trigger

Activate when the user says "plan [ticket ID]," "create a plan for [ticket ID]," "plan out [ticket ID]," or similarly asks for an implementation plan tied to a specific Linear ticket.

## Step 1: Fetch the ticket

Fetch the ticket via `Linear:get_issue`. If that tool isn't available in the current connector, fall back to `Linear:list_issues` with `query: "<ticket ID>"` — title, description, labels, priority, status, and existing comments (`Linear:list_comments`).

The `list_issues` fallback truncates long descriptions and may reference a `get_issue` tool that, if you're using this fallback, is by definition unavailable. If the description looks cut off and `get_issue` truly isn't reachable, tell the user and ask them to paste the full text or point to where it's covered (comments, linked doc) rather than planning against a partial spec.

If the description already contains an `## Implementation Plan` section, show it to the user and ask whether to revise it or start fresh. Don't silently overwrite or silently keep it.

If the ticket belongs to a project, check for an architecture doc the `architect` skill may have produced via `Linear:get_project` with `includeResources: true` (or `Linear:list_documents` scoped by `projectId`), looking for one titled `Architecture: ...`. If one exists, read its "Constraints for implementation" section — the plan must respect it. If a comment on this ticket references an architecture doc, that's a strong signal one exists even if the project-level search misses it.

## Step 2: Clarify before drafting

Before writing anything, check whether any of these are unclear from the ticket:

- What "done" looks like (acceptance criteria)
- Whether this touches any external APIs or services
- Whether there are dependencies on other tickets

If something is genuinely unclear, ask the user directly — don't guess and bury the assumption in the plan. If the ticket already answers these clearly, proceed without asking.

## Step 3: Draft the implementation plan

Write as a senior engineer: opinionated, concrete, no hedging. Use this exact structure:

```markdown
## Implementation Plan

#### Goal
One sentence. What this achieves and why.

#### Approach
2–4 sentences. The chosen strategy and why over alternatives.

#### Files and components affected
- `path/to/file` — one-line reason (create/edit/delete)

#### Implementation steps
1. Small, ordered, actionable steps. Each should be sized to a single commit.
   Include setup, migrations, and cleanup steps explicitly.

#### Tests to write
- Unit tests: specific functions/components and the cases to cover
- Integration tests: any end-to-end flows that need coverage
- Edge cases to handle explicitly

#### Open questions / risks
Anything that could change the approach and needs a decision before or during implementation.
```

## Step 4: Run review passes

Read `references/planning-reviews.md` and run each pass against the draft plan. Append findings as a `## Review notes` section at the bottom of the plan — but only include passes that actually surfaced something. Skip passes with nothing to flag entirely; don't write "no issues found" entries.

## Step 5: Iterate with the human

Present the plan and review notes in the chat (not yet written to Linear). Ask: "Any changes, or should I write this back to the ticket?"

Incorporate feedback, re-run any review passes affected by the changes, and repeat until the user signals approval (e.g. "approved," "LGTM," "looks good," "ship it").

Do not write to Linear before this approval.

## Step 6: Write back to Linear

Once approved:

1. Re-fetch the ticket description with `Linear:get_issue` (or the `Linear:list_issues` fallback if unavailable) — it may have changed since Step 1.
2. Append the plan to the end of the existing description. Never overwrite or remove existing content. Separate it from prior content with a blank line.
3. The plan section must start with the exact header `## Implementation Plan`.
4. Call `Linear:save_issue` with the updated `description` and `state` set to `Todo`.
5. Confirm to the user that it's written, and include the ticket URL.

## Notes on tone and judgment

- Be decisive in the plan itself — a senior engineer's plan makes a call and explains why, rather than listing every option.
- Reserve hedging for the "Open questions / risks" section, not the main body.
- If the ticket is too vague to plan (e.g. no clear scope at all), say so and ask the user to clarify the ticket rather than fabricating scope.
