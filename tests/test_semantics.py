"""Semantic contract tests: task specs must be oracle-precise (no verifier here).

Every family declares the exact semantics a future independent oracle needs.
Ambiguous templates are rejected at load time.
"""

import pytest

from verified_data_factory.task_engine import generate_task
from verified_data_factory.task_engine.errors import TemplateError
from verified_data_factory.task_engine.template import template_from_dict
from verified_data_factory.task_engine.validation import SEMANTIC_REQUIREMENTS


def test_every_family_has_registered_semantic_keys(registry):
    families = {t.family for t in registry.list()}
    assert families == set(SEMANTIC_REQUIREMENTS)


def test_generated_tasks_carry_family_semantics(registry):
    for template in registry.list():
        task = generate_task(template, seed=77)
        for key in SEMANTIC_REQUIREMENTS[template.family]:
            assert key in task.requirements, f"{template.template_id} missing {key}"


def test_retention_semantics_are_exact(registry):
    task = generate_task(registry.get("sql.retention.30_day"), seed=901)
    req = task.requirements
    assert req["retention_window_days"] == 30
    assert req["qualifying_event"] == "purchase"
    assert req["cohort_definition"] == "all_customers_signup_anchored"
    assert req["boundary_policy"] == "inclusive_both_ends_day_30_counts"
    assert req["repeated_event_policy"] == "any_qualifying_event_retained"
    text = task.instruction.lower()
    assert "30 days" in text and "purchase" in text


def test_dedup_semantics_are_exact(registry):
    task = generate_task(registry.get("sql.dedup.latest"), seed=801)
    req = task.requirements
    assert req["duplicate_key"] == "customer_id_event_type_event_time"
    assert req["winner_rule"] == "max_event_time"
    assert req["tie_break"] == "highest_event_id"
    assert req["timestamp_tie_policy"] == "highest_event_id_wins"


def test_funnel_semantics_are_exact(registry):
    task = generate_task(registry.get("sql.funnel.completion"), seed=1001)
    req = task.requirements
    assert req["funnel_steps"] == ["view", "add_to_cart", "checkout", "purchase"]
    assert req["session_gap_minutes"] == 30
    assert req["consecutiveness"] == "steps_in_order_gaps_allowed"
    assert req["cross_session_policy"] == "steps_may_span_sessions"
    assert req["repeat_policy"] == "first_occurrence_chains"


def test_window_semantics_are_exact(registry):
    task = generate_task(registry.get("sql.windows.ranked"), seed=601)
    req = task.requirements
    assert req["partition_by"] == "customer_id"
    assert req["tie_policy"] == "rank_gaps_shared_rank"
    assert req["null_ordering"] == "nulls_last"


def test_ambiguous_template_rejected(registry):
    template = registry.get("sql.retention.30_day")
    data = template.model_dump(mode="json", by_alias=True)
    req = dict(data["requirements"])
    del req["boundary_policy"]  # "within 30 days" without a boundary rule is ambiguous
    data["requirements"] = req
    with pytest.raises(TemplateError):
        template_from_dict(data)


def test_unknown_family_rejected(registry):
    template = registry.get("sql.joins.simple")
    data = template.model_dump(mode="json", by_alias=True)
    data["template_id"] = "sql.mystery.thing"
    data["family"] = "mystery"
    with pytest.raises(TemplateError):
        template_from_dict(data)
