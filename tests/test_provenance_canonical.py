"""Canonical serialization tests (Phase 6, §8 + §45)."""

import datetime as _dt
from decimal import Decimal

import pytest

from verified_data_factory.provenance import canonical_bytes, canonical_json, normalize
from verified_data_factory.provenance.errors import CanonicalizationError


def test_dict_order_does_not_affect_hash():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_stable_nested_serialization():
    value = {"z": [{"b": 1, "a": [3, 2, {"y": None, "x": True}]}], "a": "text"}
    first = canonical_json(value)
    assert canonical_json(value) == first
    assert (
        canonical_json({"a": "text", "z": [{"a": [3, 2, {"x": True, "y": None}], "b": 1}]}) == first
    )


def test_enum_handling():
    import enum

    class Color(enum.Enum):
        RED = "red"

    assert normalize(Color.RED) == "red"
    assert canonical_json({"color": Color.RED}) == canonical_json({"color": "red"})


def test_timestamp_handling():
    moment = _dt.datetime(2026, 1, 2, 3, 4, 5)  # noqa: DTZ001 (naive input is the case under test)
    assert normalize(moment) == {"$datetime": "2026-01-02T03:04:05"}
    assert normalize(_dt.date(2026, 1, 2)) == {"$datetime": "2026-01-02"}


def test_null_handling():
    assert normalize(None) is None
    assert normalize([None, False, 0, ""]) == [None, False, 0, ""]
    # Null never coerces to false/zero/empty in canonical form.
    assert canonical_json({"v": None}) != canonical_json({"v": False})


def test_numeric_handling():
    assert normalize(3) == 3
    assert normalize(3.0) == 3.0
    # Decimal is tagged so float 1.0 never collides with Decimal("1.0").
    assert normalize(Decimal("1.0")) == {"$decimal": "1.0"}
    assert canonical_json(1.0) != canonical_json(Decimal("1.0"))
    assert canonical_json(True) != canonical_json(1)
    with pytest.raises(CanonicalizationError):
        normalize(float("nan"))
    with pytest.raises(CanonicalizationError):
        normalize(float("inf"))


def test_unicode_stability():
    text = "café \u00e9clair"
    first = canonical_json({"text": text})
    assert canonical_json({"text": text}) == first
    assert first.encode("utf-8").decode("utf-8") == first


def test_pydantic_models_normalize():
    from verified_data_factory.task_engine.models import ColumnDefinition

    column = ColumnDefinition(name="id", type="INTEGER", nullable=False)
    assert normalize(column) == {"name": "id", "type": "INTEGER", "nullable": False}


def test_bytes_and_sets_tagged():
    assert normalize(b"\x00\xff") == {"$bytes": "00ff"}
    assert normalize({2, 1}) == normalize({1, 2})
    assert normalize({1, 2}) == {"$set": ["1", "2"]}
    assert normalize(set()) != normalize([])


def test_unknown_types_raise():
    class Custom:
        pass

    with pytest.raises(CanonicalizationError):
        normalize(Custom())


def test_canonical_bytes_utf8():
    assert canonical_bytes({"a": 1}) == b'{"a":1}'
