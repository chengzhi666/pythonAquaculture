# Python Review Checklist

Use this checklist when reviewing Python changes in this repository.

## Correctness

- Does changed logic match intended behavior in all common paths?
- Are edge cases handled (empty input, null values, missing keys, timeout)?
- Are return types and error paths consistent with callers?

## Reliability

- Are retries and timeouts appropriate for network operations?
- Are exceptions either handled with context or intentionally propagated?
- Are resources cleaned up (db cursor, connection, file handle)?

## Data Safety

- Are write operations idempotent where needed?
- Could this create duplicate rows or partial state?
- Are transaction boundaries correct for multi-step writes?

## Compatibility

- Do parser/schema assumptions still match real input?
- Are imports/path handling stable for both package and script execution?
- Do changes preserve behavior on existing configs and env vars?

## Observability

- Are failures logged with enough context to debug quickly?
- Is sensitive data excluded from logs?
- Are warning/error levels used appropriately?

## Test Coverage

- Is there at least one test for each high-risk behavior change?
- Are negative cases covered (error path, invalid input)?
- Are flaky tests introduced by sleep/time/network assumptions?
