"""Deterministic Phase 7 fixture: synthetic Golden records + snapshot (no Docker, no models).

Builds a 40-record Golden set with controlled structure the product
tests can assert on: shared semantic groups (for isolation tests),
exact-duplicate pairs, PRIVATE_EVAL roles, and one hard-contaminated
record (for visibility tests). All Golden records are hand-assembled to
the Phase 5 contract — the product layer never looks behind them.
"""

from verified_data_factory.provenance import build_dataset_snapshot
from verified_data_factory.provenance.models import DatasetSnapshot
from verified_data_factory.quality.models import GoldenRecord

FAMILIES = ("simple_joins", "aggregation", "retention", "funnel")


def _task_dict(index: int, family: str) -> dict:
    return {
        "task_id": f"task-{index:03d}",
        "template_id": f"sql.test.{family}",
        "template_version": 1,
        "family": family,
        "difficulty": (index % 5) + 1,
        "seed": 1000 + index,
    }


def _schema_dict() -> list[dict]:
    return [
        {
            "name": "orders",
            "columns": [
                {"name": "order_id", "type": "INTEGER", "nullable": False},
                {"name": "amount", "type": "DOUBLE", "nullable": True},
            ],
        }
    ]


def make_golden(index: int, family: str) -> GoldenRecord:
    return GoldenRecord(
        record_id=f"sha256:{index:064x}",
        candidate_id=f"cand-{index:03d}",
        task=_task_dict(index, family),
        instruction=f"Question {index} about {family}",
        schema_=_schema_dict(),
        fixture={"seed": 1000 + index, "engine": "test", "tables": {"orders": 10}},
        candidate_solution=f"SELECT * FROM orders WHERE order_id > {index};",
        verification={"verdict": "PASS"},
        quality={"decision": "GOLDEN"},
        dataset_role="TRAIN",
        audit_status="PASS",
    )


def quality_entry(
    candidate_id: str,
    *,
    role: str = "TRAIN",
    semantic_group: str | None = None,
    exact_group: str | None = None,
    hard_contamination: bool = False,
    internal_only: bool = False,
    family: str = "simple_joins",
) -> dict:
    flags = (
        [{"flag_type": "EXACT_OVERLAP", "detail": "test", "hard": True}]
        if hard_contamination
        else []
    )
    return {
        "candidate_id": candidate_id,
        "role": role,
        "family": family,
        "semantic_duplicate_group": semantic_group,
        "exact_duplicate_group": exact_group,
        "contamination_flags": flags,
        "internal_only": internal_only,
        "verification": {
            "verification_strength": "STRONG",
            "mutation_applicable": 1,
            "mutation_status": "SCORED",
            "mutation_score": 1.0,
        },
        "auditor_result": "PASS",
    }


def build_product_fixture(
    n: int = 40,
) -> tuple[list[GoldenRecord], dict[str, dict], DatasetSnapshot]:
    """Return (golden_records, quality_by_id, snapshot) deterministically.

    - Records 0-7 share semantic group ``sem-a`` (isolation test).
    - Records 8-9 share exact group ``exa-b`` (isolation test).
    - Record 10 has role PRIVATE_EVAL (visibility test).
    - Record 11 carries a hard contamination flag (visibility test).
    - The rest are plain TRAIN records across four families.
    """
    goldens: list[GoldenRecord] = []
    quality_by_id: dict[str, dict] = {}
    for index in range(n):
        family = FAMILIES[index % len(FAMILIES)]
        golden = make_golden(index, family)
        goldens.append(golden)
        quality_by_id[golden.candidate_id] = quality_entry(golden.candidate_id, family=family)

    for index in range(8):
        quality_by_id[f"cand-{index:03d}"]["semantic_duplicate_group"] = "sem-a"
    for index in (8, 9):
        quality_by_id[f"cand-{index:03d}"]["exact_duplicate_group"] = "exa-b"
    quality_by_id["cand-010"]["role"] = "PRIVATE_EVAL"
    quality_by_id["cand-011"]["contamination_flags"] = [
        {"flag_type": "EXACT_OVERLAP", "detail": "test-hard", "hard": True}
    ]

    snapshot = build_dataset_snapshot(
        [g.candidate_id for g in goldens],
        "product-fixture",
        "1.0",
        "selection-fixture-1",
        "5.0",
    )
    return goldens, quality_by_id, snapshot
