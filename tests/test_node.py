"""Tests for LedgerNode and EventType in swarmledger.core.node."""

import pytest

from swarmledger.core.node import EventType, LedgerNode


def test_event_type_values():
    assert EventType.PROMPT.value == "PROMPT"
    assert EventType.DELEGATE.value == "DELEGATE"
    assert EventType.LEASE.value == "LEASE"
    assert EventType.MUTATE.value == "MUTATE"
    assert EventType.PROOF.value == "PROOF"
    assert EventType.GATE.value == "GATE"
    assert EventType.SAGA_STEP.value == "SAGA_STEP"
    assert EventType.COMMIT.value == "COMMIT"
    assert EventType.ABORT.value == "ABORT"
    assert len(EventType) == 9


def test_event_type_is_string_enum():
    assert EventType.COMMIT == "COMMIT"
    assert isinstance(EventType.GATE, str)


def _node():
    return LedgerNode(
        node_id="nod_abc",
        span_id="span_1",
        parent_node_ids=["nod_root"],
        lamport_seq=3,
        event_type=EventType.MUTATE,
        agent_id="agent_7",
        payload={"file": "x.py"},
        capability_token_hash="tokhash",
        timestamp=1700000000.0,
        node_hash="deadbeef",
    )


def test_to_dict_serializes_event_type_as_value():
    d = _node().to_dict()
    assert d["event_type"] == "MUTATE"
    assert d["node_id"] == "nod_abc"
    assert d["lamport_seq"] == 3
    assert d["payload"] == {"file": "x.py"}
    assert d["capability_token_hash"] == "tokhash"
    assert d["node_hash"] == "deadbeef"


def test_from_dict_roundtrip():
    original = _node()
    restored = LedgerNode.from_dict(original.to_dict())
    assert restored == original


def test_from_dict_defaults():
    minimal = {
        "node_id": "nod_min",
        "span_id": "span_min",
        "lamport_seq": 1,
        "event_type": "PROMPT",
        "agent_id": "user",
    }
    n = LedgerNode.from_dict(minimal)
    assert n.parent_node_ids == []
    assert n.payload == {}
    assert n.capability_token_hash is None
    assert n.node_hash is None
    assert isinstance(n.timestamp, float)


def test_from_dict_rejects_unknown_event_type():
    data = {
        "node_id": "n",
        "span_id": "s",
        "lamport_seq": 1,
        "event_type": "BOGUS",
        "agent_id": "a",
    }
    with pytest.raises(ValueError):
        LedgerNode.from_dict(data)
