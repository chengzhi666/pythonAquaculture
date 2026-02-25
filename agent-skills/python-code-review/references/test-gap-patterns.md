# Common Test Gaps

Use these patterns to spot missing tests during review.

## Branch Gaps

- New branch added, but tests only cover previous happy path.
- Fallback path added without test asserting fallback trigger conditions.

## Error-Path Gaps

- Exception handling changed without a test that forces the exception.
- Retry logic changed without tests for final failure behavior.

## Data-Integrity Gaps

- Insert/update logic changed without duplicate and idempotency tests.
- Parsing rules changed without malformed input tests.

## Config Gaps

- New env var introduced without default/invalid/missing value tests.
- Path or encoding handling changed without cross-platform test coverage.

## Integration Gaps

- Crawler selector update without fixture/html snapshot regression test.
- DB schema touchpoint changed without integration test on write path.
