"""Confined append-only receipts and independent immutable input identities."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from scripts.engineering_guarded_operation import PROTECTED, run_guarded
from verified_data_factory.local_paths import io_path


@pytest.fixture
def root(tmp_path: Path) -> Path:
    for folder in PROTECTED:
        (tmp_path / folder).mkdir()
    (tmp_path / "src/input.py").write_text("original", encoding="utf-8")
    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence/old.json").write_text("old FAIL", encoding="utf-8")
    (tmp_path / "scratch/operations").mkdir(parents=True)
    return tmp_path


def run(root: Path, code: str, **kwargs):
    return run_guarded(
        root, "scratch/operations/new", [sys.executable, "-B", "-c", code],
        ["marker.json"], kwargs.pop("timeout_s", 5), ["evidence"],
        output_boundary="scratch/operations/new", guard=kwargs.pop("guard", lambda _: None),
        **kwargs,
    )


MARKER = "from pathlib import Path; Path('scratch/operations/new/marker.json').write_text('{}')"


def test_output_creation_pass(root):
    result = run(root, MARKER)
    assert result["status"] == "PASS"
    assert result["exit_code"] == 0
    assert result["identity_match"]
    output = root / "scratch/operations/new"
    assert json.loads((output / "receipt.json").read_text()) == result
    launch = json.loads((output / "launch.json").read_text())
    assert launch["identity"]["evidence"]["evidence/old.json"]
    assert (root / "evidence/old.json").read_text() == "old FAIL"
    assert {p.name for p in output.iterdir()} == {
        "launch.json", "post.json", "terminal.json", "receipt.json", "stdout.log",
        "stderr.log", "marker.json",
    }


@pytest.mark.skipif(os.name != "nt", reason="Windows reserved basename semantics")
def test_existing_literal_reserved_name_is_inventoried_without_device_alias(root):
    literal = io_path(root / "NUL")
    literal.write_text("preserve actual user file", encoding="utf-8")
    result = run(root, MARKER)
    assert result["status"] == "PASS"
    launch = json.loads((root / "scratch/operations/new/launch.json").read_text())
    assert launch["identity"]["workspace"]["NUL"][0] == "file"
    assert literal.read_text(encoding="utf-8") == "preserve actual user file"


@pytest.mark.parametrize("path", ["src/input.py", "evidence/old.json", "docs/new.md"])
def test_source_or_evidence_change_fail(root, path):
    result = run(root, MARKER + f"; Path({path!r}).write_text('changed')")
    assert result["status"] == "FAIL"
    assert not result["identity_match"]


@pytest.mark.parametrize("code", ["pass", MARKER.replace("'{}'", "''")])
def test_missing_or_empty_completion_fail(root, code):
    result = run(root, code)
    assert result["status"] == "FAIL"
    assert any("completion file" in e for e in result["errors"])


def test_nonzero_fail(root):
    result = run(root, MARKER + "; raise SystemExit(7)")
    assert result["status"] == "FAIL"
    assert result["exit_code"] == 7


def test_hard_link_to_protected_evidence_is_not_a_new_output(root):
    code = "import os; os.link('evidence/old.json','scratch/operations/new/marker.json')"
    result = run(root, code)
    assert result["status"] == "FAIL"
    assert any("hard-linked output" in error for error in result["errors"])
    assert (root / "evidence/old.json").read_text() == "old FAIL"


def test_timeout_interrupted(root):
    result = run(root, MARKER + "; import time; time.sleep(10)", timeout_s=0.3)
    assert result["status"] == "INTERRUPTED"
    assert result["timed_out"]
    assert result["exit_code"] is None
    terminal = json.loads((root / "scratch/operations/new/terminal.json").read_text())
    assert terminal == {"exit_code": None, "timed_out": True}


@pytest.mark.parametrize("output", [".", "scratch", "scratch/operations", "../escape",
                                    "scratch/operations/../new", "src/nested/new"])
def test_broad_traversal_or_source_output_rejected(root, output):
    with pytest.raises(ValueError):
        run_guarded(root, output, [sys.executable, "-c", "pass"], ["done"], 2,
                    ["evidence"], output_boundary=output, guard=lambda _: None)
    assert not (root / "scratch/operations/new").exists()


def test_required_traversal_rejected(root):
    with pytest.raises(ValueError, match="traversal"):
        run_guarded(root, "scratch/operations/new", [sys.executable, "-c", "pass"],
                    ["../done"], 2, ["evidence"], output_boundary="scratch/operations/new",
                    guard=lambda _: None)


def test_preexisting_destination_rejected_without_overwrite(root):
    destination = root / "scratch/operations/new"
    destination.mkdir()
    (destination / "receipt.json").write_text("old FAIL")
    with pytest.raises(ValueError, match="fresh"):
        run(root, MARKER)
    assert (destination / "receipt.json").read_text() == "old FAIL"


def symlink_or_skip(link: Path, target: Path):
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        if os.name == "nt" and exc.winerror == 1314:
            pytest.skip("Windows symlink privilege unavailable (winerror 1314)")
        raise


def test_symbolic_redirection_rejected(root):
    symlink_or_skip(root / "scratch/redirect", root / "evidence")
    with pytest.raises(ValueError, match="redirection"):
        run_guarded(root, "scratch/redirect/new", [sys.executable, "-c", "pass"],
                    ["done"], 2, ["evidence"], output_boundary="scratch/redirect/new",
                    guard=lambda _: None)


def test_junction_redirection_rejected(root):
    if os.name != "nt":
        pytest.skip("junctions are Windows-only")
    link = root / "scratch/redirect"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(root / "evidence")],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    try:
        with pytest.raises(ValueError, match="redirection"):
            run_guarded(root, "scratch/redirect/new", [sys.executable, "-c", "pass"],
                        ["done"], 2, ["evidence"], output_boundary="scratch/redirect/new",
                        guard=lambda _: None)
    finally:
        link.rmdir()


def allow_output_swap(monkeypatch):
    # Windows denies directory rename while regular logs are open. Close only
    # these test-owned logs to exercise the independent post-run swap detector.
    from scripts import engineering_guarded_operation as wrapper
    execute = wrapper._execute

    def without_open_logs(command, root, timeout, stdout, stderr):
        stdout.close()
        stderr.close()
        with open(os.devnull, "wb") as sink:
            return execute(command, root, timeout, sink, sink)

    monkeypatch.setattr(wrapper, "_execute", without_open_logs)


def test_malicious_output_swap_caught_post(root, monkeypatch):
    allow_output_swap(monkeypatch)
    if os.name == "nt":
        redirect = (
            "import subprocess; "
            "subprocess.run(['cmd','/c','mklink','/J',str(p),str(Path('evidence').resolve())], "
            "check=True)"
        )
    else:
        redirect = "p.symlink_to(Path('evidence').resolve(), target_is_directory=True)"
    code = ("from pathlib import Path; p=Path('scratch/operations/new'); "
            "p.rename(p.with_name('stolen')); " + redirect)
    try:
        result = run(root, code)
        assert result["status"] == "FAIL"
        assert any("output integrity" in e for e in result["errors"])
        assert sorted(p.name for p in (root / "evidence").iterdir()) == ["old.json"]
    finally:
        link = root / "scratch/operations/new"
        if link.is_symlink():
            link.unlink()
        elif os.name == "nt" and link.exists():
            link.rmdir()


def test_completion_symlink_rejected(root):
    probe = root / "scratch/probe"
    symlink_or_skip(probe, root / "evidence")
    probe.unlink()
    result = run(root, "from pathlib import Path; "
                 "Path('scratch/operations/new/marker.json').symlink_to("
                 "Path('evidence/old.json').resolve())")
    assert result["status"] == "FAIL"


def test_post_guard_failure(root):
    calls = []

    def guard(_):
        calls.append(1)
        if len(calls) == 2:
            raise ValueError("frozen mismatch")

    result = run(root, MARKER, guard=guard)
    assert result["status"] == "FAIL"
    assert any("frozen mismatch" in e for e in result["errors"])


def test_child_cannot_precreate_receipt_for_pass(root):
    result = run(root, MARKER + "; Path('scratch/operations/new/receipt.json').write_text('old')")
    assert result["status"] == "FAIL"
    assert (root / "scratch/operations/new/receipt.json").read_text() == "old"


def test_launch_failure(root):
    result = run_guarded(root, "scratch/operations/new", [str(root / "missing-command")],
                         ["marker.json"], 2, ["evidence"],
                         output_boundary="scratch/operations/new", guard=lambda _: None)
    assert result["status"] == "FAIL"
    assert result["exit_code"] is None


def test_exact_boundary_required(root):
    with pytest.raises(ValueError, match="exact narrow"):
        run_guarded(root, "scratch/operations/new", [sys.executable, "-c", "pass"],
                    ["done"], 2, ["evidence"], output_boundary="scratch/operations",
                    guard=lambda _: None)


def test_authoritative_evidence_required(root):
    with pytest.raises(ValueError, match="authoritative"):
        run_guarded(root, "scratch/operations/new", [sys.executable, "-c", "pass"],
                    ["done"], 2, output_boundary="scratch/operations/new", guard=lambda _: None)


def test_output_overlap_with_whole_evidence_directory_rejected(root):
    with pytest.raises(ValueError, match="overlaps"):
        run_guarded(root, "scratch/operations/new", [sys.executable, "-c", "pass"],
                    ["done"], 2, ["scratch/operations"],
                    output_boundary="scratch/operations/new", guard=lambda _: None)


def test_ordinary_directory_replacement_caught(root, monkeypatch):
    allow_output_swap(monkeypatch)
    result = run(root, "from pathlib import Path; p=Path('scratch/operations/new'); "
                 "p.rename(p.with_name('stolen')); p.mkdir(); (p/'marker.json').write_text('{}')")
    assert result["status"] == "FAIL"
    assert any("directory replaced" in error for error in result["errors"])
    assert not (root / "scratch/operations/new/receipt.json").exists()


def test_alternate_stream_rejected(root):
    with pytest.raises(ValueError, match="alternate-stream"):
        run_guarded(root, "scratch/operations/new", [sys.executable, "-c", "pass"],
                    ["marker.json:stream"], 2, ["evidence"],
                    output_boundary="scratch/operations/new", guard=lambda _: None)


def test_pre_guard_failure_creates_no_output(root):
    def blocked(_):
        raise ValueError("frozen preflight blocked")

    with pytest.raises(ValueError, match="preflight blocked"):
        run(root, MARKER, guard=blocked)
    assert not (root / "scratch/operations/new").exists()


@pytest.mark.parametrize("path", ["scratch/operations/unapproved.json", "new-authority.json",
                                  "new-source.py", "scratch/new-directory/file.txt"])
def test_new_outside_boundary_fails(root, path):
    result = run(root, MARKER + f"; p=Path({path!r}); p.parent.mkdir(parents=True, exist_ok=True); p.write_text('new')")
    assert result["status"] == "FAIL"
    assert not result["identity_match"]


def test_undeclared_existing_metadata_change_fails(root):
    (root / "scratch/archive.bin").write_bytes(b"old")
    result = run(root, MARKER + "; Path('scratch/archive.bin').write_bytes(b'changed')")
    assert result["status"] == "FAIL"


def test_evidence_deletion_fails(root):
    assert run(root, MARKER + "; Path('evidence/old.json').unlink()")["status"] == "FAIL"


@pytest.mark.parametrize("action", ["p.write_text('{}')", "p.unlink()",
                                    "p.rename(p.with_name('old-launch')); p.write_text('{}')"])
def test_launch_tampering_fails(root, action):
    result = run(root, MARKER + "; p=Path('scratch/operations/new/launch.json'); " + action)
    assert result["status"] == "FAIL"


@pytest.mark.parametrize("name", ["terminal.json", "post.json", "receipt.json"])
def test_reserved_records_fail(root, name):
    result = run(root, MARKER + f"; Path('scratch/operations/new/{name}').write_text('command-owned')")
    assert result["status"] == "FAIL"
    assert (root / f"scratch/operations/new/{name}").read_text() == "command-owned"


def test_terminal_precedes_post_hash(root, monkeypatch):
    from scripts import engineering_guarded_operation as wrapper
    original = wrapper._snapshot
    calls = []

    def snapshot(*args, **kwargs):
        calls.append(1)
        if len(calls) > 2:
            assert (root / "scratch/operations/new/terminal.json").is_file()
        return original(*args, **kwargs)

    monkeypatch.setattr(wrapper, "_snapshot", snapshot)
    assert run(root, MARKER)["status"] == "PASS"


def test_descendant_timeout_and_output_integrity(root):
    outsider = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(10)"])
    try:
        code = (MARKER + "; import subprocess, sys, time; "
                "print('stdout intact', flush=True); print('stderr intact', file=sys.stderr, flush=True); "
                "subprocess.Popen([sys.executable, '-B', '-c', "
                "\"import time; from pathlib import Path; time.sleep(1); "
                "Path('scratch/operations/new/late.json').write_text('escaped')\"]); time.sleep(10)")
        started = time.monotonic()
        result = run(root, code, timeout_s=0.1)
        assert time.monotonic() - started < 1
        assert result["status"] == "INTERRUPTED"
        assert outsider.poll() is None
        output = root / "scratch/operations/new"
        assert (output / "stdout.log").read_text().strip() == "stdout intact"
        assert (output / "stderr.log").read_text().strip() == "stderr intact"
        time.sleep(1.2)
        assert not (output / "late.json").exists()
    finally:
        outsider.terminate()
        outsider.wait(timeout=5)


def test_unrelated_workspace_junction_rejected(root):
    if os.name != "nt":
        pytest.skip("junctions are Windows-only")
    link = root / "scratch/archive-link"
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(root / "evidence")], check=True,
                   capture_output=True)
    try:
        with pytest.raises(ValueError, match="redirection"):
            run(root, MARKER)
    finally:
        link.rmdir()
