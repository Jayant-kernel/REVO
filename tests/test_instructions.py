"""Instruction tests: rendering, semantic coverage, determinism."""

from verified_data_factory.task_engine import generate_task


def test_instruction_renders_for_all_templates(registry):
    for template in registry.list():
        task = generate_task(template, seed=11)
        assert task.instruction.strip()
        assert "{" not in task.instruction and "}" not in task.instruction


def test_instruction_contains_semantic_information(registry):
    template = registry.get("sql.joins.simple")
    task = generate_task(template, seed=101)
    text = task.instruction.lower()
    assert "customer" in text
    assert "2025" in text
    assert "revenue" in text


def test_instruction_is_deterministic(registry):
    template = registry.get("sql.funnel.completion")
    a = generate_task(template, seed=1001)
    b = generate_task(template, seed=1001)
    assert a.instruction == b.instruction
