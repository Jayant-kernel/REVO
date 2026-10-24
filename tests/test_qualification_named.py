"""Exact attributed, executable probes retained by qualification bundles."""
import pytest

from scripts.engineering_receipt_artifacts import SUPPORTED
from scripts.phase3_diagnostic import _reference_sql
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.verification.comparator import compare
from verified_data_factory.verification.oracle_registry import get_oracle


@pytest.mark.parametrize("contract", sorted(contract for contract, _ in SUPPORTED))
def test_attributed_contract_execution(contract, request, record_property):
    version = next(version for candidate, version in SUPPORTED if candidate == contract)
    record_property("node_id", request.node.nodeid)
    record_property("contract_id", contract)
    record_property("contract_version", str(version))
    task = generate_task(load_builtin_registry().get(contract, version), 94001)
    con = materialize_duckdb(task.schema_, task.tables)
    try:
        cursor = con.execute(_reference_sql()[contract])
        columns = cursor.description
        rows = [list(row) for row in cursor.fetchall()]
        expected = get_oracle(contract, version).fn(task.requirements, task.tables)
        assert compare(expected, [column[0] for column in columns], rows,
                       column_types=[str(column[1]) for column in columns]).match
    finally:
        con.close()
