"""Renewal evidence must survive the real receipt JSON boundary without waivers."""
import json
from copy import deepcopy
from datetime import UTC, datetime

import pytest

from scripts.engineering_receipt_artifacts import ArtifactWriter
from verified_data_factory.verification.behavior_authority import public_behavior_map
from verified_data_factory.verification.qualification import renewal_coverage_profile as p
from verified_data_factory.verification.qualification.public_rule_proofs import schema_checks
from verified_data_factory.verification.readiness import receipt
from verified_data_factory.verification.receipt_models import RulesDetail
from verified_data_factory.verification.receipt_validation import DetailValidator

pytest_plugins = ["tests.test_stage2_receipt_producer"]


def differences(recorded, live, path):
    if isinstance(recorded, dict) and isinstance(live, dict):
        for key in sorted(recorded.keys() | live.keys()):
            yield from differences(recorded.get(key), live.get(key), f"{path}.{key}")
    elif isinstance(recorded, list) and isinstance(live, list):
        assert len(recorded) == len(live)
        for index, (a, b) in enumerate(zip(recorded, live, strict=True)):
            yield from differences(a, b, f"{path}[{index}]")
    elif type(recorded) is not type(live) or recorded != live:
        yield {"path": path, "recorded_type": type(recorded).__name__,
               "recorded_repr": repr(recorded), "live_type": type(live).__name__,
               "live_repr": repr(live)}


def test_actual_rules_receipt_json_replay_and_tamper(producer_root):
    writer = ArtifactWriter(producer_root, "probe-roundtrip", p.CONTRACT, 1, ["pyproject.toml"])
    detail = writer.rules()
    reference = writer.receipt("rules", detail)
    reference = json.loads(json.dumps(reference.model_dump(mode="json")))
    payload = json.loads((producer_root / reference["path"]).read_text(encoding="utf-8"))
    wire = RulesDetail.model_validate(payload["details"])
    mismatches = []
    for rule in wire.rules:
        if rule.domain_checks:
            table, column = rule.rule_id.removeprefix("schema:").split(".")
            live = schema_checks(writer.task, table, column)
            mismatches.extend(differences(rule.domain_checks, live, rule.rule_id + ".domain_checks"))
    print(json.dumps({"diagnostic": "renewal-schema-wire", "differences": mismatches}, sort_keys=True))
    valid, reason = receipt(producer_root, reference, p.CONTRACT, 1, "rules")
    assert valid is not None, reason
    assert reason == "fresh executed evidence"
    assert mismatches == []
    assert detail.model_dump() == wire.model_dump()

    def replay(changed):
        with DetailValidator(producer_root, writer.task, public_behavior_map(writer.task),
                             writer.sources, writer.thresholds) as checker:
            return checker.rules(changed)

    for field in ("raw_rejections", "raw_conformance", "source_clause", "rejection", "witness"):
        changed = deepcopy(wire)
        index = next(i for i, r in enumerate(changed.rules) if r.rule_id == "schema:episodes.expires_at")
        rule = changed.rules[index]
        if field in {"raw_rejections", "raw_conformance"}:
            rule.domain_checks[field][-1]["value"] = "wrong raw value"
        elif field == "witness":
            changed.rules[index] = rule.model_copy(update={"invalid_tables": next(
                r.invalid_tables for r in changed.rules if r.rule_id == "schema:episodes.member_id")})
        else:
            changed.rules[index] = rule.model_copy(update={field: "tampered"})
        with pytest.raises(ValueError):
            replay(changed)


def test_raw_timestamp_domain_and_wire_determinism():
    naive = datetime(2025, 1, 1)  # noqa: DTZ001 -- naive timestamps are the public domain.
    assert p.timestamp(naive) is naive
    with pytest.raises(ValueError):
        p.timestamp(naive.replace(tzinfo=UTC))
    for table, columns in p.SCHEMA.items():
        for column in columns:
            checks = p.schema_checks(None, table, column)
            assert checks == json.loads(json.dumps(checks))
            assert checks == p.schema_checks(None, table, column)
            for item in checks["raw_conformance"]:
                p.validate_rows(item["tables"])
            for item in checks["raw_rejections"]:
                with pytest.raises(ValueError):
                    p.validate_rows(item["tables"])
