# Crawler Failure Patterns

Use this guide to map symptoms to likely root causes.

## Zero Results Suddenly

Likely causes:
- Selector drift
- Anti-bot challenge page returned
- Cookie/session expired

Checks:
- Compare saved response HTML to expected page structure.
- Verify login/cookie freshness and status codes.
- Inspect parser assumptions for missing nodes.

## Partial Results

Likely causes:
- Pagination stopped early
- Intermittent timeout
- Dedup logic too aggressive

Checks:
- Confirm page traversal counters and stop condition.
- Inspect retry counts and timeout exceptions in logs.
- Validate key used for dedup.

## Frequent Timeouts or Connection Errors

Likely causes:
- DNS/network instability
- Too short timeout
- Remote throttling

Checks:
- Validate timeout settings and retry backoff.
- Compare failure rate by target host/time window.
- Add jitter and lower concurrency if throttled.

## Write Failures or Missing Rows

Likely causes:
- Schema mismatch
- Transaction rollback
- Type conversion error

Checks:
- Inspect SQL error logs and failing payload sample.
- Validate schema field names and types.
- Confirm commit/rollback behavior in error path.
