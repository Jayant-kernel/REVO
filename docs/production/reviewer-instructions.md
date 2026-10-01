# SQL review instructions (draft rubric `sql-review-v1`)

For the 80-row premium pool, the coordinator first runs the read-only
composition and automated-evidence screen. A nonzero exit means the pool is
not ready to be presented as a premium release candidate:

```powershell
factory quality premium-check --golden <verified-candidates.jsonl> --output <pre-review-report.json>
```

The coordinator then freezes the exact Golden JSONL into a new review package:

```powershell
factory quality review-freeze --golden <verified-candidates.jsonl> --out-dir <new-review-directory> --premium
```

Without `--premium`, the command creates a *diagnostic* review package, not a
premium release candidate. The automated screen still cannot prove material
instruction novelty, AST/semantic uniqueness, external benchmark cleanliness,
or independent adversarial fixture design. The coordinator must resolve those
checks separately before final acceptance.

Each reviewer sees `items.jsonl`, which contains the business question,
schema, SQL, expected result, edge-case labels, and verification summary.
Reviewers do not see the oracle implementation or each other's decision.
The coordinator assigns distinct human identities to the first and second
slots and controls access to the decision journal.
The coordinator records decisions serially; concurrent writes to the same
journal are not supported. Reviewer IDs are not an authentication mechanism.

For each record, check whether the instruction has a clear business meaning,
the schema supports it, the SQL implements it for all relevant rows, the
expected result matches the instruction, and the edge cases distinguish
plausible incorrect SQL. Check naturalness as an analyst request. Choose
`PASS`, `FAIL`, or `UNCLEAR` and give a concrete reason. For a defect, describe
the smallest counterexample or ambiguous phrase. The coordinator may present
calibration examples, but calibration decisions are not release decisions.

```powershell
factory quality review-decide --package <review-directory> --record-id <record-id> --reviewer-id <human-id> --slot first --verdict PASS --reason "..." --rubric-version sql-review-v1
factory quality review-decide --package <review-directory> --record-id <record-id> --reviewer-id <different-human-id> --slot second --verdict PASS --reason "..." --rubric-version sql-review-v1
factory quality review-status --package <review-directory>
```

When first and second verdicts disagree, a third distinct reviewer enters an
`adjudicator` decision. Changed SQL, task wording, schema, expected result, or
verification evidence requires a new frozen package and new decisions.
Journal entries are append-only and hash-chained; never edit them. A correction
to a review decision also requires a new package rather than rewriting an
entry. The coordinator validates the named humans and access procedure before
using the evidence.

Only after all items have final PASS may the coordinator derive quality input
for a later product build:

```powershell
factory quality review-export --package <review-directory> --golden <same-verified-candidates.jsonl> --out-dir <new-derived-evidence-directory>
```

The export contains `qualities.json` and `review-summary.json`. The source
file's hash and every source row are verified. This is a review-evidence
artifact, not commercial release approval. Rights, independent replay,
utility, and the other frozen release gates remain separate.
