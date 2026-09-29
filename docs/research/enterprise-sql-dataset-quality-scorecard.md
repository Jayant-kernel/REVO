# Decision scorecard — enterprise SQL dataset quality

Date: 2026-09-26. Full reasoning:
`docs/research/enterprise-sql-dataset-quality-research.md`.
TQ-004 numbers are PROVISIONAL (re-verification running).

## Weights (100)

Correctness proof 25 · Integrity 15 · Coverage/diversity 15 ·
Docs/provenance 15 · Audit 10 · Reproducibility 10 · Legal/commercial 10.

## Scores

| Category (max) | Production-001 | TQ-003 (latest final) | Future commercial target |
|---|---:|---:|---:|
| Correctness proof (25) | 20 | 20 | 25 |
| Integrity (15) | 11 | 13 | 15 |
| Coverage/diversity (15) | 6 | 9 | 14 |
| Docs/provenance (15) | 12 | 12 | 15 |
| Audit (10) | 3 | 3 | 10 |
| Reproducibility (10) | 9 | 9 | 10 |
| Legal/commercial (10) | 1 | 1 | 8 |
| **Total** | **62** | **67** | **97** |

## Band interpretation (house scale, no public standard)

- < 60: not ready for production.
- 60–74: controlled qualification only.
- 75–84: limited production batch / public sample.
- 85–94: customer pilot.
- ≥ 95: commercial release.

## Recommendation

**READY FOR ANOTHER CONTROLLED QUALIFICATION.** Production-001 (62)
and TQ-003 (67) sit in the qualification band: machinery proven,
evidence gaps (audit, license, diversity, provisionality) block
production, pilots, and sale. The P0–P2 roadmap in the main report is
the exit path.
