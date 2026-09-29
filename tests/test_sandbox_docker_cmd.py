"""Docker command construction tests: the boundary, statically verified.

These tests prove isolation properties of the invocation itself without a
daemon: no mounts, no cp, no socket, no env inheritance, SQL never in argv
(it travels on stdin, which subprocess never inspects).
"""

import subprocess
from pathlib import Path

from verified_data_factory.sandbox import DockerRunner, SandboxConfig, docker_available
from verified_data_factory.sandbox.models import RunResult


class _Proc:
    returncode = 0

    def __init__(self, seen):
        self._seen = seen

    def communicate(self, payload=None, timeout=None):
        self._seen.append(payload)
        return b'{"status": "ok"}', b"OK\n"


def _capture_runner(monkeypatch):
    cfg = SandboxConfig()
    runner = DockerRunner(cfg)
    seen_argv = []
    seen_payloads = []

    def fake_popen(cmd, **kwargs):
        seen_argv.append(cmd)
        proc = _Proc(seen_payloads)
        return proc

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    return runner, seen_argv, seen_payloads


def test_run_uses_isolation_flags(monkeypatch):
    runner, argv_seen, _ = _capture_runner(monkeypatch)
    outcome = runner.run_container("vdf-abc", "exec-1", b'{"sql": "SELECT 1;"}', 10.0)
    assert isinstance(outcome, RunResult)
    assert outcome.exit_code == 0
    argv = argv_seen[0]
    assert argv[0] == "docker" and argv[1] == "run"
    for flag in (
        ("--network", "none"),
        ("--read-only", None),
        ("--cap-drop", "ALL"),
        ("--security-opt", "no-new-privileges"),
        ("--memory", "512m"),
        ("--memory-swap", "512m"),
        ("--cpus", "1.0"),
        ("--pids-limit", "64"),
        ("--user", "10000:10000"),
        ("--workdir", "/work"),
        ("--stop-timeout", "5"),
        ("-i", None),
        ("--stdin", None),
    ):
        assert flag[0] in argv, flag
        if flag[1] is not None:
            assert argv[argv.index(flag[0]) + 1] == flag[1], flag
    assert any(a == "/tmp:size=64m,mode=1777" for a in argv)
    assert "/harness/run.py" in argv


def test_no_host_mounts_or_copies_or_socket(monkeypatch):
    runner, argv_seen, _ = _capture_runner(monkeypatch)
    runner.run_container("vdf-abc", "exec-1", b"{}", 10.0)
    argv = " ".join(argv_seen[0])
    for banned in ("-v ", "--volume", "--mount", "docker.sock", "/var/run", " cp ", '"cp"'):
        assert banned not in argv, banned
    import verified_data_factory.sandbox.docker as docker_mod

    source = Path(docker_mod.__file__).read_text(encoding="utf-8")
    assert '"cp"' not in source and "'cp'" not in source


def test_minimal_environment(monkeypatch):
    runner, argv_seen, _ = _capture_runner(monkeypatch)
    runner.run_container("vdf-abc", "exec-1", b"{}", 10.0)
    argv = argv_seen[0]
    env_values = [argv[i + 1] for i, a in enumerate(argv) if a == "--env"]
    assert env_values == ["VDF_EXECUTION_ID=exec-1"]
    joined = " ".join(argv)
    assert "VDF_API_KEY" not in joined and "SECRET" not in joined.upper()


def test_candidate_sql_never_in_argv(monkeypatch):
    runner, argv_seen, payloads = _capture_runner(monkeypatch)
    runner.run_container("vdf-abc", "exec-1", b'{"sql": "SELECT * FROM secrets;"}', 10.0)
    joined = " ".join(argv_seen[0])
    assert "SELECT" not in joined
    assert payloads and b"SELECT * FROM secrets;" in payloads[0]


def test_payload_delivered_on_stdin_not_argv(monkeypatch):
    runner, _, payloads = _capture_runner(monkeypatch)
    payload = b'{"fixture": {}, "sql": "SELECT 1;"}'
    runner.run_container("vdf-abc", "exec-1", payload, 10.0)
    assert payloads == [payload]


def test_timeout_kills_and_raises(monkeypatch):
    cfg = SandboxConfig()
    runner = DockerRunner(cfg)
    killed = []

    class HangingProc:
        returncode = -1

        def __init__(self):
            self.attempts = 0

        def communicate(self, payload=None, timeout=None):
            self.attempts += 1
            if self.attempts == 1:
                raise subprocess.TimeoutExpired(cmd="docker", timeout=timeout)
            return b"", b""

        def kill(self):
            pass

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: HangingProc())
    monkeypatch.setattr(runner, "kill", lambda name: killed.append(name))
    from verified_data_factory.sandbox.errors import RunnerTimeoutError

    try:
        runner.run_container("vdf-hang", "exec-1", b"{}", 1.0)
        raise AssertionError("expected RunnerTimeoutError")
    except RunnerTimeoutError:
        pass
    assert killed == ["vdf-hang"]


def test_no_shell_invocation():
    import verified_data_factory.sandbox.docker as docker_mod

    source = Path(docker_mod.__file__).read_text(encoding="utf-8")
    assert "shell=True" not in source


def test_docker_available_gate_reports_bool():
    assert isinstance(docker_available(timeout_s=1.0), bool)
