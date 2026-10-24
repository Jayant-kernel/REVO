import importlib.util
from pathlib import Path
from types import SimpleNamespace

from verified_data_factory.production import load_config
from verified_data_factory.production.api import (
    _distinct_contract_preflight,
    contract_readiness_from_manifest,
)
from verified_data_factory.production.models import FAMILIES, ProductionConfig
from verified_data_factory.production.runner import _scheduled_templates
from verified_data_factory.provenance import content_id

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SCRIPT = ROOT / "scripts" / "phase3_readiness_manifest.py"


def _manifest_module():
    spec = importlib.util.spec_from_file_location("phase3_readiness_manifest", MANIFEST_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Registry:
    def __init__(self) -> None:
        self.templates = {
            family: [SimpleNamespace(template_id=f"sql.{family}.only", family=family, version=1)]
            for family in FAMILIES
        }
        self.templates["simple_joins"] = [
            SimpleNamespace(template_id="sql.simple_joins.beta", family="simple_joins", version=1),
            SimpleNamespace(template_id="sql.simple_joins.alpha", family="simple_joins", version=1),
        ]

    def list_by_family(self, family: str) -> list[SimpleNamespace]:
        return self.templates[family]

    def get(self, template_id: str) -> SimpleNamespace:
        for templates in self.templates.values():
            for template in templates:
                if template.template_id == template_id:
                    return template
        raise ValueError(template_id)


def distinct_config(*, simple_count: int = 1) -> ProductionConfig:
    base = load_config("configs/production/smoke_qualification_001.yaml").model_dump()
    distribution = {family: 1 for family in FAMILIES}
    distribution["simple_joins"] = simple_count
    selected = {family: [f"sql.{family}.only"] for family in FAMILIES}
    selected["simple_joins"] = ["sql.simple_joins.beta", "sql.simple_joins.alpha"]
    return ProductionConfig.model_validate(
        {
            **base,
            "initial_task_batch": sum(distribution.values()),
            "family_distribution": distribution,
            "budget": {
                **base["budget"],
                "max_total_tasks": 100,
                "max_total_candidates": 100,
            },
            "schedule_mode": "distinct_contract",
            "selected_contract_ids": selected,
        }
    )


def test_distinct_assignment_uses_one_contract_per_family_without_repeats() -> None:
    config = distinct_config(simple_count=2)
    selected = _scheduled_templates(config, Registry(), "simple_joins", batch_index=3)

    assert [template.template_id for template in selected] == [
        "sql.simple_joins.alpha",
        "sql.simple_joins.beta",
    ]
    assert len({template.template_id for template in selected}) == len(selected)


def test_distinct_preflight_rejects_insufficient_selected_contracts() -> None:
    config = distinct_config(simple_count=2).model_copy(
        update={"selected_contract_ids": {**distinct_config().selected_contract_ids, "simple_joins": ["sql.simple_joins.alpha"]}}
    )

    result = _distinct_contract_preflight(config, Registry(), lambda _: True)

    assert result["ok"] is False
    assert result["failures"]["simple_joins"] == ["insufficient selected contracts"]


def test_distinct_preflight_rejects_unverified_selected_contract() -> None:
    config = distinct_config()

    result = _distinct_contract_preflight(
        config, Registry(), lambda contract_id: contract_id != "sql.simple_joins.alpha"
    )

    assert result["ok"] is False
    assert result["failures"]["simple_joins"] == [
        "contract ID sql.simple_joins.alpha is not fully verified"
    ]


def test_readiness_manifest_regenerates_identically_and_enables_distinct_mode(tmp_path: Path) -> None:
    generator = _manifest_module()
    first, second = tmp_path / "first.json", tmp_path / "second.json"

    first_manifest = generator.write_manifest(first)
    second_manifest = generator.write_manifest(second)

    assert first.read_bytes() == second.read_bytes()
    assert first_manifest["manifest_hash"] == second_manifest["manifest_hash"]

    selected = {
        family: [next(row["contract_id"] for row in first_manifest["contracts"] if row["family"] == family)]
        for family in FAMILIES
    }
    templates = {
        family: [SimpleNamespace(template_id=contract_ids[0], family=family, version=1)]
        for family, contract_ids in selected.items()
    }
    registry = SimpleNamespace(
        get=lambda contract_id: next(
            template
            for family_templates in templates.values()
            for template in family_templates
            if template.template_id == contract_id
        )
    )
    config = distinct_config().model_copy(update={"selected_contract_ids": selected})
    readiness = contract_readiness_from_manifest(first)
    result = _distinct_contract_preflight(config, registry, readiness)

    assert result["ok"] is True


def test_distinct_surplus_selection_is_contract_id_deterministic() -> None:
    config = distinct_config()
    registry = Registry()

    assert [template.template_id for template in _scheduled_templates(config, registry, "simple_joins", 0)] == [
        "sql.simple_joins.alpha"
    ]
    assert [template.template_id for template in _scheduled_templates(config, registry, "simple_joins", 9)] == [
        "sql.simple_joins.alpha"
    ]


def test_legacy_schedule_selection_is_identical_to_historic_rotation() -> None:
    config = load_config("configs/production/premium_qualification_80.yaml")
    registry = Registry()
    count = config.family_distribution["simple_joins"]
    templates = sorted(registry.list_by_family("simple_joins"), key=lambda template: template.template_id)

    actual = _scheduled_templates(config, registry, "simple_joins", batch_index=2)
    expected = [templates[(2 * count + index) % len(templates)] for index in range(count)]

    assert config.schedule_mode == "legacy"
    assert actual == expected


def test_legacy_config_identity_excludes_new_scheduler_defaults() -> None:
    from verified_data_factory.production import config_id

    config = load_config("configs/production/premium_qualification_80.yaml")
    historic_payload = config.model_dump(mode="json")
    historic_payload.pop("schedule_mode")
    historic_payload.pop("selected_contract_ids")
    historic_payload.pop("distinct_contract_selection")

    assert config_id(config) == content_id(
        "PRODUCTION_CONFIG", config.config_version, historic_payload
    )
