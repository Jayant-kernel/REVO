# Package A completion reassessment

The previous blanket statement that every phase is complete is withdrawn. A
passing pytest suite establishes software regression status, not fulfillment of
every phase's acceptance criteria. Package A is the requested audit scope; no
definitions for the additional approximately 40 phases have been supplied.

## Phase-by-phase assessment

| Phase | Assessment | Evidence or outstanding requirement |
|---|---|---|
| 0 | Current guard verified; historical identity unproven | 15-file baseline guard; identity before its creation cannot be reconstructed |
| 1 | Evidence exists; original provenance unproven | Historical SaaS assignment remains unproven, as documented |
| 2 | Focused semantics verified | SaaS oracle tests pass; differential verification, independence unproven |
| 3 | Evidence exists; certification not fully re-audited | Full mutant/test lineage and historical inconclusive reason require further review |
| 4 | Current formulations verified on focused suite | Recursive and join SQL differential tests pass |
| 5 | Original gate deficient; executable corpus repaired | Original corpus has 8 wrong queries; new repair has 22 witnessed executable wrong queries and a regression test; complete resealing/alternative qualification must be reviewed |
| 6 | Evidence exists; focused fuzz verification pending final smoke | Recorded 900-case campaign; coverage instrumentation must not be inferred from pytest count alone |
| 7 | Historical software checks exist | Fresh complete regression required for this repair |
| 8 | Partial qualification with explicit quarantine | Most funnel contracts remain quarantined, not fully verified |
| 9 | Audit artifacts exist; strict acceptance not fully re-audited | AST, semantic diversity and all vacuous guard boundaries require additional review |
| 10 | Strict readiness deficient | Generator determines readiness from structural checks without requiring all per-contract challenge/fuzz/metamorphic records |
| 11 | Incomplete | Component-level numeric diagnostic, recomputed human/AI allocation and minimum human path above 85 not established |
| 12 | Generic runner incomplete against declared interface | Call key omits contract version; provider does not send declared temperature/top_p/seed; fake gate alone does not establish real-run parity |
| 13 | Accounting claim corrected; strict protocol completion unproven | Ledger contains 36 calls; report counted 12 reused baselines as extra calls. Separate smoke receipts and provider sampling lock need verification |
| 14 | Incomplete | Report inherits unproven gate claims and omits sufficient detail for several acceptance criteria |

## Actual Phase 13 call accounting

| Arm | Actual logged model calls | Reported including reused candidates |
|---|---:|---:|
| Devstral baseline | 6 | 6 |
| Devstral feedback | 12 | 18 |
| Qwen baseline | 6 | 6 |
| Qwen feedback | 12 | 18 |
| Total | 36 | 48 |

Reused initial candidates are not fresh calls. All arms still report zero
verified passes. Historical experiment artifacts have not been edited.

## Score implications

The official score remains 52/100. The earlier 73 ceiling is a planning mapping,
not earned points. No higher numeric diagnostic is justified by this audit.
The new executable challenge evidence improves verification discrimination, but
does not supply human semantic approval, rights clearance, independent signed
replay, buyer-approved utility thresholds, or a training utility result.

## Reproduction

```
python scripts/package_a_reaudit.py
python scripts/package_a_challenge_repair.py
python -m pytest tests/test_package_a_challenge_repair.py -q
```

The challenge repair is private: never include its SQL or counterexamples in
model prompts, retry feedback, training data, or model-visible logs.
