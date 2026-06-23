---
name: requirements-analyst
description: Turns a vague or underspecified Linear or Jira ticket into a clear, reviewed "## Requirements" section — problem statement, acceptance criteria, scope boundaries, and open questions — then writes it back to the ticket and moves it to "Ready for Planning." Use this skill whenever the user says "analyze TICKET-ID," "write requirements for TICKET-ID," "flesh out TICKET-ID," "what does TICKET-ID actually need," or otherwise asks to clarify or scope a ticket before planning starts — even if they don't use the word "requirements." This is the step that runs BEFORE linear-implementation-plan; always use this skill first on a ticket that doesn't yet have a "## Requirements" section, rather than letting the planning skill infer scope on its own.
---

# Requirements Analyst

Acts as a requirements analyst turning a vague ticket into a precise, reviewed problem statement and acceptance criteria — the thing the architect and planner build from. This is deliberately the step _before_ `linear-implementation-plan`: it owns "what are we building and how do we know it's done," not "how do we build it."

## Trigger

Activate when the user says "analyze [ticket ID]," "write requirements for [ticket ID]," "flesh out [ticket ID]," "scope [ticket ID]," or otherwise asks to clarify what a ticket actually needs before planning begins.

## Step 1: Identify the tracker and fetch the ticket

Tickets can come from Linear or Jira, and key format alone doesn't disambiguate them (both use `TEAM-123`). Resolve it like this:

1. If the user's message names the tool ("the Jira ticket," "in Linear") or the conversation has an established tracker for this project, use that.
2. Otherwise, try `Linear:get_issue` first. If that tool isn't available in the current connector, fall back to `Linear:list_issues` with `query: "<ticket ID>"` — but be aware this fallback path truncates long descriptions (see below). If the lookup returns a clear "not found" rather than an auth/permission error, try Jira: call `Atlassian Rovo:getAccessibleAtlassianResources` to get the `cloudId`, then `Atlassian Rovo:getJiraIssue`.
3. If neither resolves cleanly, ask the user which tracker the ticket is in rather than guessing further.

**Truncated descriptions**: if `Linear:get_issue` isn't available and the `list_issues` fallback is used, long descriptions get truncated with a note pointing back to `get_issue` — a loop, since that's the tool that was unavailable in the first place. If a description appears truncated (ends mid-sentence, or contains literal text like "truncated" or "use get_issue") and `get_issue` truly isn't reachable, tell the user the description appears cut off and ask them to paste the rest, or check `Linear:list_comments` and any linked documents for content that might cover the missing part. Never analyze or draft requirements against a description you know is incomplete without flagging that explicitly.

Once fetched, read the title, description, labels, priority, and any existing comments (`Linear:list_comments` or comments included in the Jira issue fields).

If the description already contains a `## Requirements` section, show it to the user and ask whether to revise it or start fresh — don't silently overwrite or silently keep it.

## Step 2: Read the ticket for what it's actually saying

Before asking the user anything, work out what's already answered versus genuinely missing. A surprising amount of "vague" tickets aren't actually vague — they just have the answer buried in a comment thread or linked doc. Check linked issues/docs if referenced.

Then identify gaps against this checklist:

- **Problem, not solution**: does the ticket describe a problem/need, or does it jump straight to an implementation detail that may not be the only valid approach? (Worth flagging even if you don't resolve it here — that's the architect's call, not yours.)
- **Who is this for / who's affected**: is the user, persona, or system boundary clear?
- **Done means what**: is there any way to tell, objectively, when this is complete?
- **Scope edges**: what's explicitly out of scope, and is there an obvious adjacent thing someone will assume is included unless told otherwise?
- **Constraints**: deadlines, compliance/legal requirements, must-use/must-avoid tech, backward compatibility needs.
- **Dependencies**: other tickets, teams, or external systems this is blocked by or blocks.

## Step 3: Clarify before drafting

For anything genuinely unresolved after Step 2 — not things you could reasonably infer — ask the user directly. Don't guess and bury the assumption in the document.

Keep this efficient: batch the real questions together rather than going back and forth one at a time. If everything is answerable from the ticket and linked context, skip this step entirely and say so.

If the ticket is so thin there's nothing to analyze (a one-line title, no context, no linked discussion), say that plainly and ask the user for the missing context rather than fabricating a problem statement to fill space.

## Step 4: Draft the requirements

Use this exact structure:

```markdown
## Requirements

#### Problem statement

1-3 sentences. What's broken, missing, or needed, and for whom. Not how to fix it.

#### Acceptance criteria

- Concrete, testable conditions. Each one should be checkable by someone who didn't write it.
- Prefer "Given/when/then" or plain checklist form over vague statements like "works well."

#### In scope

- What this ticket covers, stated specifically enough to be unambiguous.

#### Out of scope

- Adjacent things explicitly NOT covered here, especially anything a reader might otherwise assume is included.

#### Constraints

- Deadlines, compliance, must-use/must-avoid technology, compatibility requirements. Omit this section if there are none.

#### Dependencies

- Other tickets, teams, or systems this relies on or blocks. Omit this section if there are none.

#### Open questions / risks

- Anything still unresolved that the architect or planner needs to make a call on, or that could change scope later.
```

Write it the way a sharp PM or staff engineer would: specific and decisive about what's known, honest about what isn't. Don't pad sections to look thorough — an empty "Out of scope" section you skip is better than one with filler.

## Step 5: Run review passes

Read `references/requirements-reviews.md` and run each pass against the draft. Append findings as a `## Review notes` section at the bottom — but only include passes that actually surfaced something worth flagging. Skip passes with nothing to flag; don't write "no issues found" entries.

## Step 6: Iterate with the human

Present the requirements and review notes in the chat (not yet written to the tracker). Ask: "Any changes, or should I write this back to the ticket?"

Incorporate feedback, re-run any review passes affected by the changes, and repeat until the user signals approval (e.g. "approved," "LGTM," "looks good," "ship it").

Do not write to the tracker before this approval.

## Step 7: Write back to the tracker

Once approved:

1. Re-fetch the ticket — it may have changed since Step 1.
2. Append the requirements to the end of the existing description. Never overwrite or remove existing content. Separate it from prior content with a blank line.
3. The section must start with the exact header `## Requirements`.
4. Update the ticket:
   - **Linear**: `Linear:save_issue` with the updated `description` and `state` set to `"Ready for Planning"` (or the closest equivalent status that exists in the team's workflow — check `Linear:list_issue_statuses` if `"Ready for Planning"` doesn't exist verbatim, and ask the user which status to use if there's no reasonable match).
   - **Jira**: `Atlassian Rovo:editJiraIssue` with the updated `description`. For status, check `Atlassian Rovo:getTransitionsForJiraIssue` for a transition matching "Ready for Planning" or equivalent, then `Atlassian Rovo:transitionJiraIssue`. If no matching transition exists, tell the user instead of forcing an unrelated one.
5. Confirm to the user that it's written, and include the ticket URL.

## Notes on tone and judgment

- Be decisive about what you do know; reserve hedging for "Open questions / risks," not the rest of the document.
- This skill clarifies _what_ and _done_, not _how_. If you catch yourself writing implementation detail (specific functions, file names, library choices), that belongs in the planning step — cut it or move it to a note for the planner, don't expand it here.
- If the ticket is too vague to analyze at all (no scope, no context, nothing linked), say so and ask the user for more rather than fabricating a problem statement.
- If you discover during analysis that the ticket as written is solving the wrong problem, say that directly to the user before drafting — don't quietly write requirements for a problem you suspect is mis-specified.
