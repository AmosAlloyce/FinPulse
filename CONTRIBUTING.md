# Contributing

FinPulse uses small, reviewable changes and treats data contracts like public APIs.

1. Create a branch and describe the business or operational outcome.
2. Add or update tests before changing a contract, quality rule, or mart.
3. Run `make format`, `make lint`, `make test`, and `make local-demo`.
4. For schema changes, document compatibility and a replay/backfill plan.
5. For pipeline changes, include expected throughput, failure behavior, and observability.

Pull requests should separate functional changes from mechanical formatting and must not include real personal or financial data.

