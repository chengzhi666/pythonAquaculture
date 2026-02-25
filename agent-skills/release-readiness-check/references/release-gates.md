# Release Gates

A release is ready only if all gates pass.

## Gate 1: Code Health

- Linting/static checks pass for changed code.
- Tests pass for changed and critical dependent paths.
- No unresolved high severity review findings.

## Gate 2: Config Safety

- Required env vars documented and validated.
- No secrets in tracked files.
- Production toggles and endpoints verified.

## Gate 3: Data Safety

- DB writes are idempotent where required.
- Migration/DDL impact understood and reversible.
- Rollback strategy exists for data-impacting changes.

## Gate 4: Runtime Reliability

- Retry/timeout policy sane for external calls.
- Failure handling does not silently drop critical data.
- Backpressure and partial-failure behavior understood.

## Gate 5: Operational Readiness

- Logging is sufficient for incident triage.
- Alerting exists for critical job failure.
- Owner and response path are clear.

## Decision Rule

- Ship: all gates pass.
- Ship with conditions: no blockers, but documented high-risk warnings with owner and deadline.
- No-ship: any blocker in code health, config safety, or data safety.
