"""New runtime identity: current replay of retained witnesses, never old hashes."""
from __future__ import annotations

import argparse
import importlib.util
import json
import time
import traceback
from uuid import uuid4

spec = importlib.util.spec_from_file_location("retained_v33_controller", "NEW v2/qualification-v33.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
v.PRODUCER = "NEW v2/qualification-v34.py"
v.BASE = v.ROOT / "scratch/funnel_experiment/engineering/qualified-receipts-v34"
v.EXPLICIT = (*v.INPUTS, v.PRODUCER, "NEW v2/qualification-v33.py",
              "scratch/company_evaluation/record-delivery-v2/SPEC.md",
              "NEW v2/implementation-verification-v2.md")
from verified_data_factory.verification.readiness import receipt, effective_quarantine
from verified_data_factory.verification.receipt_validation import validate_sources
from verified_data_factory.verification.receipt_models import ReceiptV2

original_writer = v.writer


def writer(pair):
    w = original_writer(pair)
    # Regenerate all rules and attributed tests; reuse SQL witnesses only after
    # current writer validation AND an independent public serialized replay.
    rules_path = w.destination / "rules-collected-detail.json"
    if not rules_path.exists():
        v.write_new(rules_path, w.rules().model_dump(mode="json"))
    if pair == v.NEW[0]:
        old = v.ROOT / "scratch/funnel_experiment/engineering/qualified-receipts-v33" / (pair[0] + "-v1")
        for category in v.REQUIRED:
            if category in {"rules", "named_tests"}:
                continue
            target = w.destination / (category + "-collected-detail.json")
            if not target.exists():
                reference = v.ArtifactRef.model_validate(v.read(old / (category + "-checkpoint.json"))["receipt"])
                payload = v.read(v.artifact(v.ROOT, reference))
                detail = v.DETAILS[category].model_validate(payload["details"])
                v.write_new(target, detail.model_dump(mode="json"))
                v.write_new(w.destination / (category + "-retained-provenance.json"), dict(
                    previous_receipt=reference.model_dump(), prior_overall="NOT_QUALIFIED",
                    scope="retained witnesses only; new envelope requires current replay"))
    original_receipt = w.receipt

    def checked_receipt(category, detail):
        ref = original_receipt(category, detail)
        data, reason = receipt(v.ROOT, json.loads(json.dumps(ref.model_dump(mode="json"))), *pair, category)
        if data is None:
            raise ValueError(category + ": independent serialized receipt replay: " + reason)
        v.write_new(w.destination / (category + "-public-replay.json"), dict(
            receipt=ref.model_dump(), reason=reason, checked_at=time.time(),
            scope="independent public readiness.receipt after actual JSON serialization"))
        return ref

    w.receipt = checked_receipt
    return w


v.writer = writer


def freeze():
    # The imported controller is an immutable input; only this new producer is
    # allowed to create the v34 freeze and new envelopes.
    v.freeze()


def preflight():
    v.stable()
    w = writer(v.NEW[0])
    checkpoint = w.destination / "rules-checkpoint.json"
    assert not checkpoint.exists(), "preflight identity already consumed"
    detail = v.RulesDetail.model_validate(v.read(w.destination / "rules-collected-detail.json"))
    ref = w.receipt("rules", detail)
    payload = v.read(v.artifact(v.ROOT, ref))
    v.write_new(checkpoint, dict(category="rules", receipt=ref.model_dump(),
        source_hashes=w.sources, metrics=payload["metrics"], checks_run=payload["checks_run"],
        scope="fresh rules; actual serialized public replay before any fuzz"))
    v.stable()
    v.progress(phase="CHEAP_RULES_PUBLIC_JSON_REPLAY_PASS", contract=v.NEW[0][0])


def advance(seconds):
    assert (v.BASE / (v.NEW[0][0] + "-v1") / "rules-public-replay.json").exists(), "preflight required before collection"
    v.advance(seconds)


def audit():
    frozen = v.stable()
    records = v.authoritative_records(v.ROOT)
    assert len(records) == 20
    assert {(r["contract_id"], r["contract_version"]) for r in records} == v.SUPPORTED
    results = []
    for record in records:
        pair = record["contract_id"], record["contract_version"]
        assert all(ref["path"].startswith(v.BASE.relative_to(v.ROOT).as_posix() + "/") for ref in record["evidence"].values())
        result = v.qualify(v.ROOT, record)
        assert result["eligible"], (pair, result)
        for ref in record["evidence"].values():
            validate_sources(v.ROOT, ReceiptV2.model_validate(v.read(v.artifact(v.ROOT, v.ArtifactRef.model_validate(ref)))))
        results.append(dict(contract_id=pair[0], contract_version=pair[1], **result))
        v.progress(phase="AUDIT_CURRENT_QUALIFIED", contract=pair[0])
    registry = v.load_builtin_registry()
    latest = {(tid, registry.get(tid).version) for tid in {t.template_id for t in registry.list()}}
    quarantined = [dict(contract_id=tid, contract_version=version) for tid, version in sorted(latest)
                   if effective_quarantine(v.ROOT, tid, version)]
    historical = v.read(v.ROOT / "manifests/package-a-contract-quarantine.json")["quarantines"]
    nonlatest = sorted({(r["contract_id"], r["contract_version"]) for r in historical} - latest)
    assert len(latest) == 62 and len(quarantined) == 42
    assert len(list(v.BASE.glob("*/*-checkpoint.json"))) == 140
    v.stable()
    report = dict(status="PUBLISHED_QUAL20_SOURCE_BOUND_AUDIT_PASS", results=results,
        latest_registry_ids=62, latest_qualified=20, latest_quarantined=42,
        category_receipts=140, historical_quarantine_entries=len(historical), nonlatest_quarantines=nonlatest,
        effective_latest_quarantines=quarantined, budget=v.usage(), model_calls=0,
        source_files=len(frozen["hashes"]), source_freeze="freeze.json", checked_at=time.time(),
        human_review="PENDING", sharing="BLOCKED", accepted80=False)
    v.write_new(v.BASE / ("final-audit-" + uuid4().hex + ".json"), report)
    v.progress(phase=report["status"], qualified=20, quarantined=42, registry=62, receipts=140)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "preflight", "advance", "audit"))
    parser.add_argument("--seconds", type=float, default=900)
    args = parser.parse_args()
    try:
        if args.action == "advance":
            advance(args.seconds)
        else:
            globals()[args.action]()
    except Exception as exc:
        if v.BASE.exists():
            v.write_new(v.BASE / ("failure-" + uuid4().hex + ".json"), dict(
                error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc(),
                recorded_at=time.time(), pid=v.os.getpid(), model_calls=0, status="STOPPED_GATE_FAILURE"))
        raise
