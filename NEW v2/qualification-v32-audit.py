"""Read-only bounded checkpoint audit, deliberately not a qualification replay."""
from __future__ import annotations

import json
import runpy
import time

scope = runpy.run_path("NEW v2/qualification-v32.py")
root, base = scope["ROOT"], scope["BASE"]
read = scope["read"]
frozen = scope["stable"]()
records = scope["authoritative_records"](root)
checkpoints = []
for path in sorted(base.glob("*/*-checkpoint.json")):
    data = read(path)
    ref = scope["ArtifactRef"].model_validate(data["receipt"])
    envelope = read(scope["artifact"](root, ref))
    # Source-only validation: no duplicate SQL census or qualification claim.
    from verified_data_factory.verification.receipt_models import ReceiptV2
    from verified_data_factory.verification.receipt_validation import validate_sources

    validate_sources(root, ReceiptV2.model_validate(envelope))
    checkpoints.append(dict(path=path.relative_to(root).as_posix(), category=data["category"],
                            metrics=data["metrics"], checks_run=data["checks_run"]))
failures = [dict(path=p.relative_to(root).as_posix(), **read(p))
            for p in sorted(base.glob("failure-*.json"))]
report = dict(status="STOPPED_CONTROLLER_FAILURE_NOT_QUALIFIED", checked_at=time.time(),
    scope="frozen bytes/runtime/budget and emitted-envelope metadata only; no full SQL census",
    frozen_sources_unchanged=True, frozen_source_files=len(frozen["hashes"]),
    runtime_unchanged=True, budget=scope["usage"](), model_calls_this_run=0,
    authoritative_records=len(records), historical_records_unchanged=records == frozen["originals"],
    emitted_category_receipts=len(checkpoints), checkpoints=checkpoints,
    newly_published_bundles=len(list(base.glob("*/delivery-result.json"))),
    completed_bundles=len(list(base.glob("*/bundle.json"))),
    fuzz_batches=len(list(base.glob("*/fuzz-batch-*.json"))), failures=failures,
    required_completion=dict(individually_qualified=20, category_receipts=140, latest_quarantined=42,
                             latest_registry_ids=62),
    completion_claim=False, source_fix_authorized=False,
    next_step="Do not edit frozen producer or old hashes. Obtain authorization for a new producer identity/freeze with collision-safe append-only progress names.")
scope["write_new"](base / "stopped-checkpoint-audit.json", report)
print(json.dumps({k: v for k, v in report.items() if k not in {"failures", "checkpoints"}}, sort_keys=True))
for item in checkpoints:
    print(json.dumps(item, sort_keys=True))
for failure in failures:
    print(json.dumps({k: failure[k] for k in ("path", "error_type", "error", "status")}, sort_keys=True))
