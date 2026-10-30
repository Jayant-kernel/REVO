# Observed queue harness v2 — harness-only repair

The original observed candidate is rejudged with the normal SandboxExecutor and
verify_candidate/DerivedTaskBackend path. No core, original task, candidate SQL,
protocol, raw response, source helper, or existing report was changed.

The harness validates physical provenance with the existing
company_generation_experiment.validate_attempt_binding(RUN, 0, candidate, events)
and the actual budget journal. It decodes the HTTP wrapper's JSON-string body,
reads the frozen Pydantic generation config through model_dump/attributes, and
checks that mutation is present before accessing it. Original run JSON hashes
and the budget journal bytes must remain unchanged.

Each invocation exclusively creates its artifact directory and JSON files beneath
pytest's unique tmp_path. Repeats never write into NEWobservedQueue-v35 or any
existing report. The controller may copy these temporary artifacts for retention.

## First verification

Command: `python -m pytest tests/test_queue_observed_forms.py -s -q`

```text
actual candidate: all attributed semantic witnesses discriminate; aliases preserved
actual SQL seed=1: 300 typed matches; all 27 behaviors >=20
actual SQL seed=43: 300 typed matches; all 27 behaviors >=20
actual SQL seed=94001: 300 typed matches; all 27 behaviors >=20
6 passed in 83.47s (0:01:23)
```

Native verdict: PASS/STRONG; SUCCEEDED execution; mutation score 1.0;
18/18 semantic kills, complete coverage. Full native execution, verification,
and original-hash/binding report:

`C:\Users\jayan\AppData\Local\Temp\pytest-of-jayan\pytest-653\test_native_v35_rejudge0\observed-queue-v35-harness-v2`

Command: `python -m mypy src`

```text
Success: no issues found in 203 source files
```

The first Ruff run identified only import grouping in the changed test; the
extra separator was removed. Native console output was shortened; complete
mutation details remain in verification.json and report.json.

## Gate

This is not qualification, queue admission, model accuracy certification, or
promotion. Original slot history remains intact. Budget remains 33 attempts /
468.498 seconds; the test asserts the journal is byte-for-byte unchanged. Freeze
the current core; the parent owns the next 20-profile renewal before queue
admission. No provider, model, download, human, or Git write action was performed.
