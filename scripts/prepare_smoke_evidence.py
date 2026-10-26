"""Derive diagnostics, provenance, pending review and same-host replay in a NEW directory.

No model generation, human decisions, source run edits or commercial export.
Reference SQL from tests is never used as a candidate in this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from verified_data_factory.production import load_config
from verified_data_factory.production.api import config_id, preflight
from verified_data_factory.provenance import build_bundle, export_provenance_bundle
from verified_data_factory.quality import analyze_dataset, load_quality_config
from verified_data_factory.quality.export import build_golden_record_id
from verified_data_factory.quality.models import GoldenRecord, VerifiedRecord
from verified_data_factory.quality.premium_candidate import assess_premium_candidate
from verified_data_factory.quality.review_package import freeze_review_package
from verified_data_factory.sandbox import SandboxExecutor
from verified_data_factory.sandbox import load_config as load_sandbox
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification import verify_candidate
from verified_data_factory.verification.backend import DerivedTaskBackend


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def digest(path: Path) -> str:
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    config = load_config(args.config)
    root = Path(config.output_dir)
    target = args.out_dir
    if target.exists() or not target.parent.is_dir():
        raise ValueError('derived evidence requires a new destination and existing parent')
    manifest_path = root / 'manifests/run-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest['production_config_id'] != config_id(config):
        raise ValueError('source run/config identity mismatch')
    readiness = preflight(config)
    if not readiness['ok']:
        raise ValueError('local replay preflight failed')
    hashes_before = {str(p.relative_to(root)): digest(p) for p in root.rglob('*') if p.is_file()}
    verdicts = {r['candidate_id']: r for r in read_rows(root / 'verification/verification.jsonl')}
    records = [VerifiedRecord.model_validate({**r, 'verification': verdicts[r['candidate']['candidate_id']]})
               for r in read_rows(root / 'execution/triples.jsonl')]
    quality = load_quality_config(config.quality_config).model_copy(update={'audit_rate': 0.0, 'audit_seed': config.audit.seed})
    analysis = analyze_dataset(records, quality)
    source_golden = root / 'quality/export/golden.jsonl'
    golden = [GoldenRecord.model_validate(r) for r in read_rows(source_golden)]
    if {g.candidate_id for g in golden} != {q.candidate_id for q in analysis.qualities if q.decision == 'GOLDEN'}:
        raise ValueError('recomputed automated selection differs from frozen run')
    target.mkdir()
    write_json(target / 'preflight.json', readiness)
    (target / 'golden.jsonl').write_bytes(source_golden.read_bytes())
    with (target / 'verified_records.jsonl').open('w', encoding='utf-8') as handle:
        for record in records:
            handle.write(record.model_dump_json(by_alias=True) + '\n')
    with (target / 'qualities.jsonl').open('w', encoding='utf-8') as handle:
        for q in analysis.qualities:
            handle.write(q.model_dump_json() + '\n')
    bundle = build_bundle(records, analysis.qualities, golden, analysis.audit_sample,
                          quality.model_dump(mode='json'), None, '0.8.0', 'diverse-smoke-002-diagnostic', repo_root=Path.cwd())
    export_provenance_bundle(target / 'provenance', bundle['manifest'], bundle['reproduction'].model_dump(mode='json'),
                            bundle['snapshot'], list(bundle['nodes'].values()), bundle['edges'], bundle['activities'],
                            bundle['artifacts'], bundle['golden'], bundle['reproducibility'], bundle['completeness'], bundle['artifact_payloads'])
    frozen = freeze_review_package(target / 'golden.jsonl', target / 'review')
    write_json(target / 'premium-screen.json', assess_premium_candidate(source_golden))
    by_template: dict[str, Counter[str]] = defaultdict(Counter)
    failures = []
    for record in records:
        by_template[record.task.template_id][record.verification.verdict] += 1
        if record.verification.verdict != 'PASS':
            failures.append({'template_id': record.task.template_id, 'candidate_id': record.candidate.candidate_id,
                             'sql': record.candidate.candidate_sql, 'verification': record.verification.model_dump(mode='json'),
                             'execution': record.execution.model_dump(mode='json')})
    write_json(target / 'diagnosis.json', {'label': 'MEASURED outcomes; root causes require semantic inspection',
               'protocol': 'two independent templates per family, one seed per template, three local model attempts, temperature 0.3; no tuning after answers',
               'by_template': {k: dict(v) for k, v in by_template.items()}, 'failed_candidates': failures,
               'limitations': ['single checkpoint', 'one task instance per template', 'three correlated attempts are not broad difficulty calibration']})
    selected = {g.candidate_id: g for g in golden}
    registry = load_builtin_registry()
    sandbox = load_sandbox(config.sandbox_config)
    executor = SandboxExecutor(sandbox)
    backend = DerivedTaskBackend(sandbox)
    replay = []
    for record in records:
        if record.candidate.candidate_id not in selected:
            continue
        started = time.monotonic()
        regenerated = generate_task(registry.get(record.task.template_id, record.task.template_version), record.task.seed,
                                    dict(record.task.generation_metadata.config))
        execution = executor.execute(record.task, record.candidate)
        result = verify_candidate(record.task, record.candidate, execution, backend=backend)
        content_id = build_golden_record_id(task=record.task.model_dump(mode='json', by_alias=True), instruction=record.task.instruction,
                     schema=[t.model_dump(mode='json') for t in record.task.schema_], candidate_solution=record.candidate.candidate_sql or '')
        original = record.verification
        matching = (regenerated == record.task and content_id == selected[record.candidate.candidate_id].record_id
                    and result.verdict == original.verdict and result.verification_strength == original.verification_strength
                    and result.mutation == original.mutation and result.hidden == original.hidden
                    and result.properties == original.properties and result.metamorphic == original.metamorphic)
        replay.append({'record_id': content_id, 'template_id': record.task.template_id, 'matches': matching,
                       'verdict': result.verdict, 'seconds': time.monotonic() - started,
                       'verification': result.model_dump(mode='json')})
    write_json(target / 'replay.json', {'label': 'MEASURED same-host task regeneration and fresh-container replay',
               'independent_environment_attestation': 'NOT_MEASURED',
               'clean_host_dependency_environment': 'NOT_MEASURED',
               'health_metric_replay': 'NOT_MEASURED; selected rows only, operational timings are expected to vary',
               'rows': replay, 'all_selected_semantic_checks_match': all(r['matches'] for r in replay)})
    if hashes_before != {str(p.relative_to(root)): digest(p) for p in root.rglob('*') if p.is_file()}:
        raise ValueError('source run changed during derived evidence preparation')
    write_json(target / 'manifest.json', {
        'label': 'Internal verified diagnostic review candidate — human review pending',
        'source_run_manifest_sha256': digest(manifest_path), 'source_golden_sha256': digest(source_golden),
        'record_count': len(golden), 'snapshot_id': bundle['snapshot'].dataset_snapshot_id,
        'review_package_id': frozen['package_id'], 'source_artifact_hashes': hashes_before,
        'derived_artifact_hashes': {str(p.relative_to(target)): digest(p) for p in sorted(target.rglob('*')) if p.is_file()},
        'qualification_status': 'BLOCKED; premium composition and template floor not met',
        'human_review': 'PENDING', 'external_overlap': 'NOT_MEASURED', 'rights': 'NOT_CLEARED',
    })
    print(json.dumps({'out_dir': str(target), 'golden': len(golden), 'replay_matches': sum(r['matches'] for r in replay),
                      'snapshot_id': bundle['snapshot'].dataset_snapshot_id, 'source_golden_sha256': digest(source_golden)}, indent=2))


if __name__ == '__main__':
    main()
