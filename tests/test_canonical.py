"""Tests for the RFC 8785 (JCS) canonical serializer in swarmledger.core.canonical."""

import math

import pytest

from swarmledger.core.canonical import canonicalize


def test_keys_sorted_lexicographically_by_utf8_bytes():
    obj = {"z": 1, "a": 2, "m": 3}
    assert canonicalize(obj) == b'{"a":2,"m":3,"z":1}'


def test_nested_key_order_is_deterministic_across_insertion_order():
    a = {"outer": {"z": 1, "a": 2}, "list": [{"y": 1, "b": 2}]}
    b = {"list": [{"b": 2, "y": 1}], "outer": {"a": 2, "z": 1}}
    assert canonicalize(a) == canonicalize(b)


def test_no_delimiter_whitespace():
    out = canonicalize({"a": [1, 2], "b": {"c": None}})
    assert b": " not in out
    assert b", " not in out
    assert out == b'{"a":[1,2],"b":{"c":null}}'


def test_scalars_serialize():
    assert canonicalize(None) == b"null"
    assert canonicalize(True) == b"true"
    assert canonicalize(False) == b"false"
    assert canonicalize(42) == b"42"
    assert canonicalize(-7) == b"-7"
    assert canonicalize("hi") == b'"hi"'


def test_integer_valued_floats_serialize_as_integers():
    assert canonicalize(1.0) == b"1"
    assert canonicalize(-3.0) == b"-3"


def test_floats_have_no_trailing_zeroes():
    assert canonicalize(3.140) == b"3.14"
    assert canonicalize(0.5) == b"0.5"


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_nan_and_infinity_are_rejected(bad):
    with pytest.raises(ValueError, match="RFC 8785"):
        canonicalize(bad)


def test_string_escaping():
    assert canonicalize('a"b') == b'"a\\"b"'
    assert canonicalize("a\\b") == b'"a\\\\b"'
    assert canonicalize("a\nb\tc\rd\be\ff") == b'"a\\nb\\tc\\rd\\be\\ff"'
    assert canonicalize("a\x01b") == b'"a\\u0001b"'
    assert canonicalize("") == b'""'


def test_tuples_serialize_as_arrays():
    assert canonicalize((1, "a", None)) == b'[1,"a",null]'


def test_object_with_to_dict_falls_back_to_dict_serialization():
    class HasDict:
        def to_dict(self):
            return {"b": 2, "a": 1}

    assert canonicalize(HasDict()) == b'{"a":1,"b":2}'


def test_unknown_object_falls_back_to_str():
    class Opaque:
        def __str__(self):
            return "opaque<1>"

    assert canonicalize(Opaque()) == b'"opaque<1>"'


def test_empty_containers():
    assert canonicalize({}) == b"{}"
    assert canonicalize([]) == b"[]"


def test_returns_bytes():
    out = canonicalize({"k": "v"})
    assert isinstance(out, bytes)
    assert out.decode("utf-8") == '{"k":"v"}'
