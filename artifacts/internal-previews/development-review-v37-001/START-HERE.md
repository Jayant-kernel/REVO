# Revo — eight-record DEVELOPMENT REVIEW PREVIEW

**Internal early feedback only. External sharing BLOCKED. Human review PENDING.**
These are eight exposed development/TRAIN examples, not unseen evaluation material.
Full80 accepted=0; original requirements completed=2/16 (12.5%); W14 remains open.

## Review in this order

1. Read [the overview](review/overview.md) and [dataset card](review/dataset-card.md).
2. Pick a business question below. Inspect its schema, original answer, input and
   expected output; record ambiguity or correctness concerns in the feedback form.
3. Run lightweight **A** if you want to execute the public fixture. Read the
   [evidence index](review/evidence-index.md) for realistic authored wrong answers
   and recorded correct alternatives. None of these controls is relabeled as a
   model failure or a new independent/human review.
4. For complete trust/qualification/candidate replay, use **B** and its pinned
   dependency package. A passing public fixture is not B validation.
5. Submit findings using [feedback.md](review/feedback.md). Consult
   [limitations](review/limitations.md) and [sharing decisions](review/sharing-readiness.md).

| Example | Question |
|---|---|
| [01 — Fulfillment SLA](examples/01-fulfillment-sla.md) | Delivered and on-time fulfillments by warehouse |
| [02 — Grade revisions](examples/02-grade-revisions.md) | Select the valid winning grade revision |
| [03 — Previous play](examples/03-previous-play.md) | Previous completed play in each playback history |
| [04 — Lowest quote](examples/04-lowest-quote.md) | Lowest eligible quote with declared tie-break |
| [05 — Requested titles](examples/05-language-titles.md) | Requested-language titles, preserving unmatched rows and duplicates |
| [06 — Shipping Pareto](examples/06-pareto-shipping.md) | Nondominated quotes within each lane |
| [07 — Renewal coverage](examples/07-renewal-coverage.md) | Whether each eligible episode has qualifying member renewal coverage |
| [08 — Queue batches](examples/08-queue-batches.md) | Three ordered batches within each queue |

## A — illustrative public/base-fixture replay (quick start)

Supported and tested: Windows, Python 3.12.10, already-installed DuckDB 1.5.5.
No installation or download is performed. Copy this reviewer layer to a **fresh
working directory**, then open PowerShell in that copy (keep the frozen preview
artifact unchanged):

```powershell
python -B .\replay\replay.py illustrative --examples .\examples --result .\illustrative-results-001.json
```

Choose a new result filename on every run. Expected: exit 0, `passed: true`, eight
record results with all comparison flags true. Per-record actual/expected data
and comparisons are under `records` in the JSON output. No checkout or package
dependency is needed for A; provenance source paths are metadata, not accessed.

A runs the original SQL on retained small public/base fixtures. It compares exact
column names/types, observed row sequence, typed values, count and truncation.
Some questions permit unordered results: agreement in the retained sequence is
an observation on the tested runtime, not a new ordering contract. A checks neither
qualification nor hidden/mutation evidence. See [replay instructions](replay/README.md).

## B — authoritative validation (separate, slower workflow)

You must also have the immutable dependency package at a known path:
`artifacts/internal-deliveries/v37-original8-001/original8/`.
The reviewer layer alone is NOT its standalone replacement. The package is
123,854 files / 602,194,502 bytes; 123,765 files are declared release assets.
See [why these dependencies exist](replay/DEPENDENCIES.md).

First inspect the pins (does NOT execute native replay):

```powershell
python -B .\replay\replay.py check-inputs --package "C:\Users\jayan\OneDrive\Desktop\Revo\artifacts\internal-deliveries\v37-original8-001\original8"
```

For new full validation, require the installed pinned dependencies and existing
Docker sandbox described in `replay/DEPENDENCIES.md`. No model/server inference is
needed. Use short, **absent**, disjoint work/output directories with existing
parents; replace the suffixes each time:

```powershell
python -B .\replay\replay.py validate --package "C:\Users\jayan\OneDrive\Desktop\Revo\artifacts\internal-deliveries\v37-original8-001\original8" --work "C:\Users\jayan\AppData\Local\Temp\opencode\preview37-work-001" --output "C:\Users\jayan\AppData\Local\Temp\opencode\preview37-result-001" --timeout 7200
```

Replace the package path for your environment. The immutable package is read;
all writing validation uses a fresh full clone. Do not run a validator directly
against the delivered package. Expected: worker exit0, `bundled-validation-result.json`
VALID with 8 records/zero errors/zero warnings; all eight
`per-record-results.json` statuses PASS. Read `terminal.json` and stdout/stderr
on failure. Large copy preparation precedes the bounded native phase; coordinator
integration additionally bounds the whole invocation. Details in `replay/README.md`.

## What completion does and does not mean

This preview packages already verified examples for useful internal feedback.
The original suite remains 1980 passed/2 skipped/22 warnings; strict complete
certificate false; historical native incidents unresolved. This work establishes
no general SQL accuracy, training improvement, human approval or quality score.
Rights, attribution, exact recipient and distribution scope require approval
before any external review. Nothing in these instructions grants that approval.

Coordinator integration and internal review results are recorded in `audit/`:
[fresh-location A/B result](audit/integration-result.json),
[native per-record results](audit/native-per-record-results.json), and
[postintegration review closeout](audit/REVIEW-CLOSEOUT.md).
The separate reviewer pass discloses prior access and is neither blind nor human.
