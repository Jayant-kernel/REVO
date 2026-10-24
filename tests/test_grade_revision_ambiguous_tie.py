"""The public grade contract does not resolve equal timestamp AND revision-ID payload ties."""
import json

from scripts.phase3_diagnostic import _reference_sql
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.verification.oracle_registry import get_oracle


def test_conflicting_equal_grade_winners_are_an_unresolved_public_domain(tmp_path):
    contract = "sql.dedup.education_grade_revisions"
    task = generate_task(load_builtin_registry().get(contract, 1), 94001)
    first = {"revision_id": 7, "student_id": 1, "course_id": 10,
             "recorded_at": "2025-01-01 00:00:00", "revision_status": "valid", "grade": "A"}
    second = {**first, "grade": "B"}
    outcomes = []
    for rows in ([first, second], [second, first]):
        tables = {"grade_revisions": rows}
        connection = materialize_duckdb(task.schema_, tables)
        try:
            actual = [list(row) for row in connection.execute(_reference_sql()[contract]).fetchall()]
            expected = get_oracle(contract, 1).fn(task.requirements, tables)
            outcomes.append({"tables": tables, "sql_rows": actual, "oracle_rows": expected.rows})
        finally:
            connection.close()
    (tmp_path / "conflicting-grade-tie.json").write_text(json.dumps({
        "contract_id": contract, "version": 1, "status": "SPECIFICATION_DEPENDENCY",
        "missing": "uniqueness or a rule for differing grades with the same student/course/timestamp/revision_id",
        "outcomes": outcomes,
    }, default=str, indent=2), encoding="utf-8")
    # Both inputs satisfy declared SQL types/nullability. Choosing the first seen
    # payload changes on permutation, yet public table order carries no semantics.
    assert outcomes[0]["oracle_rows"] != outcomes[1]["oracle_rows"]
    assert {outcome["sql_rows"][0][2] for outcome in outcomes} <= {"A", "B"}
