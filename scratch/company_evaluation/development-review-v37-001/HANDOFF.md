# Development review preview V37-001 — COMPLETE

Open the frozen reviewer artifact at:
`artifacts/internal-previews/development-review-v37-001/START-HERE.md`.

This is an INTERNAL early-feedback preview of eight exposed TRAIN examples.
It does not replace full80, close W14, authorize external sharing, establish a
quality score or satisfy pending human review.

## Completion

**P01–P08: 8/8 preview tasks complete.** This denominator is separate from the
original 16 requirements. All eight pages are readable and traceable; original
model SQL/public base inputs/typed expected results match the existing delivery.
There are 8 retained candidate PASS/STRONG records, 8 illustrative A replays and
8 fresh authoritative B replays. No candidate rejudgments, qualification renewals
or full-suite reruns were necessary.

Three workers had disjoint ownership: A examples, B replay, C review documents.
A then performed a separate internal AI review with its earlier authorship and
access explicitly disclosed. Original and postintegration review reports are
retained; no human, blind or fully independent review claim is made.

## Exact artifacts and sizes

| Artifact | Files | Bytes |
|---|---:|---:|
| Frozen reviewer layer (including manifest and selected audit results) | 51 | 322,114 |
| Required unchanged V37 package | 123,854 | 602,194,502 |
| Manifest-declared release assets within that package | 123,765 | 528,602,604 |

Reviewer manifest SHA256:
`2e2b63e30a49ae88a838ff29b6c8b747987b98b7e97d950d294f3fe7f92a58c1`.
The manifest excludes itself from its member hashes; final total above includes it.
The reviewer layer does not replace the large dependency package for B validation.

Package manifest SHA256:
`a470e889b701571af653bb30a1d9d3036a828096e8a7370f858d2788f01784eb`.
Anchor `9d8566217753b3fd1187961b0e2009ca81e4b3a16c0f4f25e99a15f165d9f266`;
supplied context `8233f895f6e58b10ea827b8d16b709aca8a9d36cc1ff56795275882fe075fb80`.
The dependency census explains 49,029 initially discovered files + 74,726
recursively retained qualification/replay inputs + 10 release assets. Broad
historical source discovery and recursive receipt dependencies explain the size;
no smaller authoritative closure was proved or fabricated.

## Tested reviewer workflows

From a fresh copy of the reviewer layer (already-installed Python/DuckDB only):

```powershell
python -B .\replay\replay.py illustrative --examples .\examples --result .\illustrative-results-001.json
```

New results need new names. A is only the retained public/base fixture illustration:
8/8 column/type/ordered-typed-value/count/truncation matches; it cannot establish B.

Full B was actually executed from fresh
`C:/Users/jayan/AppData/Local/Temp/opencode/review-preview37-copy-001/`:

```powershell
python -B .\replay\replay.py validate --package "C:\Users\jayan\OneDrive\Desktop\Revo\artifacts\internal-deliveries\v37-original8-001\original8" --work "C:\Users\jayan\AppData\Local\Temp\opencode\preview37-work-001" --output "C:\Users\jayan\AppData\Local\Temp\opencode\preview37-result-001" --timeout 7200
```

Work/output identities above are consumed. Replace suffixes for future runs. Never
write into the frozen reviewer artifact or immutable package. B requires the full
local package, pinned installed runtime and configured Docker sandbox/image; no
original checkout imports, automatic installs or downloads are used. Detailed
evidence references may require original checkout/package context; five optional
suite-negative artifacts remain nondurable local Temp references, explicitly
disclosed. The reviewer is not claimed standalone for all evidence traversal.

Full B results: VALID / 8 records / 123765 declared files / zero errors/warnings;
all eight original bundled check_source calls observed PASS. Native invocation
exit0, no timeout, approximately 1294s including preparation. Supervisor bounds
the whole command at 10800s; the native child is in a kill-on-close Windows Job
and has a 7200s native bound. Commands/PIDs/start/log/terminal/per-record evidence
are in audit. `finalization-correction.md` explains the duplicate outer/child
supervision filename collision; actual child metadata remains retained, and
outer tool terminal is not confused with child observation.

Focused checks: six tests PASS, including typed/result/hash tampering, fresh identity
rejection, SELECT boundary, fresh-location CLI and Windows Job ownership. Scoped
Ruff PASS for new reviewer tooling. Final source references and Markdown links
were checked; every executable file matches the fresh-copy tested bytes. No
production source changes were made, so no full regression or renewal was repeated.

## Findings fixed and deferred

- Fixed M01: renewal navigation label now describes coverage for every eligible
  episode, matching the original question rather than suggesting only uncovered
  episodes are returned.
- Fixed final document pin: the fresh-copy/navigation clarification changed
  START-HERE after indexing; the fail-closed assertion caught it before artifact
  creation and the index pin was corrected. Original evidence was untouched.
- Deferred, disclosed: optional old suite Temp evidence durability, authoritative
  dependency slimming, non-Windows portability. These do not invalidate the
  bounded tested A/B claims. No unresolved review correctness/integrity/replay
  blockers remain. Review snapshot hashes describe their exact review times;
  coordinator final checks cover later bounded document integration changes.

## Preserved baseline and next action

Both existing package inventories and all 687 V37 qualification inputs remain
unchanged; the source identity matches the prior final suite. No new model calls.
Budget journal is still **36 / 558.327 seconds / no unfinished attempts**.
Original checklist remains **2 completed / 5 partial / 8 blocked / 1 unstarted**,
**2/16=12.5%**. Accepted80=0; company-showcase accepted=0; human review PENDING;
external sharing BLOCKED; utility NOT_MEASURED; no rating assigned.

The original suite remains 1980 passed / 2 symlink-privilege skips / 22
record_property warnings, strict complete certificate false. Historical native
crashes remain unresolved. These consequences were disclosed, not waived.

**Next product action:** obtain domain/SQL reviewer feedback with the included
form, then triage substantive findings into the next bounded product/coverage
milestone before spending generation calls. For external review, the user/owner
must approve the exact preview scope, selected-output rights/attribution and
recipient/destination; internal preview completion grants no sharing permission.
