# Precise continuation decisions — proposals, not changed contracts

Grade@2 immutable identity **APPROVED_BY_USER** through the in-session contract
decision. Implement that forward version and qualification; old @1 stays unchanged
and quarantined. Warehouse@2 forward auxiliary clarification is also
**APPROVED_BY_USER**, preserving mandatory HAVING and requiring separate structural
evidence. Other dedup business specifications remain **DECISION_REQUIRED**.
Existing contracts, quarantine history and frozen
acceptance remain unchanged. This document does not authorize promotion or claim
that named-oracle registration establishes a complete public domain.

## Deduplication inventory

All four latest registered dedup contracts were read:

- `sql.dedup.latest@2`: chooses highest event_time then event_id, projecting
  event_type. Valid rows can tie on both winner fields but differ in event_type.
  Duplicate_key includes event_type, so these are not identical business duplicates.
  No uniqueness constraint or remaining tie rule is declared.
- `sql.dedup.education_grade_revisions@1`: the V21 retained conflicting-grade tie
  remains unresolved; do not reuse that old proof as a qualification.
- `sql.dedup.payments_latest_profile@1`: generic eligible-value ledger does not
  specify full latest-profile selection, effective/revision ordering, stable market
  membership and whether amount is a snapshot or event measure. Its registered
  aggregate oracle does not establish named latest-profile semantics.
- `sql.dedup.refund_prefer_approved@1`: generic eligible-value ledger does not
  define the approval-state vocabulary/precedence, refund business key, revision
  selection and amount source sufficiently to establish the named objective.

No inspected contract resolves all of its declared valid-input cases. Keep them
quarantined and continue independent specified work.

## Concrete grade@2 proposal

Approved forward data-domain contract:

1. Preserve latest *valid* recorded_at, then highest revision_id per student/course.
2. Declare `(student_id, course_id, recorded_at, revision_id)` an immutable valid
   revision identity: repeated valid rows at that identity must agree on grade.
3. Permit exact repeated rows; they do not create another winner. Reject conflicting
   valid payloads explicitly as out-of-domain instead of selecting by insertion order.
4. Ignore cancelled corrections before winner selection. Pairs with no valid row
   have no output. Preserve existing output columns/order and explicit NULL types.
5. Publish a new version, new domain/schema rules, adversarial ties, nonidentical
   correct formulations, semantic mutants, relations and all three executed campaigns.

User selected **Immutable identity (Recommended)**: equal valid revision identities
must agree on grade, exact repeats allowed, conflicts rejected. This is a business
specification clarification, not human SQL review or sharing approval. Do not add
alphabetical-grade priority or global ID uniqueness. Old grade@1 remains unchanged.

## Warehouse throughput@1 inspection

The business calculation is explicit: posted units in 2025, summed per warehouse,
total >=40 with zero/negative values and omitted below-threshold/absent groups.
The instruction additionally mandates an aggregate HAVING clause. Two obligations
need precise treatment before the existing rule-proof authority can qualify it:

- `count_semantics: count_star_counts_rows` declares COUNT behavior, but the public
  query asks only for warehouse and SUM(units). A wrong sum is not a clause-specific
  proof about an unprojected COUNT. Do not manufacture that attribution.
- `null_handling: sum_ignores_nulls` coexists with declared non-null units. A NULL
  unit is an invalid schema input; it cannot be passed off as a valid semantic kill.
- A result-equivalent CTE/filter formulation without HAVING violates the explicit
  structural instruction while returning the same typed result. This requires
  separate executed structural-rule evidence, not a fabricated semantic mismatch.

Concrete forward proposal: warehouse throughput@2 keeps the business outputs and
all existing threshold/date/group rules, states `posted_rows_summed_once` and
`units_are_non_null`, and makes the HAVING requirement an explicit structural
obligation. **User decision:** forward auxiliary clarifications approved for @2.
HAVING is already
mandatory in @1 and must remain enforced; supporting its separate structural proof
is an engineering task, not permission to reinterpret it as optional. Do not
silently alter @1 or count a syntactic violation as a non-equivalent semantic mutant.
Proceed with other unambiguous business profiles while this disposition is pending.
