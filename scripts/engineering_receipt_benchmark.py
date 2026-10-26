"""Small real-execution benchmark, never a qualification receipt or threshold override."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from contextlib import ExitStack
from pathlib import Path
from time import perf_counter
from typing import Any
from unittest.mock import patch

from scripts import engineering_receipt_artifacts as writer_module
from tests.test_stage2_receipt_producer import ALTERNATIVES, SCRAP
from verified_data_factory.task_engine import hidden_fixtures
from verified_data_factory.verification import receipt_validation as validator_module
from verified_data_factory.verification.behavior_authority import public_behavior_map
from verified_data_factory.verification.receipt_observations import observation_fixture


def benchmark(cases: int, temporary_parent: Path) -> dict[str, Any]:
    live = Path(__file__).resolve().parents[1]
    measurements: dict[str, dict[str, float | int]] = {}

    def measured(label: str, function: Any) -> Any:
        def call(*args: Any, **kwargs: Any) -> Any:
            entry = measurements.setdefault(label, {"calls": 0, "seconds": 0.0})
            start = perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                entry["calls"] += 1
                entry["seconds"] += perf_counter() - start
        return call

    with tempfile.TemporaryDirectory(prefix="stage2-benchmark-", dir=temporary_parent) as directory:
        root = Path(directory)
        paths = set(validator_module.required_sources())
        for folder in ("scripts", "tests"):
            paths.update(p.relative_to(live).as_posix() for p in (live / folder).rglob("*.py"))
        for relative in paths:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(live / relative, destination)
        writer = writer_module.ArtifactWriter(root, "benchmark-not-qualification", SCRAP, 1, [])
        with ExitStack() as stack:
            for module, attribute, label in (
                (writer_module, "materialize_duckdb", "writer_materialize"),
                (validator_module, "materialize_duckdb", "validator_materialize"),
                (hidden_fixtures, "materialize_duckdb", "fingerprint_materialize"),
                (writer_module, "digest", "writer_digest"),
                (validator_module, "digest", "validator_digest"),
            ):
                stack.enter_context(patch.object(module, attribute,
                                                 measured(label, getattr(module, attribute))))
            start = perf_counter()
            runs = []
            for index in range(cases):
                fixture = writer.fixture(observation_fixture(SCRAP, 1, 1, index))
                runs.append(writer.sql_many(ALTERNATIVES, fixture))
            writer_seconds = perf_counter() - start
            passes = []
            # Mirror the old three complete traversals, without qualifying a small suite.
            for _ in range(3):
                start = perf_counter()
                checker = validator_module.DetailValidator(
                    root, writer.task, public_behavior_map(writer.task), writer.sources, writer.thresholds,
                )
                with checker:
                    for index, alternatives in enumerate(runs):
                        checker.fixture(alternatives[0].fixture)
                        generated = observation_fixture(SCRAP, 1, 1, index)
                        assert alternatives[0].fixture.fingerprint == (
                            hidden_fixtures.fixture_fingerprint(writer.task, generated)
                        )
                        for witness in alternatives:
                            checker.sql(witness)
                    assert checker.run_count == cases * 3
                passes.append(perf_counter() - start)
        return {"label": "benchmark-not-qualification", "cases": cases,
                "alternatives_per_case": 3, "writer_seconds": writer_seconds,
                "validation_pass_seconds": passes, "measurements_inclusive": measurements}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=10, choices=range(1, 31))
    parser.add_argument("--temporary-parent", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = benchmark(args.cases, args.temporary_parent)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
