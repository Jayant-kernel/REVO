"""Regression evidence against the immutable observed candidate, not a replacement."""
from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.test_queue_batches_profile import TASK, execute, matches
from verified_data_factory.verification.qualification import (
    queue_batches_candidate_transforms as ast,
)
from verified_data_factory.verification.qualification import queue_batches_profile as p

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/company-queue-batches-cpu-v34-002"
SQL = json.loads((RUN / "attempt-000/generation.json").read_text())["candidate_solution"]["candidate_sql"]


@pytest.fixture
def connection() -> Iterator[Any]:
    import duckdb

    with duckdb.connect(config={"enable_external_access": "false"}) as conn:
        yield conn


def status(sql: str) -> str:
    result = ast.structural_checks(TASK, sql)
    assert result is not None
    return str(result["status"])


def test_actual_proofs_and_alias_preservation(connection: Any) -> None:
    assert status(SQL) == "PASS"
    for sql in (SQL, SQL.replace(") sub", ") renamed")):
        proofs = ast.candidate_proofs(sql, p.REFERENCE, p.proofs(p.REFERENCE))
        assert proofs is not None
        for key, spec in proofs.items():
            if key in p.DOMAIN_KEYS:
                with pytest.raises(ValueError):
                    p.validate_rows(spec["witness"])
                continue
            p.validate_rows(spec["witness"])
            assert matches(connection, sql, spec["witness"]), key
            if key in p.STRUCTURAL_KEYS:
                assert matches(connection, spec["structural_sql"], spec["witness"])
                assert status(spec["structural_sql"]) == "FAIL"
            else:
                assert not matches(connection, spec["wrong_sql"], spec["witness"]), key
            rendered = spec.get("wrong_sql", spec.get("structural_sql", ""))
            assert "renamed" in rendered if "renamed" in sql else "sub" in rendered
    print("actual candidate: all attributed semantic witnesses discriminate; aliases preserved")


@pytest.mark.parametrize("seed", [1, 43, 94001])
def test_actual_900_frames(connection: Any, seed: int) -> None:
    counts: Counter[str] = Counter()
    for index in range(300):
        tables = p.fixture(seed, index)
        counts.update(p.observed(tables)[2])
        assert matches(connection, SQL, tables)
        # Separate SQL-free count/remainder definition, not the profile oracle.
        output = []
        rows = tables["submissions"]
        for label in {row["queue"] for row in rows}:
            group = sorted((row for row in rows if row["queue"] == label),
                           key=lambda row: (row["submitted_at"] is None,
                                            row["submitted_at"] or "", row["submission_id"]))
            small, remainder = divmod(len(group), 3)
            buckets = [bucket for bucket in range(1, 4)
                       for _ in range(small + (bucket <= remainder))]
            output.extend([row["submission_id"], bucket]
                          for row, bucket in zip(group, buckets, strict=True))
        assert execute(connection, SQL, tables)[2] == sorted(output)
    assert set(counts) == set(p.BEHAVIORS)
    assert min(counts.values()) >= 20
    print(f"actual SQL seed={seed}: 300 typed matches; all 27 behaviors >=20")


def test_actual_near_neighbors_and_exact_types(connection: Any) -> None:
    for old, new in [("NTILE(3)", "NTILE(2)"), ("NTILE(3)", "NTILE(4)"),
                     ("NTILE(3)", "RANK()"), ("NULLS LAST", ""),
                     ("submission_id ASC", "submission_id DESC"),
                     ("submitted_at ASC", "CAST(submitted_at AS DATE) ASC"),
                     ("FROM submissions", "FROM submissions WHERE submitted_at IS NOT NULL")]:
        changed = SQL.replace(old, new)
        assert changed != SQL
        assert status(changed) != "PASS"
        assert ast.candidate_proofs(changed, p.REFERENCE, p.proofs(p.REFERENCE)) is None
    unsupported = SQL.replace("NTILE(3)", "NTILE(1+2)")
    assert matches(connection, unsupported, p.rich_fixture())
    assert status(unsupported) == "INCONCLUSIVE"
    assert ast.candidate_proofs(unsupported, p.REFERENCE, p.proofs(p.REFERENCE)) is None
    for dtype in ("INTEGER", "BIGINT"):
        cast = f"SELECT submission_id,CAST(batch_number AS {dtype}) AS batch_number FROM ({SQL}) x ORDER BY submission_id"
        actual = execute(connection, cast, p.rich_fixture())
        expected = p.expected({}, p.rich_fixture())
        assert expected.exact_column_types
        assert actual[2] == expected.rows
        assert matches(connection, cast, p.rich_fixture()) is (dtype == "BIGINT")
    decorative = f"WITH unused AS ({SQL}) SELECT submission_id,CAST(1 AS BIGINT) AS batch_number FROM submissions ORDER BY submission_id"
    assert status(decorative) == "FAIL"


def test_native_v35_rejudge(tmp_path: Path) -> None:
    from hashlib import sha256

    from scripts.company_generation_experiment import BUDGET, validate_attempt_binding
    from verified_data_factory.generation.models import CandidateSolution
    from verified_data_factory.sandbox import SandboxExecutor, load_config
    from verified_data_factory.task_engine.models import TaskInstance
    from verified_data_factory.verification import verify_candidate
    from verified_data_factory.verification.backend import DerivedTaskBackend

    originals = {path: sha256(path.read_bytes()).hexdigest()
                 for path in RUN.rglob("*.json")}
    budget_bytes = BUDGET.read_bytes()
    events = [json.loads(line) for line in budget_bytes.splitlines()]
    protocol_bytes = (RUN / "protocol.json").read_bytes()
    assert sha256(protocol_bytes).hexdigest() == json.loads(
        (RUN / "protocol-binding.json").read_text())["sha256"]
    task = TaskInstance.model_validate(json.loads(protocol_bytes)["tasks"][0])
    generation = json.loads((RUN / "attempt-000/generation.json").read_text())
    candidate = CandidateSolution.model_validate(generation["candidate_solution"])
    validate_attempt_binding(RUN, 0, candidate, events)
    request = json.loads((RUN / "attempt-000/request.json").read_text())["body"]
    response = json.loads((RUN / "attempt-000/http-response.json").read_text())
    assert response["status_code"] == 200
    assert json.loads(response["body"])["message"]["content"] == candidate.raw_response
    assert request["model"] == candidate.model
    assert request["options"]["num_gpu"] == 0
    sampling = candidate.generation_config.model_dump()
    for key in ("temperature", "top_p", "seed"):
        assert request["options"][key] == sampling[key]
    assert request["options"]["num_predict"] == candidate.generation_config.max_tokens
    assert task.task_id == candidate.task_id
    assert task.instruction in request["messages"][0]["content"]
    config = load_config("configs/sandbox_production.yaml")
    execution = SandboxExecutor(config).execute(task, candidate)
    verification = verify_candidate(task, candidate, execution, backend=DerivedTaskBackend(config))
    output = tmp_path / "observed-queue-v35-harness-v2"
    output.mkdir(exist_ok=False)
    for name, model in (("execution", execution), ("verification", verification)):
        with (output / f"{name}.json").open("x", encoding="utf-8") as stream:
            stream.write(model.model_dump_json(indent=2))
    assert {path: sha256(path.read_bytes()).hexdigest() for path in originals} == originals
    assert BUDGET.read_bytes() == budget_bytes
    assert verification.mutation is not None
    report = {
        "originals_sha256": {str(path.relative_to(ROOT)): digest for path, digest in originals.items()},
        "physical_request_binding": "PASS", "sampling_binding": "PASS",
        "verdict": verification.verdict, "strength": verification.verification_strength,
        "mutation": verification.mutation.model_dump(mode="json"),
        "admission": "NOT_QUALIFIED: requires 20-profile renewal after current core fix",
        "history": "Original first slot INCONCLUSIVE preserved; second slot WINDOW parser failure retained. Not model accuracy certification.",
        "scope": "No generation, qualification, network, authority or old bundle changes.",
    }
    with (output / "report.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2))
    print(f"native artifacts: {output}")
    print(f"v35 native: {verification.verdict}/{verification.verification_strength}; "
          f"execution={execution.status}; mutation_score={verification.mutation.mutation_score}; "
          f"coverage_complete={verification.mutation.coverage_complete}; "
          f"semantic_kills={verification.mutation.semantic_kills}")
    assert execution.status == "SUCCEEDED"
    assert verification.verdict == "PASS"
    assert verification.verification_strength == "STRONG"
    assert verification.mutation.mutation_score == 1.0
    assert verification.mutation.coverage_complete
