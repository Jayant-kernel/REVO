# Golden Selection

Status: **implemented** (Phase 5). A record becomes GOLDEN only through
hard gates plus dataset-aware selection — never by verdict alone.

## Hard gates (per record, evaluated in order)

1. Task valid (`TASK_INVALID` otherwise → EXCLUDED).
2. Verification verdict PASS (`VERIFICATION_FAIL` + code / `INCONCLUSIVE`).
3. Original execution passed; hidden/properties/metamorphic passed.
4. Suite strong enough: strength WEAK → `WEAK_SUITE`; scored mutation
   below `mutation_min_score` → `MUTATION_THRESHOLD`. NOT_APPLICABLE is
   not a pass on its own — it simply skips the threshold.
5. No hard contamination (`CONTAMINATION` + flag types).
6. Audit: FAIL → `AUDIT_FAIL`; required-but-undecided → `AUDIT_REQUIRED`.

## Dataset-aware selection (deterministic)

- **Dedup**: at most one GOLDEN per EXACT/SEMANTIC group, preferring
  stronger evidence (strength, then mutation score), ties by
  candidate_id. Others get `EXACT_DUPLICATE`/`SEMANTIC_DUPLICATE`.
- **Quotas**: `family_quotas` or `max_family_share` caps keep the
  strongest-first prefix per family (`FAMILY_QUOTA`).
- Everything sorts by candidate_id; no timestamps enter decisions.

## Reproducibility

Same records + config + versions → identical decisions and reasons
(tested, including byte-identical exports).

## Relationship to verification strength

Phase 4 already gates PASS on suite strength; Phase 5 re-checks the
threshold from stored evidence (defense in depth, no recomputation).
A correct candidate with a weak suite is INCONCLUSIVE upstream and can
never become GOLDEN here — by construction, not by accident.
