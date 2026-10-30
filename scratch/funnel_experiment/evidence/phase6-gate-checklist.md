# Phase 6 SaaS v2 Coverage-Aware Fuzzing Checklist

- [x] Frozen paused-run guard passed before the fuzz run.
- [x] Threshold file was hashed and its timestamp predates the run start.
- [x] 300 valid deterministic random cases ran for each seed: `1`, `43`, and `94001`.
- [x] Every named behavior has at least 20 cases for every seed.
- [x] Python oracle, recursive reference SQL, and chained-join SQL agree on all 900 cases.
- [x] Duplicate ordering keys and inconsistent entity groups are rejected by the oracle.
- [x] No divergence was found; no reduced counterexample or new permanent regression was required.
- [x] Focused Phase 6 regression passed.
- [x] Certified full regression passed after the source/test change.
- [x] Frozen paused-run guard passed after certification.
- [x] No model call, frozen-run mutation, commit, push, or publication occurred.
