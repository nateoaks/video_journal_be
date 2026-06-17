# Agent review passes

Run all of these mentally when drafting an implementation plan.
Flag issues inline in the plan under a "Review notes" section. Only
include passes that actually found something — skip empty ones, and
never write "No issues found" for a pass.

## Architecture
- If an architecture doc exists for this project (see Step 1), does the plan respect every constraint in its "Constraints for implementation" section? Flag any conflict explicitly rather than letting it pass quietly.
- Does this fit existing patterns in the codebase?
- Are we adding new abstractions that duplicate existing ones?
- Does it respect module/feature boundaries?
- Any circular dependencies introduced?
- If this ticket seems to require a system-level decision that isn't covered by an existing architecture doc (new service vs. extend, new data model, major tech choice) — that's outside this skill's scope. Flag it and suggest running the `architect` skill before proceeding, rather than deciding it ad hoc here.

## Security
- Any new endpoints/handlers/entry points — are they behind the appropriate auth checks?
- Any user/external input — is it validated and sanitized before use?
- Any new data stored — is it the minimum necessary?
- Any secrets — are they in env vars / a secrets manager, not hardcoded?

## Testing
- What are the happy path tests?
- What are the failure/edge case tests?
- Does anything need an integration test vs unit test?
- Are there any async flows that need specific test setup?

## Complexity
- Is the scope right for a single ticket?
- Is there a simpler approach that achieves the same goal?
- Any premature abstractions or over-engineering?
- Could this be split into smaller tickets?

## Performance (flag if relevant)
- Any new data-store queries — could they cause N+1s or repeated round-trips?
- Any loops over large collections?
- Any missing indexes or unbounded scans on new query/access patterns?
