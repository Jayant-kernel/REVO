"""Deterministic fallback for hypothesis-backed verifier properties.

test_verify_hypothesis.py covers these invariants with randomized
strategies, but hypothesis cannot load where its native extension is
blocked (environmental AppControl policy — verified independent of
this repository). These fixed-example tests pin the same invariants
without hypothesis so the properties stay checked everywhere. They
narrow nothing: the hypothesis suite remains authoritative where it runs.
"""

import json
import random

from verified_data_factory.verification.comparator import cells_equal, compare
from verified_data_factory.verification.hidden import derive_hidden_seed
from verified_data_factory.verification.models import ComparisonPolicy, ExpectedResult, OrderSpec

POLICY = ComparisonPolicy()
TIGHT = ComparisonPolicy(float_abs_tol=1e-9, float_rel_tol=0.0)


def test_unordered_permutation_invariance_fixed():
    rows = [[1, "a", None], [2, "b", 3.5], [3, None, True], []]
    cols = ["c0", "c1", "c2"]
    norm = [list(r) + [None] * (len(cols) - len(r)) for r in rows]
    norm = [[None if value is None else json.dumps(value) for value in row] for row in norm]
    expected = ExpectedResult(columns=cols, column_types=["VARCHAR"] * len(cols), rows=norm, order=OrderSpec())
    shuffled = list(norm)
    random.Random(7).shuffle(shuffled)
    assert compare(expected, cols, shuffled, POLICY).match


def test_tolerance_boundary_fixed():
    for x in (0.01, 1.0, 42.5, 99.99):
        assert cells_equal(x, x + 5e-10, TIGHT)
        assert not cells_equal(x, x + 5e-9, TIGHT)


def test_null_reflexivity_fixed():
    for value in (None, 0, 1, -5, "abc", "", True):
        assert cells_equal(value, value, POLICY)
        if value is not None:
            assert not cells_equal(None, value, POLICY)
            assert not cells_equal(value, None, POLICY)


def test_hidden_seeds_deterministic_and_distinct_fixed():
    for seed in (0, 1, 2**62):
        for index in range(10):
            first = derive_hidden_seed(seed, "1.0", index)
            assert first == derive_hidden_seed(seed, "1.0", index)
            others = {derive_hidden_seed(seed, "1.0", i) for i in range(10) if i != index}
            assert first not in others


def test_ordered_keys_detect_permutation_fixed():
    order = OrderSpec(type="ordered", keys=[("v", "asc")])
    rows = [[v] for v in sorted([5, 1, 9, 3, 7])]
    expected = ExpectedResult(columns=["v"], column_types=["BIGINT"], rows=rows, order=order)
    assert compare(expected, ["v"], rows, POLICY).match
    assert not compare(expected, ["v"], rows[::-1], POLICY).match
