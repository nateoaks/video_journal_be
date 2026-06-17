---
name: release-prep
description: Prepares a release — determines the version bump from merged PRs since the last release (semver), writes/maintains the CHANGELOG from those PRs, and creates a version tag — then stops. Does NOT trigger any deploy, push to production, or run deploy scripts/pipelines; if the user wants an actual deploy, tell them this skill doesn't do that and ask how their deploy is triggered. Always requires explicit human approval before tagging or writing the CHANGELOG — no autonomous path, unlike dependency-upgrade. Use whenever the user says "cut a release", "prepare a release", "what's changed since the last release", "bump the version", or "update the changelog". This skill owns the CHANGELOG that documentation and dependency-upgrade skills explicitly defer to it.
---

# Release Prep

Prepares a release: figures out the version bump, writes the CHANGELOG, creates the tag. That's the full scope. **This skill does not deploy anything** — no pipeline trigger, no deploy script, no push to a hosting/cloud platform. If "release" in your setup also means "and now it's live," that trigger step doesn't exist yet; this skill stops at a tagged, documented release ready for whatever deploy mechanism you use.

Every release prepared by this skill requires explicit human approval before anything is written or tagged — there's no autonomous path here, unlike `dependency-upgrade`. The work here is comparatively infrequent and the cost of a wrong version number or a bad tag is annoying to unwind, so the bar stays at "always ask."

## Scope boundary

Owns: determining the version bump, writing/maintaining `CHANGELOG.md` from merged PRs since the last release, and creating the version tag (and a corresponding tracker entry/notification if relevant).

Does not own:
- **Triggering any deploy** — explicitly out of scope. If asked to deploy, say plainly that this skill doesn't do that, and ask how the user's deploy is actually triggered (CI on tag push, a manual pipeline run, a separate script) so they can do that step themselves or point to the right tool.
- **Deciding whether code is ready to release** (that's what code-reviewer/security-reviewer/test-runner-qa already gated before merge) — this skill assumes anything merged to the release branch already passed those gates. It doesn't re-review merged code.
- **Routine dependency bumps and their changelog-worthiness calls** — `dependency-upgrade` already flags what's changelog-worthy when it merges; this skill picks that up rather than re-deciding it.

## Trigger

Activate when the user says "cut a release," "prepare a release," "what's changed since the last release," "bump the version," or "update the changelog."

## Step 1: Establish the range

Find the last release: most recent tag matching the project's versioning convention (check existing tags, e.g. `git tag --sort=-creatordate | head`), or the last entry in `CHANGELOG.md` if tags aren't used consistently. Get every merged PR (or, if PRs aren't used, every merge commit) between that point and the current release branch tip.

If there's no prior release (first one ever), say so and ask the user for the intended starting version rather than assuming `0.1.0` or `1.0.0` — that's a real choice, not a default.

## Step 2: Classify changes and determine the bump

For each merged PR/commit in range, classify it: breaking change, feature/enhancement, fix, dependency update (routine or CVE — `dependency-upgrade`'s PRs are usually labeled clearly enough to tell), documentation-only, or internal/chore with no user-visible effect.

Determine the version bump per semver (or the project's actual convention, if it deviates — check existing tag history for the pattern actually in use rather than assuming strict semver):
- Any breaking change → major.
- No breaking changes, at least one feature → minor.
- Only fixes/patches (including dependency patches) → patch.

If something is ambiguous (a PR's actual user-facing impact isn't clear from its title/description alone), open it and check rather than guessing the safer-sounding category — both over- and under-stating the bump cause real problems downstream.

## Step 3: Draft the CHANGELOG entry

Use Keep a Changelog-style structure (or match whatever structure the existing `CHANGELOG.md` already uses, if it differs):

```markdown
## [<version>] - <date>

### Breaking
- <change, plain language, what consumers need to do — omit section if none>

### Added
- <feature, plain language — omit section if none>

### Fixed
- <fix, plain language — omit section if none>

### Security
- <CVE patches by package and CVE ID, omit section if none>

### Dependencies
- <routine dependency bumps, can be a single summarized line if there are many — omit section if none>
```

Write each entry in plain, user-facing language describing the effect, not the PR title verbatim or internal implementation detail — "Fixed an issue where exports could silently drop the last row" not "Fix off-by-one in export loop." Omit empty sections rather than including them with nothing in them.

## Step 4: Present for approval

Show the user: the determined bump and why (which PRs drove it), the full draft CHANGELOG entry, and the proposed tag name. Ask for explicit approval — and ask now whether they want this skill to stop after tagging or whether they'll handle the actual deploy trigger themselves, so the handoff is clear either way.

Incorporate any requested changes (reclassifying a bump, rewording an entry, adjusting the version) and re-present until approved. Do not write or tag anything before this approval — there's no autonomous path for this skill, regardless of how routine the release looks.

## Step 5: Apply

Once approved:
1. Prepend the new entry to `CHANGELOG.md` (don't overwrite prior entries).
2. Update the version in the project's manifest (`package.json`, `pyproject.toml`, `Cargo.toml`, etc.) to match.
3. Commit both changes together with a clear message (e.g. `chore: release v<version>`).
4. Create the tag: `git tag -a v<version> -m "<version> — <one-line summary>"`.
5. Push the commit and tag only after confirming with the user that pushing now is correct (some teams want the tag pushed immediately to trigger CI; others want a separate go-ahead). If unsure, ask rather than assuming push-on-tag is wanted.

## What NOT to do

- Do not run, trigger, or write a deploy script/pipeline/cloud command — that's outside this skill entirely, not just deferred.
- Do not tag or write the CHANGELOG without explicit approval, regardless of how mechanical the release looks.
- Do not invent a version number convention different from what the project's tag history already shows.
- Do not bury a breaking change in the "Fixed" or "Dependencies" section to make a release look smaller than it is — breaking changes always get their own section, prominently, even if there's only one.
- Do not silently re-decide what dependency-upgrade or documentation already flagged as changelog-worthy — incorporate it, don't second-guess their classification without a clear reason.
