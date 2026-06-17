# Performance Review Passes

Run each pass that applies to the diff's surface. Only report a finding if it's a real issue at realistic scale — not a quota, and not big-O purity for its own sake.

## 1. Query efficiency pass

For any new or modified database/ORM query: is it inside a loop that should instead be a single batched query (N+1)? Does it fetch more columns/rows than needed (`SELECT *` where a few fields would do, no pagination on a result set that can grow unbounded)? Is there a new query pattern that isn't covered by an existing index, on a table large enough or growing fast enough for that to matter? Does a new write happen inside a loop where batching would cut round-trips significantly?

## 2. Loop and collection pass

For any loop over a collection: does the size of that collection grow with something outside the developer's control (user count, table rows, time)? Is there nesting that creates quadratic or worse behavior over data that can realistically be large? Is the same computation repeated inside a loop when it could be hoisted outside (recomputing something constant on every iteration)? Is a linear search (`.find()`, `.includes()`) used repeatedly where a set/map lookup would avoid it, and does that matter given realistic input size?

## 3. Caching and recomputation pass

Is something expensive (a query, a parse, a network call) being recomputed on every call when memoizing or caching it would be safe and valuable? Conversely — does a new cache lack any invalidation/expiry strategy, risking staleness or unbounded memory growth? Is a value computed once and then needed again recomputed instead of reused within the same diff's logic?

## 4. Memory pass

Does this diff load an entire dataset into memory where streaming or pagination would do (reading a large file/result set fully when only part is needed)? Does a new data structure (cache, buffer, queue) have a bound, or can it grow without limit under normal operation? Are large objects retained longer than needed (held in closures, module-level state) when they could be released?

## 5. Blocking and concurrency pass

Does a request-handling path make a blocking/synchronous call (network, disk, subprocess) where the runtime expects non-blocking behavior, and could that stall other work? Are independent operations done sequentially when they could run concurrently with a meaningful time savings? Is a lock or mutex held longer than necessary, serializing work that didn't need to be serialized?

## 6. Realistic-scale sanity check (apply to every finding before reporting it)

Before tagging anything Critical, ask: given what this code actually handles (internal tool vs. public hot path; tens of rows vs. millions; once-a-day batch job vs. per-request), does the inefficiency identified actually cause a problem anyone would notice? An O(n²) algorithm over a list capped at 20 items is not a finding. The same algorithm over a list that grows with all users in the system is.

## 7. Adjacent-concern flag (not a full review)

If a performance issue is also a potential security issue (e.g. an unbounded query an attacker could trigger repeatedly — a DoS vector) or a correctness issue (e.g. a cache with no invalidation that will also serve wrong data, not just stale-fast data), flag that the adjacent concern exists and which skill should look at it (`security-reviewer` or `code-reviewer`), without writing the full finding for that other domain here.
