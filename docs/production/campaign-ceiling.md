# Campaign Ceiling Diagnostic

## Status

**DIAGNOSTIC ONLY.** The official commercial-readiness assessment remains
**52/100**. This document does not rescore a product, authorize a release, or
assert that any release gate is satisfied.

The frozen acceptance specification is the authority: the score remains 52
until human review, rights clearance, independent replay, and the utility
experiment produce their required evidence
([release specification](../release-93-spec.md#status)).

## Evidence Authority

| Source | Read-only finding | Use in this diagnostic |
| --- | --- | --- |
| `docs/release-93-spec.md` | Defines the frozen 80-record composition, record acceptance, release gates, utility decision rule, and required approvals. | Determines which gates automation cannot close. |
| `docs/research-roadmap-90.md` | Defines the frozen 100-point rubric and its evidence targets. | Supplies the rubric dimensions and weights. |
| `docs/production/phase3-score-mapping-20261002.md` | Assigns the AI-only component bounds. | Supplies the component arithmetic below; it is not a score update. |
| `scratch/funnel_experiment/evidence/phase10-contract-evidence-index.json` | Current contract-level readiness evidence. | Primary current technical-readiness source. |
| `scratch/funnel_experiment/evidence/phase10-readiness-count-20261005.json` | Independently validates the index and matrix linkage. | Confirms the derived readiness counts. |

The Phase 10 count report is `PASS`: it validates the index hash and matrix
linkage, and reports 57 contract/version pairs, 50 `FULLY_VERIFIED`, 7
`QUARANTINED`, 8 funnels, and 1 fully verified funnel. The Phase 10 campaign
handoff instead says 49 fully verified and zero fully verified funnels. That
handoff conflicts with the structured count report and its listed matrix row
for `sql.funnel.saas_activation_payment@2`; this diagnostic relies on the
independently validated structured artifacts and records the handoff as stale.
Neither count is evidence of commercial readiness or release eligibility.

## Theoretical Automation Ceiling

The ceiling is recomputed from the frozen rubric dimensions and the existing
AI-only mapping, without crediting any unobserved work:

| Rubric dimension | Weight | AI-only bound | Why automation stops there |
| --- | ---: | ---: | --- |
| Semantic correctness assurance | 15 | 13 | Independent dual review and adjudication are required for the remaining credit. |
| Verification discrimination | 15 | 15 | Automation can add the required fixtures, independent-oracle evidence, mutation accounting, and replay evidence. |
| Instruction quality and task independence | 10 | 8 | Mechanical screening can help, but reviewer approval is required for the higher target. |
| Diversity and independent coverage | 15 | 14 | The frozen roadmap retains residual diversity and generalization risk for a compact product. |
| Realism and demonstrated difficulty | 10 | 7 | Automated measurement can improve the technical evidence, but cannot establish buyer acceptance or utility. |
| Human review and adjudication | 10 | 1 | Tooling and AI-authored fixtures do not substitute for blind human decisions and adjudication. |
| Identity, provenance, reproducibility | 10 | 9 | The final credit requires clean-environment independent replay and a signed report. |
| Separation and contamination assurance | 5 | 4 | Unknown external corpora prevent proof of universal absence of overlap. |
| Rights and commercial clearance | 5 | 0 | Signed, release-specific owner clearance is not automatable. |
| Documentation and demonstrated utility | 5 | 2 | Documentation can be drafted, but a positive preregistered utility study is required for the higher target. |
| **Arithmetic planning bound** | **100** | **73** | Sum of the component bounds only. |

This 73 is a theoretical automation ceiling, not an attained diagnostic score,
not a replacement for the official 52, and not release authorization. It
cannot override any frozen binary release gate.

## Multidimensional Profile

| Dimension | Evidence-grounded status | Diagnostic implication |
| --- | --- | --- |
| Contract readiness | 50 of 57 contract/version pairs are marked `FULLY_VERIFIED`; seven are quarantined. Seven of eight funnel contracts remain quarantined. | Do not use the catalog as an unqualified funnel-selection source. |
| Verification | The readiness index records fixture, named independent-oracle, adversarial-case, mutation-applicability, registry, reference-SQL, and focused-test checks per contract. | This is technical contract evidence, not row-level premium acceptance. |
| Release composition | The frozen specification requires exactly 80 accepted records, eight per family, all tracked constructs, at least 15 tracked edge categories, at least 40 materially different instructions, and schema/domain caps. | No evidence here establishes a qualified 80-record release pool. |
| Human review | Every accepted record needs two blind independent decisions, adjudication for disagreements, and final human `PASS`. | Unmet human gate; automation cannot convert pending or absent decisions into review evidence. |
| Reproducibility | Same-host and paused-run evidence exist; the frozen specification requires clean-environment independent replay without changed hashes, verdicts, or health metrics. | Independent replay remains a release blocker. |
| Rights | The frozen release gate fails while commercial-use or redistribution status is `UNKNOWN`; release-specific owner approval is required. | Rights clearance remains a release blocker. |
| Contamination and separation | The frozen gates prohibit train/evaluation crossing and unexplained exact external matches. | Automated screening can improve evidence, but cannot prove absence against unknown corpora. |
| Utility | The frozen utility rule requires a preregistered multi-seed comparison, buyer-approved minimum useful effect, confidence interval excluding zero, and no critical-family regression. | No utility outcome is asserted. |

## Automation Opportunities

Automation may produce evidence for, but must not claim closure of:

- Contract-specific fixtures, independent-oracle checks, property and metamorphic
  checks, valid-mutant accounting, and deterministic replay receipts.
- Versioned external-fingerprint reports, split-isolation checks, and explicit
  unresolved-match registers.
- Release-composition measurement for family, construct, edge, instruction,
  schema, and domain constraints.
- Reproducible provenance bundles, content hashes, change maps, datasheet
  drafts, Croissant metadata drafts, notices inventories, and audit-report
  drafts.
- Preregistered utility-study materials and machine-generated outcome reports
  after an authorized study; the study's buyer threshold and decision remain
  owner-controlled.

Automation cannot create human review decisions, adjudicate as an independent
reviewer, grant rights, attest an independently operated replay, approve a
buyer threshold, or declare a commercial release.

## Phase 11 Checklist

- [x] Read frozen rubric and release documents without editing them.
- [x] Preserve the official 52/100 assessment.
- [x] Recompute the planning ceiling from the documented component bounds:
  `13 + 15 + 8 + 14 + 7 + 1 + 9 + 4 + 0 + 2 = 73`.
- [x] Verify the structured Phase 10 readiness count and record its conflict
  with the stale handoff rather than silently harmonizing it.
- [x] Make no model call, source edit, frozen-file edit, score change, commit,
  push, publication, or release action.
- [x] Run the frozen paused-run guard after this documentation change.
- [x] Run documentation diff validation; a certified full regression is not
  required because no source or test file changed.

## Events

| Event | Status | Evidence |
| --- | --- | --- |
| Frozen-rubric inspection | Complete | `docs/release-93-spec.md`, `docs/research-roadmap-90.md`, and `docs/production/phase3-score-mapping-20261002.md` were used read-only. |
| Readiness-count reconciliation | Complete | `phase10-readiness-count-20261005.json` reports `PASS`; the conflicting handoff is explicitly retained as stale evidence. |
| Ceiling calculation | Complete | The component-bound arithmetic is recorded above and has not changed the official assessment. |
| Frozen paused-run guard | Complete | `scripts/package_a_paused_run_guard.py` reported `PASS`: all 15 forward-baseline files matched with no missing, unexpected, or mismatched paths. The transient report was written outside the repository. |
| Documentation validation | Complete | `git diff --check` passed. No source or test file changed, so no certified full regression was required. |

## Blockers

- Seven quarantined contracts, including seven funnel contracts, remain excluded
  from fully verified funnel selection.
- The frozen release requirements for record-level blind review, adjudication,
  rights clearance, independent clean-environment replay, contamination
  resolution, utility evidence, and approvals are unmet.
- The Phase 10 campaign handoff's readiness count conflicts with the validated
  structured count report and should be corrected only through a separately
  evidenced status update.
