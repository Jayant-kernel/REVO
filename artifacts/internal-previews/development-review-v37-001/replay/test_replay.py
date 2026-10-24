"""Light local reviewer checks; never launch native/package validation."""
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import replay

TEMP = Path(r"C:\Users\jayan\AppData\Local\Temp\opencode")


def fixture():
    return {"example_id": "01", "candidate_id": "local-unit-only", "schema": [
        {"name": "t", "columns": [{"name": "n", "type": "INTEGER", "nullable": False},
                                   {"name": "d", "type": "DECIMAL", "nullable": True}]}],
        "tables": {"t": [{"n": 2, "d": None}, {"n": 1, "d": "2.50"}]},
        "sql": "SELECT n, d FROM t ORDER BY n", "expected": {
            "columns": [{"name": "n", "type": "INTEGER"}, {"name": "d", "type": "DECIMAL(18,2)"}],
            "rows": [[1, "2.50"], [2, None]], "rows_returned": 2, "truncated": False}}


class ReviewerTests(unittest.TestCase):
    def test_actual_execution_and_tampered_comparisons(self):
        data = fixture()
        actual = replay.execute_fixture(data)
        self.assertTrue(all(replay.compare(actual, data["expected"]).values()))
        for field, mutate in (
            ("column_names", lambda x: x["columns"][0].update(name="wrong")),
            ("declared_output_types", lambda x: x["columns"][0].update(type="BIGINT")),
            ("ordered_typed_rows", lambda x: x["rows"].reverse()),
            ("ordered_typed_rows", lambda x: x["rows"][0].__setitem__(0, True)),
            ("ordered_typed_rows", lambda x: x["rows"][0].__setitem__(0, 1.0)),
            ("ordered_typed_rows", lambda x: x["rows"][0].__setitem__(1, "2.5")),
            ("rows_returned", lambda x: x.update(rows_returned=3)),
            ("truncated", lambda x: x.update(truncated=True)),
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(data["expected"])
                mutate(changed)
                self.assertFalse(replay.compare(actual, changed)[field])

    def test_single_select_boundary(self):
        data = fixture()
        data["sql"] = "SELECT 1; SELECT 2"
        with self.assertRaisesRegex(ValueError, "one SELECT"):
            replay.execute_fixture(data)

    def test_hash_and_fresh_identity(self):
        with tempfile.TemporaryDirectory(prefix="rb-", dir=TEMP) as tmp:
            root = Path(tmp)
            file = root / "asset"
            file.write_bytes(b"original")
            pin = hashlib.sha256(b"original").hexdigest()
            replay.verify_hash(file, pin)
            file.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "SHA256"):
                replay.verify_hash(file, pin)
            replay.fresh_directory(root / "work", [root / "package"])
            with self.assertRaises(FileExistsError):
                replay.fresh_directory(root / "work", [])
            with self.assertRaisesRegex(ValueError, "separate"):
                replay.fresh_directory(root / "package/out", [root / "package"])
            replay.save(root / "identity.json", {"id": "first"})
            with self.assertRaises(FileExistsError):
                replay.save(root / "identity.json", {"id": "second"})

    def test_eight_local_fixtures_fresh_location_cli_and_tamper(self):
        with tempfile.TemporaryDirectory(prefix="rb-", dir=TEMP) as tmp:
            root = Path(tmp)
            shutil.copyfile(Path(replay.__file__), root / "replay.py")
            examples = root / "examples"
            examples.mkdir()
            entries = []
            for n in range(1, 9):
                data = fixture()
                data["example_id"] = f"{n:02}"
                name = f"{n:02}.json"
                replay.save(examples / name, data)
                entries.append({"example_id": f"{n:02}", "candidate_id": data["candidate_id"], "fixture": name, "page": f"{n:02}.md"})
            replay.save(examples / "index.json", {"examples": entries})
            command = [sys.executable, "-B", str(root / "replay.py"), "illustrative", "--examples", str(examples)]
            completed = subprocess.run(command, cwd=root, capture_output=True, timeout=30, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            result = json.loads(completed.stdout)
            self.assertTrue(result["passed"])
            self.assertEqual(len(result["records"]), 8)
            data = replay.load(examples / "01.json")
            data["expected"]["rows"][0][0] = True
            (examples / "01.json").write_text(json.dumps(data), encoding="utf-8")
            completed = subprocess.run(command, cwd=root, capture_output=True, timeout=30, check=False)
            self.assertEqual(completed.returncode, 1)
            self.assertFalse(json.loads(completed.stdout)["records"][0]["comparisons"]["ordered_typed_rows"])

    def test_pinned_inspection_entry_from_fresh_location(self):
        package = Path(replay.__file__).resolve().parents[4] / "artifacts/internal-deliveries/v37-original8-001/original8"
        self.assertTrue(package.is_dir())
        with tempfile.TemporaryDirectory(prefix="rb-", dir=TEMP) as tmp:
            root = Path(tmp)
            shutil.copyfile(Path(replay.__file__), root / "replay.py")
            completed = subprocess.run([sys.executable, "-B", str(root / "replay.py"), "check-inputs", "--package", str(package)],
                                       cwd=root, capture_output=True, timeout=30, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            self.assertEqual(json.loads(completed.stdout)["declared_files"], 123765)

    @unittest.skipUnless(sys.platform == "win32", "Windows Job boundary")
    def test_owned_job_light_child(self):
        from windows_job import Job
        with Job() as job:
            child = subprocess.Popen([sys.executable, "-B", "-c", "import sys; assert sys.stdin.readline().strip() == 'GO'"], stdin=subprocess.PIPE)
            try:
                job.assign(child)
                child.stdin.write(b"GO\n")
                child.stdin.close()
                self.assertEqual(child.wait(timeout=10), 0)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=10)


if __name__ == "__main__":
    require_temp = TEMP.is_dir()
    if not require_temp:
        raise SystemExit("approved temporary parent missing")
    unittest.main()
