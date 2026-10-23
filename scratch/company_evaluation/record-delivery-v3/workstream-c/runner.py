"""Single invocation supervisor. Integrity detection, not an OS sandbox."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from scripts.engineering_guarded_operation import _WindowsJob, _snapshot, _sources
from verified_data_factory.local_paths import io_path


def save(path, data):
    with path.open('x', encoding='utf-8') as handle:
        json.dump(data, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    paths = _sources(ROOT) + [ROOT / 'governance'] + list(HERE.glob('*.py'))
    return _snapshot(ROOT, paths, source=True)


def protected(paths):
    return _snapshot(ROOT, [ROOT / 'runs/premium-qualification-080',
        ROOT / 'scratch/paused-run.baseline.sha256.txt',
        ROOT / 'scratch/funnel_experiment/engineering/company-model-role-registry.json',
        ROOT / 'scratch/funnel_experiment/engineering/generation-budget-events.jsonl', *paths], source=False)


def paused_valid():
    baseline = ROOT / 'scratch/paused-run.baseline.sha256.txt'
    expected = dict((name, digest) for digest, name in
        (line.split('  ', 1) for line in baseline.read_text().splitlines() if line))
    folder = ROOT / 'runs/premium-qualification-080'
    actual = {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob('*') if p.is_file()}
    return actual == expected and len(actual) == 15


def account(out):
    events = [json.loads(line) for line in (out / 'events.jsonl').read_text().splitlines()] if (out / 'events.jsonl').exists() else []
    nodes = json.loads((out / 'collection.actual.json').read_text()) if (out / 'collection.actual.json').exists() else []
    rows = []
    for node in nodes:
        phases = [e for e in events if e['kind'] == 'phase' and e['nodeid'] == node]
        finished = any(e['kind'] == 'node_finish' and e['nodeid'] == node for e in events)
        if not finished:
            status = 'incomplete'
        elif any(e['outcome'] == 'failed' and e['when'] != 'call' for e in phases):
            status = 'error'
        elif any(e['outcome'] == 'failed' for e in phases):
            status = 'failed'
        elif any(e['wasxfail'] and e['outcome'] == 'skipped' for e in phases):
            status = 'xfailed'
        elif any(e['wasxfail'] and e['outcome'] == 'passed' for e in phases):
            status = 'xpassed'
        elif any(e['outcome'] == 'skipped' for e in phases):
            status = 'skipped'
        elif {e['when'] for e in phases} == {'setup', 'call', 'teardown'}:
            status = 'passed'
        else:
            status = 'incomplete'
        rows.append(dict(nodeid=node, status=status, phases=phases, finished=finished))
    return dict(collected=len(nodes), nodes=rows, counts=dict(Counter(r['status'] for r in rows)),
        deselected=[n for e in events if e['kind'] == 'deselected' for n in e['nodeids']],
        collection_errors=[e for e in events if e['kind'] == 'collection_report' and e['outcome'] == 'failed'],
        collection_skips=[e for e in events if e['kind'] == 'collection_report' and e['outcome'] == 'skipped'],
        internal_errors=[e for e in events if e['kind'] == 'internal_error'],
        session_finished=any(e['kind'] == 'session_finish' for e in events))


def run(out, timeout, targets, evidence=(), expected=None, full=False):
    out = out.resolve()
    if not out.is_relative_to(HERE) or out == HERE:
        raise ValueError('Output must be a NEW child of workstream-c')
    out.mkdir(parents=True, exist_ok=False)
    child = job = None
    begin = time.monotonic()
    terminal = dict(status='INCOMPLETE', timeout=False, supervisor_pid=os.getpid(), scope='full' if full else 'smoke')
    before = guard = None
    try:
        before, guard = sources(), protected(evidence)
        save(out / 'source.pre.json', before)
        save(out / 'protected.pre.json', guard)
        if not paused_valid():
            raise ValueError('Protected15 baseline mismatch')
        if expected is not None and json.loads(expected.read_text()) != before:
            raise ValueError('Expected final source manifest differs')
        # Certification scratch lives outside the repository: short paths avoid
        # Windows MAX_PATH failures, and tmp dirs are not inside any git checkout
        # (provenance "no git" isolation depends on it). Retained as run evidence.
        basetemp = Path(tempfile.gettempdir()) / ('revo-cert-' + out.name) / 'tmp'
        basetemp.parent.mkdir(parents=True, exist_ok=True)
        if basetemp.exists():
            # Stale scratch from a killed run may hold Windows-reserved names
            # (e.g. NUL) that plain unlink cannot remove; extended path can.
            try:
                shutil.rmtree(basetemp)
            except OSError:
                shutil.rmtree(io_path(basetemp))
        command = [sys.executable, '-u', '-m', 'pytest', *targets, '-vv', '--tb=short', '-rA',
            '-p', 'no:cacheprovider', '-p', 'evidence_plugin', '--basetemp=' + str(basetemp),
            '--junitxml=' + str(out / 'junit.xml')]
        env = os.environ.copy()
        env['PYTHONPATH'] = str(HERE) + os.pathsep + env.get('PYTHONPATH', '')
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        env['REVO_CERT_OUT'] = str(out)
        # No inherited selection/xdist/maxfail options; installed plugins remain visible in stdout.
        env['PYTEST_ADDOPTS'] = ''
        save(out / 'environment.json', dict(python=sys.version, executable=sys.executable,
            platform=platform.platform(), pytest_addopts='cleared', plugins='pytest header in stdout.log',
            environment_identity='not a historical environment reconstruction'))
        with (out / 'stdout.log').open('xb') as stdout, (out / 'stderr.log').open('xb') as stderr:
            job = _WindowsJob() if os.name == 'nt' else None
            child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr,
                creationflags=0x4 if job else 0, start_new_session=not bool(job))
            save(out / 'launch.json', dict(command=command, cwd=str(ROOT), pid=child.pid,
                supervisor_pid=os.getpid(), timeout_seconds=timeout, started_at=time.time(),
                source_manifest_sha256=sha(out / 'source.pre.json'), retry=False))
            if job:
                job.start(child)
            with (out / 'heartbeat.jsonl').open('x', encoding='utf-8') as hb:
                while child.poll() is None:
                    elapsed = time.monotonic() - begin
                    hb.write(json.dumps(dict(at=time.time(), pid=child.pid, phase='pytest', elapsed=elapsed,
                        stdout_bytes=(out / 'stdout.log').stat().st_size,
                        ledger_bytes=(out / 'events.jsonl').stat().st_size if (out / 'events.jsonl').exists() else 0)) + '\n')
                    hb.flush()
                    os.fsync(hb.fileno())
                    if elapsed >= timeout:
                        terminal['timeout'] = True
                        break
                    time.sleep(0.2)
    except BaseException:
        terminal['supervisor_error'] = traceback.format_exc()
    finally:
        if job:
            job.close()
        elif child:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if child:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)
            terminal['returncode'] = child.returncode
            terminal['child_reaped'] = True
        try:
            after, postguard = sources(), protected(evidence)
            save(out / 'source.post.json', after)
            save(out / 'protected.post.json', postguard)
            terminal.update(source_unchanged=before == after, protected_unchanged=guard == postguard)
            terminal['paused15_valid'] = paused_valid()
            accounting = account(out)
            save(out / 'accounting.json', accounting)
            terminal.update({k: v for k, v in accounting.items() if k != 'nodes'})
            good = (terminal.get('returncode') == 0 and not terminal['timeout'] and
                terminal['source_unchanged'] and terminal['protected_unchanged'] and
                terminal['paused15_valid'] and
                accounting['collected'] > 0 and accounting['session_finished'] and
                not any(accounting[k] for k in ('deselected', 'collection_errors', 'internal_errors')) and
                not any(accounting['counts'].get(k, 0) for k in ('failed', 'error', 'incomplete', 'xpassed')))
            terminal['status'] = 'PASS' if good and 'supervisor_error' not in terminal else 'FAIL'
        except BaseException:
            terminal['finalization_error'] = traceback.format_exc()
        terminal['elapsed_seconds'] = time.monotonic() - begin
        save(out / 'terminal.json', terminal)
        print(json.dumps(terminal, indent=2), flush=True)
    return terminal


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['freeze', 'start'])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--expected-source', type=Path)
    parser.add_argument('--qualification-evidence', type=Path)
    parser.add_argument('--protect', type=Path, action='append', default=[])
    parser.add_argument('--lane-authorized', action='store_true')
    parser.add_argument('--timeout', type=int, default=21600)
    args = parser.parse_args()
    if args.action == 'freeze':
        if not args.out.resolve().is_relative_to(HERE):
            parser.error('freeze output must be owned')
        save(args.out, sources())
        return 0
    if not args.lane_authorized or not args.expected_source or not args.qualification_evidence:
        parser.error('start requires serialized lane authorization, final source and current qualification evidence')
    if not 1 <= args.timeout <= 21600:
        parser.error('timeout must be bounded at 21600 seconds')
    evidence = [args.qualification_evidence.resolve(), *(p.resolve() for p in args.protect)]
    if any(not p.exists() or not p.is_relative_to(ROOT) for p in evidence):
        parser.error('evidence must exist within repository')
    return 0 if run(args.out, args.timeout, ['tests'], evidence, args.expected_source, True)['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
