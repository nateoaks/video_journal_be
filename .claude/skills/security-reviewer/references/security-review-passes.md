# Security Review Passes

Run each pass that applies to the diff's surface (see Step 1 of the main skill). Only report a finding if something is genuinely exploitable or a real hardening gap — not a quota of comments.

## 1. Authentication and authorization pass

For any new or modified endpoint, handler, or action: is there an explicit auth check, and is it the _right_ check (not just "logged in" when it should be "owns this resource" or "has this role")? Look specifically for: checks present on the main path but missing on an alternate path (e.g. a bulk-action variant of an already-protected single-action endpoint), authorization checked on read but not on write (or vice versa), and IDs taken from user input used to fetch records without verifying the requester actually owns/can access that record (IDOR).

## 2. Input validation and injection pass

For any user- or external-supplied input: is it validated/sanitized before use, and is it used safely at every sink it reaches (database query, shell command, file path, HTML output, template, deserializer, regex)? Check specifically for: string concatenation building a query or command instead of parameterization, file paths built from user input without normalization (path traversal), and user input reflected into output without escaping (XSS) or interpreted by a template engine.

## 3. Secrets and credentials pass

Scan the diff for hardcoded API keys, passwords, tokens, or connection strings — including ones added "temporarily" or in test/example code. Check that any new secret usage reads from environment variables or a secrets manager, not literals. Check that logging statements added in this diff don't log credentials, tokens, full request/response bodies that might contain secrets, or other sensitive fields (passwords, SSNs, full card numbers).

## 4. Data exposure pass

For any new API response, log line, or error message: does it return more than the caller needs (e.g. an internal object dumped wholesale instead of the specific fields required)? Check that error messages returned to the client don't leak internal details (stack traces, query structure, file paths, library versions) that aid an attacker. Check that any new data storage holds only what's actually needed.

## 5. Dependency pass (only if manifest changed)

For any new or upgraded dependency: is it from a legitimate, actively maintained source? Note if a new dependency is unusually small/unmaintained for what it's being asked to do (a sign of unnecessary supply-chain risk for trivial functionality). Flag if a version pin was loosened in a way that could pull in an untested major version automatically.

## 6. Deserialization and dynamic execution pass

Flag any use of unsafe deserialization (e.g. unpickling/deserializing untrusted data with a format that allows arbitrary code execution), `eval`/dynamic code execution on anything derived from input, or dynamic require/import paths built from user input.

## 7. Session and token handling pass (only if auth/session code touched)

Check token/session expiry is enforced, not just set. Check tokens aren't placed somewhere they'll leak (URL query params, logs, client-readable storage for anything that should be httpOnly). Check that logout/invalidation actually invalidates server-side state, not just clears a client-side flag.

## 8. Non-security flag (out of scope here)

If something looks like a correctness bug with no security implication, note that it exists but defer the actual write-up to `code-reviewer` — don't produce a full correctness finding in this skill's output.
