"""Read-only measurement of historical/new runs, written to a NEW evidence file.

Usage: python scripts/quality70_evidence.py --output <new-file> [--run <run>]
Never generates candidates, changes old runs or awards rubric points.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from verified_data_factory.production import load_config, report
from verified_data_factory.production.api import implementation_id, preflight
from verified_data_factory.production.models import FAMILIES
from verified_data_factory.production.runner import _latest_templates_for_family
from verified_data_factory.quality.premium_candidate import assess_premium_candidate
from verified_data_factory.task_engine import load_builtin_registry


def sha(path: Path) -> str:
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def measure_run(root: Path) -> dict[str, Any]:
    golden = root / 'quality/export/golden.jsonl'
    result = report(root)
    if golden.exists() and golden.stat().st_size:
        result['golden_sha256'] = sha(golden)
        result['premium_screen'] = assess_premium_candidate(golden)
    manifest = root / 'manifests/run-manifest.json'
    if manifest.exists():
        result['manifest_sha256'] = sha(manifest)
        result['manifest'] = json.loads(manifest.read_text(encoding='utf-8-sig'))
    # Hash receipts let a subsequent comparison prove old evidence was untouched.
    result['artifact_hashes'] = {
        str(path.relative_to(root)): sha(path) for path in sorted(root.rglob('*'))
        if path.is_file()
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--compare-baseline', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('evidence destination already exists')
    if not args.output.parent.is_dir():
        raise ValueError('evidence parent must already exist')
    registry = load_builtin_registry()
    templates = [_latest_templates_for_family(registry, family) for family in FAMILIES]
    tasks = [t for family in templates for t in family]
    payload: dict[str, Any] = {
        'label': 'MEASURED; not commercial release approval or readiness score',
        'recorded_at': datetime.now(UTC).isoformat(),
        'implementation_id': implementation_id(),
        'versions': {p: importlib.metadata.version(p) for p in ('duckdb', 'pydantic', 'httpx', 'pyyaml', 'pyarrow')},
        'template_ids_by_family': {f: [t.template_id for t in ts] for f, ts in zip(FAMILIES, templates, strict=True)},
        'domain_counts': dict(Counter(str(t.generation_config.get('domain', 'UNSPECIFIED')) for t in tasks)),
        'template_versions': len(registry),
        'distinct_template_ids': len(tasks),
        'historical': {name: measure_run(Path('runs') / name) for name in (
            'controlled-requalification-002', 'production-001', 'smoke-qualification-001')},
        'premium_preflight': preflight(load_config('configs/production/premium_qualification_80.yaml')),
        'external_benchmark_overlap': 'NOT_MEASURED',
        'independent_replay': 'NOT_MEASURED',
        'human_review': 'PENDING',
    }
    if args.run:
        payload['new_run'] = measure_run(args.run)
    if args.compare_baseline:
        baseline = json.loads(args.compare_baseline.read_text(encoding='utf-8'))
        unchanged = {name: baseline['historical'][name]['artifact_hashes'] == data['artifact_hashes']
                     for name, data in payload['historical'].items()}
        if not all(unchanged.values()):
            raise ValueError(f'historical evidence changed: {unchanged}')
        payload['historical_artifacts_unchanged'] = unchanged
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({
        'output': str(args.output), 'sha256': sha(args.output),
        'distinct_template_ids': len(tasks),
        'historical_counts': {n: {k: r[k] for k in ('candidates', 'verifications', 'golden')} for n, r in payload['historical'].items()},
    }, indent=2))


if __name__ == '__main__':
    main()
