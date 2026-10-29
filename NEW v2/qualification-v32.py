"""Append-only runtime qualification; no source repair, inference or old hash edits."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from scripts.company_generation_experiment import BUDGET, budget_usage, source_hashes
from scripts.engineering_campaign import safety, write_new
from scripts.engineering_qualification_authority import promote
from scripts.engineering_qualification_receipts import INPUTS, profile
from scripts.engineering_receipt_artifacts import ArtifactWriter, LocalCollector, SUPPORTED
from verified_data_factory.task_engine import load_builtin_registry
from verified_data_factory.task_engine.models import TaskInstance
from verified_data_factory.verification.readiness import REQUIRED, authoritative_records, qualify
from verified_data_factory.verification.receipt_models import (
    ArtifactRef, ChallengeDetail, FixtureDetail, FuzzCase, FuzzDetail,
    MutationDetail, RelationsDetail, RulesDetail,
)
from verified_data_factory.verification.receipt_observations import observation_fixture, observed_behaviors
from verified_data_factory.verification.receipt_validation import artifact, digest, runtime_identity

PRODUCER = "NEW v2/qualification-v32.py"
BASE = ROOT / "scratch/funnel_experiment/engineering/qualified-receipts-v32"
NEW = (("sql.retention.renewal_coverage", 1), ("sql.windows.queue_batches", 1))
EXPLICIT = (*INPUTS, PRODUCER, "scratch/company_evaluation/record-delivery-v2/SPEC.md",
            "NEW v2/implementation-verification-v2.md")
DETAILS = dict(rules=RulesDetail, relations=RelationsDetail, mutation=MutationDetail,
               challenge=ChallengeDetail, fixture_diversity=FixtureDetail, fuzz=FuzzDetail)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def usage():
    return budget_usage([json.loads(line) for line in BUDGET.read_text().splitlines() if line])


def stable():
    frozen = read(BASE / "freeze.json")
    assert source_hashes() == frozen["global_sources"], "global source closure changed"
    assert runtime_identity() == frozen["runtime"], "runtime changed"
    for name, checksum in frozen["hashes"].items():
        assert digest(ROOT / name) == checksum, "source changed: " + name
    assert usage() == frozen["budget"], "generation budget changed"
    safety()
    return frozen


def progress(**fields):
    payload = dict(pid=os.getpid(), at=time.time(), **fields)
    write_new(BASE / ("progress-" + str(time.time_ns()) + ".json"), payload)
    print(json.dumps(payload), flush=True)


def writer(pair):
    folder = BASE / (pair[0] + "-v" + str(pair[1]))
    state_path = folder / "writer-state.json"
    if not state_path.exists():
        assert not folder.exists(), "unbound partial writer; retain and escalate"
        w = ArtifactWriter(ROOT, folder.relative_to(ROOT).as_posix(), *pair, EXPLICIT)
        write_new(state_path, dict(task_ref=w.task_ref.model_dump(), sources=w.sources,
                                  runtime=w.runtime, thresholds=w.thresholds))
        return w
    state = read(state_path)
    w = object.__new__(ArtifactWriter)
    w.root, w.destination = ROOT, folder
    w.task_ref = ArtifactRef.model_validate(state["task_ref"])
    w.task = TaskInstance.model_validate_json(artifact(ROOT, w.task_ref).read_text())
    w.sources, w.runtime, w.thresholds = state["sources"], state["runtime"], state["thresholds"]
    w.collector = LocalCollector()
    w._sequence = max([0, *[int(p.name.split("-")[1].split(".")[0]) for p in folder.iterdir()
                           if p.name.startswith(("run-", "fixture-", "invalid-", "domain-"))]])
    return w


def fuzz_step(w, alternatives):
    batches = sorted(w.destination.glob("fuzz-batch-*.json"))
    offset = sum(len(read(p)["cases"]) for p in batches)
    seeds, n = w.thresholds["hidden_seeds"], w.thresholds["random_cases_per_seed"]
    assert seeds == [1, 43, 94001] and n == 300
    if offset < len(seeds) * n:
        cases = []
        started = time.monotonic()
        for position in range(offset, min(offset + 25, len(seeds) * n)):
            seed, index = seeds[position // n], position % n
            fixture = w.fixture(observation_fixture(*NEW[0], seed, index) if
                                w.task.template_id == NEW[0][0] else
                                observation_fixture(*NEW[1], seed, index))
            tables = read(artifact(ROOT, fixture.tables))
            policy, required, observed = observed_behaviors(w.task.template_id, w.task.template_version, tables)
            cases.append(FuzzCase(seed=seed, index=index, observed_behaviors=sorted(observed),
                                  alternatives=w.sql_many(alternatives, fixture)).model_dump(mode="json"))
        stable()
        write_new(w.destination / f"fuzz-batch-{offset:04d}.json", dict(cases=cases, policy=policy,
                  required=required, source_hashes=w.sources, elapsed_seconds=time.monotonic()-started))
        progress(contract=w.task.template_id, category="fuzz", cases=offset+len(cases), total=900)
        return None
    cases = [case for p in batches for case in read(p)["cases"]]
    required = read(batches[0])["required"]
    counts = {}
    for seed in seeds:
        counter = Counter({key: 0 for key in required})
        for case in cases:
            if case["seed"] == seed:
                counter.update(case["observed_behaviors"])
        assert min(counter.values()) >= 20 and counter["empty_input"] == 23, counter
        counts[str(seed)] = dict(counter)
    return FuzzDetail.model_validate(dict(cases=cases, observed_counts=counts,
                                         observation_policy=read(batches[0])["policy"]))


def advance(seconds):
    frozen = stable()
    deadline = time.monotonic() + seconds
    originals = frozen["originals"]
    pairs = (*NEW, *((r["contract_id"], r["contract_version"]) for r in originals))
    for pair in pairs:
        w = writer(pair)
        previous = next((r for r in originals if (r["contract_id"], r["contract_version"]) == pair), None)
        for category in REQUIRED:
            checkpoint = w.destination / (category + "-checkpoint.json")
            if checkpoint.exists():
                ref = ArtifactRef.model_validate(read(checkpoint)["receipt"])
                artifact(ROOT, ref)
                continue
            started = time.monotonic()
            progress(contract=pair[0], category=category, phase="START")
            receipt_path = w.destination / (category + "-receipt.json")
            assert not receipt_path.exists(), "receipt without checkpoint; retain and escalate"
            detail_path = w.destination / (category + "-collected-detail.json")
            if detail_path.exists() and category != "named_tests":
                detail = DETAILS[category].model_validate(read(detail_path))
            elif category == "named_tests":
                detail = w.named_tests(["tests/test_qualification_named.py::test_attributed_contract_execution[" + pair[0] + "]"])
            elif previous is not None:
                old = ArtifactRef.model_validate(previous["evidence"][category])
                detail = DETAILS[category].model_validate(read(artifact(ROOT, old))["details"])
            else:
                alternatives, wrong, relations = profile(ROOT, *pair)
                if category == "rules":
                    detail = w.rules()
                elif category == "mutation":
                    detail = w.mutations(RulesDetail.model_validate(read(w.destination / "rules-receipt.json")["details"]))
                elif category == "relations":
                    detail = w.relations(alternatives[0], relations)
                elif category == "challenge":
                    detail = w.challenges(wrong, alternatives)
                elif category == "fixture_diversity":
                    detail = w.diversity()
                else:
                    detail = fuzz_step(w, alternatives)
                    while detail is None:
                        if time.monotonic() >= deadline:
                            return
                        detail = fuzz_step(w, alternatives)
            if not detail_path.exists():
                write_new(detail_path, detail.model_dump(mode="json"))
            stable()
            # Public writer reexecutes all retained SQL through the current validator.
            ref = w.receipt(category, detail)
            data = read(artifact(ROOT, ref))
            stable()
            write_new(checkpoint, dict(category=category, receipt=ref.model_dump(),
                previous_receipt=previous["evidence"][category] if previous else None,
                source_hashes=w.sources, metrics=data["metrics"], checks_run=data["checks_run"],
                elapsed_seconds=time.monotonic()-started,
                scope="fresh current-validator execution; retained witness timestamps unchanged; fresh attributed named tests"))
            progress(contract=pair[0], category=category, phase="RECEIPT", metrics=data["metrics"],
                     elapsed_seconds=time.monotonic()-started)
            if time.monotonic() >= deadline:
                return
        bundle = w.destination / "bundle.json"
        if not bundle.exists():
            record = previous or dict(contract_id=pair[0], contract_version=pair[1], family=w.task.family,
                independence="differential verification", authorship="independent authorship unproven",
                candidate_origin="reference-authored; no model generation", prerequisites=dict(template_validates=True))
            w.write("bundle.json", {**record, "evidence": {c: read(w.destination / (c+"-checkpoint.json"))["receipt"] for c in REQUIRED}})
        result_path = w.destination / "delivery-result.json"
        if not result_path.exists():
            stable()
            progress(contract=pair[0], phase="PROMOTE_AND_QUALIFY")
            record = read(bundle)
            ref = ArtifactRef(path=bundle.relative_to(ROOT).as_posix(), sha256=digest(bundle))
            active = authoritative_records(ROOT)
            event_id = "bundle-" + ref.sha256
            if not any(r == record for r in active):
                event_id = promote(ROOT, ref, resolve_absent_evidence=True)["evidence_id"]
            stable()
            q = qualify(ROOT, record)
            write_new(w.destination / "post-publication-status.json", dict(qualification=q, event_id=event_id, bundle=ref.model_dump()))
            assert q["eligible"], q
            stable()
            write_new(result_path, dict(contract_id=pair[0], contract_version=pair[1], qualification=q,
                event_id=event_id, bundle=ref.model_dump(), checked_at=time.time(), model_calls=0, accepted80=False))
            progress(contract=pair[0], phase="CURRENT_QUALIFIED")
        if time.monotonic() >= deadline:
            return
    progress(phase="COLLECTION_PUBLICATION_COMPLETE", bundles=20, category_receipts=140)


def freeze():
    safety()
    assert not BASE.exists(), "v32 identity already used"
    originals = authoritative_records(ROOT)
    assert len(originals) == 18 and len(SUPPORTED) == 20
    assert {(r["contract_id"], r["contract_version"]) for r in originals} == SUPPORTED - set(NEW)
    registry = load_builtin_registry()
    assert len({t.template_id for t in registry.list()}) == 62
    budget = usage()
    assert budget["physical_attempts"] == 28 and round(budget["generation_seconds"], 3) == 400.483, budget
    sources = source_hashes()
    hashes = {**sources, **{n: digest(ROOT/n) for n in EXPLICIT}}
    for folder in ("src", "scripts", "tests"):
        hashes.update({p.relative_to(ROOT).as_posix(): digest(p) for p in (ROOT/folder).rglob("*.py")})
    hashes.update({p.relative_to(ROOT).as_posix(): digest(p) for p in (ROOT/"templates").rglob("*.yaml")})
    BASE.mkdir()
    write_new(BASE / "freeze.json", dict(global_sources=sources, hashes=hashes, originals=originals,
        runtime=runtime_identity(), budget=budget, producer=PRODUCER, created_at=time.time(),
        scope="runtime only; 25-case resumable batches; historical packages untouched"))
    stable()
    progress(phase="FROZEN", originals=18, supported=20, registry=62, source_files=len(hashes), model_calls=0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "advance"))
    parser.add_argument("--seconds", type=float, default=180)
    args = parser.parse_args()
    try:
        freeze() if args.action == "freeze" else advance(args.seconds)
    except Exception as exc:
        if BASE.exists():
            write_new(BASE / ("failure-" + str(time.time_ns()) + ".json"), dict(error_type=type(exc).__name__,
                error=str(exc), traceback=traceback.format_exc(), recorded_at=time.time(), pid=os.getpid(),
                model_calls=0, status="STOPPED_GATE_FAILURE"))
        raise
