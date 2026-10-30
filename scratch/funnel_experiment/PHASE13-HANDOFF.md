# Phase 13 Hard Stop

Phase 13 cannot resume against its locked protocol. The existing authoritative experiment artifact at `scratch/funnel-generation-experiment/phase13-authoritative/` records runner SHA-256 `08bab6558e185c750eee5dd80a7db004649feb90e709c5c5aa3cc64b851f105d`, while the current runner SHA-256 is `b070a7f248d61616a3a819575f87c875faa21c9f51b1af1770913732c8ee0786`.

The existing ledger has 36 rows: `pinned-baseline` 6, `pinned-feedback` 12, `qwen-baseline` 6, and `qwen-feedback` 12. Running or resuming with a different runner would change the locked Phase 13 protocol. The authoritative rules require a hard stop rather than changing source locks, arms, population, retries, or call plan.

Next action: resolve the runner-lock discrepancy without changing the locked protocol, or explicitly authorize a new Phase 13 protocol. No further model calls were made in this session after detecting the mismatch.
