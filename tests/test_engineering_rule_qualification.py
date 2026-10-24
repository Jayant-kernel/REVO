"""Qualification cannot survive an unimplemented or unproven rule profile."""
import json
from pathlib import Path

from verified_data_factory.production import contract_readiness_from_manifest


def test_generic_window_contract_without_ranking_proof_is_not_admitted():
    ready = contract_readiness_from_manifest(Path("manifests/phase3-contract-readiness.json"))
    assert not ready("sql.windows.payments_risk_rank")


def test_named_contract_without_complete_rule_evidence_is_not_admitted():
    ready = contract_readiness_from_manifest(Path("manifests/phase3-contract-readiness.json"))
    assert not ready("sql.joins.simple")


def test_every_declared_requirement_has_a_proof_or_quarantine():
    report = json.loads(Path("scratch/funnel_experiment/engineering/phase4-rules.json").read_text())
    assert len(report["contracts"]) == 57
    ready = contract_readiness_from_manifest(Path("manifests/phase3-contract-readiness.json"))
    for record in report["contracts"]:
        assert record["rule_map"]
        if record["status"] == "RULES_EXECUTED":
            assert all(r["outcome"] in {"EXECUTED_RULE_PROOF", "REJECTED_INVALID_INPUT"} for r in record["rule_map"].values())
        else:
            assert not ready(record["contract_id"])


def test_shared_sum_is_not_automatically_a_semantic_defect():
    report = json.loads(Path("scratch/funnel_experiment/engineering/phase4-rules.json").read_text())
    scrap = next(r for r in report["contracts"] if r["contract_id"] == "sql.aggregation.manufacturing_line_scrap")
    assert scrap["shared_generic_oracle"]
    assert scrap["status"] == "RULES_EXECUTED"
    assert all(r["outcome"] != "OPEN" for r in scrap["rule_map"].values())
