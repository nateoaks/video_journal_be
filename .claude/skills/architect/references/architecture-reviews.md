# Architecture Review Passes

Run each of these against the drafted design doc. Only surface a finding if something is genuinely off.

## 1. Reversibility pass

For each major decision in the doc, ask: how expensive is this to undo in three months? Flag any decision that's hard to reverse (data model choices, public API shapes, technology with high switching cost) but was made with the same casualness as something easily changed. These deserve the most scrutiny in Step 3, not the least.

## 2. Existing-pattern pass

Check the "Decision" against what already exists in the codebase. Does it introduce a new way of doing something the codebase already does a different way, without a stated reason? Inconsistency without justification compounds — flag it even if the new way is arguably better, so the user can decide if the inconsistency is worth it.

## 3. Boundary-clarity pass

For each component listed in "Components and boundaries," check that its contract with neighbors is concrete enough that two different engineers building on either side of it wouldn't need to talk to agree on the interface. Vague boundaries ("the service handles user data") are where integration bugs come from later — flag them.

## 4. Overreach pass

Check whether the doc is making decisions that belong to a single ticket's implementation plan, not here (specific function names, file structure, exact test cases). This skill should stop at the constraint, not the implementation. Flag and suggest moving such detail to "Constraints for implementation" (as a rule) or removing it (if it's just premature detail).

## 5. Underreach pass

The opposite problem: check whether something flagged in Step 2 as a real decision got hand-waved in the draft instead of actually decided. A "Decision" section that lists options without picking one didn't do the job.

## 6. Blast-radius pass

Check "Constraints for implementation" against the actual tickets/scope this project covers. Is there a constraint that's easy to forget when several tickets are being planned independently, possibly by different people or agents, weeks apart? If so, make sure it's stated as something checkable in a later review pass, not just prose a planner might skim past.
