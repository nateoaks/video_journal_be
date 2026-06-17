Review the current diff (uncommitted changes, or the branch/commit given in $ARGUMENTS) using `code-reviewer`, `test-runner-qa`, and — if the diff touches auth, input, secrets, or dependencies — `security-reviewer`, and — if it touches queries, loops, or hot paths — `performance-reviewer`.

Present a single consolidated findings list grouped by severity across all skills that ran, rather than four separate reports.
