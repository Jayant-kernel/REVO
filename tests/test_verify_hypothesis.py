"""Hypothesis-backed verifier properties (no SQL generation involved).

Covers: comparator permutation invariance, tolerance boundaries, NULL
handling, hidden-seed determinism/distinctness, and metamorphic shuffle
determinism. Strategies stay small and fast.
"""

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from verified_data_factory.verification.comparator import cells_equal, compare
from verified_data_factory.verification.hidden import derive_hidden_seed
from verified_data_factory.verification.models import ComparisonPolicy, ExpectedResult, OrderSpec

POLICY = ComparisonPolicy()
TIGHT = ComparisonPolicy(float_abs_tol=1e-9, float_rel_tol=0.0)

_atoms = st.one_of(
    st.integers(-1000, 1000),
    st.floats(-1000, 1000, allow_nan=False, allow_infinity=False),
    st.text(max_size=8),
    st.booleans(),
    st.none(),
)


@settings(max_examples=60, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(st.lists(_atoms, min_size=1, max_size=3), min_size=0, max_size=8))
def test_unordered_permutation_invariance(rows):
    cols = ["c0", "c1", "c2"][: max(1, max((len(r) for r in rows), default=1))]
    norm = [list(r) + [None] * (len(cols) - len(r)) for r in rows]
    expected = ExpectedResult(columns=cols, rows=norm, order=OrderSpec())
    import random

    shuffled = list(norm)
    random.Random(7).shuffle(shuffled)
    assert compare(expected, cols, shuffled, POLICY).match


@settings(max_examples=40)
@given(st.floats(0.01, 100.0, allow_nan=False, allow_infinity=False))
def test_tolerance_boundary_property(x):
    assert cells_equal(x, x + 5e-10, TIGHT)
    assert not cells_equal(x, x + 5e-9, TIGHT)


@settings(max_examples=40)
@given(st.one_of(st.none(), st.integers(), st.text(max_size=5)))
def test_null_reflexivity_property(value):
    assert cells_equal(value, value, POLICY)
    if value is not None:
        assert not cells_equal(None, value, POLICY)
        assert not cells_equal(value, None, POLICY)


@settings(max_examples=30)
@given(st.integers(min_value=0, max_value=2**62), st.integers(min_value=0, max_value=9))
def test_hidden_seeds_deterministic_and_distinct(seed, index):
    first = derive_hidden_seed(seed, "1.0", index)
    assert first == derive_hidden_seed(seed, "1.0", index)
    others = {derive_hidden_seed(seed, "1.0", i) for i in range(10) if i != index}
    assert first not in others


@settings(max_examples=30)
@given(st.lists(st.integers(0, 50), min_size=1, max_size=10))
def test_ordered_keys_detect_permutation(values):
    order = OrderSpec(type="ordered", keys=[("v", "asc")])
    rows = [[v] for v in sorted(values)]
    expected = ExpectedResult(columns=["v"], rows=rows, order=order)
    assert compare(expected, ["v"], rows, POLICY).match
    if len(set(values)) == len(values) and len(values) > 1:
        rev = rows[::-1]
        assert not compare(expected, ["v"], rev, POLICY).match
