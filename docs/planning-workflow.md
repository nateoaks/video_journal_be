# Planning workflow

## Trigger
When told to "plan [ticket ID]" or "create a plan for [ticket ID]":

## Steps

### 1. Fetch the ticket
- Read the ticket from Linear (title, description, labels, priority, any existing comments)
- If the ticket already has an "## Implementation Plan" section, show it and ask whether to revise it or start fresh

### 2. Clarify before drafting (if needed)
Before writing the plan, check if any of these are unclear:
- What "done" looks like (acceptance criteria)
- Whether this touches any external APIs or services
- Whether there are dependencies on other tickets
If yes, ask the user — don't guess and bury assumptions in the plan.

### 3. Draft the implementation plan
Structure the plan as:

#### Goal
One sentence. What this achieves and why.

#### Approach
2–4 sentences. The chosen strategy and why over alternatives.

#### Files and components affected
Bullet list of files/modules to create, edit, or delete with a one-line reason each.

#### Implementation steps
Numbered, ordered, actionable steps. Each step should be small enough 
to be a single commit. Include setup steps, migrations, and cleanup.

#### Tests to write
- Unit tests: list specific functions/components and what cases to cover
- Integration tests: any flows that need end-to-end coverage
- Edge cases to handle explicitly

#### Open questions / risks
Anything that could affect the approach that needs a decision before or during implementation.

### 4. Run review passes
After drafting, annotate the plan with findings from each pass.
Use a "## Review notes" section at the bottom. Only include passes
that found something — skip empty ones.

@docs/planning-reviews.md

### 5. Iterate with the human
- Present the plan and review notes
- Ask: "Any changes, or should I write this back to the ticket?"
- Incorporate feedback and re-run affected review passes
- Repeat until the human says approved / LGTM / looks good

### 6. Write back to Linear
When approved:
- Fetch the current ticket description again (it may have changed)
- Append to the end — never overwrite existing content
- Use this exact header: `## Implementation Plan`
- Confirm to the user once written with the ticket URL
- Move the ticket into Todo status