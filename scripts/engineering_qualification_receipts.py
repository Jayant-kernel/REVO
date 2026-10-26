"""Collect immutable detailed qualification bundles; no legacy summary admission."""
from __future__ import annotations

import argparse
import json
import runpy
from pathlib import Path
from typing import Any

from scripts.engineering_campaign import OUT, ROOT, safety
from scripts.engineering_receipt_artifacts import SUPPORTED, ArtifactWriter, catalog_blockers
from scripts.engineering_rule_audit import ledger
from scripts.phase3_diagnostic import _reference_sql
from verified_data_factory.verification.readiness import REQUIRED, receipt
from verified_data_factory.verification.receipt_validation import confined, digest

INPUTS = (
    "pyproject.toml", "configs/sandbox_production.yaml",
    "scratch/funnel_experiment/evidence/challenge-repair-private.json",
    "scratch/funnel_experiment/evidence/run_phase5_private_corpus.py",
    "scratch/funnel_experiment/engineering/phase7-scrap-coverage.json",
)


def profile(root: Path, contract: str, version: int) -> tuple[list[str], list[tuple[str, Any]], list[tuple[str, str, Any]]]:
    pair = contract, version
    if pair not in SUPPORTED:
        raise ValueError("unsupported qualification profile contract/version")
    reference = _reference_sql()[contract]
    from verified_data_factory.verification.qualification.delivery_profiles import get_profile

    followup = get_profile(contract, version)
    if followup is not None:
        return followup.alternatives(reference), followup.challenge_specs(reference), followup.relation_specs(reference)
    if pair == ("sql.dedup.lowest_quote", 1):
        from verified_data_factory.verification.qualification import lowest_quote_profile as quote

        return quote.alternatives(reference), quote.challenge_specs(reference), quote.relation_specs(reference)
    if pair == ("sql.cte.inventory_net_flow", 2):
        from verified_data_factory.verification.qualification import (
            inventory_flow_profile as inventory,
        )

        return inventory.alternatives(reference), inventory.challenge_specs(reference), inventory.relation_specs(reference)
    if pair == ("sql.subqueries.education_all_required", 1):
        from verified_data_factory.verification.qualification import (
            required_courses_profile as required,
        )

        return required.alternatives(reference), required.challenge_specs(reference), required.relation_specs(reference)
    if pair == ("sql.aggregation.warehouse_throughput", 2):
        from verified_data_factory.verification.qualification import (
            throughput_profile as throughput,
        )

        return throughput.alternatives(reference), throughput.challenge_specs(reference), throughput.relation_specs(reference)
    if pair == ("sql.dedup.education_grade_revisions", 2):
        from verified_data_factory.verification.qualification import (
            grade_revisions_profile as grade,
        )

        return grade.alternatives(reference), grade.challenge_specs(reference), grade.relation_specs(reference)
    if pair == ("sql.aggregation.support_sla_breaches", 1):
        from verified_data_factory.verification.qualification import (
            support_breaches_profile as support,
        )

        return support.alternatives(reference), support.challenge_specs(reference), support.relation_specs(reference)
    if pair == ("sql.windows.media_previous_play", 1):
        from verified_data_factory.verification.qualification import (
            previous_play_profile as previous,
        )

        return previous.alternatives(reference), previous.challenge_specs(reference), previous.relation_specs(reference)
    if pair == ("sql.cte.order_line_reconciliation", 1):
        from verified_data_factory.verification.qualification import (
            reconciliation_profile as reconciliation,
        )

        return reconciliation.alternatives(reference), reconciliation.challenge_specs(reference), reconciliation.relation_specs(reference)
    if pair == ("sql.retention.saas_repeat_payment", 1):
        from verified_data_factory.verification.qualification import (
            repeat_payment_profile as retention,
        )

        return retention.alternatives(reference), retention.challenge_specs(reference), retention.relation_specs(reference)
    if pair == ("sql.temporal.clinic_weekly_visits", 1):
        from verified_data_factory.verification.qualification import weekly_visits_profile as weekly

        return weekly.alternatives(reference), weekly.challenge_specs(reference), weekly.relation_specs(reference)
    if pair == ("sql.joins.logistics_final_leg", 1):
        from verified_data_factory.verification.qualification import final_leg_profile as final_leg

        return final_leg.alternatives(reference), final_leg.challenge_specs(reference), final_leg.relation_specs(reference)
    if pair == ("sql.joins.saas_paid_invoices", 1):
        from verified_data_factory.verification.qualification import paid_invoices_profile as paid

        return paid.alternatives(reference), paid.challenge_specs(reference), paid.relation_specs(reference)
    if pair == ("sql.subqueries.exists", 2):
        from verified_data_factory.verification.qualification import exists_profile as exists

        return exists.alternatives(reference), exists.challenge_specs(reference), exists.relation_specs(reference)
    if pair == ("sql.aggregation.fulfillment_sla_dashboard", 1):
        from verified_data_factory.verification.qualification.sla_profile import (
            alternatives as sla_alternatives,
        )
        from verified_data_factory.verification.qualification.sla_profile import (
            challenge_specs,
            row,
        )

        baseline = {"fulfillments": [row(1)]}
        return sla_alternatives(reference), challenge_specs(reference), [
            ("SLA_DELIVERED_CLONE", reference.replace("COUNT(*)", "COUNT(DISTINCT warehouse)"), baseline),
            ("SLA_CANCELLED_ROW", reference.replace("fulfillment_status='delivered'", "TRUE"), baseline),
        ]
    if pair == ("sql.funnel.saas_activation_payment", 2):
        from tests.test_saas_v2_differential_sql import RECURSIVE_SQL

        private = json.loads(confined(root, INPUTS[2]).read_text())
        historical = runpy.run_path(str(confined(root, INPUTS[3])))
        alternatives = [reference, RECURSIVE_SQL, historical["LATERAL_JOIN_SQL"]]
        wrong = [(q["sql"], q["witness"]) for q in private["queries"]]
        baseline = ledger(["signup", "trial", "activation", "payment"])
        relations = [
            ("SAAS_LATER_PAYMENT", reference.replace("ORDER BY p.occurred_at, p.sequence",
             "ORDER BY p.occurred_at DESC, p.sequence DESC"), baseline),
            ("SAAS_EXCLUDED_GROUP", reference.replace("SELECT DISTINCT group_key FROM scoped",
             "SELECT DISTINCT group_key FROM account_funnel"), baseline),
        ]
    elif pair == ("sql.aggregation.manufacturing_line_scrap", 1):
        private = json.loads(confined(root, INPUTS[4]).read_text())
        alternatives = [reference,
            ("SELECT DISTINCT group_key, SUM(amount) OVER (PARTITION BY group_key) AS total_amount "
            "FROM production_runs WHERE status='eligible' AND EXTRACT(YEAR FROM occurred_at)=2025 ORDER BY group_key ASC"),
            ("WITH scoped AS (SELECT * FROM production_runs WHERE status='eligible' AND EXTRACT(YEAR FROM occurred_at)=2025) "
            "SELECT g.group_key, (SELECT SUM(s.amount) FROM scoped s WHERE s.group_key=g.group_key) AS total_amount "
            "FROM (SELECT DISTINCT group_key FROM scoped) g ORDER BY g.group_key ASC")]
        wrong = [(q["sql"], q["witness"]) for q in private["wrong_challenges"]]
        baseline = {"production_runs": [{"record_id": 1, "entity_id": 1, "group_key": "a",
                    "occurred_at": "2025-01-01 00:00:00", "status": "eligible", "amount": 1, "sequence": 1}]}
        relations = [
            ("SCRAP_ADDITIVITY", reference.replace("SUM(amount)", "COUNT(amount)"), baseline),
            ("SCRAP_EXCLUDED_ROW", reference.replace("status='eligible' AND ", ""), baseline),
        ]
    else:
        raise ValueError("unsupported qualification profile contract/version")
    return alternatives, wrong, relations


def collect(root: Path, destination: str, contract: str, version: int) -> dict[str, Any]:
    writer = ArtifactWriter(root, destination, contract, version, INPUTS)
    alternatives, wrong, discriminators = profile(root, contract, version)
    named = writer.named_tests([
        f"tests/test_qualification_named.py::test_attributed_contract_execution[{contract}]",
    ])
    rules = writer.rules()
    details = {
        "rules": rules, "mutation": writer.mutations(rules),
        "fixture_diversity": writer.diversity(),
        "challenge": writer.challenges(wrong, alternatives),
        "relations": writer.relations(alternatives[0], discriminators),
        "named_tests": named,
    }
    references = {category: writer.receipt(category, detail).model_dump()
                  for category, detail in details.items()}
    references["fuzz"] = writer.receipt("fuzz", writer.fuzz(alternatives)).model_dump()
    for category in REQUIRED:
        valid, reason = receipt(root, references[category], contract, version, category)
        if valid is None:
            raise ValueError(f"bundle replay failed: {category}: {reason}")
    record = {"contract_id": contract, "contract_version": version, "family": writer.task.family,
              "independence": "differential verification", "authorship": "independent authorship unproven",
              "candidate_origin": "reference-authored; no model generation",
              "prerequisites": {"template_validates": True}, "evidence": references}
    writer.write("bundle.json", record)
    return record


def main() -> None:
    safety()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", default="qualified-receipts-v9")
    parser.add_argument("--promote", action="store_true", help="Commit complete replayed bundles to local authority")
    parser.add_argument("--resolve-absent-evidence", action="store_true", help="Resolve only the historical missing-counterexample quarantine after all checks pass")
    args = parser.parse_args()
    if Path(args.identity).name != args.identity:
        raise ValueError("identity must be a directory name")
    destination = OUT / args.identity
    destination.mkdir(exist_ok=False)
    records = []
    for contract, version in sorted(SUPPORTED):
        relative = (destination / f"{contract}-v{version}").relative_to(ROOT).as_posix()
        records.append(collect(ROOT, relative, contract, version))
    # A completed collection is not ACTIVE until the authority transaction succeeds.
    with (destination / "collection.json").open("x", encoding="utf-8") as handle:
        json.dump({"status": "COLLECTED_NOT_PROMOTED", "contracts": records,
                   "catalog": catalog_blockers(), "source": digest(Path(__file__))}, handle, indent=2)
    print(f"Collected {len(records)} detailed bundles at {destination}; authority promotion required")
    if args.promote:
        from scripts.engineering_qualification_authority import promote
        from verified_data_factory.verification.readiness import qualify
        from verified_data_factory.verification.receipt_models import ArtifactRef

        for record in records:
            bundle = destination / f"{record['contract_id']}-v{record['contract_version']}" / "bundle.json"
            promote(ROOT, ArtifactRef(path=bundle.relative_to(ROOT).as_posix(), sha256=digest(bundle)),
                    resolve_absent_evidence=args.resolve_absent_evidence)
        dispositions = [{**record, "qualification": qualify(ROOT, record)} for record in records]
        with (destination / "readiness.json").open("x", encoding="utf-8") as handle:
            json.dump(dispositions, handle, indent=2)
        if not all(r["qualification"]["eligible"] for r in dispositions):
            raise ValueError("promoted bundle did not qualify; retain failure and investigate")
        print(f"{len(dispositions)} complete bundles qualify through the authoritative path")


if __name__ == "__main__":
    main()
