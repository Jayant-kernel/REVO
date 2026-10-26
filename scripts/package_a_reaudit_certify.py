"""Capture launch/post identities and terminal regression, then smoke last."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    evidence = root / "scratch/funnel_experiment/evidence"
    paths = {name: evidence / f"reaudit-{name}" for name in
             ("launch.json", "post.json", "regression.log", "smoke.log", "certification.json")}
    for path in paths.values():
        path.touch(exist_ok=True)
    guard = [sys.executable, "scripts/package_a_paused_run_guard.py", "--output"]
    subprocess.run(guard + [str(paths["launch.json"])], cwd=root, check=True)
    with paths["regression.log"].open("w", encoding="utf-8") as log:
        regression = subprocess.run([sys.executable, "-m", "pytest", "--durations=25"], cwd=root,
                                    stdout=log, stderr=subprocess.STDOUT, check=False)
    subprocess.run(guard + [str(paths["post.json"])], cwd=root, check=True)
    before = json.loads(paths["launch.json"].read_text())["source_tree_identity"]
    after = json.loads(paths["post.json"].read_text())["source_tree_identity"]
    with paths["smoke.log"].open("w", encoding="utf-8") as log:
        smoke = subprocess.run([sys.executable, "-m", "pytest", "tests/test_saas_funnel_oracle.py",
                                "tests/test_package_a_challenge_repair.py", "tests/test_phase6_saas_v2_fuzz.py",
                                "tests/e2e/test_business_task_pipeline.py::test_business_task_pinned_full_verification[sql.funnel.saas_activation_payment]",
                                "-q", "-rs"], cwd=root, stdout=log, stderr=subprocess.STDOUT, check=False)
    result = {"regression_exit_code": regression.returncode, "smoke_exit_code": smoke.returncode,
              "launch_identity": before, "post_identity": after, "identities_match": before == after,
              "regression_summary": paths["regression.log"].read_text().splitlines()[-1],
              "smoke_summary": paths["smoke.log"].read_text().splitlines()[-1]}
    paths["certification.json"].write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return int(regression.returncode != 0 or smoke.returncode != 0 or before != after)


if __name__ == "__main__":
    raise SystemExit(main())
