# Agent review passes

Run all of these mentally when drafting an implementation plan.
Flag issues inline in the plan under a "Review notes" section.

## Architecture
- Does this fit existing patterns in the codebase?
- Are we adding new abstractions that duplicate existing ones?
- Does it respect module/feature boundaries?
- Any circular dependencies introduced?

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