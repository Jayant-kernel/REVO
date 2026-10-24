"""Verify private challenge witnesses actually execute and disagree semantically."""
import json
from pathlib import Path

from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.verification.oracle_registry import get_oracle


def test_repaired_corpus_contains_twenty_executable_semantic_counterexamples():
    corpus = json.loads(Path("scratch/funnel_experiment/evidence/challenge-repair-private.json").read_text())
    task = generate_task(load_builtin_registry().get("sql.funnel.saas_activation_payment", 2), 1)
    assert len(corpus["queries"]) >= 20
    for query in corpus["queries"]:
        expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, query["witness"])
        connection = materialize_duckdb(task.schema_, query["witness"])
        try:
            actual = [list(row) for row in connection.execute(query["sql"]).fetchall()]
        finally:
            connection.close()
        assert query["classification"] == "KILLED_WRONG_ANSWER"
        assert expected.rows == query["expected"]
        assert actual == query["actual"]
        assert actual != expected.rows, query["name"]
