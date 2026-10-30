# Gate 2 Checklist

- Oracle import list and differential label: `phase2-saas-rule-matrix`.
- Rule-to-evidence matrix: `phase2-saas-rule-matrix`.
- Named SaaS tests: `tests/test_saas_funnel_oracle.py`, `16 passed`.
- Metamorphic tests: `tests/test_saas_funnel_oracle.py`, `16 passed`.
- Normalized legacy comparison: `phase1-legacy-saas-normalized-comparison-r2`.
  It records actual normalized rows `[]`, oracle rows `[["north", 160],
  ["south", 0]]`, a mismatch, and the unrecovered-historical-assignment caveat.
- Paused-run guard: `phase2-content-identity-post.json`, PASS, 15 files.
- Certified full regression: terminal summary `1018 passed in 1618.41s`.
  Launch/post source identity matched, including the untracked source-content hash.

Gate 2: PASS. The SaaS oracle/SQL relationship remains differential verification;
independent authorship is deferred.
