# Premium Golden SQL release acceptance specification

## Status

**FACT** — This specification freezes the acceptance gates for the proposed
`premium-qualification-080` release before generation begins.

**INFERRED** — Passing every gate supports a buyer-oriented target of 93/100.
The score remains 52/100 until human review, rights clearance, independent replay,
and the utility experiment produce their required evidence.

## Release composition

- Exactly 80 accepted Golden records.
- Exactly 8 accepted records from each of the 10 registered SQL families.
- Coverage of all 16 tracked SQL constructs.
- Coverage of at least 15 of 17 tracked edge-case categories; 17 of 17 is the
  preferred target.
- At least 40 materially different business instructions.
- At least 10 schema fingerprints across at least 5 business domains.
- No schema contributes more than 12 records.
- No exact duplicate, cross-split sibling, normalized SQL AST overlap, or task
  lineage overlap.

Seed variation by itself does not count as instruction, schema, or semantic
diversity.

## Record acceptance

Every accepted record must have:

1. A valid task and schema contract.
2. Successful execution in the declared dialect.
3. Strong verification.
4. Independent oracle agreement.
5. Passing property and metamorphic checks.
6. Mutation score 1.0 using only valid semantic mutants.
7. At least three discriminating fixture instances.
8. No unresolved contamination match.
9. Two blind independent SQL-review decisions.
10. Third-reviewer adjudication for every disagreement.
11. Final human-review status `PASS`.
12. Complete content-bound identity and provenance.

## Release gates

The release is blocked while any condition below is true:

- a component has `UNKNOWN` commercial-use or redistribution status;
- any row lacks two independent review decisions;
- any review disagreement remains unresolved;
- any severity-1 or severity-2 defect remains open;
- any record or lineage crosses evaluation and training roles;
- any exact external benchmark match is unexplained;
- clean-environment replay changes a record hash, verdict, or health metric;
- the preregistered utility experiment is missing or fails its useful-effect
  threshold;
- the release package lacks the datasheet, Croissant metadata, license, notices,
  audit report, contamination report, replay report, utility report, and change
  map.

## Utility decision rule

The experiment compares the unchanged base model under four treatments: no added
data, current 46-row data, proposed 80-row data, and a size-matched control. It
uses at least three seeds and a sealed evaluation set containing unseen schemas.

The proposed release passes when the pre-registered primary metric has a 95%
confidence interval for improvement that excludes zero, reaches the buyer-approved
minimum useful effect, and produces no material regression in a critical family.

## Required approvals

The frozen release requires recorded approval from:

1. The responsible engineer.
2. An independent SQL reviewer.
3. The authorized legal or commercial-rights owner.
4. The product owner.

Published releases are immutable. Corrections create a new semantic version with
a row-level change map and retained prior hashes.
