"""Read-only current qualification gates and post-suite checks; no producer stable()."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

from runner import HERE, ROOT, paused_valid, save, sha, sources
from scripts.company_generation_experiment import BUDGET, budget_usage, source_hashes
from scripts.engineering_campaign import safety
from verified_data_factory.local_paths import io_path
from verified_data_factory.verification.readiness import authoritative_records, effective_evidence
from verified_data_factory.verification.receipt_models import ReceiptV2
from verified_data_factory.verification.receipt_validation import runtime_identity, validate_sources

OUT = HERE / 'certification-v37'
QUAL = ROOT / 'scratch/funnel_experiment/engineering/qualified-receipts-v37'
SUITE = HERE / 'full-suite-v37'
EXPECTED = HERE / 'expected-source-v37.json'
PACKAGE = ROOT / 'artifacts/internal-deliveries/v36/original8'


def read(path):
    return json.loads(io_path(path).read_bytes())


def check(label):
    begin = time.monotonic()
    safety()
    assert paused_valid(), 'paused15 baseline mismatch'
    frozen = read(QUAL / 'freeze.json')
    assert len(frozen['hashes']) == 687
    assert source_hashes() == frozen['global_sources'], 'global source closure mismatch'
    assert runtime_identity() == frozen['runtime'], 'runtime mismatch'
    budget_key = BUDGET.relative_to(ROOT).as_posix()
    changed = [p for p, digest in frozen['hashes'].items() if sha(ROOT / p) != digest]
    assert set(changed) <= {budget_key}, changed
    usage = budget_usage([json.loads(line) for line in BUDGET.read_text().splitlines() if line])
    assert usage['physical_attempts'] == 36 and round(usage['generation_seconds'], 3) == 558.327
    assert not usage['unfinished_attempts']
    records = authoritative_records(ROOT)
    assert len(records) == 20
    receipts = 0
    for record in records:
        effective_evidence(ROOT, record)
        for reference in record['evidence'].values():
            path = ROOT / reference['path']
            assert path.is_relative_to(QUAL)
            assert sha(path) == reference['sha256']
            validate_sources(ROOT, ReceiptV2.model_validate(read(path)))
            receipts += 1
    assert receipts == 140
    pins = {
        'release/manifest.json': 'fc4539b62510d71136d27fea1d0b62e543f6dd14870d913be2bc852a94d065bc',
        'anchor.json': '75400755bbf402b3e2a82c296449ec966a672db42c9eb4dfda7de65b80e9b11c',
        'quality-context.json': '6b9eaab02135511710c03e9e24e99f8b5e5e3b2385673ac31260a77947011387',
        'validate_bound_release_windows.py': 'fef7a1557705a997e4e455bb19dcb1dadce913768fc446e44b129715c27f3726'}
    assert all(sha(PACKAGE / name) == digest for name, digest in pins.items())
    result = dict(status='CURRENT_BINDINGS_PASS', label=label, runtime=runtime_identity(),
        v37_bound_inputs=687, immutable_inputs_checked=687-len(changed), historical_changed_paths=changed,
        historical_budget=frozen['budget'], current_budget=usage, qualified=20, category_receipts=receipts,
        phase0='PASS', paused15='PASS', package_critical_pins=pins,
        package_scope='critical pins only; no duplicate 77073-file whole-package replay/hash campaign',
        elapsed_seconds=time.monotonic()-begin)
    save(OUT / (label + '-bindings.json'), result)
    print(json.dumps(result, indent=2), flush=True)
    return result


def command(label, args, timeout):
    begin = time.monotonic()
    cmd = [sys.executable, '-B', '-m', *args]
    save(OUT / (label + '-launch.json'), dict(command=cmd, timeout_seconds=timeout,
        source_manifest_sha256=sha(EXPECTED)))
    with (OUT / (label + '.stdout.log')).open('xb') as stdout, (OUT / (label + '.stderr.log')).open('xb') as stderr:
        from scripts.engineering_guarded_operation import _execute
        code, timed = _execute(cmd, ROOT, timeout, stdout, stderr)
    result = dict(command=cmd, returncode=code, timeout=timed, elapsed_seconds=time.monotonic()-begin)
    save(OUT / (label + '-terminal.json'), result)
    print(json.dumps(result), flush=True)
    return result


def finish():
    results = {}
    results['mypy'] = command('mypy', ['mypy', 'src'], 1800)
    scoped = ['src/verified_data_factory/verification/adversarial.py',
        'src/verified_data_factory/verification/delivery_adversarial.py',
        'src/verified_data_factory/verification/qualification/structural.py',
        'src/verified_data_factory/verification/verifier.py',
        'tests/test_delivery_adversarial.py', 'tests/test_reconciliation_cte_structure.py']
    results['ruff'] = command('production-ruff', ['ruff', 'check', *scoped], 300)
    guards = check('post')
    terminal = read(SUITE / 'terminal.json')
    accounting = read(SUITE / 'accounting.json')
    source = sources()
    save(OUT / 'source.after-followups.json', source)
    same = source == read(EXPECTED)
    skips = [row for row in accounting['nodes'] if row['status'] in ('skipped', 'xfailed', 'xpassed')]
    log = (SUITE / 'stdout.log').read_text(encoding='utf-8', errors='replace')
    warnings = log[log.find('warnings summary'):] if 'warnings summary' in log else 'No warnings summary emitted; inspect complete stdout/stderr.'
    with (OUT / 'warnings-and-summary.txt').open('x', encoding='utf-8') as handle:
        handle.write(warnings)
    ledger = [json.loads(line) for line in (SUITE / 'events.jsonl').read_text().splitlines()]
    phase_counts = dict(Counter(e['when'] for e in ledger if e['kind'] == 'phase'))
    result = dict(suite=terminal, phase_report_counts=phase_counts, skips_and_xfails=skips,
        followups=results, post_guards=guards, source_unchanged_through_followups=same,
        source_manifest_sha256=sha(EXPECTED),
        complete_certification=(terminal['status'] == 'PASS' and same and not skips and
            all(r['returncode'] == 0 and not r['timeout'] for r in results.values())),
        historical='1938 later collection/1789 symbols/149 tail not authoritative original mapping; no composite pass',
        native='old incidents RETAINED_UNRESOLVED; passing suite not causal proof',
        optional_recovery_operator_ruff='27 historical findings retained; not production Ruff pass',
        product='W16 broader dependencies not certified; accepted80=0; human PENDING; sharing BLOCKED; utility NOT_MEASURED')
    save(OUT / 'ACCOUNTING-v37.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('skips_and_xfails', 'post_guards')}, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['pre', 'post'])
    args = parser.parse_args()
    if args.action == 'pre':
        OUT.mkdir(exist_ok=False)
        check('pre')
    else:
        finish()


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        traceback.print_exc()
        raise
