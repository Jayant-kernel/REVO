# Phase 8 Funnel Contract Inventory

The frozen paused run is not modified. No model is loaded, queried, or selected.

| Contract | Active version | Phase 8 status | Evidence |
| --- | ---: | --- | --- |
| `sql.funnel.saas_activation_payment` | 2 | FULLY_VERIFIED | Phase 3 mutations, Phase 4 differential SQL, Phase 5 private corpus, Phase 6 coverage-aware fuzzing, and Phase 7 full regression. |
| `sql.funnel.logistics_parcel_delivery` | 1 | QUARANTINED | Superseded forward by v2; v1 remains replayable only. |
| `sql.funnel.logistics_parcel_delivery` | 2 | QUARANTINED | Named bounded-consecutive oracle, dedicated fixture, window and self-join SQL formulations, and six source-derived killed breakages exist; production verifier returned `INCONCLUSIVE`. |
| `sql.funnel.checkout_paid_session` | 1 | QUARANTINED | Existing named oracle/fixture evidence does not meet the Phase 8 qualification gate. |
| `sql.funnel.curriculum_gate_completion` | 1 | QUARANTINED | Existing named oracle/fixture evidence does not meet the Phase 8 qualification gate. |
| `sql.funnel.kyc_document_approval` | 1 | QUARANTINED | Existing named oracle/fixture evidence does not meet the Phase 8 qualification gate. |
| `sql.funnel.parcel_exception_recovery` | 1 | QUARANTINED | Existing named oracle/fixture evidence does not meet the Phase 8 qualification gate. |
| `sql.funnel.support_resolution_chain` | 1 | QUARANTINED | Existing named oracle/fixture evidence does not meet the Phase 8 qualification gate. |
| `sql.funnel.completion` | 3 | QUARANTINED | Frozen mutation-applicability excludes it from the experiment population. |

Only SaaS v2 is fully verified. The package quarantine manifest is authoritative for production, distinct
selection, and experiment admission. Qualification here is verifier evidence,
not a release, quality, or model-performance claim.
