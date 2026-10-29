"""Final source-current runtime renewal; retained witnesses, no inference."""
from __future__ import annotations

import argparse
import importlib.util
import time
import traceback
from uuid import uuid4

spec = importlib.util.spec_from_file_location("runtime_v34", "NEW v2/qualification-v34.py")
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
v = prior.v
v.PRODUCER = "NEW v2/qualification-v35.py"
v.BASE = v.ROOT / "scratch/funnel_experiment/engineering/qualified-receipts-v35"
v.EXPLICIT = (*v.INPUTS, v.PRODUCER, "NEW v2/qualification-v34.py",
              "NEW v2/qualification-v33.py",
              "scratch/company_evaluation/record-delivery-v2/SPEC.md",
              "NEW v2/implementation-verification-v2.md",
              "NEW v2/queue-observed-challenge-v35.md")


def freeze():
    v.safety()
    assert not v.BASE.exists(), "v35 identity already consumed"
    records = v.authoritative_records(v.ROOT)
    assert len(records) == 20
    assert {(r["contract_id"], r["contract_version"]) for r in records} == v.SUPPORTED
    budget = v.usage()
    assert budget["physical_attempts"] == 33 and round(budget["generation_seconds"], 3) == 468.498
    assert not budget["unfinished_attempts"]
    sources = v.source_hashes()
    hashes = {**sources, **{n: v.digest(v.ROOT / n) for n in v.EXPLICIT}}
    for folder, pattern in (("src", "*.py"), ("scripts", "*.py"), ("tests", "*.py"), ("templates", "*.yaml")):
        hashes.update({p.relative_to(v.ROOT).as_posix(): v.digest(p) for p in (v.ROOT / folder).rglob(pattern)})
    v.BASE.mkdir()
    v.write_new(v.BASE / "freeze.json", dict(global_sources=sources, hashes=hashes,
        originals=records, runtime=v.runtime_identity(), budget=budget, producer=v.PRODUCER,
        created_at=time.time(), scope="fresh rules/tests; current replay of retained witnesses; no regeneration"))
    v.stable()
    v.progress(phase="FROZEN", originals=20, supported=20, source_files=len(hashes), model_calls=0)


def audit():
    frozen = v.stable()
    records = v.authoritative_records(v.ROOT)
    assert len(records) == 20
    assert {(r["contract_id"], r["contract_version"]) for r in records} == v.SUPPORTED
    from verified_data_factory.verification.readiness import effective_evidence
    from verified_data_factory.verification.receipt_validation import validate_sources
    from verified_data_factory.verification.receipt_models import ReceiptV2
    for record in records:
        pair = record["contract_id"], record["contract_version"]
        folder = v.BASE / (pair[0] + "-v" + str(pair[1]))
        result = v.read(folder / "delivery-result.json")
        assert result["qualification"]["eligible"]
        assert v.read(folder / "bundle.json") == record
        effective_evidence(v.ROOT, record)
        for category, ref in record["evidence"].items():
            assert ref["path"].startswith(v.BASE.relative_to(v.ROOT).as_posix() + "/")
            parsed = ReceiptV2.model_validate(v.read(v.artifact(v.ROOT, v.ArtifactRef.model_validate(ref))))
            validate_sources(v.ROOT, parsed)
            assert v.read(folder / (category + "-public-replay.json"))["reason"] == "fresh executed evidence"
    registry = v.load_builtin_registry()
    latest = {(tid, registry.get(tid).version) for tid in {t.template_id for t in registry.list()}}
    historical = v.read(v.ROOT / "manifests/package-a-contract-quarantine.json")["quarantines"]
    historical_pairs = {(r["contract_id"], r["contract_version"]) for r in historical}
    nonlatest = historical_pairs - latest
    quarantined = latest - v.SUPPORTED
    assert len(latest) == 62 and len(quarantined) == 42 and len(nonlatest) == 4
    assert quarantined <= historical_pairs
    assert len(list(v.BASE.glob("*/*-checkpoint.json"))) == 140
    v.stable()
    report = dict(status="QUAL20_SOURCE_BOUND_AUDIT_PASS", latest_registry_ids=62,
        latest_qualified=20, latest_quarantined=42, nonlatest_quarantines=sorted(nonlatest),
        historical_effective_quarantined_versions=46, category_receipts=140,
        audit_scope="source/journal-bound completed individual public qualifications; no duplicate full SQL replay",
        source_files=len(frozen["hashes"]), budget=v.usage(), model_calls=0,
        human_review="PENDING", sharing="BLOCKED", accepted80=False)
    v.write_new(v.BASE / ("final-audit-" + uuid4().hex + ".json"), report)
    v.progress(**report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "preflight", "advance", "audit"))
    parser.add_argument("--seconds", type=float, default=1800)
    args = parser.parse_args()
    try:
        if args.action == "advance":
            prior.advance(args.seconds)
        elif args.action == "preflight":
            prior.preflight()
        else:
            globals()[args.action]()
    except Exception as exc:
        if v.BASE.exists():
            v.write_new(v.BASE / ("failure-" + uuid4().hex + ".json"), dict(
                error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc(),
                recorded_at=time.time(), pid=v.os.getpid(), model_calls=0, status="STOPPED_GATE_FAILURE"))
        raise
