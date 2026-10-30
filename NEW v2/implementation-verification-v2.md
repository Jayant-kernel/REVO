# Revo v2 — implementation gate verification

Date: 2026-10-16. Scope: current implementation only, before live qualification.

VERIFY-PASS: Revo-v2-implementation-scoped — 79 focused tests and 216 integration/regression tests passed; scoped production Ruff passed; strict mypy passed for 203 source files. These are two invocations, not 295 unique tests (the exact-queue tests overlap).

## Acceptance-to-evidence map

| Bounded criterion | Evidence inspected/executed | Result / boundary |
| --- | --- | --- |
| Inventory v2 independent dispatch and bag corrections | verification/adversarial.py:23; business_adversarial.py:144; tests/test_inventory_row_bag_v2.py; tests/test_business_tasks.py; tests/e2e/test_diverse_template_pipeline.py | Fresh passing unit and E2E execution |
| Grade v2 STRONG versus v1 quarantine | tests/e2e/test_diverse_template_pipeline.py; tests/test_grade_v2_domain.py | Fresh passing execution; no promotion performed |
| Unordered bag and initial-new-v1 oracle policy | tests/test_engineering_output_authority.py; verification/oracle_registry.py:48–52 | Fresh passing execution; older advanced oracle versions remain explicit in source |
| Registry 75 versions / 62 IDs / retention 6 | tests/test_registry.py:9–10,26; tests/test_registry.py | Fresh exact assertions passed |
| Queue exact INTEGER/BIGINT opt-in without default serialization change | verification/models.py:75–83; qualification/queue_batches_profile.py:112; comparator.py:294; tests/test_exact_queue_types.py; tests/test_verify_serialization.py | Fresh passing execution; false opt-in field omitted by serializer |
| New queue profile raw/domain/actual-AST/relations | tests/test_queue_batches_profile.py:77–197 | Fresh passing execution, including renamed actual candidates, unsupported/decorative forms and typed casts |
| Equivalent queue structure control matches output but fails structure, never semantic kill | tests/test_queue_batches_profile.py:85–99,125–132,185–197 | Fresh passing execution, including seeded arithmetic/native comparisons |
| Renewal naive microsecond timestamps, one spanning interval, no stitching, cross-year inputs | tests/test_renewal_coverage_profile.py:82–132 | Fresh passing execution; timezone-aware input rejection is intentional, not UTC coercion |
| Renewal actual-candidate AST mutations and relations | tests/test_renewal_coverage_profile.py:135–197; qualification/renewal_coverage_candidate_transforms.py:75–77 | Fresh passing execution with noncanonical sentinel reference, alias forms and discriminating relations |
| Existing integration interfaces and scoped source health | tests/test_record_delivery_v2_integration.py; command results below | Fresh passing execution; no receipt renewal or model call |

Paths above are relative to src/verified_data_factory unless explicitly prefixed tests/.

## Commands actually rerun

```text
python -m pytest -q tests/test_inventory_row_bag_v2.py tests/test_grade_v2_domain.py tests/test_exact_queue_types.py tests/test_queue_batches_profile.py tests/test_renewal_coverage_profile.py tests/test_registry.py tests/test_engineering_output_authority.py
79 passed in 104.42s (0:01:44)

python -m ruff check src/verified_data_factory/verification src/verified_data_factory/task_engine src/verified_data_factory/products src/verified_data_factory/production
All checks passed!

python -m mypy src
Success: no issues found in 203 source files

python -m pytest -q tests/test_record_delivery_v2_integration.py tests/test_exact_queue_types.py tests/test_verify_serialization.py tests/test_business_tasks.py tests/e2e/test_diverse_template_pipeline.py
216 passed in 90.72s (0:01:30)
```

Deterministic execution preceded semantic judgment. No package build or complete suite was run. Git status and relevant tracked diffs were inspected; this checkout already contains substantial unrelated dirty/untracked work. The only authored file in this verification is this report.

## Historical regression evidence and limits

Existing regression-repairs-v1.md records nine repaired nodes, 249 nearby passes, and a retained strict-export failure. Existing tail-repairs-v1.md records three repaired nodes and 41 nearby passes. The user's supplied checkpoint also records the queue 95-pass run and the full-suite three-hour timeout at 89% with 12 failures, followed by 149 tail tests / 146 passes / three fixes. Those historical totals are not freshly rerun totals and are not a same-source complete certificate. Fresh current checks above include the previously repaired inventory/grade paths.

Historical evidence search limitation: a broad *.log search exceeded the search tool's 65536-byte JSON-record limit. Therefore this report does not independently authenticate every retained failing-before log or combine the old runs into a certificate. The regression-repair report is advisory context, not a substitute for the fresh results above.

The source registry visibly declares the five initial-v1 entries at oracle_registry.py:48–52 with authored strategy names. Exact 80-oracle/YAML metadata reconciliation and proof that metadata alone changed are not separately certified here: the tracked diff is against the repository baseline, not a supplied stabilized-before snapshot. This bounded PASS must not be cited as historical edit-provenance attestation.

## Explicit ship/certificate blocker

Final certification remains BLOCKED: there is no same-source complete full-suite certificate, and positive strict export remains deferred until the authorized live20 fresh qualification/dependency renewal. Stale-source rejection must remain strict; no old receipt hashes may be refreshed in place. This result permits proceeding to the separately controlled qualification stage, not admission, promotion, publication, or a qualified claim. All frozen category thresholds, budget and isolation controls remain in force.

No source, YAML, business rule, task/version, frozen control, qualification artifact or promotion state was edited by this verification. No inference/model calls were made. No new semantics were inferred from the user's final metadata-like token sequence.
