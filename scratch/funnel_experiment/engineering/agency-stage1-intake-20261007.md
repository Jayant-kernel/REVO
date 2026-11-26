# Agency Stage 1 intake — 2026-10-07

Status: **BLOCKED before SPEC-FROZEN**

## Requested campaign

Run a FULL-tier, seven-stage Revo SQL verification campaign using the mandatory
agency sequence: research, spec challenge, bounded build briefs, build challenge,
independent verification, and director-owned retries. Preserve the dirty
worktree, frozen assets, scoring authorities, and historical artifacts. Evidence
must be append-only. No commits, pushes, publication, downloads, model calls, or
real-model execution are authorized.

## Intake evidence

- Repository: `C:\Users\jayan\OneDrive\Desktop\Revo`
- Branch/HEAD at intake: `main` / `22ecfeb4e8a92c7c4909c11197dee1e455c4f500`
- Upstream divergence at intake: `0 0` against `origin/main`
- Worktree: extremely dirty; all existing changes treated as preserved user or
  campaign work.
- Frozen lock: `scratch/funnel_experiment/engineering/phase0-lock.json`
- Lock validation: all 8 paths listed under `measurement_sources` and
  `frozen_assets` matched their recorded SHA-256 values.
- `git diff --check`: exit code 0; only line-ending warnings were emitted.
- Historical handoff: `scratch/funnel_experiment/ENGINEERING-HANDOFF.md`
  records a through-Phase-10 regression of 1240 passing tests and explicitly
  says Phase 11 scoring and final smoke were pending. This is historical
  evidence, not a current regression result.

## Blocking ambiguity

The user identifies the exact draft specification as “the seven-stage prompt in
the immediately preceding user message.” That prompt is not present in the
conversation context available to this run and was not found in the repository.
The surviving `ENGINEERING-HANDOFF.md` describes an older 11-phase campaign and
cannot be substituted without changing scope. Therefore goal details,
stage-by-stage acceptance criteria, listed authority files, proof commands, and
required output shapes cannot be frozen faithfully.

The current tool surface also provides no isolated agency worker/subagent
interface. Calling a CLI-backed worker would violate the explicit prohibition on
real-model calls. The mandatory researcher/challenger/builder/verifier role
separation therefore cannot begin unless a non-model isolated worker mechanism
is made available or the user changes that constraint.

## Required unblock

1. Re-send the exact seven-stage prompt (including its authority-file list and
   stage acceptance/proof requirements).
2. Provide a permitted non-model isolated worker mechanism, or explicitly
   authorize an alternative execution arrangement. No alternative is assumed.

No source, test, frozen, scoring, or historical artifact was modified during
this intake.

Verdict: INTAKE-BLOCKED
