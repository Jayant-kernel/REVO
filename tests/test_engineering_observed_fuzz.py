from scripts.engineering_fuzz import classify, generate


def row(i, entity, group, status, year=2025):
    return {"record_id": i, "entity_id": entity, "group_key": group, "status": status,
            "occurred_at": f"{year}-01-01 00:00:00", "sequence": i, "amount": 1}


def test_observed_classifier_does_not_credit_absent_groups_or_completion():
    found = classify({"account_funnel": [row(1, 1, "a", "signup")]})
    assert "incomplete" in found
    assert "zero_completion_groups" in found
    assert "completed" not in found
    assert "multiple_entities" not in found
    assert "multiple_groups" not in found
    assert "out_of_scope_only_groups" not in found


def test_excluded_only_group_and_multiple_groups_are_actually_observed():
    tables = {"account_funnel": [row(1, 1, "a", "signup"), row(2, 2, "outside", "cancelled")]}
    found = classify(tables)
    assert {"multiple_groups", "multiple_entities", "out_of_scope_only_groups"} <= found


def test_completed_sequence_requires_order_and_all_steps():
    complete = {"account_funnel": [row(i, 1, "a", s) for i, s in enumerate(["signup", "trial", "activation", "payment"], 1)]}
    assert "completed" in classify(complete)
    complete["account_funnel"][1]["status"] = "payment"
    assert "completed" not in classify(complete)


def test_random_generator_preserves_entity_group_and_order_key_guarantees():
    for seed in (1, 43, 94001):
        hashes = set()
        for index in range(30):
            tables = generate(seed, index)
            groups = {}
            keys = set()
            for r in tables["account_funnel"]:
                assert groups.setdefault(r["entity_id"], r["group_key"]) == r["group_key"]
                key = r["entity_id"], r["occurred_at"], r["sequence"]
                assert key not in keys
                keys.add(key)
            hashes.add(tuple(sorted(keys)))
        assert len(hashes) == 30
